from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
import json
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from movimentacoes.services import registrar_devolucao, registrar_devolucoes, registrar_retirada_reserva
from movimentacoes.test_devolucao import retirar
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.services import _equipamentos_disponiveis

from .models import Manutencao
from .services import abrir_manutencao, concluir_manutencao, iniciar_manutencao


class ManutencaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()

    def setUp(self):
        self.administrador = self.cenario["administrador"]
        self.equipamento = self.cenario["equipamento"]

    def abrir(self, **alteracoes):
        return abrir_manutencao(**{
            "administrador": self.administrador, "equipamento_id": self.equipamento.pk,
            "descricao_problema": "  Não liga.  ", **alteracoes,
        })

    def iniciar(self, manutencao):
        return iniciar_manutencao(administrador=self.administrador, manutencao_id=manutencao.pk)

    def concluir(self, manutencao, **alteracoes):
        return concluir_manutencao(**{
            "administrador": self.administrador, "manutencao_id": manutencao.pk,
            "resultado": "REPARADO", "descricao_solucao": "  Fonte substituída.  ", **alteracoes,
        })

    def test_ciclo_manual_preserva_responsaveis_datas_e_auditoria(self):
        manutencao = self.abrir()
        self.assertEqual(manutencao.estado, "PENDENTE")
        self.assertEqual(manutencao.aberto_por, self.administrador)
        self.assertEqual(manutencao.descricao_problema, "Não liga.")
        self.assertIsNone(manutencao.devolucao_origem_id)
        self.assertIsNone(manutencao.data_inicio)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "MANUTENCAO")
        iniciada = self.iniciar(manutencao)
        self.assertEqual(iniciada.estado, "EM_ANDAMENTO")
        self.assertEqual(iniciada.iniciado_por, self.administrador)
        concluida = self.concluir(iniciada)
        self.assertEqual(concluida.estado, "CONCLUIDA")
        self.assertEqual(concluida.resultado, "REPARADO")
        self.assertEqual(concluida.descricao_solucao, "Fonte substituída.")
        self.assertEqual(concluida.concluido_por, self.administrador)
        self.assertLessEqual(concluida.data_abertura, concluida.data_inicio)
        self.assertLessEqual(concluida.data_inicio, concluida.data_conclusao)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "DISPONIVEL")
        self.assertTrue(self.equipamento.ativo)
        eventos = RegistroAuditoria.objects.filter(entidade="manutencoes.Manutencao", entidade_id=str(manutencao.pk))
        self.assertEqual(set(eventos.values_list("acao", flat=True)), {
            AcaoAuditoria.MANUTENCAO_ABERTA, AcaoAuditoria.MANUTENCAO_INICIADA, AcaoAuditoria.MANUTENCAO_CONCLUIDA,
        })
        self.assertEqual(set(eventos.values_list("usuario_id", flat=True)), {self.administrador.pk})

    def test_sem_reparo_inativa_preservando_historico(self):
        manutencao = self.iniciar(self.abrir())
        self.concluir(manutencao, resultado="SEM_REPARO", descricao_solucao="Placa sem reparo.")
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)
        self.assertEqual(self.equipamento.situacao, "MANUTENCAO")
        self.assertTrue(Manutencao.objects.filter(pk=manutencao.pk).exists())
        with self.assertRaises(ValidationError):
            self.abrir()

    def test_reparo_nao_reativa_inativacao_independente(self):
        manutencao = self.iniciar(self.abrir())
        self.equipamento.delete()
        self.concluir(manutencao)
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)
        self.assertEqual(self.equipamento.situacao, "DISPONIVEL")

    def test_abertura_rejeita_vazio_inativo_em_uso_e_inexistente(self):
        for descricao in ("", "   "):
            with self.subTest(descricao=descricao), self.assertRaises(ValidationError):
                self.abrir(descricao_problema=descricao)
        for ativo, situacao in ((False, "DISPONIVEL"), (True, "EM_USO"), (True, "MANUTENCAO")):
            Equipamento.objects.filter(pk=self.equipamento.pk).update(ativo=ativo, situacao=situacao)
            with self.subTest(ativo=ativo, situacao=situacao), self.assertRaises(ValidationError):
                self.abrir()
        with self.assertRaises(ValidationError):
            self.abrir(equipamento_id=999999)
        self.assertFalse(Manutencao.objects.exists())

    def test_nao_duplica_abertura_e_permite_nova_intervencao_apos_reparo(self):
        primeira = self.abrir()
        with self.assertRaises(ValidationError):
            self.abrir()
        self.concluir(self.iniciar(primeira))
        segunda = self.abrir(descricao_problema="Novo defeito.")
        self.assertNotEqual(primeira.pk, segunda.pk)
        self.assertEqual(Manutencao.objects.count(), 2)

    def test_transicoes_invalidas_nao_alteram_estado_ou_datas(self):
        manutencao = self.abrir()
        with self.assertRaises(ValidationError):
            self.concluir(manutencao)
        self.iniciar(manutencao)
        inicio = Manutencao.objects.get(pk=manutencao.pk).data_inicio
        with self.assertRaises(ValidationError):
            self.iniciar(manutencao)
        for resultado, descricao in (("", "Análise"), ("OUTRO", "Análise"), ("REPARADO", " ")):
            with self.subTest(resultado=resultado), self.assertRaises(ValidationError):
                self.concluir(manutencao, resultado=resultado, descricao_solucao=descricao)
        manutencao.refresh_from_db()
        self.assertEqual(manutencao.estado, "EM_ANDAMENTO")
        self.assertEqual(manutencao.data_inicio, inicio)
        self.assertIsNone(manutencao.data_conclusao)
        self.concluir(manutencao)
        dados = Manutencao.objects.values().get(pk=manutencao.pk)
        with self.assertRaises(ValidationError):
            self.concluir(manutencao, resultado="SEM_REPARO")
        with self.assertRaises(ValidationError):
            self.iniciar(manutencao)
        self.assertEqual(Manutencao.objects.values().get(pk=manutencao.pk), dados)

    def test_servicos_reconsultam_conta_grupo_e_permissao(self):
        manutencao = self.abrir()
        for usuario in (self.cenario["operador"], self.cenario["professor"]):
            for servico, dados in (
                (self.abrir, {}), (iniciar_manutencao, {"manutencao_id": manutencao.pk}),
                (concluir_manutencao, {"manutencao_id": manutencao.pk, "resultado": "REPARADO", "descricao_solucao": "Concluído"}),
            ):
                with self.subTest(usuario=usuario, servico=servico), self.assertRaises(PermissionDenied):
                    servico(administrador=usuario, **dados)
        Group.objects.get(name="Administrador").permissions.remove(Permission.objects.get(codename="change_manutencao"))
        with self.assertRaises(PermissionDenied):
            self.iniciar(manutencao)
        get_user_model().objects.filter(pk=self.administrador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.abrir()

    def test_rollback_abertura_inicio_e_conclusao_se_auditoria_falha(self):
        with patch("manutencoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.abrir()
        self.assertFalse(Manutencao.objects.exists())
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "DISPONIVEL")
        manutencao = self.abrir()
        with patch("manutencoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.iniciar(manutencao)
        manutencao.refresh_from_db()
        self.assertEqual(manutencao.estado, "PENDENTE")
        self.assertIsNone(manutencao.data_inicio)
        self.iniciar(manutencao)
        with patch("manutencoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.concluir(manutencao, resultado="SEM_REPARO")
        manutencao.refresh_from_db()
        self.equipamento.refresh_from_db()
        self.assertEqual(manutencao.estado, "EM_ANDAMENTO")
        self.assertTrue(self.equipamento.ativo)
        self.assertEqual(self.equipamento.situacao, "MANUTENCAO")
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.MANUTENCAO_CONCLUIDA).exists())

    def test_constraints_banco_impedem_duplicidade_estado_e_conclusao_incompleta(self):
        manutencao = self.abrir()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Manutencao.objects.create(equipamento=self.equipamento, aberto_por=self.administrador, descricao_problema="Duplicada")
        for alteracoes in ({"estado": "INVALIDO"}, {"estado": "CONCLUIDA"}, {"descricao_problema": ""}, {"resultado": "REPARADO"}):
            with self.subTest(alteracoes=alteracoes), self.assertRaises(IntegrityError), transaction.atomic():
                Manutencao.objects.filter(pk=manutencao.pk).update(**alteracoes)
        self.iniciar(manutencao)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Manutencao.objects.filter(pk=manutencao.pk).update(data_inicio=manutencao.data_abertura - timedelta(seconds=1))

    def test_historico_impede_exclusao_do_equipamento_e_responsavel(self):
        manutencao = self.abrir()
        self.equipamento.delete()
        self.assertTrue(Equipamento.objects.filter(pk=self.equipamento.pk, ativo=False).exists())
        with self.assertRaises(ProtectedError):
            self.administrador.delete()
        self.assertTrue(Manutencao.objects.filter(pk=manutencao.pk).exists())

    def test_manutencao_bloqueia_disponibilidade_reserva_e_retirada(self):
        self.abrir()
        self.assertFalse(_equipamentos_disponiveis(
            self.equipamento.tipo, self.equipamento.local, timezone.now(), timezone.now() + timedelta(hours=1),
        ).exists())
        with self.assertRaises(ValidationError):
            retirar(self.cenario)

    def test_manutencao_de_unidade_alocada_impede_retirada_reserva(self):
        reserva, unidades = criar_reserva_alocada(self.cenario, quantidade=1)
        self.abrir(equipamento_id=unidades[0].pk)
        with patch("movimentacoes.services.timezone.now", return_value=reserva.inicio + timedelta(minutes=5)):
            with self.assertRaises(ValidationError):
                registrar_retirada_reserva(operador=self.cenario["operador"], reserva_id=reserva.pk)
        self.assertFalse(Movimentacao.objects.filter(reserva=reserva).exists())

    def test_exportacao_inclui_responsabilidades_sem_duplicar_ou_expor_outros_usuarios(self):
        manutencao = self.concluir(self.iniciar(self.abrir()))
        saida = StringIO()
        call_command("exportar_dados_usuario", self.administrador.username, stdout=saida)
        dados = json.loads(saida.getvalue())["manutencoes"]
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]["id"], manutencao.pk)
        self.assertEqual(dados[0]["responsabilidades"], ["abertura", "inicio", "conclusao"])
        self.assertNotIn("aberto_por", dados[0])
        saida = StringIO()
        call_command("exportar_dados_usuario", self.cenario["professor"].username, stdout=saida)
        self.assertEqual(json.loads(saida.getvalue())["manutencoes"], [])

    def test_inicio_e_conclusao_por_outro_administrador_preservam_abertura(self):
        outro = get_user_model().objects.create_user(username="outro-admin")
        outro.groups.add(Group.objects.get(name="Administrador"))
        manutencao = self.abrir()
        iniciar_manutencao(administrador=outro, manutencao_id=manutencao.pk)
        concluir_manutencao(administrador=outro, manutencao_id=manutencao.pk, resultado="REPARADO", descricao_solucao="Reparo")
        manutencao.refresh_from_db()
        self.assertEqual(manutencao.aberto_por, self.administrador)
        self.assertEqual(manutencao.iniciado_por, outro)
        self.assertEqual(manutencao.concluido_por, outro)


class DevolucaoComProblemaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        referencia = cls.cenario["equipamento"]
        cls.unidades = [referencia] + [Equipamento.objects.create(
            numero_patrimonio=f"RN14-{indice}", tipo=referencia.tipo, local=referencia.local,
        ) for indice in range(2)]
        cls.retiradas = retirar(cls.cenario, cls.unidades)

    def setUp(self):
        self.ids = [item.pk for item in self.retiradas]
        self.url = reverse("movimentacoes:devolucao_registrar", args=[self.ids[0]])
        self.client.force_login(self.cenario["operador"])

    def devolver(self, **alteracoes):
        return registrar_devolucoes(**{
            "operador": self.cenario["operador"], "retirada_id": self.ids[0], "retiradas_ids": self.ids,
            "problemas": {self.ids[1]: "Tela quebrada."}, **alteracoes,
        })

    def test_lote_misto_preserva_origem_e_encaminha_so_unidade_afetada(self):
        devolucoes = self.devolver()
        manutencao = Manutencao.objects.get()
        self.assertEqual(manutencao.devolucao_origem.retirada_origem_id, self.ids[1])
        self.assertEqual(manutencao.equipamento_id, self.retiradas[1].equipamento_id)
        self.assertEqual(manutencao.aberto_por, self.cenario["operador"])
        self.assertEqual(manutencao.estado, "PENDENTE")
        self.assertEqual([Equipamento.objects.get(pk=item.pk).situacao for item in self.unidades], ["DISPONIVEL", "MANUTENCAO", "DISPONIVEL"])
        self.assertEqual(len(devolucoes), 3)
        with self.assertRaises(ProtectedError):
            manutencao.devolucao_origem.delete()
        resposta = self.client.get(reverse("movimentacoes:historico_lista"))
        self.assertContains(resposta, f"Manutenção #{manutencao.pk}")
        self.assertNotContains(resposta, reverse("manutencoes:manutencao_detalhe", args=[manutencao.pk]))

    def test_tela_encaminha_por_patrimonio_sem_javascript_e_preserva_parcial(self):
        resposta = self.client.post(self.url, {
            "retiradas": self.ids[:2], f"problema_{self.ids[1]}": "on",
            f"descricao_problema_{self.ids[1]}": "Falha ao ligar.", "estado": "CONCLUIDA",
            "aberto_por": self.cenario["administrador"].pk,
        }, follow=True)
        self.assertContains(resposta, "1 manutenção(ões) aberta(s)")
        manutencao = Manutencao.objects.get()
        self.assertEqual(manutencao.aberto_por, self.cenario["operador"])
        self.assertEqual(manutencao.estado, "PENDENTE")
        self.assertEqual(Movimentacao.objects.filter(tipo="DEVOLUCAO").count(), 2)
        self.unidades[2].refresh_from_db()
        self.assertEqual(self.unidades[2].situacao, "EM_USO")

    def test_descricao_obrigatoria_e_problema_so_em_recebidas(self):
        casos = (
            {"retiradas": self.ids, f"problema_{self.ids[1]}": "on"},
            {"retiradas": self.ids[:1], f"problema_{self.ids[1]}": "on", f"descricao_problema_{self.ids[1]}": "Quebrado"},
            {"retiradas": self.ids, f"descricao_problema_{self.ids[1]}": "Descrição sem confirmação"},
        )
        for dados in casos:
            with self.subTest(dados=dados):
                resposta = self.client.post(self.url, dados)
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors)
                self.assertFalse(Manutencao.objects.exists())
                self.assertFalse(Movimentacao.objects.filter(tipo="DEVOLUCAO").exists())
        for problemas in ({self.ids[0]: " "}, {999999: "Quebrado"}):
            with self.subTest(problemas=problemas), self.assertRaises(ValidationError):
                self.devolver(problemas=problemas)

    def test_falha_manutencao_reverte_todo_lote_inclusive_primeira_unidade(self):
        with patch("manutencoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.devolver()
        self.assertFalse(Manutencao.objects.exists())
        self.assertFalse(Movimentacao.objects.filter(tipo="DEVOLUCAO").exists())
        self.assertEqual(Equipamento.objects.filter(situacao="EM_USO").count(), 3)
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA).exists())

    def test_falha_auditoria_devolucao_reverte_manutencao(self):
        with patch("movimentacoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.devolver(problemas={self.ids[0]: "Quebrado"})
        self.assertFalse(Manutencao.objects.exists())
        self.assertFalse(Movimentacao.objects.filter(tipo="DEVOLUCAO").exists())
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.MANUTENCAO_ABERTA).exists())

    def test_manutencao_preexistente_impede_segunda_abertura_sem_recebimento_parcial(self):
        Manutencao.objects.create(equipamento=self.unidades[1], aberto_por=self.cenario["administrador"], descricao_problema="Anterior")
        with self.assertRaisesMessage(ValidationError, "já possui uma manutenção"):
            self.devolver()
        self.assertEqual(Manutencao.objects.count(), 1)
        self.assertFalse(Movimentacao.objects.filter(tipo="DEVOLUCAO").exists())

    def test_devolucao_individual_com_problema_e_duplicidade(self):
        devolucao = registrar_devolucao(operador=self.cenario["operador"], retirada_id=self.ids[0], descricao_problema="Falha")
        self.assertEqual(Manutencao.objects.get().devolucao_origem_id, devolucao.pk)
        with self.assertRaises(ValidationError):
            registrar_devolucao(operador=self.cenario["operador"], retirada_id=self.ids[0], descricao_problema="Outra falha")
        self.assertEqual(Manutencao.objects.count(), 1)

    def test_devolucao_com_problema_preserva_reserva_e_destinatario_inativo(self):
        reserva, unidades = criar_reserva_alocada(self.cenario, quantidade=1)
        with patch("movimentacoes.services.timezone.now", return_value=reserva.inicio + timedelta(minutes=5)):
            retirada = registrar_retirada_reserva(operador=self.cenario["operador"], reserva_id=reserva.pk)[0]
        get_user_model().objects.filter(pk=self.cenario["professor"].pk).update(is_active=False)
        # A devolução ocorre após a data sintética de retirada da reserva.
        with patch("movimentacoes.services.timezone.now", return_value=reserva.inicio + timedelta(hours=1)):
            devolucao = registrar_devolucao(operador=self.cenario["operador"], retirada_id=retirada.pk, descricao_problema="Falha")
        self.assertEqual(devolucao.reserva_id, reserva.pk)
        self.assertEqual(devolucao.destinatario_id, retirada.destinatario_id)
        self.assertEqual(Manutencao.objects.get().devolucao_origem_id, devolucao.pk)

    def test_recebimento_com_problema_nao_reativa_equipamento_inativo(self):
        Equipamento.objects.filter(pk=self.unidades[0].pk).update(ativo=False)
        self.devolver(problemas={self.ids[0]: "Falha"})
        self.unidades[0].refresh_from_db()
        self.assertFalse(self.unidades[0].ativo)
        self.assertEqual(self.unidades[0].situacao, "MANUTENCAO")

    def test_origem_modelo_exige_devolucao_do_mesmo_equipamento(self):
        with self.assertRaises(ValidationError):
            Manutencao(equipamento=self.unidades[0], aberto_por=self.cenario["operador"], descricao_problema="Falha", devolucao_origem=self.retiradas[0]).full_clean()
        devolucao = registrar_devolucao(operador=self.cenario["operador"], retirada_id=self.ids[0])
        with self.assertRaises(ValidationError):
            Manutencao(equipamento=self.unidades[1], aberto_por=self.cenario["operador"], descricao_problema="Falha", devolucao_origem=devolucao).full_clean()


class ManutencaoInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()

    def setUp(self):
        self.admin = self.cenario["administrador"]
        self.equipamento = self.cenario["equipamento"]
        self.client.force_login(self.admin)
        self.lista = reverse("manutencoes:manutencao_lista")
        self.nova = reverse("manutencoes:manutencao_abrir")

    def abrir(self):
        return abrir_manutencao(administrador=self.admin, equipamento_id=self.equipamento.pk, descricao_problema="Falha")

    def test_fluxo_completo_post_e_dados_derivados_no_servidor(self):
        resposta = self.client.post(self.nova, {
            "equipamento": self.equipamento.pk, "descricao_problema": "Não liga", "estado": "CONCLUIDA",
            "aberto_por": self.cenario["professor"].pk, "data_abertura": "2000-01-01",
        })
        manutencao = Manutencao.objects.get()
        detalhe = reverse("manutencoes:manutencao_detalhe", args=[manutencao.pk])
        self.assertRedirects(resposta, detalhe)
        self.assertEqual(manutencao.estado, "PENDENTE")
        self.assertEqual(manutencao.aberto_por, self.admin)
        self.assertContains(self.client.get(detalhe), "Iniciar manutenção")
        self.assertRedirects(self.client.post(reverse("manutencoes:manutencao_iniciar", args=[manutencao.pk])), detalhe)
        self.assertContains(self.client.get(detalhe), "Concluir manutenção")
        conclusao = reverse("manutencoes:manutencao_concluir", args=[manutencao.pk])
        self.assertContains(self.client.post(conclusao, {"resultado": "REPARADO", "descricao_solucao": " "}), "Este campo é obrigatório")
        self.assertRedirects(self.client.post(conclusao, {"resultado": "REPARADO", "descricao_solucao": "Fonte reparada"}), detalhe)
        self.assertContains(self.client.get(detalhe), "Fonte reparada")
        self.assertNotContains(self.client.get(detalhe), "Iniciar manutenção")

    def test_get_nao_muda_estado_csrf_exigido_e_rotas_sem_exclusao(self):
        manutencao = self.abrir()
        iniciar = reverse("manutencoes:manutencao_iniciar", args=[manutencao.pk])
        self.assertEqual(self.client.get(iniciar).status_code, 405)
        self.client.get(reverse("manutencoes:manutencao_concluir", args=[manutencao.pk]))
        manutencao.refresh_from_db()
        self.assertEqual(manutencao.estado, "PENDENTE")
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(iniciar).status_code, 403)
        self.assertEqual(cliente.post(self.nova, {}).status_code, 403)
        self.assertEqual(self.client.post(f"/manutencoes/{manutencao.pk}/excluir/").status_code, 404)

    def test_perfis_incorretos_superuser_multiplos_e_permissao_individual_negados(self):
        manutencao = self.abrir()
        tecnico = get_user_model().objects.create_user(username="tecnico-rf07", is_superuser=True)
        misto = get_user_model().objects.create_user(username="misto-rf07")
        misto.groups.add(Group.objects.get(name="Administrador"), Group.objects.get(name="Professor"))
        for usuario in (tecnico, misto):
            registrar_aceite_vigente(usuario)
        for usuario in (self.cenario["professor"], self.cenario["operador"], tecnico, misto):
            usuario.user_permissions.add(*Permission.objects.filter(content_type__app_label="manutencoes"))
            self.client.force_login(usuario)
            urls = [self.lista, self.nova, reverse("manutencoes:manutencao_detalhe", args=[manutencao.pk]), reverse("manutencoes:manutencao_concluir", args=[manutencao.pk])]
            for url in urls:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    esperado = 405 if url in (self.lista, reverse("manutencoes:manutencao_detalhe", args=[manutencao.pk])) else 403
                    self.assertEqual(self.client.post(url, {}).status_code, esperado)
            self.assertEqual(self.client.post(reverse("manutencoes:manutencao_iniciar", args=[manutencao.pk])).status_code, 403)
        manutencao.refresh_from_db()
        self.assertEqual(manutencao.estado, "PENDENTE")

    def test_permissao_por_acao_menu_e_comando_idempotente(self):
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(codename="add_manutencao"))
        self.assertEqual(self.client.get(self.nova).status_code, 403)
        self.assertNotContains(self.client.get(self.lista), "Abrir manutenção")
        call_command("configurar_perfis", stdout=StringIO())
        call_command("configurar_perfis", stdout=StringIO())
        self.assertEqual(grupo.permissions.filter(content_type__app_label="manutencoes").count(), 3)
        self.assertFalse(grupo.permissions.filter(codename="delete_manutencao").exists())
        self.assertContains(self.client.get(self.lista), "Abrir manutenção")
        grupo.permissions.remove(Permission.objects.get(codename="view_manutencao"))
        self.assertEqual(self.client.get(self.lista).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.lista).status_code, 302)

    def test_busca_filtro_paginacao_e_historico_concluido(self):
        for indice in range(17):
            equipamento = Equipamento.objects.create(numero_patrimonio=f"MAN-{indice:02}", tipo=self.equipamento.tipo, local=self.equipamento.local)
            abrir_manutencao(administrador=self.admin, equipamento_id=equipamento.pk, descricao_problema="Defeito")
        resposta = self.client.get(self.lista)
        self.assertEqual(len(resposta.context["pagina"]), 15)
        self.assertEqual(resposta.context["pagina"].paginator.count, 17)
        self.assertEqual(len(self.client.get(self.lista, {"pagina": 2}).context["pagina"]), 2)
        encontrada = self.client.get(self.lista, {"busca": "MAN-16", "estado": "PENDENTE"})
        self.assertEqual(encontrada.context["pagina"].paginator.count, 1)
        self.assertEqual(self.client.get(self.lista, {"estado": "CONCLUIDA"}).context["pagina"].paginator.count, 0)

    def test_descricao_escapada_e_erro_preserva_entrada(self):
        resposta = self.client.post(self.nova, {"equipamento": self.equipamento.pk, "descricao_problema": "<script>alert(1)</script>"}, follow=True)
        self.assertContains(resposta, "&lt;script&gt;")
        self.assertNotContains(resposta, "<script>alert(1)</script>")
        resposta = self.client.post(self.nova, {"equipamento": 999999, "descricao_problema": "Texto preservado"})
        self.assertContains(resposta, "Texto preservado")
        self.assertTrue(resposta.context["form"].errors)

    def test_erro_transacional_mostra_mensagem_e_registra_falha(self):
        with patch("manutencoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            resposta = self.client.post(self.nova, {"equipamento": self.equipamento.pk, "descricao_problema": "Falha"})
        self.assertContains(resposta, "Nenhuma alteração foi salva")
        self.assertFalse(Manutencao.objects.exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.MANUTENCAO_ABERTA, resultado="FALHA").exists())

    def test_edicao_inventario_nao_libera_manutencao_aberta_e_exclusao_preserva(self):
        manutencao = self.abrir()
        dados = {
            "numero_patrimonio": self.equipamento.numero_patrimonio, "nome": self.equipamento.tipo.nome,
            "categoria": self.equipamento.tipo.categoria_id, "local": self.equipamento.local_id,
            "descricao": "Dados", "situacao": "DISPONIVEL",
        }
        resposta = self.client.post(reverse("inventario:equipamento_editar", args=[self.equipamento.pk]), dados)
        self.assertContains(resposta, "Conclua a manutenção")
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "MANUTENCAO")
        self.equipamento.delete()
        self.assertTrue(Manutencao.objects.filter(pk=manutencao.pk).exists())


