from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, HttpResponseForbidden
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse

from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from usuarios.permissoes import GRUPO_ADMINISTRADOR, GRUPO_PROFESSOR

from .admin import RegistroAuditoriaAdmin
from .eventos import AcaoAuditoria
from .models import RegistroAuditoria
from .services import registrar_evento


@permission_required("inventario.change_equipamento", raise_exception=True)
def view_protegida_para_teste(request):
    return HttpResponse("Acesso permitido")


def view_proibida_para_teste(request):
    return HttpResponseForbidden("Acesso negado")


def logout_para_teste(request):
    return HttpResponse("Logout")


urlpatterns = [
    path("", include("legal.urls")),
    path("teste/permissao/", view_protegida_para_teste, name="teste_permissao"),
    path("teste/proibido/", view_proibida_para_teste, name="teste_proibido"),
    path("teste/logout/", logout_para_teste, name="logout"),
]


class RegistroAuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="administrador",
            password="senha-segura-123",
        )

    def test_registra_evento_com_usuario_e_entidade(self):
        registro = registrar_evento(
            usuario=self.usuario,
            acao="EQUIPAMENTO_CADASTRADO",
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="inventario.Equipamento",
            entidade_id=42,
        )

        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.acao, "EQUIPAMENTO_CADASTRADO")
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.SUCESSO)
        self.assertEqual(registro.entidade, "inventario.Equipamento")
        self.assertEqual(registro.entidade_id, "42")
        self.assertIsNotNone(registro.data_hora)

    def test_registra_evento_anonimo_sem_associar_usuario(self):
        registro = registrar_evento(
            usuario=AnonymousUser(),
            acao="LOGIN_FALHOU",
            resultado=RegistroAuditoria.Resultado.FALHA,
        )

        self.assertIsNone(registro.usuario)

    def test_impede_exclusao_do_usuario_associado_ao_registro(self):
        registro = registrar_evento(
            usuario=self.usuario,
            acao="LOGIN_REALIZADO",
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        )

        with self.assertRaises(ProtectedError):
            self.usuario.delete()

        self.assertTrue(get_user_model().objects.filter(pk=self.usuario.pk).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(pk=registro.pk).exists())

    def test_rejeita_acao_vazia_no_servico(self):
        with self.assertRaisesMessage(ValueError, "não pode ficar vazia"):
            registrar_evento(
                acao="   ",
                resultado=RegistroAuditoria.Resultado.SUCESSO,
            )

    def test_rejeita_texto_livre_como_acao(self):
        with self.assertRaisesMessage(ValueError, "código técnico"):
            registrar_evento(
                acao="Usuário informou uma senha no formulário",
                resultado=RegistroAuditoria.Resultado.FALHA,
            )

    def test_banco_rejeita_resultado_invalido(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroAuditoria.objects.create(
                    acao="EVENTO_INVALIDO",
                    resultado="DESCONHECIDO",
                )


class RegistroAuditoriaAdminTests(TestCase):
    def setUp(self):
        self.model_admin = RegistroAuditoriaAdmin(RegistroAuditoria, admin.site)
        self.request = RequestFactory().get("/admin/auditoria/registroauditoria/")

    def test_registros_nao_podem_ser_incluidos_editados_ou_excluidos_no_admin(self):
        self.assertFalse(self.model_admin.has_add_permission(self.request))
        self.assertFalse(self.model_admin.has_change_permission(self.request))
        self.assertFalse(self.model_admin.has_delete_permission(self.request))


class AuditoriaInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Notebook auditoria")
        cls.local = Local.objects.get(nome="Laboratório de informática")
        cls.usuario = get_user_model().objects.create_user(
            username="operador_auditoria",
            password="senha-segura-123",
        )
        cls.usuario.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        registrar_aceite_vigente(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)

    def dados_equipamento(self, patrimonio):
        return {
            "numero_patrimonio": patrimonio,
            "nome": "Notebook educacional",
            "descricao": "Uso em sala de aula",
            "categoria": self.categoria.pk,
            "local": self.local.pk,
            "situacao": Equipamento.Situacao.DISPONIVEL,
        }

    def test_cadastro_bem_sucedido_registra_usuario_e_equipamento(self):
        resposta = self.client.post(
            reverse("inventario:equipamento_novo"),
            self.dados_equipamento("PAT-AUD-001"),
        )

        equipamento = Equipamento.objects.get(numero_patrimonio="PAT-AUD-001")
        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.EQUIPAMENTO_CADASTRADO
        )
        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.acao, AcaoAuditoria.EQUIPAMENTO_CADASTRADO)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.SUCESSO)
        self.assertEqual(registro.entidade_id, str(equipamento.pk))

    def test_cadastro_invalido_registra_falha_sem_dados_do_formulario(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-AUD-002",
            tipo=self.tipo,
            local=self.local,
        )

        self.client.post(
            reverse("inventario:equipamento_novo"),
            self.dados_equipamento("PAT-AUD-002"),
        )

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.EQUIPAMENTO_CADASTRADO
        )
        self.assertEqual(registro.acao, AcaoAuditoria.EQUIPAMENTO_CADASTRADO)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.FALHA)
        self.assertEqual(registro.entidade_id, "")

    def test_importacao_bem_sucedida_registra_um_evento_para_o_lote(self):
        conteudo = "\n".join(
            (
                "numero_patrimonio;nome;descricao;categoria;local;situacao",
                (
                    "PAT-AUD-003;Notebook educacional;Uso em sala;"
                    f"{self.categoria.nome};{self.local.nome};"
                    f"{Equipamento.Situacao.DISPONIVEL}"
                ),
            )
        )
        arquivo = SimpleUploadedFile(
            "equipamentos.csv",
            conteudo.encode("utf-8"),
            content_type="text/csv",
        )

        self.client.post(
            reverse("inventario:equipamento_importar"),
            {"arquivo": arquivo},
        )

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.EQUIPAMENTOS_IMPORTADOS
        )
        self.assertEqual(registro.acao, AcaoAuditoria.EQUIPAMENTOS_IMPORTADOS)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.SUCESSO)
        self.assertEqual(registro.entidade, "inventario.Equipamento")

    def test_consulta_filtrada_registra_evento_sem_valores_pesquisados(self):
        resposta = self.client.get(
            reverse("inventario:equipamento_lista"),
            {"busca": "termo que não deve ser armazenado"},
        )

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.INVENTARIO_CONSULTADO
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.entidade, "inventario.Equipamento")
        self.assertEqual(registro.entidade_id, "")
        self.assertFalse(hasattr(registro, "parametros"))

    def test_abertura_do_inventario_sem_filtros_nao_gera_evento_de_consulta(self):
        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.INVENTARIO_CONSULTADO
            ).exists()
        )

    def test_download_do_modelo_csv_registra_evento_sem_conteudo_do_arquivo(self):
        resposta = self.client.get(reverse("inventario:equipamento_modelo_csv"))

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.MODELO_CSV_BAIXADO
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.entidade, "inventario.Equipamento")
        self.assertFalse(hasattr(registro, "conteudo_arquivo"))

    def test_exclusao_e_inativacao_geram_eventos_distintos(self):
        sem_historico = Equipamento.objects.create(
            numero_patrimonio="PAT-AUD-004",
            tipo=self.tipo,
            local=self.local,
        )
        com_historico = Equipamento.objects.create(
            numero_patrimonio="PAT-AUD-005",
            tipo=self.tipo,
            local=self.local,
        )
        destinatario = get_user_model().objects.create_user(
            username="professor_auditoria",
            password="senha-segura-123",
        )
        Movimentacao.objects.create(
            equipamento=com_historico,
            operador=self.usuario,
            destinatario=destinatario,
            tipo="RETIRADA",
        )

        self.client.post(
            reverse("inventario:equipamento_excluir", args=[sem_historico.pk])
        )
        self.client.post(
            reverse("inventario:equipamento_excluir", args=[com_historico.pk])
        )

        self.assertTrue(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.EQUIPAMENTO_EXCLUIDO,
                entidade_id=str(sem_historico.pk),
            ).exists()
        )
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.EQUIPAMENTO_INATIVADO,
                entidade_id=str(com_historico.pk),
            ).exists()
        )


