from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.services import criar_reserva

from .models import AlteracaoCalendario, CalendarioEscolar, FaixaHorario, RegraCalendario
from .services import salvar_regra


class ConcorrenciaCalendarioTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_edicoes_da_mesma_versao_nao_sobrescrevem_a_primeira(self):
        cenario = criar_cenario()
        CalendarioEscolar.objects.create(pk=1)
        barreira = Barrier(2)

        def editar(hora):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                try:
                    salvar_regra(usuario=cenario["administrador"],
                        regra=RegraCalendario(finalidade="USO", dia_semana=0),
                        faixas=[FaixaHorario(inicio=time(hora), fim=time(hora + 1))],
                        motivo="Ajuste de turno", versao=1)
                    return "salva"
                except ValidationError as erro:
                    self.assertIn("outro Administrador", str(erro))
                    return "desatualizada"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            a, b = executor.submit(editar, 7), executor.submit(editar, 9)
            self.assertCountEqual([a.result(timeout=30), b.result(timeout=30)], ["salva", "desatualizada"])
        self.assertEqual(RegraCalendario.objects.count(), 1)
        self.assertEqual(AlteracaoCalendario.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_agendamento_e_fechamento_usam_a_mesma_versao_bloqueada(self):
        cenario = criar_cenario()
        reserva, _ = criar_reserva_alocada(cenario, quantidade=1)
        CalendarioEscolar.objects.create(pk=1)
        barreira = Barrier(2)

        def executar(fechar):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                if fechar:
                    salvar_regra(usuario=cenario["administrador"],
                        regra=RegraCalendario(finalidade="USO", data=reserva.inicio.date()),
                        faixas=[], motivo="Fechamento excepcional", versao=1)
                    return "fechado"
                try:
                    nova = criar_reserva(professor=cenario["professor"], tipo_equipamento=reserva.tipo_equipamento,
                        local=reserva.local, quantidade=1, inicio=reserva.inicio, fim=reserva.fim,
                        turma=reserva.turma, disciplina=reserva.disciplina, atividade=reserva.atividade)
                    self.assertEqual(nova.calendario_confirmado["versao"], 1)
                    return "criada"
                except ValidationError as erro:
                    self.assertIn("fora do calendário", str(erro))
                    return "recusada"
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", return_value=reserva.inicio - timedelta(hours=1)):
            with ThreadPoolExecutor(max_workers=2) as executor:
                a, b = executor.submit(executar, False), executor.submit(executar, True)
                self.assertIn(a.result(timeout=30), ["criada", "recusada"])
                self.assertEqual(b.result(timeout=30), "fechado")
