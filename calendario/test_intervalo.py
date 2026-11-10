from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from manutencoes.services import abrir_manutencao
from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.services import registrar_devolucoes
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva, ReservaEquipamento
from reservas.services import consultar_disponibilidade, criar_reserva

from .models import AlteracaoCalendario, CalendarioEscolar
from .services import intervalo_vigente, salvar_intervalo


class IntervaloReservasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.legada, unidades = criar_reserva_alocada(cls.cenario, quantidade=1)
        cls.unidade = unidades[0]
        cls.cenario["equipamento"].ativo = False
        cls.cenario["equipamento"].save(update_fields=["ativo"])

    def setUp(self):
        self.admin = self.cenario["administrador"]
        self.inicio = self.legada.inicio
        relogio = patch("django.utils.timezone.now", return_value=self.inicio - timedelta(hours=2))
        relogio.start()
        self.addCleanup(relogio.stop)
        self.client.force_login(self.admin)

    def configurar(self, minutos):
        return salvar_intervalo(usuario=self.admin, minutos=minutos, motivo="Tempo de conferência do setor.",
            versao=CalendarioEscolar.objects.filter(pk=1).values_list("versao", flat=True).first() or 1)

    def reservar(self, inicio, fim=None, **outros):
        return criar_reserva(professor=self.cenario["professor"], tipo_equipamento=self.legada.tipo_equipamento,
            local=self.legada.local, quantidade=1, inicio=inicio, fim=fim or inicio + timedelta(hours=1),
            turma=self.legada.turma, disciplina=self.legada.disciplina, atividade=self.legada.atividade, **outros)

    def disponiveis(self, inicio, fim=None):
        return consultar_disponibilidade(professor=self.cenario["professor"], tipo_equipamento=self.legada.tipo_equipamento,
            local=self.legada.local, inicio=inicio, fim=fim or inicio + timedelta(hours=1))

    def primeira_nova(self):
        self.legada.status = Reserva.Status.CANCELADA
        self.legada.save(update_fields=["status"])
        return self.reservar(self.inicio)

    def test_padrao_e_reserva_legada_preservam_politicas_distintas(self):
        self.assertEqual(intervalo_vigente(), timedelta(minutes=5))
        nova = self.reservar(self.legada.fim)
        self.assertEqual(self.legada.intervalo_apos_uso, timedelta())
        self.assertEqual(nova.intervalo_apos_uso, timedelta(minutes=5))

    def test_limites_antes_exatamente_e_depois_da_margem(self):
        anterior = self.primeira_nova()
        for minutos, esperado in [(0, 0), (4, 0), (5, 1), (6, 1)]:
            with self.subTest(minutos=minutos):
                self.assertEqual(self.disponiveis(anterior.fim + timedelta(minutes=minutos)), esperado)
        with self.assertRaises(ValidationError):
            self.reservar(anterior.fim + timedelta(minutes=4))
        seguinte = self.reservar(anterior.fim + timedelta(minutes=5))
        self.assertEqual(seguinte.itens.get().equipamento_id, self.unidade.pk)

    def test_margem_da_nova_tambem_e_respeitada_antes_de_reserva_futura(self):
        # A legada começa às 9h. O novo uso precisa terminar às 8h55 ou antes.
        for minutos, esperado in [(0, 0), (4, 0), (5, 1)]:
            with self.subTest(minutos=minutos):
                fim = self.inicio - timedelta(minutes=minutos)
                self.assertEqual(self.disponiveis(self.inicio - timedelta(hours=1), fim), esperado)
        self.reservar(self.inicio - timedelta(hours=1), self.inicio - timedelta(minutes=5))

    def test_mudanca_preserva_cinco_minutos_anteriores_e_grava_novo_valor(self):
        anterior = self.primeira_nova()
        self.configurar(20)
        self.assertEqual(self.disponiveis(anterior.fim + timedelta(minutes=5)), 1)
        nova = self.reservar(anterior.fim + timedelta(minutes=5))
        anterior.refresh_from_db()
        self.assertEqual(anterior.intervalo_apos_uso, timedelta(minutes=5))
        self.assertEqual(nova.intervalo_apos_uso, timedelta(minutes=20))

    def test_zero_permite_adjacencia_sem_apagar_margem_ja_acordada(self):
        anterior = self.primeira_nova()
        self.configurar(0)
        self.assertEqual(intervalo_vigente(), timedelta())
        self.assertEqual(self.disponiveis(anterior.fim), 0)
        nova = self.reservar(anterior.fim + timedelta(minutes=5))
        seguinte = self.reservar(nova.fim)
        self.assertEqual(seguinte.intervalo_apos_uso, timedelta())

    def test_cancelamento_e_expiracao_nao_mantem_margem(self):
        anterior = self.primeira_nova()
        for status in [Reserva.Status.CANCELADA, Reserva.Status.EXPIRADA]:
            with self.subTest(status=status):
                anterior.status = status
                anterior.save(update_fields=["status"])
                self.assertEqual(self.disponiveis(anterior.fim), 1)

    def test_unidades_diferentes_podem_ser_usadas_sem_intervalo_entre_si(self):
        anterior = self.primeira_nova()
        outra = Equipamento.objects.create(numero_patrimonio="OUTRA-INTERVALO", tipo=self.legada.tipo_equipamento, local=self.legada.local)
        seguinte = self.reservar(anterior.fim)
        self.assertEqual(seguinte.itens.get().equipamento_id, outra.pk)

    def test_fim_do_intervalo_nao_libera_custodia_fisica(self):
        anterior = self.primeira_nova()
        with patch("django.utils.timezone.now", return_value=anterior.inicio):
            registrar_entrega_conferida(operador=self.cenario["operador"], reserva_id=anterior.pk)
        self.assertEqual(self.disponiveis(anterior.fim + timedelta(minutes=10)), 0)

    def test_devolucao_antecipada_preserva_margem_acordada(self):
        anterior = self.primeira_nova()
        with patch("django.utils.timezone.now", return_value=anterior.inicio):
            entregas = registrar_entrega_conferida(operador=self.cenario["operador"], reserva_id=anterior.pk)
            registrar_devolucoes(operador=self.cenario["operador"], retirada_id=entregas[0].pk, retiradas_ids=[entregas[0].pk])
        self.assertEqual(self.disponiveis(anterior.fim + timedelta(minutes=4)), 0)
        self.assertEqual(self.disponiveis(anterior.fim + timedelta(minutes=5)), 1)

    def test_substituicao_por_manutencao_respeita_intervalo_acordado(self):
        anterior = self.primeira_nova()
        substituta = Equipamento.objects.create(numero_patrimonio="SUBSTITUTA-INTERVALO", tipo=anterior.tipo_equipamento, local=anterior.local)
        futura = Reserva.objects.create(professor=anterior.professor, tipo_equipamento=anterior.tipo_equipamento,
            local=anterior.local, inicio=anterior.fim + timedelta(minutes=4), fim=anterior.fim + timedelta(hours=1))
        ReservaEquipamento.objects.create(reserva=futura, equipamento=substituta)
        # A configuração atual não pode mudar o intervalo de uma substituição anterior.
        self.configurar(0)
        abrir_manutencao(administrador=self.admin, equipamento_id=self.unidade.pk, descricao_problema="Falha no projetor.")
        self.assertEqual(anterior.itens.get().equipamento_id, self.unidade.pk)
        self.assertFalse(anterior.substituicoes.exists())

    def test_admin_salva_com_historico_e_auditoria(self):
        resposta = self.client.post(reverse("calendario:intervalo"), {"intervalo_minutos": 12, "motivo": "Conferência do lote", "versao": 1})
        self.assertRedirects(resposta, reverse("calendario:calendario_escola") + "?secao=reservas")
        self.assertEqual(intervalo_vigente(), timedelta(minutes=12))
        alteracao = AlteracaoCalendario.objects.get()
        self.assertEqual(alteracao.anterior["intervalo_minutos"], 5)
        self.assertEqual(alteracao.novo["intervalo_minutos"], 12)
        self.assertEqual(alteracao.usuario, self.admin)
        self.assertEqual(alteracao.motivo, "Conferência do lote")
        self.assertTrue(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.CALENDARIO_ALTERADO, entidade_id=str(alteracao.pk)).exists())

    def test_formulario_adulterado_e_motivo_ausente_nao_gravam(self):
        for valor in ["-1", "1.5", "32768", "abc", ""]:
            with self.subTest(valor=valor):
                resposta = self.client.post(reverse("calendario:intervalo"), {"intervalo_minutos": valor, "motivo": "Teste", "versao": 1})
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors)
        resposta = self.client.post(reverse("calendario:intervalo"), {"intervalo_minutos": 10, "motivo": " ", "versao": 1})
        self.assertIn("motivo", resposta.context["form"].errors)
        self.assertFalse(AlteracaoCalendario.objects.exists())

    def test_valores_invalidos_tambem_sao_recusados_no_servico(self):
        for minutos in [-1, 32768]:
            with self.subTest(minutos=minutos), self.assertRaises(ValidationError):
                self.configurar(minutos)
        self.assertEqual(intervalo_vigente(), timedelta(minutes=5))

    def test_tela_e_servico_rejeitam_outros_perfis_e_admin_sem_permissao(self):
        for perfil in ["professor", "operador"]:
            usuario = self.cenario[perfil]
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("calendario:intervalo")).status_code, 403)
            self.assertEqual(self.client.post(reverse("calendario:intervalo"), {}).status_code, 403)
            with self.assertRaises(PermissionDenied):
                salvar_intervalo(usuario=usuario, minutos=10, motivo="Teste", versao=1)
        self.admin.groups.get().permissions.remove(Permission.objects.get(codename="configurar_calendario"))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("calendario:intervalo")).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.configurar(10)

    def test_versao_desatualizada_nao_sobrescreve_configuracao(self):
        self.configurar(10)
        with self.assertRaisesMessage(ValidationError, "outro Administrador"):
            salvar_intervalo(usuario=self.admin, minutos=20, motivo="Teste", versao=1)
        self.assertEqual(intervalo_vigente(), timedelta(minutes=10))
        self.assertEqual(AlteracaoCalendario.objects.count(), 1)

    def test_falha_na_auditoria_reverte_configuracao_e_historico(self):
        with patch("calendario.services.registrar_evento", side_effect=RuntimeError("Auditoria indisponível")):
            with self.assertRaises(RuntimeError):
                self.configurar(15)
        self.assertEqual(intervalo_vigente(), timedelta(minutes=5))
        self.assertFalse(AlteracaoCalendario.objects.exists())
