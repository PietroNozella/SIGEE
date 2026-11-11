from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from calendario.models import AlteracaoCalendario, CalendarioEscolar
from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.models import Movimentacao
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.brasilapi import ConsultaFeriados

from .permissoes import GRUPO_ADMINISTRADOR, GRUPO_PROFESSOR
from .sessoes import INICIO_SESSAO, ULTIMA_ATIVIDADE


@override_settings(SESSION_IDLE_TIMEOUT=1800, SESSION_ABSOLUTE_TIMEOUT=28800)
class TempoSessaoTests(TestCase):
    SENHA = "Senha-SIGEE-2026!"

    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.usuario = get_user_model().objects.create_user(username="sessao-admin", password=cls.SENHA)
        cls.usuario.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        registrar_aceite_vigente(cls.usuario)
        cls.professor = get_user_model().objects.create_user(username="sessao-professor")
        cls.professor.groups.add(Group.objects.get(name=GRUPO_PROFESSOR))
        registrar_aceite_vigente(cls.professor)
        categoria = Categoria.objects.create(nome="Sessão")
        tipo = TipoEquipamento.objects.create(nome="Notebook sessão", categoria=categoria)
        local = Local.objects.create(nome="Sala sessão")
        cls.equipamento = Equipamento.objects.create(numero_patrimonio="SESS-01", tipo=tipo, local=local)

    def setUp(self):
        self.agora = timezone.now().timestamp()
        self.relogio = patch("usuarios.sessoes.agora_em_segundos", return_value=self.agora)
        self.tempo = self.relogio.start()
        self.addCleanup(self.relogio.stop)
        self.client.force_login(self.usuario)
        self.lista = reverse("inventario:equipamento_lista")
        self.status = reverse("usuarios:sessao_status")

    def ajustar_horarios(self, *, inicio, atividade):
        sessao = self.client.session
        sessao[INICIO_SESSAO] = inicio
        sessao[ULTIMA_ATIVIDADE] = atividade
        sessao.save()

    def assertExpirada(self, response):
        self.assertEqual(response.status_code, 302)
        destino = urlsplit(response.url)
        self.assertEqual(destino.path, reverse("login"))
        self.assertEqual(parse_qs(destino.query)["sessao"], ["expirada"])
        self.assertNotIn(SESSION_KEY, self.client.session)
        return parse_qs(destino.query)

    def test_login_inicia_horarios_e_prazo_nativo_absoluto(self):
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": self.usuario.username, "password": self.SENHA})
        self.assertEqual(response.status_code, 302)
        sessao = self.client.session
        self.assertEqual(sessao[INICIO_SESSAO], self.agora)
        self.assertEqual(sessao[ULTIMA_ATIVIDADE], self.agora)
        registro = Session.objects.get(session_key=sessao.session_key)
        self.assertAlmostEqual(registro.expire_date.timestamp() - self.agora, 28800, delta=2)
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]["httponly"])

    def test_navegacao_renova_inatividade_sem_mudar_inicio_ou_prazo_absoluto(self):
        prazo = self.client.session.get_expiry_date()
        for instante in (1799, 3500):
            self.tempo.return_value = self.agora + instante
            response = self.client.get(self.lista)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora + instante)
            self.assertEqual(self.client.session[INICIO_SESSAO], self.agora)
            self.assertEqual(self.client.session.get_expiry_date(), prazo)

    def test_expira_exatamente_no_limite_de_inatividade_e_invalida_cookie_antigo(self):
        chave = self.client.session.session_key
        self.tempo.return_value = self.agora + 1800
        response = self.client.get(self.lista + "?busca=Notebook")
        parametros = self.assertExpirada(response)
        self.assertEqual(parametros["next"], [self.lista + "?busca=Notebook"])
        self.assertFalse(Session.objects.filter(session_key=chave).exists())
        self.assertEqual(RegistroAuditoria.objects.filter(usuario=self.usuario, acao=AcaoAuditoria.SESSAO_EXPIRADA).count(), 1)
        outro = Client()
        outro.cookies[settings.SESSION_COOKIE_NAME] = chave
        self.assertEqual(outro.get(self.status).status_code, 401)

    def test_atividade_nao_ultrapassa_o_limite_absoluto(self):
        self.ajustar_horarios(inicio=self.agora - 28799, atividade=self.agora - 10)
        self.assertEqual(self.client.get(self.lista).status_code, 200)
        self.tempo.return_value = self.agora + 1
        self.assertExpirada(self.client.get(self.lista))

    def test_consulta_periodica_nao_renova_prazo_nem_grava_sessao(self):
        for instante in (60, 900, 1799):
            self.tempo.return_value = self.agora + instante
            response = self.client.get(self.status)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["segundos_restantes"], 1800 - instante)
            self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora)
            self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)
            self.assertIn("no-store", response["Cache-Control"])
        self.tempo.return_value = self.agora + 1800
        response = self.client.get(self.status)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["codigo"], "sessao_expirada")

    def test_feriados_nao_renovam_mesmo_sem_cabecalho_ajax(self):
        for usuario, nome, consulta in (
            (self.usuario, "calendario:feriados", "calendario.views.feriados_para_calendario"),
            (self.professor, "reservas:reserva_feriados", "reservas.views.feriados_para_calendario"),
        ):
            with self.subTest(rota=nome), patch(consulta, return_value={"completa": True, "feriados": []}):
                self.tempo.return_value = self.agora
                self.client.force_login(usuario)
                self.tempo.return_value = self.agora + 900
                self.assertEqual(self.client.get(reverse(nome), {"ano": 2026}).status_code, 200)
                self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora)
        self.assertEqual(self.client.get(self.status).json()["segundos_restantes"], 900)

    @patch("reservas.views.consultar_feriados_no_periodo", return_value=ConsultaFeriados(feriados=(), completa=True, anos_indisponiveis=()))
    @patch("reservas.views.resumo_disponibilidade", return_value={"disponiveis": 1, "cota": {"limite": None}})
    def test_disponibilidade_nao_renova_mesmo_sem_cabecalho_ajax(self, disponibilidade, feriados):
        self.client.force_login(self.professor)
        self.tempo.return_value = self.agora + 900
        hoje = timezone.localdate()
        data = hoje + timedelta(days=(7 - hoje.weekday()) % 7 or 7)
        response = self.client.get(reverse("reservas:reserva_disponibilidade"), {
            "tipo_equipamento": self.equipamento.tipo_id, "local": self.equipamento.local_id,
            "data_reserva": data.isoformat(), "hora_inicio": "09:00", "hora_fim": "10:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["disponiveis"], 1)
        self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora)

    def test_consulta_json_em_pagina_nao_renova_atividade(self):
        self.tempo.return_value = self.agora + 900
        self.assertEqual(self.client.get(self.lista, HTTP_ACCEPT="application/json").status_code, 200)
        self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora)

    def test_fetch_sem_accept_json_nao_renova_atividade(self):
        self.tempo.return_value = self.agora + 900
        self.assertEqual(self.client.get(self.lista, HTTP_SEC_FETCH_MODE="same-origin").status_code, 200)
        self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora)

    def test_ajax_expirado_recebe_401_sem_html_de_login(self):
        self.tempo.return_value = self.agora + 1800
        response = self.client.get(reverse("reservas:reserva_disponibilidade"), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["codigo"], "sessao_expirada")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("next", parse_qs(urlsplit(response.json()["login_url"]).query))

    def test_post_expirado_nao_exclui_equipamento_nem_e_retomado_apos_login(self):
        self.tempo.return_value = self.agora + 1800
        url = reverse("inventario:equipamento_excluir", args=[self.equipamento.pk])
        response = self.client.post(url)
        self.assertNotIn("next", self.assertExpirada(response))
        self.assertTrue(Equipamento.objects.filter(pk=self.equipamento.pk, ativo=True).exists())
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.EQUIPAMENTO_EXCLUIDO).exists())
        login = self.client.get(response.url)
        self.assertContains(login, "Sua sessão terminou.")
        self.assertNotContains(login, 'name="next"')
        response = self.client.post(response.url, {"username": self.usuario.username, "password": self.SENHA})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Equipamento.objects.filter(pk=self.equipamento.pk).exists())
        self.assertEqual(self.client.session[INICIO_SESSAO], self.agora + 1800)

    def test_configuracao_nao_e_alterada_com_sessao_expirada(self):
        calendario = CalendarioEscolar.objects.create(pk=1)
        self.tempo.return_value = self.agora + 1800
        response = self.client.post(reverse("calendario:intervalo"), {
            "intervalo_minutos": 15, "motivo": "Conferência", "versao": calendario.versao,
        })
        self.assertExpirada(response)
        calendario.refresh_from_db()
        self.assertEqual(calendario.intervalo_minutos, 5)
        self.assertFalse(AlteracaoCalendario.objects.exists())
        self.client.force_login(self.usuario)
        response = self.client.post(reverse("calendario:intervalo"), {
            "intervalo_minutos": 15, "motivo": "Conferência", "versao": calendario.versao,
        })
        self.assertEqual(response.status_code, 302)
        calendario.refresh_from_db()
        self.assertEqual(calendario.intervalo_minutos, 15)
        self.assertEqual(AlteracaoCalendario.objects.count(), 1)

    def test_post_valido_renova_atividade(self):
        self.tempo.return_value = self.agora + 900
        response = self.client.post(reverse("inventario:equipamento_excluir", args=[self.equipamento.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Equipamento.objects.filter(pk=self.equipamento.pk).exists())
        self.assertEqual(self.client.session[ULTIMA_ATIVIDADE], self.agora + 900)

    def test_csrf_invalido_e_404_nao_renovam_atividade(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.cookies[settings.SESSION_COOKIE_NAME] = self.client.session.session_key
        self.tempo.return_value = self.agora + 900
        response = cliente.post(reverse("inventario:equipamento_excluir", args=[self.equipamento.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(cliente.get("/rota-inexistente/").status_code, 404)
        self.assertEqual(cliente.session[ULTIMA_ATIVIDADE], self.agora)
        self.assertTrue(Equipamento.objects.filter(pk=self.equipamento.pk).exists())

    def test_sessao_legada_exige_novo_login(self):
        sessao = self.client.session
        del sessao[INICIO_SESSAO]
        del sessao[ULTIMA_ATIVIDADE]
        sessao.save()
        self.assertExpirada(self.client.get(self.lista))

    def test_sessao_nativamente_expirada_informa_login_no_json(self):
        Session.objects.filter(session_key=self.client.session.session_key).update(expire_date=timezone.now() - timedelta(seconds=1))
        response = self.client.get(self.status)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["codigo"], "sessao_expirada")

    def test_login_e_documentos_publicos_continuam_disponiveis(self):
        self.tempo.return_value = self.agora + 1800
        self.assertContains(self.client.get(reverse("login")), "Sua sessão terminou.")
        self.assertEqual(self.client.get(reverse("password_reset")).status_code, 200)
        self.assertEqual(self.client.get(reverse("legal:termos_de_uso")).status_code, 200)

    def test_sessao_status_funciona_antes_do_aceite_legal(self):
        usuario = get_user_model().objects.create_user(username="sessao-sem-aceite")
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(self.status).status_code, 200)
        self.assertRedirects(self.client.get(self.lista), reverse("legal:aceite_documentos") + "?next=%2Fequipamentos%2F", fetch_redirect_response=False)

    def test_abas_compartilham_atividade_sem_status_renovar_sessao(self):
        outra_aba = Client()
        outra_aba.cookies[settings.SESSION_COOKIE_NAME] = self.client.session.session_key
        self.tempo.return_value = self.agora + 900
        self.assertEqual(self.client.get(self.lista).status_code, 200)
        self.tempo.return_value = self.agora + 1800
        self.assertEqual(outra_aba.get(self.status).json()["segundos_restantes"], 900)
        self.tempo.return_value = self.agora + 2700
        self.assertEqual(outra_aba.get(self.status).status_code, 401)

    @override_settings(SESSION_IDLE_TIMEOUT=60, SESSION_ABSOLUTE_TIMEOUT=120)
    def test_limites_configurados_sao_respeitados(self):
        self.client.force_login(self.usuario)
        self.tempo.return_value = self.agora + 60
        self.assertEqual(self.client.get(self.status).status_code, 401)
        self.client.force_login(self.usuario)
        self.ajustar_horarios(inicio=self.agora - 60, atividade=self.agora + 59)
        self.assertEqual(self.client.get(self.status).status_code, 401)

    @override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True)
    def test_cookie_de_navegador_continua_sujeito_ao_limite_absoluto(self):
        self.client.force_login(self.usuario)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.ajustar_horarios(inicio=self.agora - 28800, atividade=self.agora - 1)
        self.assertEqual(self.client.get(self.status).status_code, 401)

    def test_logout_manual_preserva_evento_e_exige_novo_login(self):
        chave = self.client.session.session_key
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)
        self.assertFalse(Session.objects.filter(session_key=chave).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(usuario=self.usuario, acao=AcaoAuditoria.LOGOUT_REALIZADO).exists())
        self.assertEqual(self.client.get(self.status).status_code, 401)


class MovimentacoesSessaoExpiradaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario)

    def setUp(self):
        relogio = patch("django.utils.timezone.now", return_value=self.reserva.inicio + timedelta(minutes=5))
        relogio.start()
        self.addCleanup(relogio.stop)
        self.operador = self.cenario["operador"]
        self.client.force_login(self.operador)

    def expirar_sessao(self):
        sessao = self.client.session
        sessao[INICIO_SESSAO] -= settings.SESSION_IDLE_TIMEOUT
        sessao[ULTIMA_ATIVIDADE] -= settings.SESSION_IDLE_TIMEOUT
        sessao.save()

    def test_entrega_expirada_nao_grava_e_reenvio_autenticado_nao_duplica(self):
        url = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
        conferencia = self.client.get(url).context["form"].initial["conferencia"]
        self.expirar_sessao()
        response = self.client.post(url, {"conferencia": conferencia})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))
        self.assertFalse(Movimentacao.objects.exists())
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades], situacao="DISPONIVEL").count(), 3)

        self.client.force_login(self.operador)
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"conferencia": conferencia}).status_code, 302)
        self.assertEqual(Movimentacao.objects.filter(tipo="RETIRADA").count(), 3)

    def test_devolucao_parcial_expirada_nao_libera_unidades(self):
        retiradas = registrar_entrega_conferida(operador=self.operador, reserva_id=self.reserva.pk)
        url = reverse("movimentacoes:devolucao_registrar", args=[retiradas[0].pk])
        self.expirar_sessao()
        response = self.client.post(url, {"retiradas": [retiradas[0].pk]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))
        self.assertFalse(Movimentacao.objects.filter(tipo="DEVOLUCAO").exists())
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades], situacao="EM_USO").count(), 3)
