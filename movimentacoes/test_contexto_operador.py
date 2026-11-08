from django.test import TestCase
from django.urls import reverse

from .tests import criar_cenario
from .test_retirada_reserva import criar_reserva_alocada


class ContextoOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, _ = criar_reserva_alocada(cls.cenario)
        cls.reserva.observacao_pedagogica = "Observação exclusiva do planejamento"
        cls.reserva.save()

    def test_operador_consulta_turma_sem_demais_dados_pedagogicos(self):
        self.client.force_login(self.cenario["operador"])
        for rota in ("reservas:reserva_detalhe", "movimentacoes:retirada_reserva_registrar"):
            resposta = self.client.get(reverse(rota, args=[self.reserva.pk]))
            self.assertContains(resposta, self.reserva.turma.nome)
            self.assertNotContains(resposta, self.reserva.disciplina.nome)
            self.assertNotContains(resposta, self.reserva.atividade.nome)
            self.assertNotContains(resposta, self.reserva.observacao_pedagogica)
