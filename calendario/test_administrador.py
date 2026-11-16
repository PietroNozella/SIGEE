from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from movimentacoes.tests import criar_cenario
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from reservas.models import Reserva

from .models import AlteracaoCalendario


class CoesaoAdministradorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()

    def setUp(self):
        self.client.force_login(self.cenario["administrador"])

    def test_historico_permite_consultar_alteracao_anterior_as_quinze_mais_recentes(self):
        for indice in range(16):
            AlteracaoCalendario.objects.create(
                usuario=self.cenario["administrador"], motivo=f"Motivo {indice}", versao=indice + 1,
                anterior={"resumo": "Anterior"}, novo={"titulo": f"Mudança {indice}", "resumo": "Atual"},
            )
        url = reverse("calendario:calendario_escola")
        primeira = self.client.get(url, {"secao": "historico"})
        self.assertNotContains(primeira, "Motivo 0</")
        self.assertContains(primeira, "secao=historico&amp;pagina_historico=2")
        segunda = self.client.get(url, {"secao": "historico", "pagina_historico": 2})
        self.assertContains(segunda, "Motivo 0</")
        self.assertEqual(segunda.context["secao"], "historico")
        self.assertEqual(AlteracaoCalendario.objects.count(), 16)

    def test_desativacao_orienta_consulta_que_sincroniza_reserva_vencida(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        Reserva.objects.filter(pk=reserva.pk).update(
            inicio=timezone.now() - timedelta(days=1), fim=timezone.now() - timedelta(hours=23),
        )
        professor = self.cenario["professor"]
        url = reverse("usuarios:usuario_desativar", args=[professor.pk])
        bloqueada = self.client.post(url, follow=True)
        professor.refresh_from_db()
        self.assertTrue(professor.is_active)
        self.assertContains(bloqueada, f'<a href="{reverse("reservas:reserva_consulta")}">Consultar reservas</a>', html=True)
        self.client.get(reverse("reservas:reserva_consulta"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "EXPIRADA")
        self.client.post(url)
        professor.refresh_from_db()
        self.assertFalse(professor.is_active)
