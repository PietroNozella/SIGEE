from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from inventario.models import Equipamento
from manutencoes.services import abrir_manutencao
from pedagogico.models import UtilizacaoPedagogica
from reservas.models import Reserva
from reservas.services import resumo_entrega

from .models import Movimentacao
from .services import registrar_devolucoes, registrar_retirada_reserva, reservas_para_retirada
from .test_retirada_reserva import criar_reserva_alocada
from .tests import criar_cenario


class EntregaParcialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.cenario["equipamento"].delete()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario, quantidade=3)

    def setUp(self):
        self.operador = self.cenario["operador"]
        self.client.force_login(self.operador)
        self.relogio = patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio + timedelta(minutes=5))
        self.agora = self.relogio.start()
        self.addCleanup(self.relogio.stop)
        self.manutencao = abrir_manutencao(administrador=self.operador, equipamento_id=self.unidades[0].pk, descricao_problema="Não liga")

    def entregar(self, **dados):
        return registrar_retirada_reserva(operador=self.operador, reserva_id=self.reserva.pk, **dados)

    def novo_equipamento(self):
        return Equipamento.objects.create(numero_patrimonio="COMPLEMENTO", tipo=self.reserva.tipo_equipamento, local=self.reserva.local)

    def test_exige_comunicacao_ao_professor_sem_gravar_entrega_incompleta(self):
        with self.assertRaisesMessage(ValidationError, "Informe o Professor"):
            self.entregar()
        self.assertFalse(Movimentacao.objects.exists())

    def test_entrega_parcial_separa_falta_de_entrega_de_devolucao(self):
        entregas = self.entregar(professor_informado=True)
        self.assertEqual(len(entregas), 2)
        self.assertTrue(all(m.professor_informado for m in entregas))
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 2)
        self.assertFalse(Movimentacao.objects.filter(equipamento=self.unidades[0]).exists())
        resumo = resumo_entrega(self.reserva)
        self.assertEqual((resumo["entregues"], resumo["pendentes"], resumo["devolucoes_pendentes"]), (2, 1, 2))
        self.assertTrue(reservas_para_retirada().filter(pk=self.reserva.pk).exists())
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, "ATIVA")

    def test_complementa_apos_tolerancia_sem_reentregar_unidades(self):
        primeiras = self.entregar(professor_informado=True)
        equipamento = self.novo_equipamento()
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio + timedelta(minutes=45)):
            complemento = self.entregar()
        self.assertEqual(len(complemento), 1)
        self.assertEqual(complemento[0].equipamento, equipamento)
        self.assertNotEqual(primeiras[0].lote_retirada, complemento[0].lote_retirada)
        self.assertEqual(Movimentacao.objects.filter(reserva=self.reserva, tipo="RETIRADA").count(), 3)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        self.assertFalse(reservas_para_retirada().filter(pk=self.reserva.pk).exists())
        with self.assertRaisesMessage(ValidationError, "já possui retirada"):
            self.entregar()

    def test_prazo_final_encerra_saldo_sem_encerrar_devolucoes(self):
        self.entregar(professor_informado=True)
        self.novo_equipamento()
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.fim):
            with self.assertRaisesMessage(ValidationError, "período reservado terminou"):
                self.entregar()
            resumo = resumo_entrega(self.reserva)
            self.assertEqual((resumo["pendentes"], resumo["nao_atendidas"], resumo["devolucoes_pendentes"]), (0, 1, 2))
            self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, "EM_USO")

    def test_todas_devolvidas_mas_saldo_de_entrega_permanece_consultavel(self):
        entregas = self.entregar(professor_informado=True)
        registrar_devolucoes(operador=self.operador, retirada_id=entregas[0].pk, retiradas_ids=[m.pk for m in entregas])
        self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, "AGUARDANDO")
        self.assertTrue(reservas_para_retirada().filter(pk=self.reserva.pk).exists())
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.fim):
            self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, "ENCERRADA")

    def test_professor_visualiza_saldo_e_nao_pode_entregar(self):
        self.entregar(professor_informado=True)
        self.client.force_login(self.cenario["professor"])
        resposta = self.client.get(reverse("reservas:reserva_detalhe", args=[self.reserva.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["resumo"]["pendentes"], 1)
        self.assertEqual(self.client.post(reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])).status_code, 403)

    def test_nenhum_disponivel_nao_grava_retirada_vazia(self):
        for unidade in self.unidades[1:]:
            abrir_manutencao(administrador=self.operador, equipamento_id=unidade.pk, descricao_problema="Falha")
        with self.assertRaisesMessage(ValidationError, "Nenhum equipamento"):
            self.entregar(professor_informado=True)
        self.assertFalse(Movimentacao.objects.exists())

    def test_complementos_sao_devolvidos_juntos_sem_incluir_unidade_nao_entregue(self):
        primeiras = self.entregar(professor_informado=True)
        self.novo_equipamento()
        complemento = self.entregar()
        ids = [m.pk for m in primeiras + complemento]
        devolucoes = registrar_devolucoes(operador=self.operador, retirada_id=ids[0], retiradas_ids=ids)
        self.assertEqual(len(devolucoes), 3)
        self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, "ENCERRADA")

    def test_falha_na_auditoria_reverte_entrega_parcial(self):
        with patch("movimentacoes.services.registrar_evento", side_effect=RuntimeError("Falha")):
            with self.assertRaises(RuntimeError):
                self.entregar(professor_informado=True)
        self.assertFalse(Movimentacao.objects.exists())
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.assertEqual(Equipamento.objects.filter(situacao="EM_USO").count(), 0)

    def test_reenvio_http_nao_duplica_entrega_parcial(self):
        url = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
        self.assertEqual(self.client.post(url, {"professor_informado": "on"}).status_code, 302)
        resposta = self.client.post(url, {"professor_informado": "on"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Movimentacao.objects.count(), 2)
