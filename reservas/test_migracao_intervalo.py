from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class MigracaoIntervaloTests(TransactionTestCase):
    def test_reservas_existentes_recebem_margem_zero_sem_mudar_seus_compromissos(self):
        executor = MigrationExecutor(connection)
        finais = executor.loader.graph.leaf_nodes()
        anteriores = [alvo for alvo in finais if alvo[0] not in ("reservas", "calendario")] + [
            ("reservas", "0009_reserva_calendario_confirmado"), ("calendario", "0001_initial"),
        ]
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state(anteriores).apps
            usuario = apps.get_model("contas", "User").objects.create(username="professor-legado-intervalo")
            categoria = apps.get_model("inventario", "Categoria").objects.create(nome="Migração intervalo")
            tipo = apps.get_model("inventario", "TipoEquipamento").objects.create(nome="Tipo legado", categoria=categoria)
            local = apps.get_model("inventario", "Local").objects.create(nome="Local legado")
            inicio = timezone.now() + timedelta(days=1)
            registro = apps.get_model("reservas", "Reserva").objects.create(professor=usuario,
                tipo_equipamento=tipo, local=local, inicio=inicio, fim=inicio + timedelta(hours=1),
                calendario_confirmado={"versao": 3, "uso": [], "atendimento": []})
            apps.get_model("calendario", "CalendarioEscolar").objects.create(pk=1, versao=3)
            executor = MigrationExecutor(connection)
            executor.migrate(finais)
            apps = executor.loader.project_state(finais).apps
            atual = apps.get_model("reservas", "Reserva").objects.get(pk=registro.pk)
            self.assertEqual(atual.intervalo_apos_uso, timedelta())
            self.assertEqual(atual.inicio, registro.inicio)
            self.assertEqual(atual.fim, registro.fim)
            self.assertEqual(atual.calendario_confirmado, registro.calendario_confirmado)
            calendario = apps.get_model("calendario", "CalendarioEscolar").objects.get()
            self.assertEqual(calendario.versao, 3)
            self.assertEqual(calendario.intervalo_minutos, 5)
        finally:
            MigrationExecutor(connection).migrate(finais)
