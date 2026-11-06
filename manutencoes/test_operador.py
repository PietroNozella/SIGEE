from datetime import timedelta
from unittest.mock import patch
from io import StringIO
import json

from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from inventario.models import Equipamento, Local
from movimentacoes.tests import criar_cenario
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from reservas.models import Reserva, ReservaEquipamento, SubstituicaoReserva
from reservas.services import substituir_equipamentos_em_manutencao

from .models import Manutencao
from .services import abrir_manutencao, iniciar_manutencao, concluir_manutencao


class ManutencaoOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario, quantidade=2)

    def setUp(self):
        self.operador = self.cenario["operador"]
        self.client.force_login(self.operador)

    def abrir(self):
        return abrir_manutencao(administrador=self.operador, equipamento_id=self.unidades[0].pk, descricao_problema="Não liga")

    def test_operador_abre_consulta_mas_nao_inicia_nem_conclui(self):
        resposta = self.client.post(reverse("manutencoes:manutencao_abrir"), {
            "equipamento": self.unidades[0].pk, "descricao_problema": "Não liga",
        })
        manutencao = Manutencao.objects.get()
        self.assertRedirects(resposta, reverse("manutencoes:manutencao_detalhe", args=[manutencao.pk]))
        self.assertEqual(manutencao.aberto_por, self.operador)
        self.assertEqual(self.client.get(reverse("manutencoes:manutencao_lista")).status_code, 200)
        self.assertEqual(self.client.post(reverse("manutencoes:manutencao_iniciar", args=[manutencao.pk])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            iniciar_manutencao(administrador=self.operador, manutencao_id=manutencao.pk)
        with self.assertRaises(PermissionDenied):
            concluir_manutencao(administrador=self.operador, manutencao_id=manutencao.pk, resultado="REPARADO", descricao_solucao="Reparado")

    def test_abertura_substitui_reservas_futuras_e_preserva_historico(self):
        manutencao = self.abrir()
        troca = SubstituicaoReserva.objects.get()
        self.assertEqual(troca.equipamento_anterior, self.unidades[0])
        self.assertEqual(troca.equipamento_substituto, self.cenario["equipamento"])
        self.assertEqual(troca.manutencao, manutencao)
        self.assertEqual(troca.registrado_por, self.operador)
        self.assertEqual(self.reserva.itens.count(), 2)
        self.assertFalse(self.reserva.itens.filter(equipamento=self.unidades[0]).exists())

    def test_sem_substituto_preserva_reserva_e_demais_unidades(self):
        self.cenario["equipamento"].delete()
        self.abrir()
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.ATIVA)
        self.assertEqual(self.reserva.quantidade, 2)
        self.assertEqual(self.reserva.itens.count(), 2)
        self.assertFalse(SubstituicaoReserva.objects.exists())

    def test_substituto_respeita_conflito_ativacao_local_e_periodo(self):
        livre = self.cenario["equipamento"]
        outra = Reserva.objects.create(professor=self.reserva.professor, tipo_equipamento=livre.tipo, local=livre.local,
            quantidade=1, inicio=self.reserva.inicio + timedelta(minutes=30), fim=self.reserva.fim)
        ReservaEquipamento.objects.create(reserva=outra, equipamento=livre)
        Equipamento.objects.create(numero_patrimonio="INATIVO", tipo=livre.tipo, local=livre.local, ativo=False)
        Equipamento.objects.create(numero_patrimonio="OUTRO-LOCAL", tipo=livre.tipo, local=Local.objects.create(nome="Outro local"))
        self.abrir()
        self.assertFalse(SubstituicaoReserva.objects.exists())

    def test_reconsulta_da_entrega_tenta_novamente_sem_duplicar_troca(self):
        livre = self.cenario["equipamento"]
        livre.ativo = False
        livre.save()
        self.abrir()
        livre.ativo = True
        livre.save()
        url = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(SubstituicaoReserva.objects.get().equipamento_substituto_id, livre.pk)
        self.client.get(url)
        self.assertEqual(SubstituicaoReserva.objects.count(), 1)

    def test_falha_na_troca_reverte_manutencao_e_alocacao(self):
        with patch("reservas.services.registrar_evento", side_effect=RuntimeError("Falha")):
            with self.assertRaises(RuntimeError):
                self.abrir()
        self.assertFalse(Manutencao.objects.exists())
        self.assertFalse(SubstituicaoReserva.objects.exists())
        self.unidades[0].refresh_from_db()
        self.assertEqual(self.unidades[0].situacao, "DISPONIVEL")

    def test_professor_nao_pode_disparar_substituicao(self):
        with self.assertRaises(PermissionDenied):
            substituir_equipamentos_em_manutencao(reserva_id=self.reserva.pk, usuario=self.cenario["professor"])

    def test_substituicoes_nao_reescrevem_entregas_existentes(self):
        from movimentacoes.services import registrar_devolucoes, registrar_retirada_reserva
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio):
            entregas = registrar_retirada_reserva(operador=self.operador, reserva_id=self.reserva.pk)
            original = next(m for m in entregas if m.equipamento_id == self.unidades[0].pk)
            registrar_devolucoes(operador=self.operador, retirada_id=original.pk, retiradas_ids=[original.pk], problemas={original.pk: "Não liga"})
        self.assertFalse(SubstituicaoReserva.objects.exists())
        self.assertTrue(self.reserva.itens.filter(equipamento=self.unidades[0]).exists())

    def test_substituto_pode_atender_periodos_adjacentes_sem_conflito(self):
        proxima = Reserva.objects.create(professor=self.reserva.professor, tipo_equipamento=self.reserva.tipo_equipamento,
            local=self.reserva.local, inicio=self.reserva.fim, fim=self.reserva.fim + timedelta(hours=1), quantidade=1)
        ReservaEquipamento.objects.create(reserva=proxima, equipamento=self.unidades[0])
        self.abrir()
        self.assertEqual(SubstituicaoReserva.objects.count(), 2)
        self.assertEqual(set(SubstituicaoReserva.objects.values_list("equipamento_substituto_id", flat=True)), {self.cenario["equipamento"].pk})

    def test_servico_rejeita_conta_desativada_mesmo_com_objeto_anterior(self):
        type(self.operador).objects.filter(pk=self.operador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            substituir_equipamentos_em_manutencao(reserva_id=self.reserva.pk, usuario=self.operador)

    def test_exportacao_inclui_trocas_do_operador_e_do_professor(self):
        self.abrir()
        for usuario in (self.operador, self.cenario["professor"]):
            saida = StringIO()
            call_command("exportar_dados_usuario", usuario.username, stdout=saida)
            dados = json.loads(saida.getvalue())
            self.assertEqual(len(dados["substituicoes_de_reserva"]), 1)
            self.assertEqual(dados["substituicoes_de_reserva"][0]["patrimonio_anterior"], self.unidades[0].numero_patrimonio)
