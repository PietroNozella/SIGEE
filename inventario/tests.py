from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase

from movimentacoes.models import Movimentacao

from .models import Categoria, Equipamento, Local


class ExclusaoEquipamentoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nome="Notebook")
        cls.local = Local.objects.create(nome="Sala de tecnologia")
        cls.operador = get_user_model().objects.create_user(
            username="operador",
            password="senha-segura-123",
        )
        cls.destinatario = get_user_model().objects.create_user(
            username="professor",
            password="senha-segura-123",
        )

    def criar_equipamento(self, numero_patrimonio):
        return Equipamento.objects.create(
            numero_patrimonio=numero_patrimonio,
            nome="Notebook educacional",
            categoria=self.categoria,
            local=self.local,
        )

    def test_exclui_definitivamente_equipamento_sem_historico(self):
        equipamento = self.criar_equipamento("PAT-001")

        equipamento.delete()

        self.assertFalse(Equipamento.objects.filter(pk=equipamento.pk).exists())

    def test_inativa_equipamento_com_movimentacao(self):
        equipamento = self.criar_equipamento("PAT-002")
        equipamento.situacao = Equipamento.Situacao.EM_USO
        equipamento.save(update_fields=["situacao", "data_atualizacao"])
        movimentacao = Movimentacao.objects.create(
            equipamento=equipamento,
            operador=self.operador,
            destinatario=self.destinatario,
            tipo="RETIRADA",
        )

        equipamento.delete()

        equipamento.refresh_from_db()
        self.assertFalse(equipamento.ativo)
        self.assertEqual(equipamento.situacao, Equipamento.Situacao.EM_USO)
        self.assertEqual(movimentacao.equipamento_id, equipamento.pk)
        self.assertTrue(Movimentacao.objects.filter(pk=movimentacao.pk).exists())

    def test_segunda_exclusao_de_equipamento_inativo_preserva_historico(self):
        equipamento = self.criar_equipamento("PAT-003")
        movimentacao = Movimentacao.objects.create(
            equipamento=equipamento,
            operador=self.operador,
            destinatario=self.destinatario,
            tipo="RETIRADA",
        )
        equipamento.delete()

        equipamento.delete()

        equipamento.refresh_from_db()
        self.assertFalse(equipamento.ativo)
        self.assertEqual(equipamento.movimentacoes.count(), 1)
        self.assertTrue(Movimentacao.objects.filter(pk=movimentacao.pk).exists())

    def test_exclusao_em_lote_do_admin_aplica_a_regra(self):
        sem_historico = self.criar_equipamento("PAT-004")
        com_historico = self.criar_equipamento("PAT-005")
        Movimentacao.objects.create(
            equipamento=com_historico,
            operador=self.operador,
            destinatario=self.destinatario,
            tipo="RETIRADA",
        )
        equipamento_admin = admin.site._registry[Equipamento]

        equipamento_admin.delete_queryset(
            request=None,
            queryset=Equipamento.objects.filter(
                pk__in=[sem_historico.pk, com_historico.pk]
            ),
        )

        self.assertFalse(Equipamento.objects.filter(pk=sem_historico.pk).exists())
        com_historico.refresh_from_db()
        self.assertFalse(com_historico.ativo)
        self.assertEqual(com_historico.movimentacoes.count(), 1)
