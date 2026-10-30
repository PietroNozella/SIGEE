from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from legal.services import registrar_aceite_vigente
from movimentacoes.tests import criar_cenario

from .services import alterar_situacao_usuario


class AdministradorPrincipalTests(TestCase):
    SENHA = "Senha-SIGEE-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.comum = cls.cenario["administrador"]
        cls.principal = get_user_model().objects.create_user(
            username="principal", password=cls.SENHA, email="principal@example.com",
            is_administrador_principal=True,
        )
        cls.principal.groups.add(Group.objects.get(name="Administrador"))
        registrar_aceite_vigente(cls.principal)
        cls.outro = get_user_model().objects.create_user(username="outro-admin")
        cls.outro.groups.add(Group.objects.get(name="Administrador"))
        registrar_aceite_vigente(cls.outro)

    def setUp(self):
        self.client.force_login(self.comum)

    def url_situacao(self, usuario, ativo=False):
        rota = "usuarios:usuario_reativar" if ativo else "usuarios:usuario_desativar"
        return reverse(rota, args=[usuario.pk])

    def test_comum_nao_desativa_nem_reativa_outro_admin_por_post_ou_servico(self):
        for ativo in (False, True):
            with self.subTest(ativo=ativo):
                self.outro.is_active = not ativo
                self.outro.save(update_fields=("is_active",))
                cliente_alvo = Client()
                cliente_alvo.force_login(self.outro)
                sessao = cliente_alvo.session.session_key
                dados = get_user_model().objects.values().get(pk=self.outro.pk)
                resposta = self.client.post(self.url_situacao(self.outro, ativo))
                self.assertEqual(resposta.status_code, 403)
                with self.assertRaises(PermissionDenied):
                    alterar_situacao_usuario(
                        administrador=self.comum, usuario_id=self.outro.pk, ativo=ativo,
                    )
                self.assertEqual(get_user_model().objects.values().get(pk=self.outro.pk), dados)
                self.assertTrue(Session.objects.filter(pk=sessao).exists())
        self.assertFalse(RegistroAuditoria.objects.filter(
            acao__in=[AcaoAuditoria.USUARIO_DESATIVADO, AcaoAuditoria.USUARIO_REATIVADO],
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).exists())
        self.assertEqual(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.ACESSO_NEGADO, usuario=self.comum,
        ).count(), 2)

    def test_principal_desativa_e_reativa_comum_preservando_dados_e_auditoria(self):
        self.client.force_login(self.principal)
        cliente_alvo = Client()
        cliente_alvo.force_login(self.comum)
        sessao = cliente_alvo.session.session_key
        dados = get_user_model().objects.values().get(pk=self.comum.pk)
        for ativo in (False, True):
            resposta = self.client.post(self.url_situacao(self.comum, ativo))
            self.assertRedirects(resposta, reverse("usuarios:usuario_lista"))
            dados["is_active"] = ativo
            self.assertEqual(get_user_model().objects.values().get(pk=self.comum.pk), dados)
        self.assertFalse(Session.objects.filter(pk=sessao).exists())
        eventos = RegistroAuditoria.objects.filter(
            acao__in=[AcaoAuditoria.USUARIO_DESATIVADO, AcaoAuditoria.USUARIO_REATIVADO],
            usuario=self.principal, entidade_id=str(self.comum.pk), resultado="SUCESSO",
        )
        self.assertEqual(eventos.count(), 2)
        self.assertTrue(self.comum.groups.filter(name="Administrador").exists())

    def test_conta_principal_protegida_e_sem_autodesativacao(self):
        for ator in (self.comum, self.principal):
            self.client.force_login(ator)
            resposta = self.client.post(self.url_situacao(self.principal))
            self.assertEqual(resposta.status_code, 403 if ator == self.comum else 302)
            self.principal.refresh_from_db()
            self.assertTrue(self.principal.is_active)
        self.assertEqual(self.client.post(self.url_situacao(self.principal, True)).status_code, 403)

    def test_principal_nao_contorna_permissao_change_user(self):
        self.client.force_login(self.principal)
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(codename="change_user"))
        self.assertEqual(self.client.post(self.url_situacao(self.comum)).status_code, 403)
        self.comum.refresh_from_db()
        self.assertTrue(self.comum.is_active)

    def test_servico_reconsulta_designacao_revogada_mesmo_com_objeto_antigo(self):
        get_user_model().objects.filter(pk=self.principal.pk).update(is_administrador_principal=False)
        self.assertTrue(self.principal.is_administrador_principal)
        with self.assertRaises(PermissionDenied):
            alterar_situacao_usuario(
                administrador=self.principal, usuario_id=self.comum.pk, ativo=False,
            )
        self.comum.refresh_from_db()
        self.assertTrue(self.comum.is_active)

    def test_comum_e_principal_continuam_gerenciando_professor_e_operador(self):
        for ator in (self.comum, self.principal):
            self.client.force_login(ator)
            for alvo in (self.cenario["professor"], self.cenario["operador"]):
                for ativo in (False, True):
                    with self.subTest(ator=ator.username, alvo=alvo.username, ativo=ativo):
                        self.assertEqual(self.client.post(self.url_situacao(alvo, ativo)).status_code, 302)
                        alvo.refresh_from_db()
                        self.assertEqual(alvo.is_active, ativo)

    def test_lista_exibe_acoes_conforme_ator_e_conta_alvo(self):
        lista = reverse("usuarios:usuario_lista")
        resposta = self.client.get(lista)
        self.assertContains(resposta, "Administrador principal")
        self.assertContains(resposta, "Conta protegida")
        self.assertNotContains(resposta, self.url_situacao(self.outro))
        self.assertNotContains(resposta, self.url_situacao(self.principal))
        self.assertContains(resposta, self.url_situacao(self.cenario["professor"]))
        self.outro.is_active = False
        self.outro.save(update_fields=("is_active",))
        self.assertNotContains(self.client.get(lista), self.url_situacao(self.outro, True))
        self.client.force_login(self.principal)
        resposta = self.client.get(lista)
        self.assertContains(resposta, self.url_situacao(self.outro, True))
        self.assertContains(resposta, self.url_situacao(self.comum))
        self.assertNotContains(resposta, self.url_situacao(self.principal))

    def test_principal_preserva_acesso_as_telas_administrativas(self):
        self.client.force_login(self.principal)
        for rota in ("usuarios:usuario_novo", "inventario:painel", "inventario:equipamento_lista"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 200)

    def test_cadastro_nao_permite_designar_principal_por_campo_injetado(self):
        for ator in (self.comum, self.principal):
            self.client.force_login(ator)
            username = f"cadastrado-por-{ator.username}"
            resposta = self.client.post(reverse("usuarios:usuario_novo"), {
                "first_name": "Novo", "last_name": "Administrador",
                "email": f"{username}@example.com", "username": username,
                "perfil": Group.objects.get(name="Administrador").pk,
                "password1": self.SENHA, "password2": self.SENHA,
                "is_administrador_principal": "on", "is_superuser": "on", "is_staff": "on",
            })
            self.assertRedirects(resposta, reverse("usuarios:usuario_novo"))
            usuario = get_user_model().objects.get(username=username)
            self.assertFalse(usuario.is_administrador_principal)
            self.assertFalse(usuario.is_superuser)
            self.assertFalse(usuario.is_staff)
            self.assertEqual(list(usuario.groups.values_list("name", flat=True)), ["Administrador"])

    def test_banco_impede_segundo_principal_e_flags_tecnicas_ou_inatividade(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.filter(pk=self.comum.pk).update(is_administrador_principal=True)
        for campo in ("is_active", "is_staff", "is_superuser"):
            with self.subTest(campo=campo), self.assertRaises(IntegrityError), transaction.atomic():
                get_user_model().objects.filter(pk=self.principal.pk).update(**{campo: campo != "is_active"})
        self.principal.refresh_from_db()
        self.assertTrue(self.principal.is_active)
        self.assertTrue(self.principal.is_administrador_principal)

    def test_anonimizacao_rejeita_principal_inclusive_com_confirmacao(self):
        dados = get_user_model().objects.values().get(pk=self.principal.pk)
        for confirmar in (False, True):
            with self.assertRaisesMessage(CommandError, "principal não pode ser anonimizado"):
                call_command("anonimizar_usuario", self.principal.username, confirmar=confirmar, stdout=StringIO())
        self.assertEqual(get_user_model().objects.values().get(pk=self.principal.pk), dados)

    def test_admin_tecnico_nao_altera_protecao_nem_exclui_principal(self):
        tecnico = get_user_model().objects.create_superuser(
            username="tecnico", password=self.SENHA, email="tecnico@example.com",
        )
        self.client.force_login(tecnico)
        url = reverse("admin:contas_user_change", args=[self.principal.pk])
        resposta = self.client.get(url)
        self.assertContains(resposta, "Administrador principal")
        self.assertNotContains(resposta, 'name="is_active"')
        self.assertNotContains(resposta, 'name="groups"')
        self.assertNotContains(resposta, 'name="is_administrador_principal"')
        data_criacao = timezone.localtime(self.principal.date_joined)
        resposta = self.client.post(url, {
            "username": self.principal.username, "first_name": "Reserva",
            "last_name": "Institucional", "email": self.principal.email,
            "date_joined_0": data_criacao.strftime("%Y-%m-%d"),
            "date_joined_1": data_criacao.strftime("%H:%M:%S"),
            "is_active": "", "is_staff": "on", "is_superuser": "on",
            "groups": [Group.objects.get(name="Professor").pk],
            "is_administrador_principal": "", "_save": "Salvar",
        })
        self.assertEqual(resposta.status_code, 302)
        self.principal.refresh_from_db()
        self.assertEqual(self.principal.first_name, "Reserva")
        self.assertTrue(self.principal.is_active)
        self.assertTrue(self.principal.is_administrador_principal)
        self.assertFalse(self.principal.is_staff)
        self.assertFalse(self.principal.is_superuser)
        self.assertEqual(list(self.principal.groups.values_list("name", flat=True)), ["Administrador"])
        excluir = reverse("admin:contas_user_delete", args=[self.principal.pk])
        self.assertEqual(self.client.post(excluir, {"post": "yes"}).status_code, 403)
        self.assertTrue(get_user_model().objects.filter(pk=self.principal.pk).exists())

    def test_exclusao_em_lote_no_admin_preserva_principal(self):
        # Exercita a proteção mesmo sem vínculos históricos com PROTECT.
        self.principal.aceites_documentos_legais.all().delete()
        tecnico = get_user_model().objects.create_superuser(
            username="tecnico", password=self.SENHA, email="tecnico@example.com",
        )
        self.client.force_login(tecnico)
        resposta = self.client.post(reverse("admin:contas_user_changelist"), {
            "action": "delete_selected", "_selected_action": [self.principal.pk], "post": "yes",
        })
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(get_user_model().objects.filter(pk=self.principal.pk).exists())


class ConfigurarAdministradorPrincipalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.administrador = cls.cenario["administrador"]
        cls.administrador.set_password("Senha-SIGEE-2026!")
        cls.administrador.save(update_fields=("password",))

    def configurar(self, usuario=None, **opcoes):
        return call_command(
            "configurar_administrador_principal",
            (usuario or self.administrador).username, stdout=StringIO(), **opcoes,
        )

    def test_designacao_preserva_credenciais_grupo_e_permissoes_e_e_idempotente(self):
        dados = get_user_model().objects.values().get(pk=self.administrador.pk)
        grupos = list(self.administrador.groups.values_list("pk", flat=True))
        self.configurar()
        self.configurar()
        dados["is_administrador_principal"] = True
        self.assertEqual(get_user_model().objects.values().get(pk=self.administrador.pk), dados)
        self.assertEqual(list(self.administrador.groups.values_list("pk", flat=True)), grupos)
        evento = RegistroAuditoria.objects.get(acao=AcaoAuditoria.ADMINISTRADOR_PRINCIPAL_DESIGNADO)
        self.assertEqual(evento.entidade_id, str(self.administrador.pk))
        self.assertIsNone(evento.usuario_id)

    def test_recusa_conta_inexistente_inativa_tecnica_perfis_invalidos_e_senha_inutilizavel(self):
        with self.assertRaisesMessage(CommandError, "Usuário não encontrado"):
            call_command("configurar_administrador_principal", "inexistente", stdout=StringIO())
        grupo = Group.objects.get(name="Administrador")
        for campo in ("is_active", "is_staff", "is_superuser"):
            usuario = get_user_model().objects.create_user(
                username=campo, password="Senha-SIGEE-2026!", **{campo: campo != "is_active"},
            )
            usuario.groups.add(grupo)
            with self.subTest(campo=campo), self.assertRaises(CommandError):
                self.configurar(usuario)
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo")
        sem_senha = get_user_model().objects.create_user(username="sem-senha")
        sem_senha.groups.add(grupo)
        multiplo = get_user_model().objects.create_user(username="multiplo")
        multiplo.groups.add(grupo, Group.objects.get(name="Professor"))
        for usuario in (sem_grupo, sem_senha, multiplo, self.cenario["professor"], self.cenario["operador"]):
            with self.subTest(usuario=usuario.username), self.assertRaises(CommandError):
                self.configurar(usuario)
        self.assertFalse(get_user_model().objects.filter(is_administrador_principal=True).exists())

    def test_substituicao_exige_flag_e_preserva_ambas_contas(self):
        self.configurar()
        substituto = get_user_model().objects.create_user(username="substituto", password="Senha-SIGEE-2026!")
        substituto.groups.add(Group.objects.get(name="Administrador"))
        with self.assertRaisesMessage(CommandError, "Use --substituir"):
            self.configurar(substituto)
        self.configurar(substituto, substituir=True)
        self.administrador.refresh_from_db()
        substituto.refresh_from_db()
        self.assertFalse(self.administrador.is_administrador_principal)
        self.assertTrue(self.administrador.is_active)
        self.assertTrue(substituto.is_administrador_principal)
        self.assertEqual(get_user_model().objects.filter(is_administrador_principal=True).count(), 1)
        self.assertTrue(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.ADMINISTRADOR_PRINCIPAL_SUBSTITUIDO,
            entidade_id=str(self.administrador.pk),
        ).exists())
        self.assertTrue(self.administrador.groups.filter(name="Administrador").exists())

    def test_falha_na_auditoria_reverte_transferencia_do_principal(self):
        self.configurar()
        substituto = get_user_model().objects.create_user(username="substituto", password="Senha-SIGEE-2026!")
        substituto.groups.add(Group.objects.get(name="Administrador"))
        with patch(
            "usuarios.management.commands.configurar_administrador_principal.registrar_evento",
            side_effect=IntegrityError,
        ), self.assertRaises(CommandError):
            self.configurar(substituto, substituir=True)
        self.administrador.refresh_from_db()
        substituto.refresh_from_db()
        self.assertTrue(self.administrador.is_administrador_principal)
        self.assertFalse(substituto.is_administrador_principal)

    def test_substituto_invalido_nao_remove_principal_atual(self):
        self.configurar()
        with self.assertRaises(CommandError):
            self.configurar(self.cenario["professor"], substituir=True)
        self.administrador.refresh_from_db()
        self.assertTrue(self.administrador.is_administrador_principal)
