import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.models import Movimentacao
from movimentacoes.services import criar_conferencia_retirada, registrar_devolucoes, registrar_retirada_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario

from .models import Reserva
from .services import cancelar_reserva_operacional, consultar_disponibilidade, resumo_entrega


class CancelamentoOperacionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario)

    def setUp(self):
        self.operador = self.cenario["operador"]
        self.url = reverse("reservas:reserva_cancelamento_operacional", args=[self.reserva.pk])
        self.agora = self.reserva.inicio + timedelta(minutes=5)
        relogio = patch("django.utils.timezone.now", return_value=self.agora)
        relogio.start()
        self.addCleanup(relogio.stop)
        self.client.force_login(self.operador)

    def cancelar(self, **alteracoes):
        return cancelar_reserva_operacional(**{
            "operador": self.operador, "reserva_id": self.reserva.pk,
            "motivo": "Professor informou que a atividade foi suspensa.",
            "desistencia_confirmada": True, **alteracoes,
        })

    def assert_reserva_preservada(self):
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.ATIVA)
        self.assertEqual(self.reserva.motivo_cancelamento, "")
        self.assertIsNone(self.reserva.cancelada_por_id)
        self.assertIsNone(self.reserva.data_cancelamento)
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_CANCELADA).exists())

    def test_cancela_lote_inteiro_com_motivo_responsavel_data_e_auditoria(self):
        itens = list(self.reserva.itens.values())
        equipamentos = list(Equipamento.objects.order_by("pk").values())
        cancelada = self.cancelar(motivo="  Professor comunicou desistência.  ")
        self.assertEqual(cancelada.status, Reserva.Status.CANCELADA)
        self.assertEqual(cancelada.motivo_cancelamento, "Professor comunicou desistência.")
        self.assertEqual(cancelada.cancelada_por_id, self.operador.pk)
        self.assertEqual(cancelada.data_cancelamento, self.agora)
        self.assertEqual(list(self.reserva.itens.values()), itens)
        self.assertEqual(list(Equipamento.objects.order_by("pk").values()), equipamentos)
        self.assertFalse(Movimentacao.objects.exists())
        registro = RegistroAuditoria.objects.get(acao=AcaoAuditoria.RESERVA_CANCELADA)
        self.assertEqual(registro.usuario_id, self.operador.pk)
        self.assertEqual(registro.entidade_id, str(self.reserva.pk))

    def test_libera_disponibilidade_imediatamente_sem_alterar_patrimonios(self):
        periodo = {
            "professor": self.cenario["professor"], "tipo_equipamento": self.reserva.tipo_equipamento,
            "local": self.reserva.local, "inicio": self.agora + timedelta(minutes=1), "fim": self.reserva.fim,
        }
        antes = consultar_disponibilidade(**periodo)
        self.cancelar()
        self.assertEqual(consultar_disponibilidade(**periodo), antes + 3)

    def test_motivo_vazio_e_desistencia_nao_confirmada_sao_recusados_no_servico(self):
        for dados in ({"motivo": ""}, {"motivo": " \n "}, {"desistencia_confirmada": False}, {"desistencia_confirmada": "false"}):
            with self.subTest(dados=dados), self.assertRaises(ValidationError):
                self.cancelar(**dados)
        self.assert_reserva_preservada()

    def test_get_somente_consulta_e_post_invalido_preserva_reserva(self):
        antes = Reserva.objects.values().get(pk=self.reserva.pk)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(Reserva.objects.values().get(pk=self.reserva.pk), antes)
        resposta = self.client.post(self.url, {"motivo": "   "})
        self.assertContains(resposta, "Informe o motivo")
        self.assertContains(resposta, "Confirme que o Professor")
        self.assert_reserva_preservada()

    def test_outros_perfis_nao_cancelam_mesmo_com_permissao_individual(self):
        permissao = Permission.objects.get(codename="cancelar_reserva_operacional")
        tecnico = get_user_model().objects.create_user(username="tecnico-cancelamento", is_superuser=True)
        tecnico.groups.add(Group.objects.get(name="Operador"))
        multiplo = get_user_model().objects.create_user(username="multiplo-cancelamento")
        multiplo.groups.add(*Group.objects.filter(name__in=("Operador", "Professor")))
        for usuario in (self.cenario["professor"], self.cenario["administrador"], tecnico, multiplo):
            usuario.user_permissions.add(permissao)
            registrar_aceite_vigente(usuario)
            self.client.force_login(usuario)
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, {"motivo": "Motivo", "desistencia_confirmada": "on"}).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    self.cancelar(operador=usuario)
        self.assert_reserva_preservada()

    def test_operador_sem_permissao_ou_inativo_nao_cancela(self):
        permissao = Permission.objects.get(codename="cancelar_reserva_operacional")
        grupo = Group.objects.get(name="Operador")
        grupo.permissions.remove(permissao)
        with self.assertRaises(PermissionDenied):
            self.cancelar()
        self.assertEqual(self.client.post(self.url).status_code, 403)
        grupo.permissions.add(permissao)
        get_user_model().objects.filter(pk=self.operador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.cancelar()
        self.assert_reserva_preservada()

    def test_cancelamento_sem_permissao_de_consulta_mostra_resultado_sem_abrir_consulta_geral(self):
        grupo = Group.objects.get(name="Operador")
        grupo.permissions.remove(*Permission.objects.filter(codename__in=("view_movimentacao", "add_movimentacao")))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        resposta = self.client.post(self.url, {"motivo": "Professor confirmou a desistência.", "desistencia_confirmada": "on"}, follow=True)
        self.assertRedirects(resposta, self.url)
        self.assertContains(resposta, "Reserva cancelada.")
        self.assertContains(resposta, "Professor confirmou a desistência.")
        self.assertContains(resposta, "Registrado por")
        self.assertNotContains(resposta, ">Consultar reserva</a>")
        self.assertNotContains(resposta, ">Manter reserva</a>")
        self.assertEqual(self.client.get(reverse("reservas:reserva_detalhe", args=[self.reserva.pk])).status_code, 403)

    def test_anonimo_csrf_metodos_e_reserva_inexistente(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.operador)
        self.assertEqual(cliente.post(self.url, {"motivo": "Motivo", "desistencia_confirmada": "on"}).status_code, 403)
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertEqual(self.client.get(reverse("reservas:reserva_cancelamento_operacional", args=[999999])).status_code, 404)
        with self.assertRaisesMessage(ValidationError, "não existe"):
            self.cancelar(reserva_id=999999)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_no_limite_expira_e_preserva_a_expiracao_apos_rejeitar_cancelamento(self):
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA):
            with self.assertRaisesMessage(ValidationError, "expirou"):
                self.cancelar()
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.EXPIRADA)
        self.assertIsNone(self.reserva.cancelada_por_id)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_EXPIRADA).count(), 1)
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_CANCELADA).exists())

    def test_imediatamente_antes_do_limite_permite_cancelamento(self):
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA - timedelta(microseconds=1)):
            self.assertEqual(self.cancelar().status, Reserva.Status.CANCELADA)

    def test_reenvio_nao_sobrescreve_motivo_autoria_ou_auditoria(self):
        self.cancelar()
        antes = Reserva.objects.values().get(pk=self.reserva.pk)
        with self.assertRaisesMessage(ValidationError, "já está cancelada"):
            self.cancelar(motivo="Outro motivo que não pode substituir o registro")
        self.assertEqual(Reserva.objects.values().get(pk=self.reserva.pk), antes)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_CANCELADA).count(), 1)

    def test_qualquer_entrega_inclusive_ja_devolvida_impede_cancelamento(self):
        retiradas = registrar_entrega_conferida(operador=self.operador, reserva_id=self.reserva.pk)
        with self.assertRaisesMessage(ValidationError, "retirada registrada"):
            self.cancelar()
        registrar_devolucoes(operador=self.operador, retirada_id=retiradas[0].pk, retiradas_ids=[r.pk for r in retiradas])
        with self.assertRaisesMessage(ValidationError, "retirada registrada"):
            self.cancelar()
        self.assert_reserva_preservada()

    def test_apos_abrir_tela_uma_entrega_impede_cancelamento(self):
        self.client.get(self.url)
        registrar_entrega_conferida(operador=self.operador, reserva_id=self.reserva.pk)
        resposta = self.client.post(self.url, {"motivo": "Desistência", "desistencia_confirmada": "on"})
        self.assertContains(resposta, "retirada registrada")
        self.assertNotContains(resposta, 'type="submit">Confirmar cancelamento')
        self.assert_reserva_preservada()

    def test_professor_e_referencias_inativos_nao_impedem_registrar_desistencia(self):
        get_user_model().objects.filter(pk=self.reserva.professor_id).update(is_active=False)
        self.reserva.tipo_equipamento.ativo = False
        self.reserva.tipo_equipamento.save(update_fields=("ativo",))
        self.reserva.local.ativo = False
        self.reserva.local.save(update_fields=("ativo",))
        self.assertEqual(self.cancelar().status, Reserva.Status.CANCELADA)

    def test_falha_na_auditoria_reverte_estado_e_metadados(self):
        with patch("reservas.services.registrar_evento", side_effect=RuntimeError("Falha na auditoria")):
            with self.assertRaises(RuntimeError):
                self.cancelar()
        self.assert_reserva_preservada()

    def test_banco_recusa_metadados_incompletos_ou_em_reserva_ativa(self):
        for dados in (
            {"motivo_cancelamento": "Incompleto"},
            {"cancelada_por": self.operador, "data_cancelamento": self.agora, "motivo_cancelamento": "Ainda ativa"},
        ):
            with self.subTest(dados=dados), self.assertRaises(IntegrityError), transaction.atomic():
                Reserva.objects.filter(pk=self.reserva.pk).update(**dados)
        self.assert_reserva_preservada()

    def test_post_ignora_autoria_forjada_e_detalhe_escapa_motivo(self):
        resposta = self.client.post(self.url, {
            "motivo": "Professor desistiu: <script>alert('x')</script>", "desistencia_confirmada": "on",
            "cancelada_por": self.cenario["administrador"].pk, "data_cancelamento": "2000-01-01",
        }, follow=True)
        self.assertRedirects(resposta, reverse("reservas:reserva_detalhe", args=[self.reserva.pk]))
        self.assertContains(resposta, "&lt;script&gt;")
        self.assertNotContains(resposta, "<script>alert('x')</script>")
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.cancelada_por_id, self.operador.pk)
        self.assertEqual(self.reserva.data_cancelamento, self.agora)

    def test_detalhe_mostra_metadados_aos_perfis_autorizados_e_preserva_escopo_docente(self):
        self.cancelar()
        detalhe = reverse("reservas:reserva_detalhe", args=[self.reserva.pk])
        for perfil in ("operador", "professor", "administrador"):
            self.client.force_login(self.cenario[perfil])
            self.assertContains(self.client.get(detalhe), self.reserva.motivo_cancelamento or "Professor informou")
        outro = get_user_model().objects.create_user(username="outro-professor-cancelamento")
        outro.groups.add(Group.objects.get(name="Professor"))
        registrar_aceite_vigente(outro)
        self.client.force_login(outro)
        self.assertEqual(self.client.get(detalhe).status_code, 404)

    def test_exportacao_inclui_cancelamento_para_professor_e_operador(self):
        self.cancelar()
        for perfil in ("professor", "operador"):
            saida = StringIO()
            call_command("exportar_dados_usuario", self.cenario[perfil].username, stdout=saida)
            dados = json.loads(saida.getvalue())
            registro = dados["reservas"][0]["cancelamento_operacional"] if perfil == "professor" else dados["reservas_canceladas_como_operador"][0]
            self.assertEqual(registro["motivo"], "Professor informou que a atividade foi suspensa.")
            self.assertIsNotNone(registro["data_hora"])


class ConcorrenciaCancelamentoOperacionalTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_cancelamento_e_entrega_disputam_a_mesma_reserva(self):
        cenario = criar_cenario()
        reserva, unidades = criar_reserva_alocada(cenario)
        token = criar_conferencia_retirada(reserva=reserva, operador=cenario["operador"], resumo=resumo_entrega(reserva))
        barreira = Barrier(2)

        def executar(cancelamento):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                try:
                    if cancelamento:
                        cancelar_reserva_operacional(
                            operador=cenario["operador"], reserva_id=reserva.pk,
                            motivo="Professor comunicou desistência.", desistencia_confirmada=True,
                        )
                        return "cancelada"
                    registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk, conferencia=token)
                    return "entregue"
                except ValidationError:
                    return "negada"
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", return_value=reserva.inicio + timedelta(minutes=5)):
            with ThreadPoolExecutor(max_workers=2) as executor:
                cancelar, entregar = executor.submit(executar, True), executor.submit(executar, False)
                resultados = [cancelar.result(timeout=30), entregar.result(timeout=30)]
        self.assertIn("negada", resultados)
        reserva.refresh_from_db()
        retiradas = Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA").count()
        if reserva.status == Reserva.Status.CANCELADA:
            self.assertCountEqual(resultados, ["cancelada", "negada"])
            self.assertEqual(retiradas, 0)
            self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_CANCELADA).count(), 1)
        else:
            self.assertCountEqual(resultados, ["negada", "entregue"])
            self.assertEqual(retiradas, 3)
            self.assertIsNone(reserva.cancelada_por_id)
        self.assertEqual(Equipamento.objects.filter(pk__in=[e.pk for e in unidades], situacao="EM_USO").count(), retiradas)
