from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import EquipamentoForm
from .models import Categoria, Equipamento, Local


class EquipamentoRN01Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.local = Local.objects.get(nome="Laboratório de informática")

    def dados_equipamento(self, numero_patrimonio):
        return {
            "numero_patrimonio": numero_patrimonio,
            "nome": "Notebook Dell",
            "descricao": "Equipamento para uso pedagógico.",
            "categoria": self.categoria.pk,
            "local": self.local.pk,
            "situacao": Equipamento.Situacao.DISPONIVEL,
        }

    def test_patrimonio_novo_e_validado_e_salvo(self):
        formulario = EquipamentoForm(data=self.dados_equipamento("PAT-001"))

        self.assertTrue(formulario.is_valid(), formulario.errors)
        equipamento = formulario.save()

        self.assertEqual(equipamento.numero_patrimonio, "PAT-001")
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_formulario_rejeita_patrimonio_duplicado(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-001",
            nome="Notebook existente",
            categoria=self.categoria,
            local=self.local,
        )
        formulario = EquipamentoForm(data=self.dados_equipamento("PAT-001"))

        self.assertFalse(formulario.is_valid())
        self.assertTrue(formulario.has_error("numero_patrimonio", code="unique"))
        self.assertIn(
            Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO,
            formulario.errors["numero_patrimonio"],
        )
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_modelo_rejeita_patrimonio_duplicado_antes_de_salvar(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-001",
            nome="Notebook existente",
            categoria=self.categoria,
            local=self.local,
        )
        duplicado = Equipamento(
            numero_patrimonio="PAT-001",
            nome="Outro notebook",
            categoria=self.categoria,
            local=self.local,
        )

        with self.assertRaisesMessage(
            ValidationError,
            Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO,
        ):
            duplicado.full_clean()

        self.assertEqual(Equipamento.objects.count(), 1)

    def test_banco_impede_patrimonio_duplicado(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-001",
            nome="Notebook existente",
            categoria=self.categoria,
            local=self.local,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Equipamento.objects.create(
                    numero_patrimonio="PAT-001",
                    nome="Outro notebook",
                    categoria=self.categoria,
                    local=self.local,
                )

        self.assertEqual(Equipamento.objects.count(), 1)

    def test_listagem_exibe_estado_vazio_e_acao_de_cadastro(self):
        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Nenhum equipamento cadastrado")
        self.assertContains(resposta, reverse("inventario:equipamento_novo"))

    def test_listagem_exibe_indicadores_calculados_com_dados_reais(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-001",
            nome="Notebook disponível",
            categoria=self.categoria,
            local=self.local,
            situacao=Equipamento.Situacao.DISPONIVEL,
        )
        Equipamento.objects.create(
            numero_patrimonio="PAT-002",
            nome="Notebook em uso",
            categoria=self.categoria,
            local=self.local,
            situacao=Equipamento.Situacao.EM_USO,
        )
        Equipamento.objects.create(
            numero_patrimonio="PAT-003",
            nome="Notebook em manutenção",
            categoria=self.categoria,
            local=self.local,
            situacao=Equipamento.Situacao.MANUTENCAO,
        )

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(
            resposta.context["indicadores"],
            {"total": 3, "disponiveis": 1, "em_uso": 1, "manutencao": 1},
        )
        self.assertContains(resposta, "Em uso")
        self.assertNotContains(resposta, "Reservados")

    def test_listagem_filtra_por_texto_categoria_local_e_situacao(self):
        outra_categoria = Categoria.objects.get(nome="Projetor")
        outro_local = Local.objects.get(nome="Sala multimídia")
        Equipamento.objects.create(
            numero_patrimonio="PAT-001",
            nome="Notebook Dell",
            categoria=self.categoria,
            local=self.local,
            situacao=Equipamento.Situacao.DISPONIVEL,
        )
        Equipamento.objects.create(
            numero_patrimonio="PAT-002",
            nome="Projetor Epson",
            categoria=outra_categoria,
            local=outro_local,
            situacao=Equipamento.Situacao.MANUTENCAO,
        )

        resposta = self.client.get(
            reverse("inventario:equipamento_lista"),
            {
                "busca": "Epson",
                "categoria": outra_categoria.pk,
                "local": outro_local.pk,
                "situacao": Equipamento.Situacao.MANUTENCAO,
            },
        )

        self.assertContains(resposta, "PAT-002")
        self.assertNotContains(resposta, "PAT-001")

    def test_tela_de_cadastro_exibe_campos_do_equipamento_form(self):
        resposta = self.client.get(reverse("inventario:equipamento_novo"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Número de patrimônio")
        self.assertContains(resposta, "Nome do equipamento")
        self.assertContains(resposta, "Categoria")
        self.assertContains(resposta, "Local")
        self.assertContains(resposta, "Situação")
        self.assertContains(resposta, "Notebook")
        self.assertContains(resposta, "Sala-01")
        self.assertContains(resposta, "csrfmiddlewaretoken")

    def test_post_cadastra_patrimonio_novo_e_confirma_sucesso(self):
        resposta = self.client.post(
            reverse("inventario:equipamento_novo"),
            self.dados_equipamento("PAT-001"),
            follow=True,
        )

        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertContains(resposta, "Equipamento cadastrado com sucesso.")
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_post_duplicado_exibe_mensagem_e_nao_cria_registro(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-001",
            nome="Notebook existente",
            categoria=self.categoria,
            local=self.local,
        )

        resposta = self.client.post(
            reverse("inventario:equipamento_novo"),
            self.dados_equipamento("PAT-001"),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO,
        )
        self.assertContains(resposta, 'aria-invalid="true"')
        self.assertEqual(Equipamento.objects.count(), 1)
