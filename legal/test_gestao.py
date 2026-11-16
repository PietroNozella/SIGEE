from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from usuarios.permissoes import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR, GRUPO_PROFESSOR

from .models import AceiteDocumentosLegais, DocumentoLegal, VersaoDocumentoLegal
from .services import publicar_rascunho, registrar_aceite_vigente, salvar_rascunho
from .test_fixtures import criar_conta


class GestaoDocumentosLegaisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.principal = criar_conta("principal-legal", GRUPO_ADMINISTRADOR, is_administrador_principal=True)
        cls.administrador = criar_conta("admin-comum-legal", GRUPO_ADMINISTRADOR)
        cls.operador = criar_conta("operador-legal", GRUPO_OPERADOR)
        cls.professor = criar_conta("professor-legal", GRUPO_PROFESSOR)
        cls.tecnico = criar_conta("tecnico-legal", is_staff=True, is_superuser=True)

    def setUp(self):
        self.tipo = DocumentoLegal.Tipo.PRIVACIDADE
        self.edicao = reverse("legal:editar_documento", args=[self.tipo])
        self.previa = reverse("legal:previa_documento", args=[self.tipo])
        self.politica = reverse("legal:politica_privacidade")
        self.aceite = reverse("legal:aceite_documentos")
        self.client.force_login(self.principal)

    def dados_rascunho(self, **dados):
        return {
            "revisao": DocumentoLegal.objects.get(pk=self.tipo).revisao_rascunho,
            "conteudo": "## Finalidade\n\nTexto revisado e validado. Contato: [[contato]]\n\n- Um item\n- Outro item",
            "contato": "privacidade@example.com",
            "resumo": "Atualizamos a descrição da finalidade.",
            **dados,
        }

    def publicar(self, **dados):
        self.assertRedirects(self.client.post(self.edicao, self.dados_rascunho(**dados)), self.previa)
        revisao = self.client.get(self.previa).context["form"]["revisao"].value()
        self.assertRedirects(self.client.post(self.previa, {"revisao": revisao}), self.edicao)
        return DocumentoLegal.objects.select_related("versao_vigente").get(pk=self.tipo).versao_vigente

    def test_edicao_publicacao_e_confirmacao_por_professor(self):
        aceite_anterior, _ = registrar_aceite_vigente(self.professor)
        visitante = Client()
        antes = visitante.get(self.politica)
        contato_anterior = antes.context["contato_privacidade"]
        self.assertContains(antes, "Versão 2.2")

        self.assertRedirects(self.client.post(self.edicao, self.dados_rascunho()), self.previa)
        previa = self.client.get(self.previa)
        self.assertContains(previa, "Texto revisado e validado")
        self.assertNotContains(visitante.get(self.politica), "Texto revisado e validado")
        anterior = DocumentoLegal.objects.get(pk=self.tipo).versao_vigente

        revisao = previa.context["form"]["revisao"].value()
        self.assertRedirects(self.client.post(self.previa, {"revisao": revisao}), self.edicao)
        publicada = VersaoDocumentoLegal.objects.get(documento_id=self.tipo, numero="2.3")
        self.assertEqual(publicada.publicado_por, self.principal)
        self.assertIsNotNone(publicada.publicado_em)
        self.assertEqual(VersaoDocumentoLegal.objects.get(pk=anterior.pk).contato, contato_anterior)
        self.assertTrue(RegistroAuditoria.objects.filter(
            usuario=self.principal, acao=AcaoAuditoria.DOCUMENTO_LEGAL_PUBLICADO,
            entidade_id=str(publicada.pk),
        ).exists())

        vigente = visitante.get(self.politica)
        self.assertContains(vigente, "Versão 2.3")
        self.assertContains(vigente, "<li>Um item</li>", html=True)
        self.assertContains(vigente, 'href="mailto:privacidade@example.com"')
        self.assertContains(vigente, publicada.resumo)
        self.assertContains(visitante.get(f"{self.politica}?versao=2.2"), "Este documento foi atualizado", status_code=409)

        visitante.force_login(self.professor)
        tela = visitante.get(reverse("inventario:equipamento_lista"), follow=True)
        self.assertEqual(tela.request["PATH_INFO"], self.aceite)
        self.assertContains(tela, publicada.resumo)
        self.assertContains(tela, f"{self.politica}?versao=2.3")
        self.assertRedirects(visitante.post(self.aceite, {
            "versao_termos": "2.0", "versao_privacidade": "2.3",
            "aceitou_termos": "on", "confirmou_ciencia_privacidade": "on",
        }), reverse("inventario:equipamento_lista"))
        self.assertEqual(list(AceiteDocumentosLegais.objects.filter(usuario=self.professor).values_list(
            "versao_termos", "versao_privacidade",
        )), [("2.0", "2.3"), ("2.0", "2.2")])
        self.assertTrue(AceiteDocumentosLegais.objects.filter(pk=aceite_anterior.pk).exists())

    def test_outros_perfis_nao_podem_consultar_ou_alterar_documentos(self):
        lista = reverse("legal:documentos_legais")
        historico = reverse("legal:historico_documento", args=[self.tipo, "2.2"])
        self.assertContains(self.client.get(lista), "Política de Privacidade")
        for usuario in (self.administrador, self.operador, self.professor, self.tecnico):
            self.client.force_login(usuario)
            for rota in (lista, self.edicao, self.previa, historico):
                with self.subTest(usuario=usuario.username, rota=rota):
                    self.assertEqual(self.client.get(rota).status_code, 403)
                    if rota != lista:
                        self.assertEqual(self.client.post(rota, self.dados_rascunho()).status_code, 403)
        self.assertEqual(DocumentoLegal.objects.get(pk=self.tipo).revisao_rascunho, 1)

    def test_permissao_e_revalidada_na_gravacao(self):
        get_user_model().objects.filter(pk=self.principal.pk).update(is_administrador_principal=False)
        with self.assertRaises(PermissionDenied):
            salvar_rascunho(usuario=self.principal, tipo=self.tipo, **self.dados_rascunho())

    def test_publicacao_e_edicao_exigem_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.principal)
        self.assertEqual(cliente.post(self.edicao, self.dados_rascunho()).status_code, 403)
        self.assertEqual(cliente.post(self.previa, {"revisao": 1}).status_code, 403)

    def test_previa_desatualizada_e_rascunho_sem_resumo_nao_publicam(self):
        self.client.post(self.edicao, self.dados_rascunho())
        antiga = self.client.get(self.previa).context["form"]["revisao"].value()
        self.client.post(self.edicao, self.dados_rascunho(resumo=""))
        resposta = self.client.post(self.previa, {"revisao": antiga}, follow=True)
        self.assertContains(resposta, "O rascunho mudou")
        atual = resposta.context["form"]["revisao"].value()
        resposta = self.client.post(self.previa, {"revisao": atual}, follow=True)
        self.assertContains(resposta, "Informe o resumo das mudanças antes de publicar.")
        self.assertEqual(VersaoDocumentoLegal.objects.filter(documento_id=self.tipo).count(), 1)

    def test_falha_na_auditoria_desfaz_publicacao(self):
        self.client.post(self.edicao, self.dados_rascunho())
        documento = DocumentoLegal.objects.get(pk=self.tipo)
        with patch("legal.services.registrar_evento", side_effect=RuntimeError("auditoria indisponível")):
            with self.assertRaises(RuntimeError):
                publicar_rascunho(usuario=self.principal, tipo=self.tipo, revisao=documento.revisao_rascunho)
        self.assertEqual(VersaoDocumentoLegal.objects.filter(documento_id=self.tipo).count(), 1)
        self.assertEqual(DocumentoLegal.objects.get(pk=self.tipo).revisao_rascunho, documento.revisao_rascunho)

    def test_recuperacao_preserva_historico_e_nao_reaproveita_numero_legado(self):
        aceite_anterior, _ = registrar_aceite_vigente(self.principal)
        AceiteDocumentosLegais.objects.create(usuario=self.professor, versao_termos="2.0", versao_privacidade="2.3")
        nova = self.publicar()
        self.assertEqual(nova.numero, "2.4")
        self.assertContains(self.client.get(self.aceite), "Gerenciar documentos legais")
        rota_anterior = reverse("legal:historico_documento", args=[self.tipo, "2.2"])
        revisao = self.client.get(rota_anterior).context["form"]["revisao"].value()
        self.assertRedirects(self.client.post(rota_anterior, {"revisao": revisao}), self.edicao)
        dados = self.client.get(self.edicao).context["form"].initial
        corrigida = self.publicar(**{**dados, "resumo": "Restauramos o texto anterior."})
        self.assertEqual(corrigida.numero, "2.5")
        self.assertEqual(corrigida.conteudo, VersaoDocumentoLegal.objects.get(documento_id=self.tipo, numero="2.2").conteudo)
        self.assertTrue(VersaoDocumentoLegal.objects.filter(pk=nova.pk).exists())
        self.assertTrue(AceiteDocumentosLegais.objects.filter(pk=aceite_anterior.pk).exists())

    def test_conteudo_e_resumo_sao_tratados_como_texto(self):
        self.publicar(conteudo="## Texto\n\n<b>Trecho literal</b>", resumo="<b>Resumo literal</b>")
        resposta = Client().get(self.politica)
        self.assertContains(resposta, "&lt;b&gt;Trecho literal&lt;/b&gt;")
        self.assertContains(resposta, "&lt;b&gt;Resumo literal&lt;/b&gt;")
