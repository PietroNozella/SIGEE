from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

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

    def test_email_e_obrigatorio_mas_pode_se_repetir(self):
        get_user_model().objects.create_user(
            username="email-existente",
            email="maria@example.com",
            password=self.SENHA,
        )
        self.client.force_login(self.administrador)

        dados_sem_email = self.dados_validos(username="sem-email")
        dados_sem_email["email"] = ""
        resposta_invalida = self.client.post(
            reverse("usuarios:usuario_novo"), dados_sem_email
        )
        resposta_valida = self.client.post(
            reverse("usuarios:usuario_novo"),
            self.dados_validos(username="email-repetido"),
        )

        self.assertEqual(resposta_invalida.status_code, 200)
        self.assertFormError(
            resposta_invalida.context["form"],
            "email",
            "Este campo é obrigatório.",
        )
        self.assertRedirects(
            resposta_valida,
            reverse("usuarios:usuario_novo"),
            fetch_redirect_response=False,
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
