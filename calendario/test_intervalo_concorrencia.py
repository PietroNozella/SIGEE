from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from inventario.models import Equipamento
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva
from reservas.services import criar_reserva

from .models import CalendarioEscolar
from .services import salvar_intervalo


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaIntervaloTests(TransactionTestCase):
    def setUp(self):
        self.cenario = criar_cenario()
        self.base, unidades = criar_reserva_alocada(self.cenario, quantidade=1)
        Equipamento.objects.exclude(pk=unidades[0].pk).update(ativo=False)
        self.base.status = Reserva.Status.CANCELADA
        self.base.save(update_fields=["status"])
        CalendarioEscolar.objects.create(pk=1)

    def reservar(self, inicio):
        return criar_reserva(professor=self.cenario["professor"], tipo_equipamento=self.base.tipo_equipamento,
            local=self.base.local, quantidade=1, inicio=inicio, fim=inicio + timedelta(hours=1),
            turma=self.base.turma, disciplina=self.base.disciplina, atividade=self.base.atividade)

    def disputar(self, operacao):
        barreira = Barrier(2)

        def executar(indice):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                return operacao(indice)
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", return_value=self.base.inicio - timedelta(hours=2)):
            with ThreadPoolExecutor(max_workers=2) as executor:
                tarefas = [executor.submit(executar, i) for i in range(2)]
                return [t.result(timeout=30) for t in tarefas]

    def test_reservas_sem_sobreposicao_mas_com_margem_em_disputa_nao_duplicam_unidade(self):
        def reservar(indice):
            try:
                self.reservar(self.base.inicio + timedelta(minutes=64 * indice))
                return "criada"
            except ValidationError as erro:
                self.assertIn("quantidade", erro.message_dict)
                return "indisponivel"

        self.assertCountEqual(self.disputar(reservar), ["criada", "indisponivel"])
        self.assertEqual(Reserva.objects.filter(status=Reserva.Status.ATIVA).count(), 1)

    def test_configuracao_e_agendamento_preservam_valor_efetivo_da_transacao(self):
        def executar(indice):
            if indice:
                salvar_intervalo(usuario=self.cenario["administrador"], minutos=20, motivo="Novo tempo de preparação", versao=1)
                return None
            return self.reservar(self.base.inicio).pk

        pk, _ = self.disputar(executar)
        reserva = Reserva.objects.get(pk=pk)
        self.assertIn(reserva.intervalo_apos_uso, [timedelta(minutes=5), timedelta(minutes=20)])
        self.assertEqual(reserva.intervalo_minutos, 5 if reserva.calendario_confirmado["versao"] == 1 else 20)
        self.assertEqual(CalendarioEscolar.objects.get().intervalo_minutos, 20)
