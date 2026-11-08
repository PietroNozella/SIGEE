from django.test import TestCase
from django.urls import reverse

from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario

from .models import Categoria, Equipamento, TipoEquipamento


class InicioOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario, quantidade=2)

    def setUp(self):
        self.url = reverse("inventario:inicio_operador")
        self.client.force_login(self.cenario["operador"])

    def test_acesso_exclusivo_e_post_recusado(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url).status_code, 405)
        for perfil in ("professor", "administrador"):
            self.client.force_login(self.cenario[perfil])
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), reverse("login") + "?next=" + self.url)

    def test_grafico_por_categoria_compartilha_criterios_e_escala_do_administrador(self):
        base = self.cenario["equipamento"]
        Equipamento.objects.filter(pk=self.unidades[0].pk).update(situacao="EM_USO")
        Equipamento.objects.filter(pk=self.unidades[1].pk).update(situacao="MANUTENCAO")
        Equipamento.objects.create(numero_patrimonio="INATIVO-GRAFICO", tipo=base.tipo, local=base.local, ativo=False)
        outra_categoria = Categoria.objects.create(nome="Outra categoria")
        outro_tipo = TipoEquipamento.objects.create(categoria=outra_categoria, nome="Outro modelo")
        for indice in range(2):
            Equipamento.objects.create(numero_patrimonio=f"OUTRO-GRAFICO-{indice}", tipo=outro_tipo, local=base.local)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["estoque"], {
            "ativos": 5, "inativos": 1, "disponiveis": 3, "em_uso": 1, "manutencao": 1,
        })
        categorias = {item["id"]: item for item in resposta.context["situacao_por_categoria"]}
        original = categorias[base.tipo.categoria_id]
        self.assertEqual((original["total"], original["disponiveis"], original["em_uso"], original["manutencao"]), (3, 1, 1, 1))
        self.assertEqual(resposta.context["maior_categoria"], 3)
        self.assertAlmostEqual(categorias[outra_categoria.pk]["segmentos"][0]["percentual"], 200 / 3)
        self.client.force_login(self.cenario["administrador"])
        painel = self.client.get(reverse("inventario:painel"))
        self.assertEqual(resposta.context["situacao_por_categoria"], painel.context["situacao_por_categoria"])
