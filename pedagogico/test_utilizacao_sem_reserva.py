import json
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente
from manutencoes.models import Manutencao
from movimentacoes.models import Movimentacao
from movimentacoes.services import registrar_devolucoes, registrar_retirada_reserva, registrar_retirada_sem_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from .models import AtividadePedagogica, Disciplina, Turma, UtilizacaoPedagogica
from .services import salvar_contexto_retirada


def preparar_sem_reserva():
    cenario = criar_cenario()
    unidades = [cenario["equipamento"]]
    for indice in range(2):
        unidades.append(Equipamento.objects.create(
            numero_patrimonio=f"SEM-RESERVA-{indice}",
            tipo=unidades[0].tipo, local=unidades[0].local,
        ))
    retiradas = registrar_retirada_sem_reserva(
        operador=cenario["operador"], destinatario=cenario["professor"],
        tipo_equipamento=unidades[0].tipo, local=unidades[0].local,
        quantidade=3, equipamentos=unidades,
    )
    escolhas = {
        "turma": Turma.objects.create(nome="Turma sem reserva"),
        "disciplina": Disciplina.objects.create(nome="Disciplina sem reserva"),
        "atividade": AtividadePedagogica.objects.create(nome="Atividade sem reserva"),
    }
    return cenario, unidades, retiradas, escolhas


class UtilizacaoSemReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario, cls.unidades, cls.retiradas, cls.escolhas = preparar_sem_reserva()
        cls.professor = cls.cenario["professor"]

    def setUp(self):
        self.client.force_login(self.professor)
        self.url = reverse("pedagogico:utilizacao_retirada", args=[self.retiradas[0].pk])
        self.lista = reverse("pedagogico:utilizacao_lista")
        self.dados = {campo: objeto.pk for campo, objeto in self.escolhas.items()}
        self.dados["observacao"] = "Uso em aula sem reserva."

    def salvar(self, **alteracoes):
        return salvar_contexto_retirada(**{
            "professor": self.professor, "retirada_id": self.retiradas[0].pk,
            **self.escolhas, **alteracoes,
        })

    def devolver(self, retiradas=None, **alteracoes):
        return registrar_devolucoes(**{
            "operador": self.cenario["operador"], "retirada_id": self.retiradas[0].pk,
            "retiradas_ids": [item.pk for item in (self.retiradas if retiradas is None else retiradas)],
            **alteracoes,
        })

    def test_fluxo_completo_lote_parcial_edicao_integral_e_consulta(self):
        self.assertContains(self.client.get(self.lista), "Vincular contexto pedagógico")
        antes = list(Movimentacao.objects.values())
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        self.assertEqual(list(Movimentacao.objects.values()), antes)
        self.devolver(self.retiradas[:1])
        disciplina = Disciplina.objects.create(nome="Disciplina corrigida sem reserva")
        self.assertRedirects(self.client.post(self.url, {**self.dados, "disciplina": disciplina.pk}), self.url)
        self.assertEqual(UtilizacaoPedagogica.objects.filter(disciplina=disciplina).count(), 3)
        self.assertEqual(self.client.get(self.url).context["pendentes"], 2)
        self.devolver(self.retiradas[1:])
        resposta = self.client.get(self.url)
        self.assertContains(resposta, disciplina.nome)
        self.assertNotContains(resposta, 'name="turma"')
        self.assertContains(self.client.post(self.url, self.dados), "devolução integral encerrou")
        self.assertEqual(UtilizacaoPedagogica.objects.filter(disciplina=disciplina).count(), 3)
        grupo = self.client.get(self.lista).context["pagina"].object_list[0]
        self.assertEqual((grupo["total"], grupo["pendentes"], grupo["com_contexto"]), (3, 0, 3))

    def test_primeiro_registro_apos_devolucao_integral_e_bloqueado(self):
        self.devolver()
        self.assertContains(self.client.post(self.url, self.dados), "devolução integral encerrou")
        with self.assertRaises(ValidationError):
            self.salvar()
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_lotes_do_mesmo_professor_e_registros_antigos_ficam_separados(self):
        outra = Movimentacao.objects.create(
            equipamento=self.unidades[0], operador=self.cenario["operador"],
            destinatario=self.professor, tipo="RETIRADA", lote_retirada=uuid4(),
        )
        antigas = [Movimentacao.objects.create(
            equipamento=self.unidades[0], operador=self.cenario["operador"],
            destinatario=self.professor, tipo="RETIRADA",
        ) for _ in range(2)]
        self.assertEqual(self.client.get(self.lista).context["pagina"].paginator.count, 4)
        self.salvar()
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        self.salvar(retirada_id=antigas[0].pk)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 4)
        self.assertFalse(UtilizacaoPedagogica.objects.filter(movimentacao__in=[outra, antigas[1]]).exists())

    def test_lista_unifica_com_reserva_e_preserva_acesso_atual(self):
        # Um cenário completo com reserva, sob outro Professor, não aparece aqui.
        outro = get_user_model().objects.create_user(username="professor-com-reserva")
        outro.groups.add(Group.objects.get(name="Professor"))
        reserva, _ = criar_reserva_alocada(self.cenario)
        reserva.professor = outro
        reserva.save(update_fields=("professor",))
        with patch("movimentacoes.services.timezone.now", return_value=reserva.inicio):
            retiradas = registrar_retirada_reserva(operador=self.cenario["operador"], reserva_id=reserva.pk)
        self.assertEqual(self.client.get(self.lista).context["pagina"].paginator.count, 1)
        reserva.professor = self.professor
        reserva.save(update_fields=("professor",))
        Movimentacao.objects.filter(pk__in=[item.pk for item in retiradas]).update(destinatario=self.professor)
        resposta = self.client.get(self.lista)
        self.assertEqual(resposta.context["pagina"].paginator.count, 2)
        self.assertContains(resposta, reverse("pedagogico:utilizacao_reserva", args=[reserva.pk]))
        self.assertEqual(self.client.get(reverse("pedagogico:utilizacao_retirada", args=[retiradas[0].pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("pedagogico:utilizacao_reserva", args=[reserva.pk])).status_code, 200)

    def test_lista_pagina_grupos_e_ordena_por_data_com_desempate(self):
        novas = [Movimentacao.objects.create(
            equipamento=self.unidades[0], operador=self.cenario["operador"],
            destinatario=self.professor, tipo="RETIRADA", lote_retirada=uuid4(),
        ) for _ in range(11)]
        Movimentacao.objects.filter(pk__in=[item.pk for item in novas]).update(data_hora=novas[0].data_hora)
        pagina = self.client.get(self.lista).context["pagina"]
        self.assertEqual((pagina.paginator.count, len(pagina.object_list)), (12, 10))
        self.assertEqual(pagina.object_list[0]["retirada_id"], novas[-1].pk)
        self.assertEqual(len(self.client.get(self.lista + "?pagina=2").context["pagina"].object_list), 2)
        self.devolver()
        self.assertEqual(self.client.get(self.lista).context["pagina"].paginator.count, 12)

    def test_lista_vazia_e_get_sem_mutacao(self):
        Movimentacao.objects.all().delete()
        self.assertContains(self.client.get(self.lista), "Nenhuma utilização registrada")
        self.assertEqual(self.client.post(self.lista).status_code, 405)
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_propriedade_e_ids_inexistentes_sao_404(self):
        outro = get_user_model().objects.create_user(username="outro-sem-reserva")
        outro.groups.add(Group.objects.get(name="Professor"))
        registrar_aceite_vigente(outro)
        self.client.force_login(outro)
        self.assertContains(self.client.get(self.lista), "Nenhuma utilização registrada")
        for url in (self.url, reverse("pedagogico:utilizacao_retirada", args=[999999])):
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.dados).status_code, 404)
        with self.assertRaises(Http404):
            self.salvar(professor=outro)

    def test_lote_com_destinatarios_inconsistentes_nao_expoe_nem_grava(self):
        Movimentacao.objects.filter(pk=self.retiradas[-1].pk).update(destinatario=self.cenario["operador"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 404)
        with self.assertRaises(ValidationError):
            self.salvar()
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_perfis_invalidos_negados_na_lista_no_detalhe_e_no_servico(self):
        tecnico = get_user_model().objects.create_user(username="tecnico-sem-reserva", is_superuser=True)
        multiplo = get_user_model().objects.create_user(username="multiplo-sem-reserva")
        multiplo.groups.add(*Group.objects.filter(name__in=("Professor", "Operador")))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo-sem-reserva")
        permissoes = Permission.objects.filter(content_type__app_label="pedagogico", codename__endswith="utilizacaopedagogica")
        for usuario in (self.cenario["administrador"], self.cenario["operador"], tecnico, multiplo, sem_grupo):
            registrar_aceite_vigente(usuario)
            usuario.user_permissions.add(*permissoes)
            self.client.force_login(usuario)
            with self.subTest(usuario=usuario.pk):
                self.assertEqual(self.client.get(self.lista).status_code, 403)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    self.salvar(professor=usuario)

    def test_permissoes_por_acao_e_menu(self):
        grupo = Group.objects.get(name="Professor")
        adicionar = Permission.objects.get(codename="add_utilizacaopedagogica")
        grupo.permissions.remove(adicionar)
        self.assertContains(self.client.get(self.lista), "Consultar contexto pedagógico")
        self.assertNotContains(self.client.get(self.url), 'name="turma"')
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
        grupo.permissions.add(adicionar)
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        grupo.permissions.remove(Permission.objects.get(codename="change_utilizacaopedagogica"))
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
        grupo.permissions.remove(Permission.objects.get(codename="view_utilizacaopedagogica"))
        self.assertEqual(self.client.get(self.lista).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("inventario:equipamento_lista")), "Minhas Utilizações")

    def test_anonimo_conta_inativa_e_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.professor)
        self.assertEqual(cliente.post(self.url, self.dados).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.lista).status_code, 302)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        get_user_model().objects.filter(pk=self.professor.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.salvar()

    def test_campos_invalidos_preservados_e_ids_derivados_no_servidor(self):
        for campo in self.escolhas:
            resposta = self.client.post(self.url, {**self.dados, campo: ""})
            self.assertIn(campo, resposta.context["form"].errors)
            self.assertContains(resposta, self.dados["observacao"])
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.assertRedirects(self.client.post(self.url, {
            **self.dados, "professor": self.cenario["operador"].pk,
            "movimentacao": 999999, "retirada_id": 999999, "lote_retirada": str(uuid4()),
        }), self.url)
        self.assertEqual(set(UtilizacaoPedagogica.objects.values_list("movimentacao_id", flat=True)), {item.pk for item in self.retiradas})
        self.assertEqual(set(UtilizacaoPedagogica.objects.values_list("professor_id", flat=True)), {self.professor.pk})

    def test_referencias_inativas_revalidacao_e_ausencia_de_opcoes(self):
        Turma.objects.filter(pk=self.escolhas["turma"].pk).update(ativo=False)
        with self.assertRaises(ValidationError):
            self.salvar()
        self.assertContains(self.client.get(self.url), "Solicite ao Administrador")
        Turma.objects.filter(pk=self.escolhas["turma"].pk).update(ativo=True)
        self.salvar()
        Turma.objects.filter(pk=self.escolhas["turma"].pk).update(ativo=False)
        self.salvar(observacao="Mantendo referência inativa")
        self.assertEqual(UtilizacaoPedagogica.objects.filter(observacao="Mantendo referência inativa").count(), 3)
        outra = Turma.objects.create(nome="Outra turma inativa", ativo=False)
        with self.assertRaises(ValidationError):
            self.salvar(turma=outra)

    def test_reenvio_idempotente_e_rollback_da_segunda_auditoria(self):
        chamadas = 0

        def auditar(**dados):
            nonlocal chamadas
            if dados["resultado"] == "SUCESSO":
                chamadas += 1
                if chamadas == 2:
                    raise IntegrityError("Falha simulada")
            return registrar_evento(**dados)

        with patch("pedagogico.services.registrar_evento", side_effect=auditar):
            self.assertContains(self.client.post(self.url, self.dados), "Nenhuma alteração foi gravada")
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA, resultado="SUCESSO").exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA, resultado="FALHA", entidade=Movimentacao._meta.label, entidade_id=str(self.retiradas[0].pk)).exists())
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        antes = list(UtilizacaoPedagogica.objects.values())
        eventos = RegistroAuditoria.objects.count()
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        self.assertEqual(list(UtilizacaoPedagogica.objects.values()), antes)
        self.assertEqual(RegistroAuditoria.objects.count(), eventos)

    def test_contexto_parcial_inconsistente_nao_grava_restante(self):
        UtilizacaoPedagogica.objects.create(movimentacao=self.retiradas[0], professor=self.professor, **self.escolhas)
        with self.assertRaisesMessage(ValidationError, "inconsistente"):
            self.salvar()
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 1)

    def test_historico_manutencao_inativacao_exportacao_e_anonimizacao(self):
        self.salvar(observacao="<script>alert('x')</script>")
        self.devolver(problemas={self.retiradas[0].pk: "Falha de projeção"})
        self.assertEqual(Manutencao.objects.count(), 1)
        Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades]).update(ativo=False)
        self.assertContains(self.client.get(self.url), self.escolhas["turma"].nome)
        for usuario in (self.cenario["operador"], self.cenario["administrador"]):
            self.client.force_login(usuario)
            resposta = self.client.get(reverse("movimentacoes:historico_lista"))
            self.assertContains(resposta, self.escolhas["atividade"].nome, count=6)
            self.assertContains(resposta, "&lt;script&gt;", count=6)
            self.assertNotContains(resposta, "<script>alert('x')</script>")
        saida = StringIO()
        call_command("exportar_dados_usuario", self.professor.username, stdout=saida)
        dados = json.loads(saida.getvalue())["utilizacoes_pedagogicas"]
        self.assertEqual(len(dados), 3)
        self.assertTrue(all(item["reserva_id"] is None for item in dados))
        with self.assertRaises(ProtectedError):
            self.retiradas[0].delete()
        call_command("anonimizar_usuario", self.professor.username, "--confirmar", stdout=StringIO())
        self.assertEqual(UtilizacaoPedagogica.objects.filter(professor=self.professor).count(), 3)


