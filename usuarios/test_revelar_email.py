from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import DatabaseError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from legal.services import registrar_aceite_vigente

from .sessoes import ULTIMA_ATIVIDADE


class RevelarEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.administrador = cls.criar_usuario("gestor", "Administrador", email="gestor@example.com")
        cls.professor = cls.criar_usuario("docente", "Professor", email="maria@example.com", first_name="Maria")
        cls.operador = cls.criar_usuario("operador", "Operador", email="operador@example.com")

    @classmethod
    def criar_usuario(cls, nome, grupo=None, **campos):
        usuario = get_user_model().objects.create_user(username=nome, **campos)
        if grupo:
            usuario.groups.add(Group.objects.get(name=grupo))
        registrar_aceite_vigente(usuario)
        return usuario

    def setUp(self):
        self.client.force_login(self.administrador)
        self.lista = reverse("usuarios:usuario_lista")
        self.url = reverse("usuarios:usuario_revelar_email", args=[self.professor.pk])

    def eventos(self):
        return RegistroAuditoria.objects.filter(acao=AcaoAuditoria.USUARIO_EMAIL_REVELADO)

    def test_html_inicial_oculta_todos_os_emails_sem_revelacao_ou_auditoria(self):
        resposta = self.client.get(self.lista)
        for usuario in (self.administrador, self.professor, self.operador):
            self.assertNotContains(resposta, usuario.email)
        self.assertContains(resposta, "E-mail oculto")
        self.assertContains(resposta, 'name="csrfmiddlewaretoken"')
        self.assertFalse(self.eventos().exists())

    def test_busca_preserva_nome_e_usuario_e_nao_procura_email(self):
        for termo in ("MARIA", "docente"):
            resposta = self.client.get(self.lista, {"busca": termo})
            self.assertQuerySetEqual(resposta.context["pagina"], [self.professor])
        resposta = self.client.get(self.lista, {"busca": "example.com"})
        self.assertQuerySetEqual(resposta.context["pagina"], [])

    def test_revelacao_retorna_so_email_solicitado_e_registra_responsavel_e_alvo(self):
        resposta = self.client.post(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"email": self.professor.email})
        self.assertNotContains(resposta, self.operador.email)
        self.assertIn("no-store", resposta["Cache-Control"])
        evento = self.eventos().get()
        self.assertEqual(evento.usuario, self.administrador)
        self.assertEqual(evento.entidade, "contas.User")
        self.assertEqual(evento.entidade_id, str(self.professor.pk))
        self.assertEqual(evento.resultado, RegistroAuditoria.Resultado.SUCESSO)
        self.assertIsNotNone(evento.data_hora)
        self.assertNotIn(self.professor.email, str(evento.__dict__))

    def test_cada_nova_revelacao_gera_novo_evento(self):
        self.client.post(self.url)
        self.client.post(self.url)
        self.assertEqual(self.eventos().count(), 2)

    def test_conta_inativa_ainda_pode_ser_consultada(self):
        self.professor.is_active = False
        self.professor.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(self.url).json(), {"email": self.professor.email})

    def test_exige_post_sem_revelar_ou_auditar_por_get(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 405)
        self.assertNotContains(resposta, self.professor.email, status_code=405)
        self.assertFalse(self.eventos().exists())

    def test_csrf_exigido_inclusive_para_administrador_somente_com_consulta(self):
        Group.objects.get(name="Administrador").permissions.remove(
            Permission.objects.get(content_type__app_label="contas", codename="change_user"),
        )
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.administrador)
        pagina = cliente.get(self.lista)
        self.assertContains(pagina, 'name="csrfmiddlewaretoken"')
        self.assertEqual(cliente.post(self.url).status_code, 403)
        self.assertFalse(self.eventos().exists())
        resposta = cliente.post(self.url, HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.eventos().count(), 1)

    def test_sem_permissao_de_consulta_nao_revela(self):
        Group.objects.get(name="Administrador").permissions.remove(
            Permission.objects.get(content_type__app_label="contas", codename="view_user"),
        )
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertFalse(self.eventos().exists())

    def test_outros_perfis_e_contas_tecnicas_nao_revelam_mesmo_com_permissao(self):
        individual = self.criar_usuario("individual")
        individual.user_permissions.add(Permission.objects.get(content_type__app_label="contas", codename="view_user"))
        tecnico = self.criar_usuario("tecnico", "Administrador", is_staff=True)
        superuser = self.criar_usuario("superuser", is_superuser=True)
        multiplo = self.criar_usuario("multiplo", "Administrador")
        multiplo.groups.add(Group.objects.get(name="Professor"))
        for usuario in (self.professor, self.operador, individual, tecnico, superuser, multiplo):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.post(self.url)
                self.assertNotContains(resposta, self.professor.email, status_code=403)
        self.assertFalse(self.eventos().exists())
        self.assertTrue(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.ACESSO_NEGADO).exists())

    def test_alvo_inexistente_tecnico_sem_grupo_multiplos_grupos_ou_sem_email_nao_revela(self):
        tecnico = self.criar_usuario("alvo-tecnico", "Professor", is_staff=True, email="tecnico@example.com")
        superuser = self.criar_usuario("alvo-super", is_superuser=True, email="super@example.com")
        sem_grupo = self.criar_usuario("alvo-sem-grupo", email="semgrupo@example.com")
        multiplo = self.criar_usuario("alvo-multiplo", "Professor", email="multiplo@example.com")
        multiplo.groups.add(Group.objects.get(name="Operador"))
        sem_email = self.criar_usuario("alvo-sem-email", "Professor")
        for alvo in (uuid4(), tecnico.pk, superuser.pk, sem_grupo.pk, multiplo.pk, sem_email.pk):
            with self.subTest(alvo=alvo):
                resposta = self.client.post(reverse("usuarios:usuario_revelar_email", args=[alvo]))
                self.assertEqual(resposta.status_code, 404)
                self.assertNotContains(resposta, "@example.com", status_code=404)
        self.assertFalse(self.eventos().exists())
        pagina = self.client.get(self.lista)
        self.assertNotContains(pagina, reverse("usuarios:usuario_revelar_email", args=[sem_email.pk]))
        self.assertContains(pagina, "Não informado")

    def test_falha_na_auditoria_desfaz_evento_e_nao_entrega_email(self):
        def registrar_e_falhar(**dados):
            registrar_evento(**dados)
            raise DatabaseError("falha simulada")

        with patch("usuarios.views.registrar_evento", side_effect=registrar_e_falhar):
            resposta = self.client.post(self.url)
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(set(resposta.json()), {"erro"})
        self.assertNotContains(resposta, self.professor.email, status_code=503)
        self.assertIn("no-store", resposta["Cache-Control"])
        self.assertFalse(self.eventos().exists())

    def test_anonimo_e_sessao_expirada_nao_recebem_email(self):
        self.client.logout()
        resposta = self.client.post(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(resposta.status_code, 401)
        self.client.force_login(self.administrador)
        sessao = self.client.session
        sessao[ULTIMA_ATIVIDADE] = timezone.now().timestamp() - settings.SESSION_IDLE_TIMEOUT - 1
        sessao.save()
        resposta = self.client.post(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(resposta.status_code, 401)
        self.assertNotContains(resposta, self.professor.email, status_code=401)
        self.assertFalse(self.eventos().exists())

    def test_evento_fica_disponivel_na_consulta_de_auditoria(self):
        self.client.post(self.url)
        resposta = self.client.get(reverse("auditoria:registro_lista"), {"acao": AcaoAuditoria.USUARIO_EMAIL_REVELADO})
        self.assertContains(resposta, AcaoAuditoria.USUARIO_EMAIL_REVELADO)
        self.assertContains(resposta, str(self.professor.pk))
        self.assertNotContains(resposta, self.professor.email)
        self.assertEqual(resposta.context["pagina"].paginator.count, 1)
