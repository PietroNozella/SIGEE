from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from usuarios.permissoes import GRUPO_ADMINISTRADOR

from .models import AceiteDocumentosLegais, DocumentoLegal
from .admin import AceiteDocumentosLegaisAdmin
from .services import (
    registrar_aceite_vigente,
    publicar_rascunho,
    salvar_rascunho,
    usuario_possui_aceite_vigente,
    versoes_atuais,
)


class DocumentosLegaisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.usuario = get_user_model().objects.create_user(
            username="usuario-aceite",
            password="senha-segura-123",
            first_name="Usuário",
            last_name="Demonstração",
            email="usuario@example.com",
        )
        cls.usuario.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))

    def setUp(self):
        self.client.force_login(self.usuario)

    def dados_aceite(self, **dados):
        versao_termos, versao_privacidade = versoes_atuais()
        return {
            "aceitou_termos": "on",
            "confirmou_ciencia_privacidade": "on",
            "versao_termos": versao_termos,
            "versao_privacidade": versao_privacidade,
            **dados,
        }

    def test_termos_e_politica_sao_publicos(self):
        self.client.logout()

        termos = self.client.get(reverse("legal:termos_de_uso"))
        politica = self.client.get(reverse("legal:politica_privacidade"))

        self.assertEqual(termos.status_code, 200)
        self.assertEqual(politica.status_code, 200)
        self.assertContains(termos, "Termos de Uso")
        self.assertContains(politica, "Política de Privacidade")
        self.assertContains(politica, "dados pessoais")
        self.assertContains(politica, "suporte.sigee@gmail.com")

    def test_login_exibe_links_para_os_documentos(self):
        self.client.logout()

        resposta = self.client.get(reverse("login"))

        self.assertContains(resposta, reverse("legal:termos_de_uso"))
        self.assertContains(resposta, reverse("legal:politica_privacidade"))

    def test_tela_de_aceite_exige_autenticacao(self):
        self.client.logout()

        resposta = self.client.get(reverse("legal:aceite_documentos"))

        self.assertRedirects(
            resposta,
            f'{reverse("login")}?next={reverse("legal:aceite_documentos")}',
            fetch_redirect_response=False,
        )

    def test_usuario_sem_aceite_e_redirecionado_antes_da_area_interna(self):
        destino = reverse("inventario:equipamento_lista")

        resposta = self.client.get(destino)

        self.assertRedirects(
            resposta,
            f'{reverse("legal:aceite_documentos")}?next={destino}',
            fetch_redirect_response=False,
        )

    def test_login_admin_preserva_aceite_obrigatorio_antes_do_painel(self):
        self.client.logout()
        resposta = self.client.post(
            reverse("login"),
            {"username": self.usuario.username, "password": "senha-segura-123"},
        )
        self.assertRedirects(
            resposta, reverse("inventario:painel"), fetch_redirect_response=False,
        )
        aceite = self.client.get(resposta.url, follow=True)
        self.assertEqual(aceite.request["PATH_INFO"], reverse("legal:aceite_documentos"))
        self.assertEqual(aceite.context["next"], reverse("inventario:painel"))
        resposta = self.client.post(
            reverse("legal:aceite_documentos"),
            self.dados_aceite(next=reverse("inventario:painel")),
        )
        self.assertRedirects(resposta, reverse("inventario:painel"))

    def test_usuario_sem_aceite_pode_sair(self):
        resposta = self.client.post(reverse("logout"))

        self.assertRedirects(
            resposta,
            reverse("login"),
            fetch_redirect_response=False,
        )

    def test_as_duas_confirmacoes_sao_obrigatorias(self):
        resposta = self.client.post(
            reverse("legal:aceite_documentos"),
            {"aceitou_termos": "on"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "confirmar a leitura da Política")
        self.assertFalse(AceiteDocumentosLegais.objects.exists())

    def test_aceite_valido_registra_usuario_versoes_e_data(self):
        resposta = self.client.post(
            reverse("legal:aceite_documentos"),
            self.dados_aceite(),
        )

        self.assertRedirects(
            resposta,
            reverse("inventario:equipamento_lista"),
            fetch_redirect_response=False,
        )
        aceite = AceiteDocumentosLegais.objects.get()
        self.assertEqual(aceite.usuario, self.usuario)
        self.assertEqual(aceite.versao_termos, "2.0")
        self.assertEqual(aceite.versao_privacidade, "2.2")
        self.assertIsNotNone(aceite.aceito_em)
        self.assertTrue(usuario_possui_aceite_vigente(self.usuario))

    def test_aceite_preserva_destino_interno(self):
        destino = reverse("inventario:equipamento_importar")

        resposta = self.client.post(
            reverse("legal:aceite_documentos"),
            self.dados_aceite(next=destino),
        )

        self.assertRedirects(resposta, destino, fetch_redirect_response=False)

    def test_destino_externo_nao_e_aceito(self):
        resposta = self.client.post(
            reverse("legal:aceite_documentos"),
            self.dados_aceite(next="https://exemplo-malicioso.invalid/"),
        )

        self.assertRedirects(
            resposta,
            reverse("inventario:equipamento_lista"),
            fetch_redirect_response=False,
        )

    def test_aceite_vigente_libera_area_interna(self):
        registrar_aceite_vigente(self.usuario)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(resposta.status_code, 200)

    def publicar_termos(self):
        principal = get_user_model().objects.create_user(
            username="principal-aceite", is_administrador_principal=True,
        )
        principal.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        documento = DocumentoLegal.objects.get(pk=DocumentoLegal.Tipo.TERMOS)
        salvar_rascunho(
            usuario=principal, tipo=documento.tipo, revisao=documento.revisao_rascunho,
            conteudo="## Atualização\n\nNovas regras de uso.", contato=documento.rascunho_contato,
            resumo="Atualização das regras de uso.",
        )
        documento.refresh_from_db()
        return publicar_rascunho(
            usuario=principal, tipo=documento.tipo, revisao=documento.revisao_rascunho,
        )

    def test_nova_versao_exige_novo_aceite(self):
        anterior, _ = registrar_aceite_vigente(self.usuario)
        self.publicar_termos()

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertRedirects(
            resposta,
            (
                f'{reverse("legal:aceite_documentos")}?next='
                f'{reverse("inventario:equipamento_lista")}'
            ),
            fetch_redirect_response=False,
        )
        self.assertTrue(AceiteDocumentosLegais.objects.filter(pk=anterior.pk).exists())

    def test_nao_registra_aceite_quando_a_versao_muda_apos_exibir_formulario(self):
        formulario_exibido = self.client.get(reverse("legal:aceite_documentos"))
        self.assertEqual(formulario_exibido.context["versao_termos"], "2.0")

        dados = self.dados_aceite()
        nova = self.publicar_termos()
        resposta = self.client.post(reverse("legal:aceite_documentos"), dados)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Os documentos foram atualizados")
        self.assertEqual(resposta.context["form"]["versao_termos"].value(), nova.numero)
        self.assertFalse(resposta.context["form"]["aceitou_termos"].value())
        self.assertFalse(resposta.context["form"]["confirmou_ciencia_privacidade"].value())
        self.assertFalse(AceiteDocumentosLegais.objects.exists())
        self.assertFalse(
            RegistroAuditoria.objects.filter(
                usuario=self.usuario,
                acao=AcaoAuditoria.DOCUMENTOS_LEGAIS_ACEITOS,
            ).exists()
        )

    def test_aceite_repetido_nao_cria_duplicidade(self):
        registrar_aceite_vigente(self.usuario)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AceiteDocumentosLegais.objects.create(
                    usuario=self.usuario,
                    versao_termos="2.0",
                    versao_privacidade="2.2",
                )

    def test_aceite_gera_evento_de_auditoria(self):
        self.client.post(
            reverse("legal:aceite_documentos"),
            self.dados_aceite(),
        )

        aceite = AceiteDocumentosLegais.objects.get()
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                usuario=self.usuario,
                acao=AcaoAuditoria.DOCUMENTOS_LEGAIS_ACEITOS,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="AceiteDocumentosLegais",
                entidade_id=str(aceite.pk),
            ).exists()
        )

    def test_aceite_protege_a_evidencia_ao_excluir_usuario(self):
        registrar_aceite_vigente(self.usuario)

        with self.assertRaises(ProtectedError):
            self.usuario.delete()

        self.assertTrue(
            get_user_model().objects.filter(pk=self.usuario.pk).exists()
        )