class ConcorrenciaUtilizacaoSemReservaTests(TransactionTestCase):
    def executar_concorrentes(self, tarefas):
        barreira = Barrier(len(tarefas))

        def executar(tarefa):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                return tarefa()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(tarefas)) as executor:
            futuros = [executor.submit(executar, tarefa) for tarefa in tarefas]
            return [futuro.result(timeout=25) for futuro in futuros]

    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_gravacoes_preservam_contexto_unico_e_uniforme(self):
        cenario, _, retiradas, escolhas = preparar_sem_reserva()
        def salvar(observacao):
            return salvar_contexto_retirada(professor=cenario["professor"], retirada_id=retiradas[0].pk, **escolhas, observacao=observacao)
        resultados = self.executar_concorrentes([lambda: salvar("Primeira"), lambda: salvar("Segunda")])
        self.assertEqual([len(itens) for itens in resultados], [3, 3])
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        self.assertEqual(UtilizacaoPedagogica.objects.values("observacao").distinct().count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_contexto_e_devolucao_integral_sao_serializados(self):
        cenario, _, retiradas, escolhas = preparar_sem_reserva()
        def salvar():
            try:
                salvar_contexto_retirada(professor=cenario["professor"], retirada_id=retiradas[0].pk, **escolhas)
            except ValidationError as erro:
                self.assertIn("devolução integral", str(erro))
                return False
            return True
        def devolver():
            return registrar_devolucoes(operador=cenario["operador"], retirada_id=retiradas[0].pk, retiradas_ids=[item.pk for item in retiradas])
        salvo, devolucoes = self.executar_concorrentes([salvar, devolver])
        self.assertEqual(len(devolucoes), 3)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3 if salvo else 0)
        with self.assertRaises(ValidationError):
            salvar_contexto_retirada(professor=cenario["professor"], retirada_id=retiradas[0].pk, **escolhas)
