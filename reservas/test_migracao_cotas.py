from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class MigracaoCotasTests(TransactionTestCase):
    def test_tipos_e_reservas_existentes_permanecem_sem_cota_inferida(self):
        executor = MigrationExecutor(connection)
        finais = executor.loader.graph.leaf_nodes()
        anteriores = [alvo for alvo in finais if alvo[0] not in ("calendario", "reservas", "inventario")] + [
            ("calendario", "0002_calendarioescolar_intervalo_minutos_and_more"),
            ("reservas", "0010_reserva_intervalo_apos_uso_and_more"), ("inventario", "0005_tipo_equipamento"),
        ]
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state(anteriores).apps
            professor = apps.get_model("contas", "User").objects.create(username="professor-legado-cotas")
            categoria = apps.get_model("inventario", "Categoria").objects.create(nome="Migração cotas")
            tipo = apps.get_model("inventario", "TipoEquipamento").objects.create(nome="Tipo sem limite", categoria=categoria)
            local = apps.get_model("inventario", "Local").objects.create(nome="Local migração cotas")
            inicio = timezone.now() + timedelta(days=1)
            reserva = apps.get_model("reservas", "Reserva").objects.create(professor=professor, tipo_equipamento=tipo,
                local=local, quantidade=20, inicio=inicio, fim=inicio + timedelta(hours=1), intervalo_apos_uso=timedelta(minutes=10))
            executor = MigrationExecutor(connection)
            executor.migrate(finais)
            apps = executor.loader.project_state(finais).apps
            self.assertIsNone(apps.get_model("inventario", "TipoEquipamento").objects.get(pk=tipo.pk).cota_por_professor)
            atual = apps.get_model("reservas", "Reserva").objects.get(pk=reserva.pk)
            self.assertIsNone(atual.cota_confirmada)
            self.assertEqual(atual.quantidade, 20)
            self.assertEqual(atual.inicio, reserva.inicio)
            self.assertEqual(atual.fim, reserva.fim)
            self.assertEqual(atual.intervalo_apos_uso, timedelta(minutes=10))
            self.assertEqual(atual.status, "ATIVA")
        finally:
            MigrationExecutor(connection).migrate(finais)
