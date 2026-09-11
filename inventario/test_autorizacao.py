from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from usuarios.permissoes import (
    GRUPO_ADMINISTRADOR,
    GRUPO_OPERADOR,
    GRUPO_PROFESSOR,
)

from .models import Categoria, Equipamento, Local


class AutorizacaoInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.local = Local.objects.get(nome="Laboratório de informática")

        cls.administrador = cls._criar_usuario(
            "admin-matriz", GRUPO_ADMINISTRADOR
        )
        cls.operador = cls._criar_usuario("operador-matriz", GRUPO_OPERADOR)
        cls.professor = cls._criar_usuario("professor-matriz", GRUPO_PROFESSOR)
        cls.sem_grupo = get_user_model().objects.create_user(
            username="sem-grupo",
            password="senha-segura-123",
        )

    @classmethod
    def _criar_usuario(cls, username, nome_grupo):
        usuario = get_user_model().objects.create_user(
            username=username,
            password="senha-segura-123",
        )
        usuario.groups.add(Group.objects.get(name=nome_grupo))
        return usuario

    def criar_equipamento(self, patrimonio="PAT-AUT-001"):
        return Equipamento.objects.create(
            numero_patrimonio=patrimonio,
            nome="Notebook de teste",
            categoria=self.categoria,
            local=self.local,
        )

    def test_tres_perfis_podem_consultar_a_listagem(self):
        for usuario in (self.administrador, self.operador, self.professor):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse("inventario:equipamento_lista"))
                self.assertEqual(resposta.status_code, 200)

    def test_usuario_sem_grupo_recebe_403_na_listagem(self):
        self.client.force_login(self.sem_grupo)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(
            resposta,
            "Acesso não autorizado",
            status_code=403,
        )

    def test_administrador_acessa_rotas_de_cadastro_e_importacao(self):
        self.client.force_login(self.administrador)

        for rota in (
            reverse("inventario:equipamento_novo"),
            reverse("inventario:equipamento_importar"),
            reverse("inventario:equipamento_modelo_csv"),
        ):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)

    def test_operador_e_professor_recebem_403_nas_rotas_de_alteracao(self):
        for usuario in (self.operador, self.professor):
            with self.subTest(usuario=usuario.username):
                equipamento = self.criar_equipamento(
                    f"PAT-{usuario.username.upper()}"
                )
                self.client.force_login(usuario)

                for rota in (
                    reverse("inventario:equipamento_novo"),
                    reverse("inventario:equipamento_importar"),
                    reverse("inventario:equipamento_modelo_csv"),
                ):
                    resposta = self.client.get(rota)
                    self.assertEqual(resposta.status_code, 403)

                resposta_exclusao = self.client.post(
                    reverse(
                        "inventario:equipamento_excluir",
                        args=[equipamento.pk],
                    )
                )
                self.assertEqual(resposta_exclusao.status_code, 403)
                self.assertTrue(
                    Equipamento.objects.filter(pk=equipamento.pk).exists()
                )

    def test_administrador_pode_excluir_por_post(self):
        equipamento = self.criar_equipamento()
        self.client.force_login(self.administrador)

        resposta = self.client.post(
            reverse("inventario:equipamento_excluir", args=[equipamento.pk])
        )

        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertFalse(Equipamento.objects.filter(pk=equipamento.pk).exists())

    def test_interface_do_administrador_exibe_acoes_e_resumo(self):
        self.criar_equipamento()
        self.client.force_login(self.administrador)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, "Resumo do inventário")
        self.assertContains(resposta, "Novo equipamento")
        self.assertContains(resposta, "Importar CSV")
        self.assertContains(resposta, "data-delete-trigger")
        self.assertContains(resposta, "Cadastrar usuário")

    def test_interface_de_consulta_esconde_acoes_e_resumo(self):
        self.criar_equipamento()

        for usuario in (self.operador, self.professor):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse("inventario:equipamento_lista"))

                self.assertNotContains(resposta, "Resumo do inventário")
                self.assertNotContains(resposta, "Novo equipamento")
                self.assertNotContains(resposta, "Importar CSV")
                self.assertNotContains(resposta, "data-delete-trigger")
                self.assertNotContains(resposta, "Cadastrar usuário")
                self.assertContains(resposta, "Equipamentos")

    def test_resumo_nao_e_calculado_sem_permissao(self):
        self.client.force_login(self.operador)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertIsNone(resposta.context["indicadores"])
