import re
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from legal.services import registrar_aceite_vigente

from .forms import CadastroUsuarioForm
from .permissoes import (
    GRUPO_ADMINISTRADOR,
    GRUPO_OPERADOR,
    GRUPO_PROFESSOR,
    PERMISSOES_POR_GRUPO,
)


class ConfigurarPerfisCommandTests(TestCase):
    def test_comando_cria_grupos_com_permissoes_exatas(self):
        call_command("configurar_perfis", stdout=StringIO())

        self.assertSetEqual(
            set(Group.objects.values_list("name", flat=True)),
            set(PERMISSOES_POR_GRUPO),
        )
        for nome_grupo, chaves_esperadas in PERMISSOES_POR_GRUPO.items():
            grupo = Group.objects.get(name=nome_grupo)
            chaves_obtidas = {
                f"{permissao.content_type.app_label}.{permissao.codename}"
                for permissao in grupo.permissions.select_related("content_type")
            }
            self.assertSetEqual(chaves_obtidas, set(chaves_esperadas))

    def test_comando_pode_ser_reexecutado_e_substitui_configuracao_anterior(self):
        call_command("configurar_perfis", stdout=StringIO())
        grupo = Group.objects.get(name=GRUPO_OPERADOR)
        grupo.permissions.add(Permission.objects.get(codename="add_user"))

        call_command("configurar_perfis", stdout=StringIO())

        self.assertEqual(
            Group.objects.filter(name__in=PERMISSOES_POR_GRUPO).count(),
            3,
        )
        self.assertSetEqual(
            set(grupo.permissions.values_list("codename", flat=True)),
            {"view_equipamento"},
        )

    def test_comando_falha_claramente_quando_permissao_nao_existe(self):
        configuracao_invalida = {"Grupo de teste": ("inventario.inexistente",)}

        with patch(
            "usuarios.management.commands.configurar_perfis.PERMISSOES_POR_GRUPO",
            configuracao_invalida,
        ):
            with self.assertRaisesMessage(
                CommandError,
                "A permissão esperada 'inventario.inexistente' não existe",
            ):
                call_command("configurar_perfis", stdout=StringIO())

        self.assertFalse(Group.objects.filter(name="Grupo de teste").exists())