class AceiteDocumentosLegaisAdminTests(TestCase):
    def test_aceite_nao_pode_ser_incluido_editado_ou_excluido_no_admin(self):
        model_admin = AceiteDocumentosLegaisAdmin(
            AceiteDocumentosLegais,
            admin.site,
        )
        request = RequestFactory().get("/admin/legal/aceitedocumentoslegais/")

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))


class TransparenciaPublicaTests(TestCase):
    def test_documentos_exibem_versao_data_fornecedores_e_direitos(self):
        politica = self.client.get(reverse("legal:politica_privacidade"))
        termos = self.client.get(reverse("legal:termos_de_uso"))

        self.assertContains(politica, "Versão 2.2")
        self.assertContains(politica, "10/11/2026")
        self.assertContains(politica, "30 minutos")
        self.assertContains(politica, "8 horas")
        self.assertContains(politica, "Vercel")
        self.assertContains(politica, "Supabase")
        self.assertContains(politica, "Direitos dos titulares")
        self.assertContains(termos, "Legislação e contato")
        self.assertContains(termos, "vigente desde 21/09/2026")

    def test_paginas_publicas_nao_carregam_fontes_ou_css_de_terceiros(self):
        for nome_rota in (
            "login",
            "password_reset",
            "legal:termos_de_uso",
            "legal:politica_privacidade",
        ):
            with self.subTest(nome_rota=nome_rota):
                resposta = self.client.get(reverse(nome_rota))
                self.assertNotContains(resposta, "fonts.googleapis.com")
                self.assertNotContains(resposta, "fonts.gstatic.com")
                self.assertNotContains(resposta, "cdn.jsdelivr.net")
                self.assertContains(
                    resposta,
                    "/static/vendor/bootstrap/bootstrap.min.css",
                )
