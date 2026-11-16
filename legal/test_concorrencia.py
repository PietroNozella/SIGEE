from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from usuarios.permissoes import GRUPO_ADMINISTRADOR, GRUPO_PROFESSOR

from . import services
from .models import AceiteDocumentosLegais, DocumentoLegal, VersaoDocumentoLegal
from .test_fixtures import criar_conta, garantir_documentos_legais


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaDocumentosLegaisTests(TransactionTestCase):
    def setUp(self):
        garantir_documentos_legais()
        self.principal = criar_conta("principal-concorrencia", GRUPO_ADMINISTRADOR, is_administrador_principal=True)
        self.professor = criar_conta("professor-concorrencia", GRUPO_PROFESSOR)
        rascunho = DocumentoLegal.objects.get(pk=services.TERMOS)
        services.salvar_rascunho(
            usuario=self.principal, tipo=services.TERMOS, revisao=rascunho.revisao_rascunho,
            conteudo="## Regras\n\nRegras atualizadas.", contato="privacidade@example.com",
            resumo="Mudaram as regras de uso.",
        )
        rascunho.refresh_from_db()
        self.revisao = rascunho.revisao_rascunho

    def publicar(self):
        try:
            return services.publicar_rascunho(usuario=self.principal, tipo=services.TERMOS, revisao=self.revisao).numero
        finally:
            connections.close_all()

    def test_duas_publicacoes_da_mesma_previa_criam_so_uma_versao(self):
        barreira = Barrier(2)

        def tentar_publicar():
            barreira.wait(timeout=10)
            try:
                return self.publicar()
            except services.RascunhoDesatualizado:
                return "desatualizada"

        with ThreadPoolExecutor(max_workers=2) as executor:
            respostas = [executor.submit(tentar_publicar) for _ in range(2)]
            self.assertCountEqual([resposta.result(timeout=25) for resposta in respostas], ["2.1", "desatualizada"])
        self.assertEqual(VersaoDocumentoLegal.objects.filter(documento_id=services.TERMOS).count(), 2)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.DOCUMENTO_LEGAL_PUBLICADO).count(), 1)

    def test_aceite_espera_publicacao_e_recusa_o_par_antigo(self):
        publicacao_em_andamento = Event()
        tentativa_de_aceite = Event()
        par_anterior = services.versoes_atuais()
        registrar_evento = services.registrar_evento
        bloquear_documentos = services._bloquear_documentos

        def registrar_apos_tentativa(**dados):
            if dados["acao"] == AcaoAuditoria.DOCUMENTO_LEGAL_PUBLICADO:
                publicacao_em_andamento.set()
                self.assertTrue(tentativa_de_aceite.wait(timeout=10))
            return registrar_evento(**dados)

        def bloquear_apos_sinal():
            if publicacao_em_andamento.is_set():
                tentativa_de_aceite.set()
            bloquear_documentos()

        def aceitar():
            try:
                return services.registrar_aceite_vigente(self.professor, versoes_enviadas=par_anterior)
            finally:
                connections.close_all()

        with (
            patch("legal.services.registrar_evento", side_effect=registrar_apos_tentativa),
            patch("legal.services._bloquear_documentos", side_effect=bloquear_apos_sinal),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            publicacao = executor.submit(self.publicar)
            self.assertTrue(publicacao_em_andamento.wait(timeout=10))
            aceite = executor.submit(aceitar)
            self.assertEqual(publicacao.result(timeout=25), "2.1")
            self.assertEqual(aceite.result(timeout=25), (None, False))

        self.assertFalse(AceiteDocumentosLegais.objects.filter(usuario=self.professor).exists())
        registro, criado = services.registrar_aceite_vigente(self.professor, versoes_enviadas=("2.1", "2.2"))
        self.assertTrue(criado)
        self.assertEqual(registro.versao_termos, "2.1")
