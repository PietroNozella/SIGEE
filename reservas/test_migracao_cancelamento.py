from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class MigracaoCancelamentoTests(TransactionTestCase):
    def test_preserva_reservas_existentes_e_acrescenta_somente_a_permissao_necessaria(self):
        executor = MigrationExecutor(connection)
        finais = executor.loader.graph.leaf_nodes()
        anteriores = [alvo for alvo in finais if alvo[0] not in ("reservas", "usuarios")] + [
            ("reservas", "0007_substituicao_por_manutencao"), ("usuarios", "0004_manutencao_operador"),
        ]
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state(anteriores).apps
            User = apps.get_model("contas", "User")
            Group = apps.get_model("auth", "Group")
            Permission = apps.get_model("auth", "Permission")
            ContentType = apps.get_model("contenttypes", "ContentType")
            Reserva = apps.get_model("reservas", "Reserva")
            Categoria = apps.get_model("inventario", "Categoria")
            TipoEquipamento = apps.get_model("inventario", "TipoEquipamento")
            Local = apps.get_model("inventario", "Local")
            professor = User.objects.create(username="professor-legado-cancelamento")
            categoria = Categoria.objects.create(nome="Categoria migração cancelamento")
            tipo = TipoEquipamento.objects.create(nome="Tipo legado", categoria=categoria)
            local = Local.objects.create(nome="Local migração cancelamento")
            inicio = timezone.now() - timedelta(days=30)
            registros = [Reserva.objects.create(
                professor=professor, tipo_equipamento=tipo, local=local,
                inicio=inicio, fim=inicio + timedelta(hours=1), status=status,
            ) for status in ("ATIVA", "CANCELADA")]
            grupo, _ = Group.objects.get_or_create(name="Operador")
            content_type, _ = ContentType.objects.get_or_create(app_label="inventario", model="equipamento")
            permissao, _ = Permission.objects.get_or_create(
                content_type_id=content_type.pk, codename="view_equipamento", defaults={"name": "View equipamento"},
            )
            grupo.permissions.add(permissao)
            anteriores_ids = set(grupo.permissions.values_list("pk", flat=True))

            executor = MigrationExecutor(connection)
            executor.migrate(finais)
            apps = executor.loader.project_state(finais).apps
            ReservaAtual = apps.get_model("reservas", "Reserva")
            GrupoAtual = apps.get_model("auth", "Group")
            for original in registros:
                atual = ReservaAtual.objects.get(pk=original.pk)
                self.assertEqual(atual.status, original.status)
                self.assertEqual(atual.professor_id, original.professor_id)
                self.assertEqual(atual.inicio, original.inicio)
                self.assertEqual(atual.motivo_cancelamento, "")
                self.assertIsNone(atual.cancelada_por_id)
                self.assertIsNone(atual.data_cancelamento)
            grupo = GrupoAtual.objects.get(pk=grupo.pk)
            self.assertTrue(anteriores_ids.issubset(set(grupo.permissions.values_list("pk", flat=True))))
            self.assertTrue(grupo.permissions.filter(codename="cancelar_reserva_operacional").exists())
        finally:
            MigrationExecutor(connection).migrate(finais)