class CadastroUsuarioTests(TestCase):
    SENHA = "Senha-SIGEE-2026!"

    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.grupo_administrador = Group.objects.get(name=GRUPO_ADMINISTRADOR)
        cls.grupo_operador = Group.objects.get(name=GRUPO_OPERADOR)
        cls.grupo_professor = Group.objects.get(name=GRUPO_PROFESSOR)

        cls.administrador = cls._criar_usuario(
            "administrador-funcional", cls.grupo_administrador
        )
        cls.operador = cls._criar_usuario("operador", cls.grupo_operador)
        cls.professor = cls._criar_usuario("professor", cls.grupo_professor)
        cls.sem_grupo = get_user_model().objects.create_user(
            username="sem-grupo",
            password=cls.SENHA,
        )
        cls.permissao_individual = get_user_model().objects.create_user(
            username="permissao-individual",
            password=cls.SENHA,
        )
        cls.permissao_individual.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="auth",
                codename="add_user",
            )
        )
        cls.multiplos_grupos = cls._criar_usuario(
            "multiplos-grupos", cls.grupo_administrador
        )
        cls.multiplos_grupos.groups.add(cls.grupo_operador)
        cls.superuser = get_user_model().objects.create_superuser(
            username="superuser-tecnico",
            email="tecnico@example.com",
            password=cls.SENHA,
        )
        for usuario in (
            cls.administrador,
            cls.operador,
            cls.professor,
            cls.sem_grupo,
            cls.permissao_individual,
            cls.multiplos_grupos,
            cls.superuser,
        ):
            registrar_aceite_vigente(usuario)

    @classmethod
    def _criar_usuario(cls, username, grupo):
        usuario = get_user_model().objects.create_user(
            username=username,
            password=cls.SENHA,
        )
        usuario.groups.add(grupo)
        return usuario

    def dados_validos(self, username="novo-usuario", perfil=None):
        return {
            "first_name": "Maria",
            "last_name": "Silva",
            "email": "maria@example.com",
            "username": username,
            "perfil": (perfil or self.grupo_professor).pk,
            "password1": self.SENHA,
            "password2": self.SENHA,
        }

    def test_usuario_anonimo_e_redirecionado_com_next(self):
        rota = reverse("usuarios:usuario_novo")

        resposta = self.client.get(rota)

        self.assertRedirects(
            resposta,
            f'{reverse("login")}?next={rota}',
            fetch_redirect_response=False,
        )

    def test_administrador_funcional_abre_formulario(self):
        self.client.force_login(self.administrador)

        resposta = self.client.get(reverse("usuarios:usuario_novo"))

        self.assertEqual(resposta.status_code, 200)
        self.assertIsInstance(resposta.context["form"], CadastroUsuarioForm)
        self.assertEqual(
            list(resposta.context["form"].fields),
            [
                "first_name",
                "last_name",
                "email",
                "username",
                "perfil",
                "password1",
                "password2",
            ],
        )
        for texto in (
            "Nome",
            "Sobrenome",
            "E-mail",
            "Nome de usuário",
            "Perfil",
            "Senha inicial",
            "Confirmação da senha",
        ):
            self.assertContains(resposta, texto)

    def test_cadastro_salva_hash_grupo_unico_e_conta_comum(self):
        self.client.force_login(self.administrador)

        resposta = self.client.post(
            reverse("usuarios:usuario_novo"),
            self.dados_validos(),
            follow=True,
        )

        self.assertRedirects(resposta, reverse("usuarios:usuario_novo"))
        self.assertContains(resposta, "Usuário cadastrado com sucesso.")
        usuario = get_user_model().objects.get(username="novo-usuario")
        self.assertEqual(usuario.first_name, "Maria")
        self.assertEqual(usuario.last_name, "Silva")
        self.assertEqual(usuario.email, "maria@example.com")
        self.assertNotEqual(usuario.password, self.SENHA)
        self.assertTrue(usuario.check_password(self.SENHA))
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertQuerySetEqual(
            usuario.groups.all(),
            [self.grupo_professor],
        )
        self.assertFalse(resposta.context["form"].is_bound)

    def test_perfil_fora_da_matriz_e_rejeitado(self):
        grupo_externo = Group.objects.create(name="Grupo externo")
        self.client.force_login(self.administrador)

        resposta = self.client.post(
            reverse("usuarios:usuario_novo"),
            self.dados_validos(perfil=grupo_externo),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFormError(
            resposta.context["form"],
            "perfil",
            "Faça uma escolha válida. Sua escolha não é uma das disponíveis.",
        )
        self.assertFalse(
            get_user_model().objects.filter(username="novo-usuario").exists()
        )

    def test_email_e_obrigatorio(self):
        self.client.force_login(self.administrador)

        dados_sem_email = self.dados_validos(username="sem-email")
        dados_sem_email["email"] = ""
        resposta = self.client.post(
            reverse("usuarios:usuario_novo"), dados_sem_email
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFormError(
            resposta.context["form"],
            "email",
            "Este campo é obrigatório.",
        )
        self.assertFalse(
            get_user_model().objects.filter(username="sem-email").exists()
        )

    def test_email_duplicado_e_rejeitado_sem_diferenciar_maiusculas(self):
        get_user_model().objects.create_user(
            username="email-existente",
            email="Maria@Example.com",
            password=self.SENHA,
        )
        self.client.force_login(self.administrador)

        resposta = self.client.post(
            reverse("usuarios:usuario_novo"),
            self.dados_validos(username="email-repetido"),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFormError(
            resposta.context["form"],
            "email",
            "Já existe um usuário cadastrado com este e-mail.",
        )
        self.assertFalse(
            get_user_model().objects.filter(username="email-repetido").exists()
        )

    def test_banco_impede_email_duplicado_sem_diferenciar_maiusculas(self):
        get_user_model().objects.create_user(
            username="email-banco-existente",
            email="contato@example.com",
            password=self.SENHA,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                get_user_model().objects.create_user(
                    username="email-banco-repetido",
                    email="CONTATO@example.com",
                    password=self.SENHA,
                )

    def test_perfis_nao_autorizados_recebem_403_em_get_e_post(self):
        usuarios_sem_acesso = (
            self.operador,
            self.professor,
            self.sem_grupo,
            self.permissao_individual,
            self.multiplos_grupos,
            self.superuser,
        )

        for indice, usuario in enumerate(usuarios_sem_acesso):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                rota = reverse("usuarios:usuario_novo")

                resposta_get = self.client.get(rota)
                resposta_post = self.client.post(
                    rota,
                    self.dados_validos(username=f"indevido-{indice}"),
                )

                self.assertEqual(resposta_get.status_code, 403)
                self.assertEqual(resposta_post.status_code, 403)
                self.assertFalse(
                    get_user_model().objects.filter(
                        username=f"indevido-{indice}"
                    ).exists()
                )

    def test_navegacao_esconde_cadastro_de_usuario_com_multiplos_grupos(self):
        self.client.force_login(self.multiplos_grupos)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, reverse("usuarios:usuario_novo"))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="SIGEE <nao-responda@example.com>",
)
class RecuperacaoSenhaTests(TestCase):
    SENHA_ATUAL = "Senha-SIGEE-2026!"
    NOVA_SENHA = "Nova-Senha-SIGEE-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="usuario-recuperacao",
            email="usuario@example.com",
            password=cls.SENHA_ATUAL,
            first_name="Maria",
            last_name="Silva",
        )
        cls.usuario_inativo = get_user_model().objects.create_user(
            username="usuario-inativo",
            email="inativo@example.com",
            password=cls.SENHA_ATUAL,
            is_active=False,
        )

    def solicitar_recuperacao(self, email="usuario@example.com"):
        return self.client.post(reverse("password_reset"), {"email": email})

    def caminho_enviado(self):
        correspondencia = re.search(
            r"http://testserver(?P<caminho>/redefinir-senha/[^\s]+)",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(correspondencia)
        return correspondencia.group("caminho")

    def test_login_exibe_link_para_recuperacao(self):
        resposta = self.client.get(reverse("login"))

        self.assertContains(
            resposta,
            f'href="{reverse("password_reset")}"',
        )
        self.assertContains(resposta, "Esqueceu a senha?")

    def test_formulario_de_recuperacao_e_publico_e_protegido_por_csrf(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("password_reset"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'name="email"')
        self.assertContains(resposta, 'name="csrfmiddlewaretoken"')
        self.assertContains(resposta, "Recuperar senha")

    def test_email_existente_recebe_link_em_texto_e_html(self):
        resposta = self.solicitar_recuperacao()

        self.assertRedirects(
            resposta,
            reverse("password_reset_done"),
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 1)
        mensagem = mail.outbox[0]
        self.assertEqual(mensagem.to, [self.usuario.email])
        self.assertEqual(mensagem.from_email, "SIGEE <nao-responda@example.com>")
        self.assertEqual(mensagem.subject, "Redefinição de senha — SIGEE")
        self.assertIn("/redefinir-senha/", mensagem.body)
        self.assertIn("60 minutos", mensagem.body)
        self.assertEqual(len(mensagem.alternatives), 1)
        self.assertEqual(mensagem.alternatives[0].mimetype, "text/html")
        self.assertIn("60 minutos", mensagem.alternatives[0].content)
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.RECUPERACAO_SENHA_SOLICITADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                usuario__isnull=True,
            ).exists()
        )

    def test_email_inexistente_ou_conta_inativa_recebe_resposta_neutra(self):
        for email in ("inexistente@example.com", self.usuario_inativo.email):
            with self.subTest(email=email):
                mail.outbox.clear()
                resposta = self.solicitar_recuperacao(email)

                self.assertRedirects(
                    resposta,
                    reverse("password_reset_done"),
                    fetch_redirect_response=False,
                )
                self.assertEqual(len(mail.outbox), 0)

        confirmacao = self.client.get(reverse("password_reset_done"))
        self.assertContains(
            confirmacao,
            "Se existir uma conta ativa com o e-mail informado",
        )

    def test_link_valido_redefine_senha_e_nao_pode_ser_reutilizado(self):
        self.solicitar_recuperacao()
        caminho_original = self.caminho_enviado()

        resposta_token = self.client.get(caminho_original)
        self.assertEqual(resposta_token.status_code, 302)
        caminho_formulario = resposta_token.url

        formulario = self.client.get(caminho_formulario)
        self.assertContains(formulario, "Defina uma nova senha")
        self.assertContains(formulario, 'name="new_password1"')
        self.assertContains(formulario, 'name="new_password2"')

        resposta = self.client.post(
            caminho_formulario,
            {
                "new_password1": self.NOVA_SENHA,
                "new_password2": self.NOVA_SENHA,
            },
        )

        self.assertRedirects(
            resposta,
            reverse("password_reset_complete"),
            fetch_redirect_response=False,
        )
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.NOVA_SENHA))
        self.assertFalse(self.usuario.check_password(self.SENHA_ATUAL))
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                usuario=self.usuario,
                acao=AcaoAuditoria.SENHA_REDEFINIDA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="auth.User",
                entidade_id=str(self.usuario.pk),
            ).exists()
        )

        reutilizacao = self.client.get(caminho_original, follow=True)
        self.assertContains(reutilizacao, "Link inválido ou expirado")

    def test_senhas_diferentes_nao_alteram_a_conta(self):
        self.solicitar_recuperacao()
        resposta_token = self.client.get(self.caminho_enviado())

        resposta = self.client.post(
            resposta_token.url,
            {
                "new_password1": self.NOVA_SENHA,
                "new_password2": "Outra-Senha-SIGEE-2026!",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Os dois campos de senha não correspondem")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.SENHA_ATUAL))
        self.assertFalse(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.SENHA_REDEFINIDA
            ).exists()
        )

    @override_settings(PASSWORD_RESET_TIMEOUT=-1)
    def test_link_expirado_e_rejeitado(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        token = default_token_generator.make_token(self.usuario)
        caminho = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": uidb64, "token": token},
        )

        resposta = self.client.get(caminho, follow=True)

        self.assertContains(resposta, "Link inválido ou expirado")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.SENHA_ATUAL))
