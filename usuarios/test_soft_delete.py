from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from legal.services import registrar_aceite_vigente
from movimentacoes.services import registrar_devolucao, registrar_retirada_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva
from reservas.services import cancelar_reserva, criar_reserva

from .forms import CadastroUsuarioForm
from .permissoes import usuarios_funcionais_ativos
from .services import alterar_situacao_usuario


class SoftDeleteUsuarioTests(TestCase):
    SENHA = "Senha-SIGEE-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.administrador = cls.cenario["administrador"]
        cls.professor = cls.cenario["professor"]
        cls.professor.first_name = "Maria"
        cls.professor.last_name = "Silva"
        cls.professor.email = "maria@example.com"
        cls.professor.set_password(cls.SENHA)
        cls.professor.save()

    def setUp(self):
        self.client.force_login(self.administrador)
        self.lista = reverse("usuarios:usuario_lista")

    def alterar(self, usuario=None, ativo=False, **opcoes):
        usuario = usuario or self.professor
        rota = "usuarios:usuario_reativar" if ativo else "usuarios:usuario_desativar"
        return self.client.post(reverse(rota, args=[usuario.pk]), **opcoes)

    def eventos_sucesso(self):
        return RegistroAuditoria.objects.filter(
            acao__in=[AcaoAuditoria.USUARIO_DESATIVADO, AcaoAuditoria.USUARIO_REATIVADO],
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        )

    def test_fluxo_desativa_preserva_dados_revoga_sessoes_e_reativa_com_novo_login(self):
        cliente_professor = Client()
        self.assertEqual(cliente_professor.post(reverse("login"), {
            "username": self.professor.username, "password": self.SENHA,
        }).status_code, 302)
        sessao_antiga = cliente_professor.session.session_key
        dados_antes = get_user_model().objects.values().get(pk=self.professor.pk)
        grupos_antes = list(self.professor.groups.values_list("pk", flat=True))
        self.professor.user_permissions.add(Permission.objects.get(codename="view_user"))

        resposta = self.alterar(follow=True)

        self.assertRedirects(resposta, self.lista)
        self.assertContains(resposta, "Usuário desativado. Os dados foram preservados.")
        self.professor.refresh_from_db()
        dados_antes["is_active"] = False
        self.assertEqual(get_user_model().objects.values().get(pk=self.professor.pk), dados_antes)
        self.assertEqual(list(self.professor.groups.values_list("pk", flat=True)), grupos_antes)
        self.assertTrue(self.professor.user_permissions.filter(codename="view_user").exists())
        self.assertTrue(self.professor.aceites_documentos_legais.exists())
        self.assertFalse(Session.objects.filter(pk=sessao_antiga).exists())
        self.assertTrue(Session.objects.filter(pk=self.client.session.session_key).exists())
        self.assertEqual(Client().post(reverse("login"), {
            "username": self.professor.username, "password": self.SENHA,
        }).status_code, 200)
        self.assertFalse(usuarios_funcionais_ativos().filter(pk=self.professor.pk).exists())

        self.alterar(ativo=True)

        self.professor.refresh_from_db()
        self.assertTrue(self.professor.is_active)
        self.assertEqual(cliente_professor.get(reverse("reservas:reserva_lista")).status_code, 302)
        self.assertEqual(cliente_professor.post(reverse("login"), {
            "username": self.professor.username, "password": self.SENHA,
        }).status_code, 302)
        self.assertEqual(cliente_professor.get(reverse("reservas:reserva_lista")).status_code, 200)
        self.assertEqual(self.eventos_sucesso().count(), 2)
        for evento in self.eventos_sucesso():
            self.assertEqual(evento.usuario_id, self.administrador.pk)
            self.assertEqual(evento.entidade, "auth.User")
            self.assertEqual(evento.entidade_id, str(self.professor.pk))

    def test_username_e_email_continuam_reservados_apos_desativacao(self):
        self.alterar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(username=self.professor.username)
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(username="duplicado", email="MARIA@example.com")
        form = CadastroUsuarioForm(data={"email": "MARIA@example.com"})
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um usuário", str(form.errors["email"]))

    def test_reativacao_tambem_revoga_sessao_anterior_a_inativacao_tecnica(self):
        cliente_professor = Client()
        cliente_professor.force_login(self.professor)
        sessao_antiga = cliente_professor.session.session_key
        get_user_model().objects.filter(pk=self.professor.pk).update(is_active=False)

        self.alterar(ativo=True)

        self.assertFalse(Session.objects.filter(pk=sessao_antiga).exists())
        self.assertEqual(cliente_professor.get(reverse("reservas:reserva_lista")).status_code, 302)

    def test_lista_filtra_situacao_busca_e_nao_exibe_contas_tecnicas_ou_anonimizadas(self):
        self.alterar()
        tecnico = get_user_model().objects.create_user(username="tecnico", is_staff=True)
        tecnico.groups.add(Group.objects.get(name="Professor"))
        get_user_model().objects.create_user(username="anonimizado-exemplo", is_active=False)
        resposta = self.client.get(self.lista, {"busca": "MARIA@EXAMPLE.COM", "situacao": "inativos"})
        self.assertQuerySetEqual(resposta.context["pagina"].object_list, [self.professor])
        self.assertContains(resposta, "Maria Silva")
        self.assertContains(resposta, reverse("usuarios:usuario_reativar", args=[self.professor.pk]))
        resposta = self.client.get(self.lista)
        self.assertNotContains(resposta, "anonimizado-exemplo")
        self.assertNotContains(resposta, "tecnico")
        resposta = self.client.get(self.lista, {"situacao": "ativos"})
        self.assertNotIn(self.professor, resposta.context["pagina"].object_list)

    def test_lista_pagina_e_escapa_conteudo(self):
        self.professor.first_name = "<script>alert(1)</script>"
        self.professor.save(update_fields=["first_name"])
        self.assertContains(self.client.get(self.lista), "&lt;script&gt;")
        for indice in range(16):
            usuario = get_user_model().objects.create_user(username=f"pagina-{indice:02}")
            usuario.groups.add(Group.objects.get(name="Professor"))
        resposta = self.client.get(self.lista, {"busca": "pagina-", "pagina": 2})
        self.assertEqual(len(resposta.context["pagina"]), 1)
        self.assertContains(resposta, "busca=pagina-")

    def test_anonimo_perfis_incorretos_e_permissao_individual_nao_autorizam(self):
        rotas = [self.lista, reverse("usuarios:usuario_desativar", args=[self.professor.pk]),
                 reverse("usuarios:usuario_reativar", args=[self.professor.pk])]
        self.client.logout()
        self.assertEqual(self.client.get(self.lista).status_code, 302)
        self.assertEqual(self.alterar().status_code, 302)
        individual = get_user_model().objects.create_user(username="individual")
        individual.user_permissions.add(*Permission.objects.filter(codename__in=["view_user", "change_user"]))
        tecnico = get_user_model().objects.create_user(username="staff", is_staff=True)
        tecnico.groups.add(Group.objects.get(name="Administrador"))
        superuser = get_user_model().objects.create_user(username="superuser", is_superuser=True)
        multiplo = get_user_model().objects.create_user(username="multiplo")
        multiplo.groups.add(*Group.objects.filter(name__in=["Administrador", "Professor"]))
        for usuario in (individual, tecnico, superuser, multiplo, self.professor, self.cenario["operador"]):
            registrar_aceite_vigente(usuario)
            self.client.force_login(usuario)
            for indice, rota in enumerate(rotas):
                with self.subTest(usuario=usuario.username, rota=rota):
                    resposta = self.client.get(rota) if indice == 0 else self.client.post(rota)
                    self.assertEqual(resposta.status_code, 403)
            resposta_inventario = self.client.get(reverse("inventario:equipamento_lista"))
            if resposta_inventario.status_code == 200:
                self.assertNotContains(resposta_inventario, f'href="{self.lista}"')
            else:
                self.assertEqual(resposta_inventario.status_code, 403)
        self.assertFalse(self.eventos_sucesso().exists())

    def test_consulta_e_alteracao_exigem_permissoes_distintas(self):
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(codename="change_user"))
        resposta = self.client.get(self.lista)
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, reverse("usuarios:usuario_desativar", args=[self.professor.pk]))
        self.assertEqual(self.alterar().status_code, 403)
        grupo.permissions.remove(Permission.objects.get(codename="view_user"))
        self.assertEqual(self.client.get(self.lista).status_code, 403)

    def test_get_csrf_e_usuario_inexistente(self):
        for rota in ("usuarios:usuario_desativar", "usuarios:usuario_reativar"):
            url = reverse(rota, args=[self.professor.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            cliente_csrf = Client(enforce_csrf_checks=True)
            cliente_csrf.force_login(self.administrador)
            self.assertEqual(cliente_csrf.post(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("usuarios:usuario_desativar", args=[999999])).status_code, 404)
        self.assertFalse(self.eventos_sucesso().exists())

    def test_impede_propria_conta_ultimo_administrador_e_contas_tecnicas(self):
        self.assertContains(self.alterar(self.administrador, follow=True), "último Administrador")
        outro = get_user_model().objects.create_user(username="outro-admin")
        outro.groups.add(Group.objects.get(name="Administrador"))
        self.assertContains(self.alterar(self.administrador, follow=True), "própria conta")
        self.alterar(outro)
        outro.refresh_from_db()
        self.assertFalse(outro.is_active)
        for campo in ("is_staff", "is_superuser"):
            tecnico = get_user_model().objects.create_user(username=campo, **{campo: True})
            self.assertContains(self.alterar(tecnico, follow=True), "Contas técnicas")
            tecnico.refresh_from_db()
            self.assertTrue(tecnico.is_active)

    def test_anonimizacao_nao_pode_ser_revertida_pelo_fluxo(self):
        call_command("anonimizar_usuario", self.professor.username, "--confirmar", stdout=StringIO())
        self.assertContains(self.alterar(ativo=True, follow=True), "Contas anonimizadas não podem ser reativadas")
        self.professor.refresh_from_db()
        self.assertFalse(self.professor.is_active)
        self.assertFalse(self.professor.has_usable_password())

    def test_reserva_pendente_bloqueia_e_cancelamento_libera_desativacao(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        self.assertContains(self.alterar(follow=True), "reservas ativas sem retirada")
        self.professor.refresh_from_db()
        self.assertTrue(self.professor.is_active)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)
        self.assertFalse(self.eventos_sucesso().exists())
        self.assertTrue(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.USUARIO_DESATIVADO, resultado="FALHA",
            usuario=self.administrador, entidade_id=str(self.professor.pk),
        ).exists())
        cancelar_reserva(professor=self.professor, reserva=reserva)
        self.alterar()
        self.professor.refresh_from_db()
        self.assertFalse(self.professor.is_active)
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())

    def test_reserva_expirada_nao_bloqueia(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        reserva.status = Reserva.Status.EXPIRADA
        reserva.save(update_fields=["status"])
        self.alterar()
        self.professor.refresh_from_db()
        self.assertFalse(self.professor.is_active)

    def test_retirada_existente_permite_desativar_e_devolver_com_historico(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        with patch("movimentacoes.services.timezone.now", return_value=reserva.inicio):
            retirada = registrar_retirada_reserva(operador=self.cenario["operador"], reserva_id=reserva.pk)[0]
        self.alterar()
        self.professor.refresh_from_db()
        self.assertFalse(self.professor.is_active)
        devolucao = registrar_devolucao(operador=self.cenario["operador"], retirada_id=retirada.pk)
        self.assertEqual(devolucao.destinatario_id, self.professor.pk)
        self.assertEqual(devolucao.retirada_origem_id, retirada.pk)
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())

    def test_servicos_revalidam_conta_desativada_mesmo_com_objeto_antigo(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        get_user_model().objects.filter(pk=self.professor.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            criar_reserva(
                professor=self.professor, tipo_equipamento=reserva.tipo_equipamento,
                local=reserva.local, quantidade=1, inicio=reserva.inicio,
                fim=reserva.inicio + timedelta(hours=1),
            )
        with self.assertRaises(ValidationError):
            cancelar_reserva(professor=self.professor, reserva=reserva)
        get_user_model().objects.filter(pk=self.administrador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            alterar_situacao_usuario(administrador=self.administrador, usuario_id=self.professor.pk, ativo=True)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_repeticao_nao_duplica_eventos_e_falha_na_auditoria_reverte_tudo(self):
        cliente_professor = Client()
        cliente_professor.force_login(self.professor)
        sessao = cliente_professor.session.session_key
        with patch("usuarios.services.registrar_evento", side_effect=IntegrityError):
            self.assertContains(self.alterar(follow=True), "Nenhuma alteração foi gravada")
        self.professor.refresh_from_db()
        self.assertTrue(self.professor.is_active)
        self.assertTrue(Session.objects.filter(pk=sessao).exists())
        self.alterar()
        self.alterar()
        self.assertEqual(self.eventos_sucesso().count(), 1)
        self.alterar(ativo=True)
        self.alterar(ativo=True)
        self.assertEqual(self.eventos_sucesso().count(), 2)


class ConcorrenciaSoftDeleteTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_administradores_nao_podem_desativar_um_ao_outro_simultaneamente(self):
        cenario = criar_cenario()
        primeiro = cenario["administrador"]
        segundo = get_user_model().objects.create_user(username="segundo-admin")
        segundo.groups.add(Group.objects.get(name="Administrador"))
        barreira = Barrier(2)

        def desativar(administrador_id, alvo_id):
            try:
                administrador = get_user_model().objects.get(pk=administrador_id)
                barreira.wait(timeout=10)
                try:
                    alterar_situacao_usuario(administrador=administrador, usuario_id=alvo_id, ativo=False)
                except (PermissionDenied, ValidationError):
                    return "negada"
                return "desativada"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            primeira = executor.submit(desativar, primeiro.pk, segundo.pk)
            segunda = executor.submit(desativar, segundo.pk, primeiro.pk)
            self.assertCountEqual([primeira.result(timeout=20), segunda.result(timeout=20)],
                                  ["desativada", "negada"])
        self.assertEqual(get_user_model().objects.filter(
            pk__in=[primeiro.pk, segundo.pk], is_active=True,
        ).count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_criar_reserva_e_desativar_professor_preservam_regra_de_pendencias(self):
        cenario = criar_cenario()
        reserva, _ = criar_reserva_alocada(cenario, quantidade=1)
        reserva.status = Reserva.Status.CANCELADA
        reserva.save(update_fields=["status"])
        barreira = Barrier(2)

        def executar(criando_reserva):
            try:
                professor = get_user_model().objects.get(pk=cenario["professor"].pk)
                administrador = get_user_model().objects.get(pk=cenario["administrador"].pk)
                barreira.wait(timeout=10)
                try:
                    if criando_reserva:
                        criar_reserva(professor=professor, tipo_equipamento=reserva.tipo_equipamento,
                                      local=reserva.local, quantidade=1, inicio=reserva.inicio, fim=reserva.fim,
                                      turma=reserva.turma, disciplina=reserva.disciplina, atividade=reserva.atividade)
                    else:
                        alterar_situacao_usuario(administrador=administrador, usuario_id=professor.pk, ativo=False)
                except ValidationError:
                    return "negada"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            criacao = executor.submit(executar, True)
            desativacao = executor.submit(executar, False)
            self.assertCountEqual([criacao.result(timeout=20), desativacao.result(timeout=20)],
                                  ["sucesso", "negada"])
        cenario["professor"].refresh_from_db()
        self.assertEqual(cenario["professor"].is_active, Reserva.objects.filter(status=Reserva.Status.ATIVA).exists())
