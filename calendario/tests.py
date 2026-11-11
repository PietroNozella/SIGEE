from datetime import date, datetime, time, timedelta
from io import StringIO
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.models import Movimentacao
from movimentacoes.services import registrar_devolucoes
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva
from reservas.brasilapi import ConsultaFeriados, Feriado
from reservas.services import criar_reserva

from .models import AlteracaoCalendario, CalendarioEscolar, FaixaHorario, RegraCalendario
from .services import dias_para_agendamento, regras_vigentes, reservas_afetadas, salvar_regra, validar_periodo_reserva


class CalendarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario, quantidade=1)

    def setUp(self):
        self.admin = self.cenario["administrador"]
        self.inicio = self.reserva.inicio
        self.relogio = patch("django.utils.timezone.now", return_value=self.inicio - timedelta(hours=1))
        self.relogio.start()
        self.addCleanup(self.relogio.stop)
        self.client.force_login(self.admin)

    def configurar(self, *, finalidade="USO", dia=0, data=None, inteiro=False, faixas=(), **outros):
        chave = {"finalidade": finalidade, "data": data, "dia_semana": None if data else dia}
        regra = RegraCalendario.objects.filter(**chave).first() or RegraCalendario(**chave)
        regra.dia_inteiro = inteiro
        return salvar_regra(usuario=self.admin, regra=regra,
            faixas=[FaixaHorario(inicio=time.fromisoformat(a), fim=time.fromisoformat(b)) for a, b in faixas],
            motivo="Ajuste do funcionamento da escola.", versao=CalendarioEscolar.objects.filter(pk=1).values_list("versao", flat=True).first() or 1, **outros)

    def criar_agendamento(self, inicio=None, fim=None):
        return criar_reserva(professor=self.cenario["professor"],
            tipo_equipamento=self.reserva.tipo_equipamento, local=self.reserva.local,
            quantidade=1, inicio=inicio or self.inicio, fim=fim or self.inicio + timedelta(hours=1),
            turma=self.reserva.turma, disciplina=self.reserva.disciplina, atividade=self.reserva.atividade)

    def dados_form(self, *, modo="FAIXAS", finalidade="USO", **outros):
        return {"finalidade": finalidade, "funcionamento": modo, "motivo": "Novo turno da escola.",
            "versao": CalendarioEscolar.objects.filter(pk=1).values_list("versao", flat=True).first() or 1,
            "faixas-TOTAL_FORMS": "2", "faixas-INITIAL_FORMS": "0",
            "faixas-0-inicio": "07:00", "faixas-0-fim": "12:00",
            "faixas-1-inicio": "13:00", "faixas-1-fim": "18:00", **outros}

    def test_padrao_preserva_dias_uteis_e_fecha_fim_de_semana(self):
        validar_periodo_reserva(self.inicio, self.inicio + timedelta(hours=1))
        with self.assertRaisesMessage(ValidationError, "sábado ou domingo"):
            validar_periodo_reserva(self.inicio + timedelta(days=5), self.inicio + timedelta(days=5, hours=1))
        self.assertFalse(RegraCalendario.objects.exists())

    def test_faixas_separadas_e_intervalo_de_almoco(self):
        self.configurar(faixas=[("07:00", "12:00"), ("13:00", "19:00")])
        self.configurar(finalidade="ATENDIMENTO", faixas=[("08:00", "18:00")])
        validar_periodo_reserva(self.inicio, self.inicio + timedelta(hours=1))
        for hora, fim, mensagem in ((7, 9, "retirada"), (11, 14, "calendário de uso"), (17, 19, "devolução prevista")):
            with self.subTest(hora=hora), self.assertRaisesMessage(ValidationError, mensagem):
                validar_periodo_reserva(self.inicio.replace(hour=hora), self.inicio.replace(hour=fim))

    def test_sabado_exige_uso_e_atendimento_liberados(self):
        sabado = self.inicio + timedelta(days=5)
        self.configurar(data=sabado.date(), inteiro=True)
        with self.assertRaisesMessage(ValidationError, "atendimento"):
            validar_periodo_reserva(sabado, sabado + timedelta(hours=1))
        self.configurar(finalidade="ATENDIMENTO", data=sabado.date(), inteiro=True)
        reserva = self.criar_agendamento(sabado, sabado + timedelta(hours=1))
        self.assertTrue(reserva.calendario_confirmado)

    def test_excecao_tem_prioridade_e_remocao_restaura_semana(self):
        self.configurar(data=self.inicio.date())
        with self.assertRaises(ValidationError):
            self.criar_agendamento()
        regra = RegraCalendario.objects.get(data=self.inicio.date())
        self.configurar(data=self.inicio.date(), remover=True)
        self.assertFalse(RegraCalendario.objects.filter(pk=regra.pk).exists())
        self.criar_agendamento()
        self.assertEqual(AlteracaoCalendario.objects.count(), 2)

    def test_fechamento_lista_reservas_sem_cancela_las(self):
        self.configurar(data=self.inicio.date())
        self.assertEqual([r.pk for r in reservas_afetadas()], [self.reserva.pk])
        resposta = self.client.get(reverse("calendario:calendario_escola"))
        self.assertContains(resposta, f"Reserva #{self.reserva.pk}")
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.ATIVA)
        self.assertFalse(Movimentacao.objects.exists())

    def test_reserva_confirmada_preserva_agenda_e_entrega_apos_mudanca(self):
        reserva = self.criar_agendamento()
        snapshot = reserva.calendario_confirmado.copy()
        self.configurar(data=self.inicio.date())
        reserva.full_clean()
        with patch("django.utils.timezone.now", return_value=self.inicio + timedelta(minutes=5)):
            entregas = registrar_entrega_conferida(operador=self.cenario["operador"], reserva_id=reserva.pk)
        self.assertEqual(len(entregas), 1)
        reserva.refresh_from_db()
        self.assertEqual(reserva.calendario_confirmado, snapshot)

    def test_retirada_fora_do_atendimento_recusada_e_devolucao_permitida(self):
        self.configurar(finalidade="ATENDIMENTO", faixas=[("09:00", "09:10"), ("09:20", "10:00")])
        reserva = self.criar_agendamento()
        with patch("django.utils.timezone.now", return_value=self.inicio + timedelta(minutes=15)):
            with self.assertRaisesMessage(ValidationError, "fora do atendimento"):
                registrar_entrega_conferida(operador=self.cenario["operador"], reserva_id=reserva.pk)
        with patch("django.utils.timezone.now", return_value=self.inicio + timedelta(minutes=5)):
            entregas = registrar_entrega_conferida(operador=self.cenario["operador"], reserva_id=reserva.pk)
        self.configurar(finalidade="ATENDIMENTO", data=self.inicio.date())
        with patch("django.utils.timezone.now", return_value=self.inicio + timedelta(hours=3)):
            devolucoes = registrar_devolucoes(operador=self.cenario["operador"], retirada_id=entregas[0].pk, retiradas_ids=[entregas[0].pk])
        self.assertEqual(len(devolucoes), 1)

    def test_confirmacao_apos_tolerancia_expira_mesmo_durante_pausa_de_atendimento(self):
        self.configurar(finalidade="ATENDIMENTO", faixas=[("09:00", "09:10"), ("10:00", "11:00")])
        reserva = self.criar_agendamento()
        self.client.force_login(self.cenario["operador"])
        url = reverse("movimentacoes:retirada_reserva_registrar", args=[reserva.pk])
        conferencia = self.client.get(url).context["form"].initial["conferencia"]

        with patch("django.utils.timezone.now", return_value=self.inicio + Reserva.TOLERANCIA_RETIRADA):
            self.client.force_login(self.cenario["operador"])
            resposta = self.client.post(url, {"conferencia": conferencia})

        self.assertContains(resposta, "expirou após os 30 minutos")
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.EXPIRADA)
        self.assertFalse(Movimentacao.objects.filter(reserva=reserva).exists())
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_EXPIRADA).count(), 1)

    def test_meia_noite_e_faixas_adjacentes(self):
        self.configurar(faixas=[("00:00", "12:00"), ("12:00", "00:00")])
        validar_periodo_reserva(self.inicio.replace(hour=11), self.inicio.replace(hour=13))
        validar_periodo_reserva(self.inicio.replace(hour=23), (self.inicio + timedelta(days=1)).replace(hour=0))

    def test_faixas_sobrepostas_ou_invertidas_nao_gravam(self):
        for faixas in ([('10:00', '09:00')], [('07:00', '12:00'), ('11:00', '13:00')]):
            with self.subTest(faixas=faixas), self.assertRaises(ValidationError):
                self.configurar(faixas=faixas)
        self.assertFalse(RegraCalendario.objects.exists())
        self.assertFalse(AlteracaoCalendario.objects.exists())

    def test_auditoria_preserva_motivo_e_antes_depois_e_rollback(self):
        alteracao = self.configurar(faixas=[("07:00", "18:00")])
        self.assertEqual(alteracao.usuario_id, self.admin.pk)
        self.assertEqual(alteracao.novo["resumo"], "07:00 às 18:00")
        self.assertEqual(RegistroAuditoria.objects.get(acao=AcaoAuditoria.CALENDARIO_ALTERADO).entidade_id, str(alteracao.pk))
        with patch("calendario.services.registrar_evento", side_effect=RuntimeError("Auditoria indisponível")):
            with self.assertRaises(RuntimeError):
                self.configurar()
        self.assertTrue(FaixaHorario.objects.exists())
        self.assertEqual(AlteracaoCalendario.objects.count(), 1)

    def test_versao_desatualizada_nao_sobrescreve_alteracao(self):
        self.configurar(inteiro=True)
        regra = RegraCalendario.objects.get()
        regra.dia_inteiro = False
        with self.assertRaisesMessage(ValidationError, "outro Administrador"):
            salvar_regra(usuario=self.admin, regra=regra, faixas=[], motivo="Outro horário", versao=1)
        regra.refresh_from_db()
        self.assertTrue(regra.dia_inteiro)

    def test_so_admin_configura_mesmo_com_permissao_forgada(self):
        permissao = Permission.objects.get(content_type__app_label="calendario", codename="configurar_calendario")
        for perfil in ("professor", "operador"):
            usuario = self.cenario[perfil]
            usuario.user_permissions.add(permissao)
            self.client.force_login(usuario)
            for rota in (reverse("calendario:calendario_escola"), reverse("calendario:regra_semanal", args=["USO", 0]), reverse("calendario:excecao_nova")):
                with self.subTest(perfil=perfil, rota=rota):
                    self.assertEqual(self.client.get(rota).status_code, 403)
                    self.assertEqual(self.client.post(rota, self.dados_form()).status_code, 405 if rota == reverse("calendario:calendario_escola") else 403)
            with self.assertRaises(PermissionDenied):
                salvar_regra(usuario=usuario, regra=RegraCalendario(finalidade="USO", dia_semana=0), faixas=[], motivo="Teste", versao=1)
        self.assertFalse(RegraCalendario.objects.exists())

    def test_admin_sem_permissao_revogada_anonimo_csrf_e_metodos(self):
        url = reverse("calendario:regra_semanal", args=["USO", 0])
        self.assertEqual(self.client.put(url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url, self.dados_form()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.admin.groups.clear()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, self.dados_form()).status_code, 403)

    def test_formulario_cria_edita_sem_perder_faixas_inalteradas(self):
        url = reverse("calendario:regra_semanal", args=["USO", 0])
        self.assertEqual(self.client.post(url, self.dados_form()).status_code, 302)
        regra = RegraCalendario.objects.get()
        faixas = list(regra.faixas.all())
        dados = self.dados_form(**{"faixas-INITIAL_FORMS": "2", "faixas-0-id": faixas[0].pk, "faixas-1-id": faixas[1].pk})
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(regra.faixas.count(), 2)

    def test_formularios_invalidos_nao_alteram_calendario(self):
        url = reverse("calendario:regra_semanal", args=["USO", 0])
        casos = [{"motivo": " "}, {"faixas-1-inicio": "11:00"}, {"faixas-0-inicio": "", "faixas-0-fim": "", "faixas-1-inicio": "", "faixas-1-fim": ""}]
        for dados in casos:
            with self.subTest(dados=dados):
                self.assertEqual(self.client.post(url, self.dados_form(**dados)).status_code, 200)
                self.assertFalse(RegraCalendario.objects.exists())

    def test_post_direto_api_e_calendario_professor_respeitam_fechamento(self):
        self.configurar(data=self.inicio.date())
        self.client.force_login(self.cenario["professor"])
        dados = {"tipo_equipamento": self.reserva.tipo_equipamento_id, "local": self.reserva.local_id,
            "quantidade": 1, "data_reserva": self.inicio.date().isoformat(), "hora_inicio": "09:00", "hora_fim": "10:00",
            "turma": self.reserva.turma_id, "disciplina": self.reserva.disciplina_id, "atividade": self.reserva.atividade_id}
        self.assertContains(self.client.post(reverse("reservas:reserva_nova"), dados), "fora do calendário")
        self.assertEqual(self.client.get(reverse("reservas:reserva_disponibilidade"), dados).status_code, 400)
        self.assertFalse(dias_para_agendamento()[self.inicio.date().isoformat()]["aberto"])
        self.assertContains(self.client.get(reverse("reservas:reserva_nova")), '"aberto": false')

    def test_get_nao_grava_e_menu_e_exclusivo_admin(self):
        resposta = self.client.get(reverse("calendario:calendario_escola"))
        self.assertContains(resposta, "Configurações da escola")
        self.assertContains(resposta, 'aria-current="page"')
        self.assertFalse(AlteracaoCalendario.objects.exists())
        self.assertFalse(RegraCalendario.objects.exists())
        for perfil in ("professor", "operador"):
            self.client.force_login(self.cenario[perfil])
            self.assertNotContains(self.client.get(reverse("inventario:equipamento_lista")), 'title="Configurações da escola"')

    def test_secoes_separam_calendario_regras_e_historico(self):
        url = reverse("calendario:calendario_escola")
        calendario = self.client.get(url)
        self.assertContains(calendario, 'id="semana-heading"')
        self.assertNotContains(calendario, 'id="regras-heading"')
        regras = self.client.get(url, {"secao": "reservas"})
        self.assertContains(regras, "Configurar intervalo")
        self.assertContains(regras, "Configurar cotas")
        self.assertNotContains(regras, 'id="semana-heading"')
        self.configurar(data=self.inicio.date())
        historico = self.client.get(url, {"secao": "historico"})
        self.assertContains(historico, "Ajuste do funcionamento da escola.")
        self.assertContains(historico, '?secao=calendario#afetadas-heading')
        self.assertNotContains(historico, 'id="semana-heading"')
        self.assertNotContains(historico, 'id="regras-heading"')

    def test_secao_desconhecida_retorna_calendario_sem_alterar_regras(self):
        resposta = self.client.get(reverse("calendario:calendario_escola"), {"secao": "desconhecida"})
        self.assertContains(resposta, 'id="semana-heading"')
        self.assertFalse(AlteracaoCalendario.objects.exists())

    def test_erro_de_funcionamento_aponta_para_grupo_de_radios(self):
        resposta = self.client.post(reverse("calendario:regra_semanal", args=["USO", 0]), self.dados_form(modo="INVALIDO"))
        self.assertContains(resposta, 'href="#funcionamento-group"')
        self.assertContains(resposta, 'aria-describedby="id_funcionamento_error"')
        self.assertNotContains(resposta, 'href="#"')

    def test_comando_perfis_preserva_exclusividade_da_configuracao(self):
        call_command("configurar_perfis", stdout=StringIO())
        self.assertTrue(self.admin.has_perm("calendario.configurar_calendario"))
        self.assertFalse(self.cenario["operador"].has_perm("calendario.configurar_calendario"))

    def test_excecao_bloqueia_data_passada_no_seletor_post_e_servico(self):
        url = reverse("calendario:excecao_nova")
        hoje = timezone.localdate()
        resposta = self.client.get(url)
        self.assertEqual(resposta.context["form"].fields["data"].widget.attrs["min"], hoje.isoformat())
        ontem = hoje - timedelta(days=1)
        resposta = self.client.post(url, self.dados_form(modo="INTEIRO", data=ontem.isoformat()))
        self.assertContains(resposta, "Escolha hoje ou uma data futura")
        with self.assertRaisesMessage(ValidationError, "Escolha hoje ou uma data futura"):
            self.configurar(data=ontem, inteiro=True)
        self.assertFalse(RegraCalendario.objects.exists())
        self.assertFalse(AlteracaoCalendario.objects.exists())

    def test_excecao_permite_hoje_e_datas_futuras(self):
        url = reverse("calendario:excecao_nova")
        for dias in (0, 1):
            data = timezone.localdate() + timedelta(days=dias)
            with self.subTest(data=data):
                resposta = self.client.post(url, self.dados_form(modo="INTEIRO", data=data.isoformat()))
                self.assertRedirects(resposta, reverse("calendario:calendario_escola"))
                self.assertTrue(RegraCalendario.objects.filter(data=data, dia_inteiro=True).exists())

    @patch("reservas.brasilapi.consultar_feriados_no_periodo")
    def test_admin_consulta_feriados_sem_alterar_funcionamento(self, consultar):
        consultar.return_value = ConsultaFeriados(
            feriados=(Feriado(data=date(2026, 11, 20), nome="Dia Nacional de Zumbi e da Consciência Negra"),),
            completa=True, anos_indisponiveis=(),
        )
        resposta = self.client.get(reverse("calendario:feriados"), {"ano": "2026"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"completa": True, "feriados": [
            {"data": "2026-11-20", "nome": "Dia Nacional de Zumbi e da Consciência Negra"},
        ]})
        consultar.assert_called_once_with(date(2026, 1, 1), date(2026, 12, 31))
        self.assertFalse(RegraCalendario.objects.exists())
        self.assertFalse(AlteracaoCalendario.objects.exists())

    @patch("reservas.brasilapi.urlopen", side_effect=URLError("Consulta indisponível"))
    def test_falha_brasilapi_informa_indisponibilidade_sem_impedir_excecao(self, consultar):
        resposta = self.client.get(reverse("calendario:feriados"), {"ano": "2026"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"completa": False, "feriados": []})
        resposta = self.client.post(reverse("calendario:excecao_nova"),
            self.dados_form(modo="INTEIRO", data=timezone.localdate().isoformat()))
        self.assertRedirects(resposta, reverse("calendario:calendario_escola"))
        self.assertEqual(consultar.call_count, 1)

    @patch("reservas.brasilapi.urlopen")
    def test_consulta_admin_rejeita_ano_invalido_antes_de_acessar_api(self, consultar):
        for ano in ("", "invalido", "0", "-1", "10000"):
            with self.subTest(ano=ano):
                resposta = self.client.get(reverse("calendario:feriados"), {"ano": ano})
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json(), {"erro": "Informe um ano válido."})
        consultar.assert_not_called()

    @patch("reservas.brasilapi.urlopen")
    def test_consulta_feriados_admin_exige_perfil_e_permissao(self, consultar):
        url = reverse("calendario:feriados")
        self.assertEqual(self.client.post(url, {"ano": "2026"}).status_code, 405)
        permissao = Permission.objects.get(content_type__app_label="calendario", codename="configurar_calendario")
        for perfil in ("professor", "operador"):
            usuario = self.cenario[perfil]
            usuario.user_permissions.add(permissao)
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(url, {"ano": "2026"}).status_code, 403)
        self.admin.groups.clear()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url, {"ano": "2026"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url, {"ano": "2026"}).status_code, 401)
        consultar.assert_not_called()

    def test_seletor_de_excecao_reutiliza_calendario_com_feriados(self):
        resposta = self.client.get(reverse("calendario:excecao_nova"))
        self.assertContains(resposta, 'data-holidays-url="' + reverse("calendario:feriados") + '"')
        self.assertContains(resposta, "data-calendar-exceptions")
        self.assertContains(resposta, "Feriado nacional")
        self.assertContains(resposta, "Escolher data da exceção")
        self.assertIsNone(resposta.context["form"].fields["data"].widget.attrs.get("max"))
