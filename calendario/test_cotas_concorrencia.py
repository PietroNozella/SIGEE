from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from inventario.models import Equipamento, Local, TipoEquipamento
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva
from reservas.services import criar_reserva

from .models import CalendarioEscolar
from .services import salvar_cota


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaCotasTests(TransactionTestCase):
    def setUp(self):
        self.cenario = criar_cenario()
        self.base, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        self.base.status = Reserva.Status.CANCELADA
        self.base.save(update_fields=["status"])
        self.outro_local = Local.objects.create(nome="Outro local da concorrência")
        for indice in range(4):
            for local in [self.base.local, self.outro_local]:
                Equipamento.objects.create(numero_patrimonio=f"COTA-CONC-{local.pk}-{indice}", tipo=self.base.tipo_equipamento, local=local)
        CalendarioEscolar.objects.create(pk=1)

    def reservar(self, local):
        return criar_reserva(professor=self.cenario["professor"], tipo_equipamento=self.base.tipo_equipamento,
            local=local, quantidade=2, inicio=self.base.inicio, fim=self.base.fim,
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

        with patch("django.utils.timezone.now", return_value=self.base.inicio - timedelta(hours=1)):
            with ThreadPoolExecutor(max_workers=2) as executor:
                tarefas = [executor.submit(executar, i) for i in range(2)]
                return [t.result(timeout=30) for t in tarefas]

    def test_pedidos_divididos_entre_locais_nao_ultrapassam_cota(self):
        TipoEquipamento.objects.filter(pk=self.base.tipo_equipamento_id).update(cota_por_professor=3)

        def reservar(indice):
            try:
                self.reservar(self.base.local if indice == 0 else self.outro_local)
                return "criada"
            except ValidationError as erro:
                self.assertIn("cota", str(erro))
                return "recusada"

        self.assertCountEqual(self.disputar(reservar), ["criada", "recusada"])
        self.assertEqual(sum(Reserva.objects.filter(status="ATIVA").values_list("quantidade", flat=True)), 2)

    def test_configuracao_e_reserva_usam_politica_efetiva_sem_aplicacao_retroativa(self):
        def executar(indice):
            if indice:
                salvar_cota(usuario=self.cenario["administrador"], tipo_id=self.base.tipo_equipamento_id,
                    limite=1, motivo="Distribuir equipamentos", versao=1)
                return "configurada"
            try:
                self.reservar(self.base.local)
                return "criada"
            except ValidationError as erro:
                self.assertIn("cota", str(erro))
                return "recusada"

        resultado, _ = self.disputar(executar)
        self.assertIn(resultado, ["criada", "recusada"])
        reservas = Reserva.objects.filter(status="ATIVA")
        if resultado == "criada":
            self.assertIsNone(reservas.get().cota_confirmada)
            self.assertEqual(reservas.get().calendario_confirmado["versao"], 1)
        else:
            self.assertFalse(reservas.exists())
        self.assertEqual(TipoEquipamento.objects.get(pk=self.base.tipo_equipamento_id).cota_por_professor, 1)
