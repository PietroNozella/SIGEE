from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from reservas.models import Reserva

from .models import Movimentacao
from .services import grupos_devolucao, registrar_devolucoes, retiradas_do_grupo
from .test_devolucao import retirar
from .tests import criar_cenario


def criar_unidades(cenario, quantidade, prefixo):
    referencia = cenario["equipamento"]
    return [Equipamento.objects.create(
        numero_patrimonio=f"{prefixo}-{indice:02}", tipo=referencia.tipo, local=referencia.local,
    ) for indice in range(quantidade)]


class DevolucaoLoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.unidades = criar_unidades(cls.cenario, 30, "LOTE")
        cls.retiradas = retirar(cls.cenario, cls.unidades)

    def setUp(self):
        self.client.force_login(self.cenario["operador"])
        self.url = reverse("movimentacoes:devolucao_registrar", args=[self.retiradas[0].pk])
        self.lista = reverse("movimentacoes:devolucao_lista")
        self.ids = [item.pk for item in self.retiradas]

    def devolver(self, ids=None):
        return registrar_devolucoes(
            operador=self.cenario["operador"], retirada_id=self.retiradas[0].pk,
            retiradas_ids=self.ids if ids is None else ids, observacao="Recebimento em lote.",
        )

    def assert_lote_integro(self):
        self.assertFalse(Movimentacao.objects.filter(tipo=Movimentacao.Tipo.DEVOLUCAO).exists())
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades], situacao="EM_USO").count(), 30)
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA, resultado="SUCESSO").exists())

    def test_retirada_cria_identificacao_comum_e_lista_mostra_um_lote_de_30(self):
        lote = self.retiradas[0].lote_retirada
        self.assertIsNotNone(lote)
        self.assertEqual({item.lote_retirada for item in self.retiradas}, {lote})
        resposta = self.client.get(self.lista)
        self.assertEqual(resposta.context["pagina"].paginator.count, 1)
        self.assertContains(resposta, "30 em aberto")
        self.assertContains(resposta, "0 devolvidas de 30")
        detalhe = self.client.get(self.url)
        self.assertEqual(len(detalhe.context["selecionados"]), 30)
        for unidade in self.unidades:
            self.assertContains(detalhe, unidade.numero_patrimonio)
        self.assert_lote_integro()

    def test_tela_devolve_30_em_uma_confirmacao_preservando_cada_origem(self):
        originais = list(Movimentacao.objects.filter(pk__in=self.ids).order_by("pk").values())
        resposta = self.client.post(self.url, {"retiradas": self.ids, "observacao": "Lote recebido."}, follow=True)
        self.assertRedirects(resposta, self.lista)
        self.assertContains(resposta, "Devolução de 30 equipamento(s) registrada com sucesso")
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades], situacao="DISPONIVEL").count(), 30)
        devolucoes = Movimentacao.objects.filter(tipo=Movimentacao.Tipo.DEVOLUCAO).select_related("retirada_origem")
        self.assertEqual(devolucoes.count(), 30)
        for item in devolucoes:
            self.assertEqual(item.destinatario_id, item.retirada_origem.destinatario_id)
            self.assertEqual(item.equipamento_id, item.retirada_origem.equipamento_id)
            self.assertEqual(item.lote_retirada, item.retirada_origem.lote_retirada)
            self.assertEqual(item.observacao, "Lote recebido.")
        self.assertEqual(list(Movimentacao.objects.filter(pk__in=self.ids).order_by("pk").values()), originais)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA, resultado="SUCESSO").count(), 30)
        self.assertEqual(grupos_devolucao().count(), 0)

    def test_devolucao_parcial_deixa_desmarcados_em_uso_e_permite_completar_depois(self):
        self.assertRedirects(self.client.post(self.url, {"retiradas": self.ids[:-2]}), self.lista)
        grupo = grupos_devolucao().get()
        self.assertEqual((grupo["total"], grupo["pendentes"]), (30, 2))
        detalhe = self.client.get(self.url)
        self.assertEqual(detalhe.context["selecionados"], [str(item) for item in self.ids[-2:]])
        self.assertContains(detalhe, "Já devolvido", count=28)
        for item in self.unidades[-2:]:
            item.refresh_from_db()
            self.assertEqual(item.situacao, "EM_USO")
        self.devolver(self.ids[-2:])
        self.assertEqual(Movimentacao.objects.filter(tipo="DEVOLUCAO").count(), 30)
        self.assertFalse(grupos_devolucao().exists())

    def test_busca_por_uma_unidade_mantem_todas_as_30_no_grupo(self):
        resposta = self.client.get(self.lista, {"busca": "LOTE-17"})
        grupo = list(resposta.context["pagina"])[0]
        self.assertEqual((grupo["total"], grupo["pendentes"]), (30, 30))
        self.assertEqual(grupo["retirada_id"], self.retiradas[0].pk)

    def test_lotes_diferentes_do_mesmo_destinatario_nao_sao_misturados(self):
        outras = retirar(self.cenario, criar_unidades(self.cenario, 2, "OUTRO"))
        self.assertNotEqual(outras[0].lote_retirada, self.retiradas[0].lote_retirada)
        self.assertEqual(grupos_devolucao().count(), 2)
        resposta = self.client.post(self.url, {"retiradas": [self.ids[0], outras[0].pk]})
        self.assertContains(resposta, "não pertence a este grupo")
        with self.assertRaisesMessage(ValidationError, "somente unidades desta retirada"):
            self.devolver([self.ids[0], outras[0].pk])
        self.assert_lote_integro()

    def test_ids_inexistentes_e_repetidos_nao_devolvem_parte_do_lote(self):
        for ids in ([self.ids[0], 999999], [self.ids[0], self.ids[0]], [str(self.ids[0]), f"{self.ids[0]:03}"]):
            with self.subTest(ids=ids):
                resposta = self.client.post(self.url, {"retiradas": ids})
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors)
                with self.assertRaises(ValidationError):
                    self.devolver(ids)
                self.assert_lote_integro()

    def test_selecao_vazia_nao_devolve_automaticamente_todas_as_unidades(self):
        resposta = self.client.post(self.url, {"observacao": "Sem unidades"})
        self.assertContains(resposta, "Marque pelo menos um patrimônio recebido")
        self.assertEqual(resposta.context["selecionados"], [])
        with self.assertRaises(ValidationError):
            self.devolver([])
        self.assert_lote_integro()

    def test_unidade_ja_devolvida_em_selecao_desatualizada_impede_todo_o_resto(self):
        self.devolver([self.ids[0]])
        with self.assertRaisesMessage(ValidationError, "já foi devolvida"):
            self.devolver(self.ids[:3])
        resposta = self.client.post(self.url, {"retiradas": self.ids[:3]})
        self.assertContains(resposta, "já foi devolvida ou não pertence a este grupo")
        self.assertEqual(Movimentacao.objects.filter(tipo="DEVOLUCAO").count(), 1)
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades], situacao="EM_USO").count(), 29)

    def test_rollback_de_todo_lote_apos_gravar_primeira_unidade_e_auditoria(self):
        from auditoria.services import registrar_evento

        contador = 0

        def gravar_e_falhar_na_segunda(**dados):
            nonlocal contador
            registrar_evento(**dados)
            contador += 1
            if contador == 2:
                raise IntegrityError("Falha na segunda unidade")

        with patch("movimentacoes.services.registrar_evento", side_effect=gravar_e_falhar_na_segunda):
            resposta = self.client.post(self.url, {"retiradas": self.ids})
        self.assertContains(resposta, "Nenhuma alteração foi salva")
        self.assert_lote_integro()

    def test_reserva_agrupa_origens_e_preserva_reserva_sem_implementar_retirada_com_reserva(self):
        outras = retirar(self.cenario, criar_unidades(self.cenario, 2, "RESERVA"))
        inicio = timezone.now() + timedelta(days=2)
        reserva = Reserva.objects.create(
            professor=self.cenario["professor"], tipo_equipamento=self.cenario["equipamento"].tipo,
            local=self.cenario["equipamento"].local, inicio=inicio, fim=inicio + timedelta(hours=1),
        )
        ids = [self.ids[0], outras[0].pk]
        Movimentacao.objects.filter(pk__in=ids).update(reserva=reserva)
        grupo = grupos_devolucao().get(chave_grupo=f"reserva:{reserva.pk}")
        self.assertEqual(grupo["pendentes"], 2)
        self.assertEqual(set(retiradas_do_grupo(Movimentacao.objects.get(pk=self.ids[0])).values_list("pk", flat=True)), set(ids))
        devolucoes = self.devolver(ids)
        self.assertEqual({item.reserva_id for item in devolucoes}, {reserva.pk})
        self.assertEqual({item.lote_retirada for item in devolucoes}, {self.retiradas[0].lote_retirada, outras[0].lote_retirada})
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)

    def test_registros_antigos_sao_pendencias_por_destinatario_sem_inventar_lotes(self):
        Movimentacao.objects.filter(pk__in=self.ids).update(lote_retirada=None)
        novas = retirar(self.cenario, criar_unidades(self.cenario, 2, "NOVA"))
        self.assertEqual(grupos_devolucao().count(), 2)
        detalhe = self.client.get(self.url)
        self.assertContains(detalhe, "anteriores à identificação de lotes")
        self.assertEqual(detalhe.context["pendentes"], 30)
        self.assertNotContains(detalhe, "NOVA-00")
        outro_destinatario = Movimentacao.objects.create(
            tipo="RETIRADA", equipamento=self.cenario["equipamento"],
            operador=self.cenario["operador"], destinatario=self.cenario["administrador"],
        )
        with self.assertRaises(ValidationError):
            self.devolver([self.ids[0], outro_destinatario.pk])
        self.devolver(self.ids[:2])
        self.assertFalse(Movimentacao.objects.filter(pk__in=self.ids, lote_retirada__isnull=False).exists())
        self.assertFalse(novas[0].devolucoes.exists())


class ConcorrenciaDevolucaoLoteTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_solicitacoes_concorrentes_com_lotes_sobrepostos_nao_geram_parcial(self):
        cenario = criar_cenario()
        unidades = criar_unidades(cenario, 3, "CONCORRENTE")
        retiradas = retirar(cenario, unidades)
        ids = [item.pk for item in retiradas]
        barreira = Barrier(2)

        def tentar_devolver(selecao):
            connections.close_all()
            try:
                operador = get_user_model().objects.get(pk=cenario["operador"].pk)
                barreira.wait(timeout=10)
                try:
                    registrar_devolucoes(operador=operador, retirada_id=ids[0], retiradas_ids=selecao)
                except ValidationError as erro:
                    self.assertIn("já foi devolvida", str(erro))
                    return "ja_devolvida"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tentativas = [executor.submit(tentar_devolver, ids[:2]), executor.submit(tentar_devolver, ids[1:])]
            resultados = [item.result(timeout=20) for item in tentativas]
        self.assertCountEqual(resultados, ["sucesso", "ja_devolvida"])
        self.assertEqual(Movimentacao.objects.filter(tipo="DEVOLUCAO").count(), 2)
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in unidades], situacao="EM_USO").count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA, resultado="SUCESSO").count(), 2)
