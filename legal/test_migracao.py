from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from .models import AceiteDocumentosLegais, DocumentoLegal
from .services import usuario_possui_aceite_vigente


class MigracaoDocumentosLegaisTests(TransactionTestCase):
    @override_settings(CONTATO_PRIVACIDADE="contato-configurado@example.com")
    def test_migracao_preserva_aceites_e_inicializa_as_versoes_vigentes(self):
        anteriores = [("legal", "0001_initial")]
        atuais = [("legal", "0002_versionar_documentos")]
        executor = MigrationExecutor(connection)
        executor.migrate(anteriores)
        try:
            legado = executor.loader.project_state(anteriores + [("contas", "0003_administrador_principal")]).apps
            usuario = legado.get_model("contas", "User").objects.create(username="aceite-migrado")
            aceite = legado.get_model("legal", "AceiteDocumentosLegais")
            vigente = aceite.objects.create(usuario_id=usuario.pk, versao_termos="2.0", versao_privacidade="2.2")
            aceite.objects.create(usuario_id=usuario.pk, versao_termos="1.0", versao_privacidade="1.0")
            antes = list(aceite.objects.values())
        finally:
            MigrationExecutor(connection).migrate(atuais)

        self.assertEqual(list(AceiteDocumentosLegais.objects.values()), antes)
        self.assertTrue(usuario_possui_aceite_vigente(AceiteDocumentosLegais.objects.get(pk=vigente.pk).usuario))
        termos = DocumentoLegal.objects.get(pk="termos").versao_vigente
        privacidade = DocumentoLegal.objects.get(pk="privacidade").versao_vigente
        self.assertEqual((termos.numero, termos.vigente_desde), ("2.0", date(2026, 9, 21)))
        self.assertEqual((privacidade.numero, privacidade.vigente_desde), ("2.2", date(2026, 11, 10)))
        self.assertEqual(termos.contato, "contato-configurado@example.com")
        self.assertEqual(privacidade.contato, termos.contato)
        self.assertIsNone(privacidade.publicado_em)
        self.assertIsNone(privacidade.publicado_por_id)
        self.assertEqual(privacidade.conteudo[0]["titulo"], "Responsabilidades no tratamento")
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT relrowsecurity FROM pg_class
                    WHERE oid IN ('legal_documentolegal'::regclass, 'legal_versaodocumentolegal'::regclass)
                """)
                self.assertEqual(cursor.fetchall(), [(True,), (True,)])
