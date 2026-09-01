from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .forms import EquipamentoForm
from .models import Categoria, Equipamento, Local


class EquipamentoRN01Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nome="Notebook")
        cls.local = Local.objects.create(nome="Laboratório de informática")

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