class ManutencaoConcorrenciaTests(TransactionTestCase):
    def setUp(self):
        self.cenario = criar_cenario()

    def executar_duas_vezes(self, operacao):
        barreira = Barrier(2)

        def executar():
            connections.close_all()
            try:
                administrador = get_user_model().objects.get(pk=self.cenario["administrador"].pk)
                barreira.wait(timeout=15)
                try:
                    operacao(administrador)
                except ValidationError:
                    return "impedida"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: executar(), range(2)))
        self.assertCountEqual(resultados, ["sucesso", "impedida"])

    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_aberturas_criam_so_uma_intervencao(self):
        self.executar_duas_vezes(lambda administrador: abrir_manutencao(
            administrador=administrador, equipamento_id=self.cenario["equipamento"].pk, descricao_problema="Falha",
        ))
        self.assertEqual(Manutencao.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_dois_inicios_preservam_uma_transicao(self):
        manutencao = abrir_manutencao(administrador=self.cenario["administrador"], equipamento_id=self.cenario["equipamento"].pk, descricao_problema="Falha")
        self.executar_duas_vezes(lambda administrador: iniciar_manutencao(administrador=administrador, manutencao_id=manutencao.pk))
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.MANUTENCAO_INICIADA).count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_conclusoes_preservam_uma_transicao(self):
        manutencao = abrir_manutencao(administrador=self.cenario["administrador"], equipamento_id=self.cenario["equipamento"].pk, descricao_problema="Falha")
        iniciar_manutencao(administrador=self.cenario["administrador"], manutencao_id=manutencao.pk)
        self.executar_duas_vezes(lambda administrador: concluir_manutencao(
            administrador=administrador, manutencao_id=manutencao.pk, resultado="REPARADO", descricao_solucao="Reparo",
        ))
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.MANUTENCAO_CONCLUIDA).count(), 1)
