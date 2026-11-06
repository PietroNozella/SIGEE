from django.test import TestCase
from django.urls import reverse

from movimentacoes.tests import criar_cenario


class MeusDadosOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.cenario["operador"].email = "operador@example.com"
        cls.cenario["operador"].save()
        cls.cenario["professor"].email = "professor-privado@example.com"
        cls.cenario["professor"].save()

    def test_consulta_somente_propria_conta_sem_edicao(self):
        self.client.force_login(self.cenario["operador"])
        url = reverse("usuarios:meus_dados")
        resposta = self.client.get(url, {"usuario": str(self.cenario["professor"].pk)})
        self.assertContains(resposta, "operador@example.com")
        self.assertNotContains(resposta, "professor-privado@example.com")
        self.assertNotContains(resposta, self.cenario["operador"].password)
        self.assertEqual(self.client.post(url, {"email": "alterado@example.com"}).status_code, 405)
        self.cenario["operador"].refresh_from_db()
        self.assertEqual(self.cenario["operador"].email, "operador@example.com")
        for perfil in ("professor", "administrador"):
            self.client.force_login(self.cenario[perfil])
            self.assertEqual(self.client.get(url).status_code, 403)