class AuditoriaCadastroUsuarioTests(TestCase):
    SENHA = "Senha-SIGEE-2026!"

    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.administrador = get_user_model().objects.create_user(
            username="administrador_contas",
            password=cls.SENHA,
        )
        cls.administrador.groups.add(
            Group.objects.get(name=GRUPO_ADMINISTRADOR)
        )
        cls.grupo_professor = Group.objects.get(name=GRUPO_PROFESSOR)
        registrar_aceite_vigente(cls.administrador)

    def dados_validos(self, username="novo_usuario_auditado"):
        return {
            "first_name": "Maria",
            "last_name": "Silva",
            "email": "maria@example.com",
            "username": username,
            "perfil": self.grupo_professor.pk,
            "password1": self.SENHA,
            "password2": self.SENHA,
        }

    def setUp(self):
        self.client.force_login(self.administrador)

    def test_cadastro_bem_sucedido_registra_administrador_e_nova_conta(self):
        resposta = self.client.post(
            reverse("usuarios:usuario_novo"),
            self.dados_validos(),
        )

        usuario_cadastrado = get_user_model().objects.get(
            username="novo_usuario_auditado"
        )
        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.USUARIO_CADASTRADO
        )
        self.assertRedirects(resposta, reverse("usuarios:usuario_novo"))
        self.assertEqual(registro.usuario, self.administrador)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.SUCESSO)
        self.assertEqual(registro.entidade, "auth.User")
        self.assertEqual(registro.entidade_id, str(usuario_cadastrado.pk))

    def test_cadastro_invalido_registra_falha_sem_dados_do_formulario(self):
        get_user_model().objects.create_user(
            username="conta_existente",
            password=self.SENHA,
        )

        resposta = self.client.post(
            reverse("usuarios:usuario_novo"),
            self.dados_validos(username="conta_existente"),
        )

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.USUARIO_CADASTRADO
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(registro.usuario, self.administrador)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.FALHA)
        self.assertEqual(registro.entidade, "auth.User")
        self.assertEqual(registro.entidade_id, "")
        self.assertFalse(hasattr(registro, "dados_formulario"))


class AuditoriaAutenticacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="usuario_autenticacao",
            password="senha-segura-123",
        )
        registrar_aceite_vigente(cls.usuario)

    def test_login_bem_sucedido_registra_usuario(self):
        autenticado = self.client.login(
            username="usuario_autenticacao",
            password="senha-segura-123",
        )

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.LOGIN_REALIZADO
        )
        self.assertTrue(autenticado)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.SUCESSO)

    def test_login_invalido_registra_falha_anonima(self):
        autenticado = self.client.login(
            username="usuario_autenticacao",
            password="senha-incorreta",
        )

        registro = RegistroAuditoria.objects.get(acao=AcaoAuditoria.LOGIN_FALHOU)
        self.assertFalse(autenticado)
        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.FALHA)
        self.assertFalse(hasattr(registro, "credentials"))

    def test_logout_registra_usuario_que_encerrou_a_sessao(self):
        self.client.force_login(self.usuario)
        RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.LOGIN_REALIZADO
        ).delete()

        self.client.logout()

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.LOGOUT_REALIZADO
        )
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.resultado, RegistroAuditoria.Resultado.SUCESSO)


@override_settings(ROOT_URLCONF=__name__)
class AuditoriaAcessoNegadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="usuario_sem_permissao",
            password="senha-segura-123",
        )
        registrar_aceite_vigente(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_resposta_403_de_usuario_autenticado_registra_acesso_negado(self):
        resposta = self.client.get(reverse("teste_permissao"))

        registro = RegistroAuditoria.objects.get(
            acao=AcaoAuditoria.ACESSO_NEGADO
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(
            registro.resultado,
            RegistroAuditoria.Resultado.ACESSO_NEGADO,
        )
        self.assertEqual(registro.entidade, "")
        self.assertEqual(registro.entidade_id, "")

    def test_acesso_permitido_nao_registra_negacao(self):
        permissao = Permission.objects.get(codename="change_equipamento")
        self.usuario.user_permissions.add(permissao)

        resposta = self.client.get(reverse("teste_permissao"))

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.ACESSO_NEGADO
            ).exists()
        )

    def test_resposta_403_anonima_nao_cria_registro_de_acesso_negado(self):
        self.client.logout()
        RegistroAuditoria.objects.all().delete()

        resposta = self.client.get(reverse("teste_proibido"))

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(RegistroAuditoria.objects.exists())
