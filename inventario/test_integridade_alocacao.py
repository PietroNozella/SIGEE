from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from movimentacoes.models import Movimentacao
from movimentacoes.services import criar_conferencia_retirada, registrar_retirada_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva
from reservas.services import resumo_entrega

from .models import Categoria, Equipamento, Local, TipoEquipamento


class IntegridadeCadastroEquipamentoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario, quantidade=2)
        cls.outro_local = Local.objects.create(nome="Outro local")
        cls.outra_categoria = Categoria.objects.create(nome="Outra categoria")

    def setUp(self):
        relogio = patch("django.utils.timezone.now", return_value=self.reserva.inicio - timedelta(minutes=10))
        relogio.start()
        self.addCleanup(relogio.stop)
        self.client.force_login(self.cenario["administrador"])
        self.equipamento = self.unidades[0]
        self.url = reverse("inventario:equipamento_editar", args=[self.equipamento.pk])

    def dados(self):
        return {
            "numero_patrimonio": self.equipamento.numero_patrimonio,
            "nome": self.equipamento.tipo.nome, "categoria": self.equipamento.tipo.categoria_id,
            "local": self.equipamento.local_id, "situacao": self.equipamento.situacao, "descricao": "",
        }

    def test_edicao_rejeita_tipo_categoria_ou_local_comprometido_sem_criar_tipo(self):
        total_tipos = TipoEquipamento.objects.count()
        for alteracoes in ({"nome": "Outro tipo"}, {"categoria": self.outra_categoria.pk}, {"local": self.outro_local.pk}):
            with self.subTest(alteracoes=alteracoes):
                resposta = self.client.post(self.url, {**self.dados(), **alteracoes})
                self.assertContains(resposta, "unidade com reserva vigente ou retirada em aberto")
                self.equipamento.refresh_from_db()
                self.assertEqual(self.equipamento.tipo_id, self.reserva.tipo_equipamento_id)
                self.assertEqual(self.equipamento.local_id, self.reserva.local_id)
                self.assertEqual(TipoEquipamento.objects.count(), total_tipos)

    def test_edicao_recusada_preserva_entrega_integral(self):
        self.client.post(self.url, {**self.dados(), "local": self.outro_local.pk})
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            self.client.force_login(self.cenario["operador"])
            url_entrega = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
            conferencia = self.client.get(url_entrega).context["form"].initial["conferencia"]
            self.assertEqual(self.client.post(url_entrega, {"conferencia": conferencia}).status_code, 302)
        self.assertEqual(Movimentacao.objects.filter(reserva=self.reserva, tipo="RETIRADA").count(), 2)

    def test_descricao_pode_ser_corrigida_sem_mudar_alocacao(self):
        resposta = self.client.post(self.url, {**self.dados(), "descricao": "Descrição corrigida"})
        self.assertEqual(resposta.status_code, 302)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.descricao, "Descrição corrigida")

    def test_sem_compromisso_permite_corrigir_tipo_e_local(self):
        self.reserva.status = Reserva.Status.CANCELADA
        self.reserva.save(update_fields=["status"])
        resposta = self.client.post(self.url, {**self.dados(), "nome": "Outro tipo", "local": self.outro_local.pk})
        self.assertEqual(resposta.status_code, 302)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.tipo.nome, "Outro tipo")
        self.assertEqual(self.equipamento.local_id, self.outro_local.pk)

    def test_cadastro_e_edicao_nao_aceitam_em_uso_sem_retirada(self):
        for url, patrimonio in ((reverse("inventario:equipamento_novo"), "NOVO-SEM-RETIRADA"), (self.url, self.equipamento.numero_patrimonio)):
            with self.subTest(url=url):
                resposta = self.client.post(url, {**self.dados(), "numero_patrimonio": patrimonio, "situacao": "EM_USO"})
                self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Equipamento.objects.filter(numero_patrimonio="NOVO-SEM-RETIRADA").exists())
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "DISPONIVEL")
        self.assertFalse(Movimentacao.objects.exists())

    def test_modelo_tambem_rejeita_em_uso_sem_retirada(self):
        self.equipamento.situacao = "EM_USO"
        with self.assertRaisesMessage(ValidationError, "exige uma retirada registrada"):
            self.equipamento.full_clean()

    def test_custodia_impede_mudar_situacao_e_preserva_edicao_da_descricao(self):
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            self.client.force_login(self.cenario["operador"])
            url_entrega = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
            conferencia = self.client.get(url_entrega).context["form"].initial["conferencia"]
            self.client.post(url_entrega, {"conferencia": conferencia})
            self.client.force_login(self.cenario["administrador"])
            self.equipamento.refresh_from_db()
            resposta = self.client.post(self.url, {**self.dados(), "situacao": "MANUTENCAO"})
            self.assertContains(resposta, "Registre a devolução física")
            resposta = self.client.post(self.url, {**self.dados(), "descricao": "Conferido"})
            self.assertEqual(resposta.status_code, 302)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "EM_USO")
        self.assertEqual(self.equipamento.descricao, "Conferido")


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaCadastroEquipamentoTests(TransactionTestCase):
    def test_edicao_de_local_e_entrega_preservam_compromisso(self):
        cenario = criar_cenario()
        reserva, unidades = criar_reserva_alocada(cenario, quantidade=2)
        outro_local = Local.objects.create(nome="Local pretendido")
        equipamento = unidades[0]
        token = criar_conferencia_retirada(reserva=reserva, operador=cenario["operador"], resumo=resumo_entrega(reserva))
        barreira = Barrier(2)

        def editar():
            connections.close_all()
            try:
                cliente = Client()
                cliente.force_login(cenario["administrador"])
                barreira.wait(timeout=10)
                resposta = cliente.post(reverse("inventario:equipamento_editar", args=[equipamento.pk]), {
                    "numero_patrimonio": equipamento.numero_patrimonio, "nome": equipamento.tipo.nome,
                    "categoria": equipamento.tipo.categoria_id, "local": outro_local.pk, "situacao": "DISPONIVEL",
                })
                self.assertEqual(resposta.status_code, 200)
            finally:
                connections.close_all()

        def entregar():
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk, conferencia=token)
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            with ThreadPoolExecutor(max_workers=2) as executor:
                tarefas = [executor.submit(operacao) for operacao in (editar, entregar)]
                for tarefa in tarefas:
                    tarefa.result(timeout=30)
        equipamento.refresh_from_db()
        self.assertEqual(equipamento.local_id, reserva.local_id)
        self.assertEqual(equipamento.situacao, "EM_USO")
        self.assertEqual(Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA").count(), 2)
