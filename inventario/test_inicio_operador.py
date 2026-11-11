from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.services import registrar_devolucoes
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva, ReservaEquipamento

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

    def test_sinaliza_reserva_afetada_ate_a_devolucao_de_todos_os_patrimonios(self):
        anterior = Reserva.objects.create(
            professor=self.reserva.professor, tipo_equipamento=self.reserva.tipo_equipamento,
            local=self.reserva.local, quantidade=2,
            turma=self.reserva.turma, disciplina=self.reserva.disciplina, atividade=self.reserva.atividade,
            inicio=self.reserva.inicio - timedelta(hours=2), fim=self.reserva.inicio - timedelta(hours=1),
        )
        ReservaEquipamento.objects.bulk_create(
            ReservaEquipamento(reserva=anterior, equipamento=unidade) for unidade in self.unidades
        )
        operador = self.cenario["operador"]
        with patch("django.utils.timezone.now", return_value=anterior.inicio):
            self.client.force_login(operador)
            retiradas = registrar_entrega_conferida(operador=operador, reserva_id=anterior.pk)
            self.assertEqual(self.client.get(self.url).context["total_pendencias"], 0)

        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            self.client.force_login(operador)
            resposta = self.client.get(self.url)
            self.assertEqual(list(resposta.context["pendencias"]), [self.reserva])
            self.assertEqual(resposta.context["total_pendencias"], 1)
            self.assertContains(resposta, "Há patrimônio reservado com devolução anterior vencida.")
            conferencia_url = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
            self.assertContains(resposta, conferencia_url)
            self.assertContains(self.client.get(conferencia_url), "Aguardando devolução anterior vencida", count=2)

            for retirada in retiradas:
                registrar_devolucoes(operador=operador, retirada_id=retirada.pk, retiradas_ids=[retirada.pk])
                esperado = 0 if retirada == retiradas[-1] else 1
                self.assertEqual(self.client.get(self.url).context["total_pendencias"], esperado)
                self.assertContains(self.client.get(conferencia_url), "Aguardando devolução anterior vencida", count=esperado)

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

    def test_categoria_abre_equipamentos_para_operador_e_filtra_painel_para_administrador(self):
        categoria_id = self.cenario["equipamento"].tipo.categoria_id
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, "inventario/_situacao_por_categoria.html")
        self.assertContains(
            resposta,
            f'class="category-link" href="{reverse("inventario:equipamento_lista")}?categoria={categoria_id}"',
        )
        self.assertContains(resposta, "Selecione uma categoria para consultar os equipamentos.")

        self.client.force_login(self.cenario["administrador"])
        resposta = self.client.get(reverse("inventario:painel"), {"periodo": "7"})
        self.assertTemplateUsed(resposta, "inventario/_situacao_por_categoria.html")
        self.assertContains(
            resposta,
            f'class="category-link" href="?categoria={categoria_id}&amp;periodo=7"',
        )
        self.assertContains(resposta, "Clique em uma categoria para filtrar")
        self.assertContains(resposta, "Sobre a disponibilidade")
