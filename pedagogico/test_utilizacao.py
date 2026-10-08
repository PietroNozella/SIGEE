import json
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from movimentacoes.services import registrar_devolucoes, registrar_retirada_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva

from .forms import UtilizacaoPedagogicaForm
from .models import AtividadePedagogica, Disciplina, Turma, UtilizacaoPedagogica
from .services import salvar_contexto_reserva


def preparar_utilizacao():
    cenario = criar_cenario()
    reserva, unidades = criar_reserva_alocada(cenario)
    with patch("movimentacoes.services.timezone.now", return_value=reserva.inicio):
        retiradas = registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk)
    escolhas = {
        "turma": Turma.objects.create(nome="Turma RF-10"),
        "disciplina": Disciplina.objects.create(nome="Disciplina RF-10"),
        "atividade": AtividadePedagogica.objects.create(nome="Atividade RF-10"),
    }
    return cenario, reserva, unidades, retiradas, escolhas


class UtilizacaoReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario, cls.reserva, cls.unidades, cls.retiradas, cls.escolhas = preparar_utilizacao()

    def setUp(self):
        self.professor = self.cenario["professor"]
        self.url = reverse("pedagogico:utilizacao_reserva", args=[self.reserva.pk])
        self.client.force_login(self.professor)
        self.dados = {campo: registro.pk for campo, registro in self.escolhas.items()}
        self.dados["observacao"] = "Uso em aula."

    def salvar(self, **alteracoes):
        return salvar_contexto_reserva(**{
            "professor": self.professor, "reserva_id": self.reserva.pk,
            **self.escolhas, "observacao": "Uso em aula.", **alteracoes,
        })

    def devolver(self, retiradas=None):
        return registrar_devolucoes(
            operador=self.cenario["operador"], retirada_id=self.retiradas[0].pk,
            retiradas_ids=[item.pk for item in (retiradas if retiradas is not None else self.retiradas)],
        )

    def eventos_sucesso(self):
        return RegistroAuditoria.objects.filter(
            acao__in=(AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA, AcaoAuditoria.UTILIZACAO_PEDAGOGICA_EDITADA),
            resultado="SUCESSO",
        )

    def test_fluxo_completo_lote_edicao_devolucao_parcial_integral_e_consulta(self):
        lista = reverse("reservas:reserva_lista")
        self.assertContains(self.client.get(lista), "Vincular contexto pedagógico")
        antes = list(Movimentacao.objects.values())
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        self.assertEqual(self.eventos_sucesso().count(), 3)
        self.assertEqual(list(Movimentacao.objects.values()), antes)
        self.assertContains(self.client.get(lista), "Editar contexto pedagógico")
        self.devolver(self.retiradas[:1])
        disciplina = Disciplina.objects.create(nome="Disciplina corrigida")
        self.dados["disciplina"] = disciplina.pk
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        self.assertEqual(UtilizacaoPedagogica.objects.filter(disciplina=disciplina).count(), 3)
        self.assertEqual(self.eventos_sucesso().count(), 6)
        self.assertEqual(self.client.get(self.url).context["pendentes"], 2)
        self.devolver(self.retiradas[1:])
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Disciplina corrigida")
        self.assertNotContains(resposta, 'name="turma"')
        self.assertContains(self.client.get(lista), "Consultar contexto pedagógico")
        self.dados["disciplina"] = self.escolhas["disciplina"].pk
        self.assertContains(self.client.post(self.url, self.dados), "devolução integral encerrou")
        self.assertEqual(UtilizacaoPedagogica.objects.filter(disciplina=disciplina).count(), 3)

    def test_sem_retirada_nao_ha_formulario_nem_gravacao(self):
        reserva = Reserva.objects.create(
            professor=self.professor, tipo_equipamento=self.reserva.tipo_equipamento,
            local=self.reserva.local, inicio=self.reserva.inicio, fim=self.reserva.fim,
        )
        url = reverse("pedagogico:utilizacao_reserva", args=[reserva.pk])
        self.assertNotContains(self.client.get(url), 'name="turma"')
        self.assertContains(self.client.post(url, self.dados), "após a retirada")
        with self.assertRaisesMessage(ValidationError, "após a retirada"):
            self.salvar(reserva_id=reserva.pk)
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_primeiro_registro_depois_de_devolver_tudo_e_bloqueado(self):
        self.devolver()
        self.assertContains(self.client.get(self.url), "Nenhum contexto pedagógico foi registrado")
        self.assertContains(self.client.post(self.url, self.dados), "devolução integral encerrou")
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_propriedade_404_na_view_e_no_servico(self):
        outro = get_user_model().objects.create_user(username="outro-professor-rf10")
        outro.groups.add(Group.objects.get(name="Professor"))
        registrar_aceite_vigente(outro)
        self.client.force_login(outro)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 404)
        with self.assertRaises(Http404):
            self.salvar(professor=outro)
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_perfis_incompativeis_negados_mesmo_com_permissao_individual(self):
        tecnico = get_user_model().objects.create_user(username="tecnico-rf10", is_superuser=True)
        multiplo = get_user_model().objects.create_user(username="multiplo-rf10")
        multiplo.groups.add(*Group.objects.filter(name__in=("Professor", "Operador")))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo-rf10")
        permissoes = Permission.objects.filter(content_type__app_label="pedagogico", codename__endswith="utilizacaopedagogica")
        for usuario in (self.cenario["administrador"], self.cenario["operador"], tecnico, multiplo, sem_grupo):
            registrar_aceite_vigente(usuario)
            usuario.user_permissions.add(*permissoes)
            self.client.force_login(usuario)
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    self.salvar(professor=usuario)
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_permissao_por_acao_e_consulta_sem_edicao(self):
        grupo = Group.objects.get(name="Professor")
        adicionar = Permission.objects.get(codename="add_utilizacaopedagogica")
        grupo.permissions.remove(adicionar)
        self.assertNotContains(self.client.get(self.url), 'name="turma"')
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.salvar(professor=get_user_model().objects.get(pk=self.professor.pk))
        grupo.permissions.add(adicionar)
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        grupo.permissions.remove(Permission.objects.get(codename="change_utilizacaopedagogica"))
        self.assertNotContains(self.client.get(self.url), 'name="turma"')
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
        grupo.permissions.remove(Permission.objects.get(codename="view_utilizacaopedagogica"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_conta_inativa_anonimo_get_sem_mutacao_e_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.professor)
        self.assertEqual(cliente.post(self.url, self.dados).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        get_user_model().objects.filter(pk=self.professor.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.salvar()

    def test_campos_obrigatorios_ids_invalidos_e_formulario_preservado(self):
        for campo in self.escolhas:
            for invalido in ("", 999999):
                with self.subTest(campo=campo, invalido=invalido):
                    resposta = self.client.post(self.url, {**self.dados, campo: invalido})
                    self.assertEqual(resposta.status_code, 200)
                    self.assertIn(campo, resposta.context["form"].errors)
                    self.assertContains(resposta, "Uso em aula.")
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA, resultado="FALHA").count(), 6)

    def test_ids_de_professor_movimentacao_reserva_e_data_sao_ignorados(self):
        resposta = self.client.post(self.url, {
            **self.dados, "professor": self.cenario["operador"].pk,
            "movimentacao": 999999, "reserva_id": 999999, "data_criacao": "2000-01-01",
        })
        self.assertRedirects(resposta, self.url)
        self.assertEqual(set(UtilizacaoPedagogica.objects.values_list("professor_id", flat=True)), {self.professor.pk})
        self.assertEqual(set(UtilizacaoPedagogica.objects.values_list("movimentacao_id", flat=True)), {item.pk for item in self.retiradas})

    def test_cadastro_inativado_entre_validacao_e_gravacao_e_rejeitado(self):
        form = UtilizacaoPedagogicaForm(data=self.dados)
        self.assertTrue(form.is_valid())
        Turma.objects.filter(pk=self.escolhas["turma"].pk).update(ativo=False)
        with self.assertRaises(ValidationError):
            salvar_contexto_reserva(professor=self.professor, reserva_id=self.reserva.pk, **form.cleaned_data)
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.assertIn("turma", self.client.post(self.url, self.dados).context["form"].errors)

    def test_referencia_inativa_pode_ser_mantida_mas_nao_nova_escolha(self):
        self.salvar()
        for registro in self.escolhas.values():
            type(registro).objects.filter(pk=registro.pk).update(ativo=False)
        self.assertRedirects(self.client.post(self.url, {**self.dados, "observacao": "Corrigida"}), self.url)
        self.assertEqual(UtilizacaoPedagogica.objects.filter(observacao="Corrigida").count(), 3)
        outra = Turma.objects.create(nome="Turma inativa não vinculada", ativo=False)
        resposta = self.client.post(self.url, {**self.dados, "turma": outra.pk})
        self.assertIn("turma", resposta.context["form"].errors)
        with self.assertRaises(ValidationError):
            self.salvar(turma=outra)

    def test_sem_cadastros_informa_administrador_e_desabilita_gravacao(self):
        Turma.objects.all().update(ativo=False)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Solicite ao Administrador")
        self.assertContains(resposta, " disabled")

    def test_reenvio_preserva_ids_datas_e_nao_duplica_eventos(self):
        self.salvar()
        antes = list(UtilizacaoPedagogica.objects.values())
        self.assertRedirects(self.client.post(self.url, self.dados), self.url)
        self.assertEqual(list(UtilizacaoPedagogica.objects.values()), antes)
        self.assertEqual(self.eventos_sucesso().count(), 3)

    def test_falha_na_segunda_auditoria_desfaz_todo_o_lote_e_registra_falha(self):
        contador = 0

        def auditar_e_falhar(**dados):
            nonlocal contador
            if dados["resultado"] == "SUCESSO":
                contador += 1
                registrar_evento(**dados)
                if contador == 2:
                    raise IntegrityError("Falha simulada na segunda associação")
            else:
                return registrar_evento(**dados)

        with patch("pedagogico.services.registrar_evento", side_effect=auditar_e_falhar):
            self.assertContains(self.client.post(self.url, self.dados), "Nenhuma alteração foi gravada")
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.assertFalse(self.eventos_sucesso().exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA, resultado="FALHA").exists())

    def test_historico_mostra_contexto_da_origem_na_retirada_e_devolucao_com_escape(self):
        self.salvar(observacao="<script>alert('x')</script>")
        self.devolver()
        for usuario in (self.cenario["operador"], self.cenario["administrador"]):
            self.client.force_login(usuario)
            resposta = self.client.get(reverse("movimentacoes:historico_lista"))
            self.assertContains(resposta, "Atividade RF-10", count=6)
            self.assertNotContains(resposta, "<script>alert('x')</script>")
            self.assertContains(resposta, "&lt;script&gt;", count=6)
        self.client.force_login(self.professor)
        self.assertEqual(self.client.get(reverse("movimentacoes:historico_lista")).status_code, 403)

    def test_exportacao_e_anonimizacao_preservam_vinculos(self):
        salvas = self.salvar()
        saida = StringIO()
        call_command("exportar_dados_usuario", self.professor.username, stdout=saida)
        dados = json.loads(saida.getvalue())["utilizacoes_pedagogicas"]
        self.assertEqual(len(dados), 3)
        self.assertEqual(dados[0]["turma"]["nome"], "Turma RF-10")
        self.assertEqual(dados[0]["reserva_id"], self.reserva.pk)
        call_command("anonimizar_usuario", self.professor.username, "--confirmar", stdout=StringIO())
        self.assertEqual(UtilizacaoPedagogica.objects.filter(pk__in=[item.pk for item in salvas]).count(), 3)
        self.assertEqual(UtilizacaoPedagogica.objects.first().professor_id, self.professor.pk)

    def test_inativacao_e_protect_preservam_historico(self):
        self.salvar()
        Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades]).update(ativo=False)
        self.devolver()
        self.assertContains(self.client.get(self.url), "Turma RF-10")
        for registro in (*self.escolhas.values(), self.retiradas[0], self.professor):
            with self.subTest(modelo=type(registro).__name__), self.assertRaises(ProtectedError):
                registro.delete()
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)

    def test_modelo_rejeita_devolucao_professor_incorreto_e_movimentacao_duplicada(self):
        utilizacao = UtilizacaoPedagogica(movimentacao=self.retiradas[0], professor=self.cenario["operador"], **self.escolhas)
        with self.assertRaises(ValidationError):
            utilizacao.full_clean()
        devolucao = self.devolver(self.retiradas[:1])[0]
        utilizacao = UtilizacaoPedagogica(movimentacao=devolucao, professor=self.professor, **self.escolhas)
        with self.assertRaises(ValidationError):
            utilizacao.full_clean()
        self.salvar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            UtilizacaoPedagogica.objects.create(movimentacao=self.retiradas[0], professor=self.professor, **self.escolhas)

    def test_retirada_sem_reserva_nao_pode_receber_contexto_neste_incremento(self):
        retirada = Movimentacao.objects.create(
            equipamento=self.cenario["equipamento"], operador=self.cenario["operador"],
            destinatario=self.professor, tipo="RETIRADA",
        )
        with self.assertRaises(ValidationError):
            UtilizacaoPedagogica(movimentacao=retirada, professor=self.professor, **self.escolhas).full_clean()


class ConcorrenciaUtilizacaoTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_contexto_e_ultima_devolucao_sao_serializados(self):
        cenario, reserva, unidades, retiradas, escolhas = preparar_utilizacao()
        barreira = Barrier(2)

        def executar(tipo):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                if tipo == "contexto":
                    try:
                        salvar_contexto_reserva(professor=cenario["professor"], reserva_id=reserva.pk, **escolhas)
                    except ValidationError as erro:
                        self.assertIn("devolução integral", str(erro))
                        return "encerrado"
                    return "contexto"
                registrar_devolucoes(operador=cenario["operador"], retirada_id=retiradas[0].pk, retiradas_ids=[item.pk for item in retiradas])
                return "devolucao"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futuros = [executor.submit(executar, tipo) for tipo in ("contexto", "devolucao")]
            resultados = [item.result(timeout=25) for item in futuros]
        self.assertIn("devolucao", resultados)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3 if "contexto" in resultados else 0)
        self.assertEqual(Movimentacao.objects.filter(tipo="DEVOLUCAO").count(), 3)
        with self.assertRaises(ValidationError):
            salvar_contexto_reserva(professor=cenario["professor"], reserva_id=reserva.pk, **escolhas)

    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_gravacoes_concorrentes_mantem_contexto_unico_para_todo_lote(self):
        cenario, reserva, _, _, escolhas = preparar_utilizacao()
        barreira = Barrier(2)

        def salvar(observacao):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                return salvar_contexto_reserva(professor=cenario["professor"], reserva_id=reserva.pk, **escolhas, observacao=observacao)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futuros = [executor.submit(salvar, observacao) for observacao in ("Primeira", "Segunda")]
            for item in futuros:
                self.assertEqual(len(item.result(timeout=25)), 3)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        self.assertEqual(len(set(UtilizacaoPedagogica.objects.values_list("observacao", flat=True))), 1)
