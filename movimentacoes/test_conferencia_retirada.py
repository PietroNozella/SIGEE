from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from manutencoes.services import abrir_manutencao
from reservas.models import Reserva, ReservaEquipamento
from reservas.services import consultar_disponibilidade, resumo_entrega

from .models import Movimentacao
from .services import criar_conferencia_retirada, registrar_devolucoes, registrar_retirada_reserva
from .test_retirada_reserva import criar_reserva_alocada
from .tests import criar_cenario


class ConferenciaRetiradaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario)

    def setUp(self):
        self.operador = self.cenario["operador"]
        self.client.force_login(self.operador)
        self.url = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
        relogio = patch("django.utils.timezone.now", return_value=self.reserva.inicio + timedelta(minutes=5))
        relogio.start()
        self.addCleanup(relogio.stop)

    def conferir(self):
        return self.client.get(self.url).context["form"].initial["conferencia"]

    def confirmar(self, conferencia, **dados):
        return self.client.post(self.url, {"conferencia": conferencia, **dados})

    def nova_unidade(self):
        return Equipamento.objects.create(
            numero_patrimonio="SUBSTITUTO-CONFERENCIA", tipo=self.reserva.tipo_equipamento,
            local=self.reserva.local,
        )

    def abrir_custodia(self, equipamento):
        return Movimentacao.objects.create(
            tipo="RETIRADA", equipamento=equipamento, operador=self.operador,
            destinatario=self.cenario["professor"],
        )

    def test_post_sem_conferencia_nao_registra_entrega(self):
        resposta = self.client.post(self.url)
        self.assertContains(resposta, "Reabra a conferência")
        self.assertFalse(Movimentacao.objects.exists())

    def test_servico_recusa_conferencia_ausente_ou_adulterada(self):
        token = self.conferir()
        for conferencia in (None, "", token + "adulterado"):
            with self.subTest(conferencia=conferencia), self.assertRaises(ValidationError):
                registrar_retirada_reserva(
                    operador=self.operador, reserva_id=self.reserva.pk, conferencia=conferencia,
                )
        self.assertFalse(Movimentacao.objects.exists())

    def test_conferencia_nao_pode_ser_usada_por_outro_operador(self):
        token = self.conferir()
        outro = get_user_model().objects.create_user(username="outro-operador-conferencia")
        outro.groups.add(Group.objects.get(name="Operador"))
        with self.assertRaises(ValidationError):
            registrar_retirada_reserva(operador=outro, reserva_id=self.reserva.pk, conferencia=token)
        self.assertFalse(Movimentacao.objects.exists())

    def test_conferencia_nao_pode_ser_usada_em_outra_reserva(self):
        token = self.conferir()
        outra = Reserva.objects.get(pk=self.reserva.pk)
        outra.pk = None
        outra.save()
        ReservaEquipamento.objects.bulk_create(
            ReservaEquipamento(reserva=outra, equipamento=unidade) for unidade in self.unidades
        )
        with self.assertRaises(ValidationError):
            registrar_retirada_reserva(operador=self.operador, reserva_id=outra.pk, conferencia=token)
        self.assertFalse(Movimentacao.objects.exists())

    def test_substituicao_apos_conferencia_exige_conferir_novo_patrimonio(self):
        token = self.conferir()
        abrir_manutencao(
            administrador=self.operador, equipamento_id=self.unidades[0].pk,
            descricao_problema="Falha identificada antes da entrega",
        )
        self.assertEqual(self.reserva.substituicoes.count(), 1)
        resposta = self.confirmar(token)
        self.assertContains(resposta, "confira os patrimônios novamente")
        self.assertFalse(Movimentacao.objects.exists())
        token_atualizado = resposta.context["form"]["conferencia"].value()
        self.assertEqual(self.confirmar(token_atualizado).status_code, 302)
        self.assertFalse(Movimentacao.objects.filter(equipamento=self.unidades[0]).exists())
        self.assertTrue(Movimentacao.objects.filter(equipamento=self.cenario["equipamento"]).exists())

    def test_renomeacao_do_patrimonio_exige_nova_conferencia(self):
        token = self.conferir()
        Equipamento.objects.filter(pk=self.unidades[0].pk).update(numero_patrimonio="PATRIMONIO-CORRIGIDO")
        resposta = self.confirmar(token)
        self.assertContains(resposta, "confira os patrimônios novamente")
        self.assertFalse(Movimentacao.objects.exists())

    def test_reenvio_apos_entrega_parcial_nao_incorpora_novo_substituto(self):
        self.cenario["equipamento"].delete()
        abrir_manutencao(
            administrador=self.operador, equipamento_id=self.unidades[0].pk, descricao_problema="Não liga",
        )
        token = self.conferir()
        self.assertEqual(self.confirmar(token, professor_informado="on").status_code, 302)
        antes = list(Movimentacao.objects.order_by("pk").values())
        auditorias = RegistroAuditoria.objects.count()
        substituto = self.nova_unidade()
        self.assertEqual(self.confirmar(token, professor_informado="on").status_code, 302)
        self.assertEqual(list(Movimentacao.objects.order_by("pk").values()), antes)
        self.assertEqual(RegistroAuditoria.objects.count(), auditorias)
        self.assertEqual(self.reserva.substituicoes.count(), 0)
        self.assertEqual(self.confirmar(self.conferir()).status_code, 302)
        self.assertEqual(Movimentacao.objects.filter(tipo="RETIRADA").count(), 3)
        self.assertTrue(Movimentacao.objects.filter(equipamento=substituto).exists())

    def test_reenvio_apos_devolucao_e_fim_nao_reabre_custodia(self):
        token = self.conferir()
        self.confirmar(token)
        retiradas = list(Movimentacao.objects.filter(tipo="RETIRADA"))
        registrar_devolucoes(
            operador=self.operador, retirada_id=retiradas[0].pk,
            retiradas_ids=[retirada.pk for retirada in retiradas],
        )
        antes = list(Movimentacao.objects.order_by("pk").values())
        with patch("django.utils.timezone.now", return_value=self.reserva.fim + timedelta(hours=1)):
            resposta = self.client.post(self.url, {"conferencia": token}, follow=True)
        self.assertContains(resposta, "já registrada")
        self.assertEqual(list(Movimentacao.objects.order_by("pk").values()), antes)
        self.assertEqual(Equipamento.objects.filter(pk__in=[e.pk for e in self.unidades], situacao="DISPONIVEL").count(), 3)

    def test_duas_conferencias_distintas_nao_repetem_as_mesmas_unidades(self):
        primeira, segunda = self.conferir(), self.conferir()
        self.assertEqual(self.confirmar(primeira).status_code, 302)
        self.assertContains(self.confirmar(segunda), "já possui retirada")
        self.assertEqual(Movimentacao.objects.count(), 3)

    def test_reenvio_revalida_autorizacao_atual_do_operador(self):
        token = self.conferir()
        self.confirmar(token)
        self.operador.groups.clear()
        with self.assertRaises(PermissionDenied):
            registrar_retirada_reserva(operador=self.operador, reserva_id=self.reserva.pk, conferencia=token)
        self.assertEqual(Movimentacao.objects.count(), 3)

    def test_edicao_cadastral_nao_libera_equipamento_com_custodia_aberta(self):
        unidade = self.unidades[0]
        self.abrir_custodia(unidade)
        Equipamento.objects.filter(pk=unidade.pk).update(situacao="EM_USO")
        self.client.force_login(self.cenario["administrador"])
        resposta = self.client.post(reverse("inventario:equipamento_editar", args=[unidade.pk]), {
            "numero_patrimonio": unidade.numero_patrimonio, "nome": unidade.tipo.nome,
            "categoria": unidade.tipo.categoria_id, "local": unidade.local_id, "situacao": "DISPONIVEL",
        })
        self.assertContains(resposta, "Registre a devolução física")
        unidade.refresh_from_db()
        self.assertEqual(unidade.situacao, "EM_USO")
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.EQUIPAMENTO_EDITADO, resultado="SUCESSO").exists())

    def test_disponibilidade_e_substituicao_excluem_custodia_com_situacao_inconsistente(self):
        self.abrir_custodia(self.cenario["equipamento"])
        quantidade = consultar_disponibilidade(
            professor=self.cenario["professor"], tipo_equipamento=self.reserva.tipo_equipamento,
            local=self.reserva.local, inicio=self.reserva.fim, fim=self.reserva.fim + timedelta(hours=1),
        )
        self.assertEqual(quantidade, 3)
        abrir_manutencao(
            administrador=self.operador, equipamento_id=self.unidades[0].pk, descricao_problema="Não liga",
        )
        self.assertEqual(self.reserva.substituicoes.count(), 0)

    def test_custodia_aberta_entre_tela_e_post_impede_entrega_mesmo_com_situacao_disponivel(self):
        token = self.conferir()
        origem = self.abrir_custodia(self.unidades[0])
        resposta = self.confirmar(token)
        self.assertContains(resposta, "Nenhuma alteração foi salva")
        self.assertEqual(list(Movimentacao.objects.values_list("pk", flat=True)), [origem.pk])
        self.assertFalse(Movimentacao.objects.filter(reserva=self.reserva).exists())


class ConcorrenciaConferenciaTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_reenvios_simultaneos_da_mesma_conferencia_retornam_o_mesmo_lote(self):
        cenario = criar_cenario()
        reserva, _ = criar_reserva_alocada(cenario)
        token = criar_conferencia_retirada(
            reserva=reserva, operador=cenario["operador"], resumo=resumo_entrega(reserva),
        )
        barreira = Barrier(2)

        def confirmar():
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                return [item.pk for item in registrar_retirada_reserva(
                    operador=cenario["operador"], reserva_id=reserva.pk, conferencia=token,
                )]
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            with ThreadPoolExecutor(max_workers=2) as executor:
                primeira, segunda = executor.submit(confirmar), executor.submit(confirmar)
                self.assertEqual(primeira.result(timeout=30), segunda.result(timeout=30))
        self.assertEqual(Movimentacao.objects.count(), 3)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RETIRADA_REGISTRADA, resultado="SUCESSO").count(), 3)
