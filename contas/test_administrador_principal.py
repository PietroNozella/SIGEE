from django.contrib.auth.models import Group
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from auditoria.models import RegistroAuditoria


class MigracaoAdministradorPrincipalTests(TransactionTestCase):
    def test_migracao_e_reversao_preservam_contas_grupos_auditoria_e_email_unico(self):
        anterior = [("contas", "0002_usuario_uuid")]
        atual = [("contas", "0003_administrador_principal")]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(anterior)
            UserAnterior = executor.loader.project_state(anterior).apps.get_model("contas", "User")
            grupo, _ = Group.objects.get_or_create(name="Administrador")
            usuario = UserAnterior.objects.create(
                username="admin-existente", email="Reserva@Example.com", password="hash-preservado",
            )
            usuario.groups.add(grupo.pk)
            evento = RegistroAuditoria.objects.create(
                usuario_id=usuario.pk, acao="EVENTO_ANTERIOR", resultado="SUCESSO",
            )

            executor = MigrationExecutor(connection)
            executor.migrate(atual)
            UserAtual = executor.loader.project_state(atual).apps.get_model("contas", "User")
            migrado = UserAtual.objects.get(pk=usuario.pk)
            self.assertFalse(migrado.is_administrador_principal)
            self.assertTrue(migrado.is_active)
            self.assertEqual(migrado.password, "hash-preservado")
            self.assertEqual(list(migrado.groups.values_list("name", flat=True)), ["Administrador"])
            # A versão anterior não envia a coluna nova ao cadastrar usuários.
            legado = UserAnterior.objects.create(username="cadastro-versao-anterior")
            self.assertFalse(UserAtual.objects.get(pk=legado.pk).is_administrador_principal)
            with self.assertRaises(IntegrityError), transaction.atomic():
                UserAtual.objects.create(username="duplicado", email="reserva@example.com")

            executor = MigrationExecutor(connection)
            executor.migrate(anterior)
            revertido = UserAnterior.objects.get(pk=usuario.pk)
            self.assertEqual(revertido.email, "Reserva@Example.com")
            self.assertEqual(revertido.password, "hash-preservado")
            self.assertEqual(list(revertido.groups.values_list("name", flat=True)), ["Administrador"])
            self.assertEqual(RegistroAuditoria.objects.get(pk=evento.pk).usuario_id, usuario.pk)
            with self.assertRaises(IntegrityError), transaction.atomic():
                UserAnterior.objects.create(username="duplicado", email="RESERVA@example.com")
        finally:
            MigrationExecutor(connection).migrate(atual)
