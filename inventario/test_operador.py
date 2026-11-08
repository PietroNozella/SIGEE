from django.test import TestCase
from django.urls import reverse

from movimentacoes.tests import criar_cenario


class DisponibilidadeOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()

    def test_inativo_nao_recebe_selo_disponivel_nem_aparece_no_filtro_disponivel(self):
        equipamento = self.cenario["equipamento"]
        equipamento.ativo = False
        equipamento.save()
        self.client.force_login(self.cenario["operador"])
        url = reverse("inventario:equipamento_lista")
        resposta = self.client.get(url)
        self.assertContains(resposta, "Inativo — indisponível para uso")
        self.assertNotContains(resposta, 'class="status-badge status-disponivel"')
        resposta = self.client.get(url, {"situacao": "DISPONIVEL"})
        self.assertNotContains(resposta, equipamento.numero_patrimonio)
