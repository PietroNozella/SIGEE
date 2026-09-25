import json
from datetime import date, datetime, time, timedelta
from io import BytesIO, StringIO
from unittest.mock import call, patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from usuarios.permissoes import GRUPO_OPERADOR, GRUPO_PROFESSOR

from .brasilapi import (
    BRASILAPI_TIMEOUT_SEGUNDOS,
    ConsultaBrasilAPIError,
    ConsultaFeriados,
    Feriado,
    consultar_feriados_do_ano,
    consultar_feriados_no_periodo,
)
from .models import Reserva, ReservaEquipamento
from .services import (
    cancelar_reserva,
    consultar_disponibilidade,
    criar_reserva,
    expirar_reservas_vencidas,
)


class RespostaHTTPFake(BytesIO):
    def __init__(self, conteudo, status=200):
        super().__init__(conteudo)
        self.status = status

    def getcode(self):
        return self.status


def resposta_json(conteudo, status=200):
    return RespostaHTTPFake(json.dumps(conteudo).encode(), status=status)


class ReservaBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.categoria = Categoria.objects.create(nome="Categoria para reservas")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Notebook Dell Latitude 5420")
        cls.local = Local.objects.create(nome="Local para reservas")
        cls.professor = get_user_model().objects.create_user(username="professor-reservas", password="senha-segura-123")
        cls.professor.groups.add(Group.objects.get(name=GRUPO_PROFESSOR))
        cls.operador = get_user_model().objects.create_user(username="operador-reservas", password="senha-segura-123")
        cls.operador.groups.add(Group.objects.get(name=GRUPO_OPERADOR))

    def setUp(self):
        self.equipamento = self.criar_equipamento("RES-001")
        self.inicio = self.proxima_segunda()
        self.fim = self.inicio + timedelta(hours=2)

    def criar_equipamento(self, patrimonio, **alteracoes):
        dados = {"numero_patrimonio": patrimonio, "tipo": self.tipo, "local": self.local}
        dados.update(alteracoes)
        return Equipamento.objects.create(**dados)

    @staticmethod
    def proxima_segunda():
        agora = timezone.localtime()
        dias = (7 - agora.weekday()) % 7 or 7
        return timezone.make_aware(datetime.combine(agora.date() + timedelta(days=dias), time(9)))

    def nova_reserva(self, **alteracoes):
        dados = {"professor": self.professor, "tipo_equipamento": self.tipo, "local": self.local, "quantidade": 1, "inicio": self.inicio, "fim": self.fim}
        dados.update(alteracoes)
        return Reserva(**dados)

    def salvar_reserva_com_itens(self, *, professor=None, equipamentos=None, inicio=None, fim=None, status=Reserva.Status.ATIVA):
        equipamentos = equipamentos or [self.equipamento]
        reserva = Reserva.objects.create(
            professor=professor or self.professor,
            tipo_equipamento=self.tipo,
            local=equipamentos[0].local,
            quantidade=len(equipamentos),
            inicio=inicio or self.inicio,
            fim=fim or self.fim,
            status=status,
        )
        ReservaEquipamento.objects.bulk_create(ReservaEquipamento(reserva=reserva, equipamento=e) for e in equipamentos)
        return reserva


class ReservaModelTests(ReservaBaseTests):
    def test_reserva_valida_em_dia_util(self):
        reserva = self.nova_reserva(quantidade=3)
        reserva.full_clean(); reserva.save()
        self.assertEqual(reserva.quantidade, 3)

    def test_somente_professor_funcional_pode_reservar(self):
        with self.assertRaises(ValidationError) as contexto:
            self.nova_reserva(professor=self.operador).full_clean()
        self.assertIn("professor", contexto.exception.message_dict)

    def test_usuario_com_multiplos_grupos_nao_e_professor_funcional(self):
        usuario = get_user_model().objects.create_user(username="professor-com-dois-grupos", password="senha-segura-123")
        usuario.groups.add(Group.objects.get(name=GRUPO_PROFESSOR), Group.objects.get(name=GRUPO_OPERADOR))
        with self.assertRaises(ValidationError): self.nova_reserva(professor=usuario).full_clean()

    def test_inicio_no_passado_e_bloqueado(self):
        inicio = timezone.now() - timedelta(hours=2)
        with self.assertRaises(ValidationError) as contexto: self.nova_reserva(inicio=inicio, fim=inicio + timedelta(hours=1)).full_clean()
        self.assertIn("inicio", contexto.exception.message_dict)

    def test_data_atual_e_permitida_quando_horario_ainda_nao_passou(self):
        with patch("reservas.models.timezone.now", return_value=self.inicio - timedelta(minutes=30)): self.nova_reserva().full_clean()

    def test_inicio_no_sabado_e_bloqueado(self):
        sabado = self.inicio + timedelta(days=5)
        with self.assertRaises(ValidationError) as contexto: self.nova_reserva(inicio=sabado, fim=sabado + timedelta(hours=1)).full_clean()
        self.assertIn(NON_FIELD_ERRORS, contexto.exception.message_dict)

    def test_periodo_que_atravessa_fim_de_semana_e_bloqueado(self):
        with self.assertRaises(ValidationError): self.nova_reserva(inicio=self.inicio + timedelta(days=4), fim=self.inicio + timedelta(days=7)).full_clean()

    def test_fim_deve_ser_posterior_ao_inicio(self):
        with self.assertRaises(ValidationError) as contexto: self.nova_reserva(fim=self.inicio).full_clean()
        self.assertIn("fim", contexto.exception.message_dict)
        self.assertEqual(
            contexto.exception.message_dict["fim"],
            ["A hora final deve ser posterior ao inicio da reserva"],
        )

    def test_tipo_inativo_e_bloqueado(self):
        self.tipo.ativo = False; self.tipo.save(update_fields=["ativo"])
        with self.assertRaises(ValidationError) as contexto: self.nova_reserva().full_clean()
        self.assertIn("tipo_equipamento", contexto.exception.message_dict)

    def test_local_inativo_e_bloqueado(self):
        self.local.ativo = False; self.local.save(update_fields=["ativo"])
        with self.assertRaises(ValidationError) as contexto: self.nova_reserva().full_clean()
        self.assertIn("local", contexto.exception.message_dict)

    def test_quantidade_deve_ser_positiva(self):
        with self.assertRaises(ValidationError) as contexto: self.nova_reserva(quantidade=0).full_clean()
        self.assertIn("quantidade", contexto.exception.message_dict)

    def test_banco_exige_fim_posterior_ao_inicio(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic(): Reserva.objects.create(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, inicio=self.inicio, fim=self.inicio)

    def test_banco_exige_quantidade_positiva(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic(): Reserva.objects.create(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=0, inicio=self.inicio, fim=self.fim)

    def test_equipamento_alocado_e_inativado_em_vez_de_excluido(self):
        reserva = self.salvar_reserva_com_itens(); self.equipamento.delete(); self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo); self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())


class BrasilAPITests(TestCase):
    @patch("reservas.brasilapi.urlopen")
    def test_consulta_ano_usa_endpoint_timeout_e_converte_resposta(self, urlopen):
        urlopen.return_value = resposta_json([{"date": "2026-09-07", "name": "Independência do Brasil", "type": "national", "weekday": "segunda-feira"}])
        feriados = consultar_feriados_do_ano(2026)
        self.assertEqual(feriados, (Feriado(data=datetime(2026, 9, 7).date(), nome="Independência do Brasil"),))
        self.assertEqual(urlopen.call_args.args[0].full_url, "https://brasilapi.com.br/api/feriados/v1/2026")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], BRASILAPI_TIMEOUT_SEGUNDOS)

    @patch("reservas.brasilapi.urlopen")
    def test_respostas_invalidas_sao_rejeitadas(self, urlopen):
        for resposta in ({}, [{"date": "2026-09-07", "type": "national"}], [{"date": "2026-09-07", "name": "Feriado", "type": "regional"}], [{"date": "data-invalida", "name": "Feriado", "type": "national"}], [{"date": "2027-01-01", "name": "Feriado", "type": "national"}]):
            with self.subTest(resposta=resposta):
                urlopen.return_value = resposta_json(resposta)
                with self.assertRaises(ConsultaBrasilAPIError): consultar_feriados_do_ano(2026)

    @patch("reservas.brasilapi.urlopen")
    def test_json_malformado_e_rejeitado(self, urlopen):
        urlopen.return_value = RespostaHTTPFake(b"{json-invalido")
        with self.assertRaises(ConsultaBrasilAPIError): consultar_feriados_do_ano(2026)

    @patch("reservas.brasilapi.urlopen")
    def test_status_http_inesperado_e_rejeitado(self, urlopen):
        urlopen.return_value = resposta_json([], status=503)
        with self.assertRaisesMessage(ConsultaBrasilAPIError, "status HTTP inesperado: 503"): consultar_feriados_do_ano(2026)

    @patch("reservas.brasilapi.urlopen", side_effect=URLError("indisponível"))
    def test_erro_de_rede_e_convertido_em_falha_controlada(self, urlopen):
        with self.assertRaisesMessage(ConsultaBrasilAPIError, "falha de rede ou timeout"): consultar_feriados_do_ano(2026)
        urlopen.assert_called_once()

    @patch("reservas.brasilapi.consultar_feriados_do_ano")
    def test_periodo_filtra_datas_de_forma_inclusiva(self, consultar_ano):
        consultar_ano.return_value = (Feriado(data=datetime(2026, 8, 1).date(), nome="Fora"), Feriado(data=datetime(2026, 9, 7).date(), nome="Independência"), Feriado(data=datetime(2026, 10, 12).date(), nome="Aparecida"))
        resultado = consultar_feriados_no_periodo(datetime(2026, 9, 7).date(), datetime(2026, 10, 12).date())
        self.assertEqual(len(resultado.feriados), 2); self.assertTrue(resultado.completa)

    @patch("reservas.brasilapi.consultar_feriados_do_ano")
    def test_falha_parcial_preserva_outros_anos_sem_bloquear(self, consultar_ano):
        feriado = Feriado(data=datetime(2026, 12, 31).date(), nome="Feriado de teste")
        consultar_ano.side_effect = ((feriado,), ConsultaBrasilAPIError("timeout"))
        with self.assertLogs("reservas.brasilapi", level="WARNING"):
            resultado = consultar_feriados_no_periodo(datetime(2026, 12, 31).date(), datetime(2027, 1, 2).date())
        self.assertEqual(resultado.feriados, (feriado,)); self.assertFalse(resultado.completa); self.assertEqual(resultado.anos_indisponiveis, (2027,))


class CriarReservaServiceTests(ReservaBaseTests):
    def setUp(self):
        super().setUp(); self.equipamento_2 = self.criar_equipamento("RES-002"); self.equipamento_3 = self.criar_equipamento("RES-003")

    def test_cria_uma_reserva_em_lote_com_itens_e_auditoria(self):
        reserva = criar_reserva(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=2, inicio=self.inicio, fim=self.fim)
        self.assertEqual(reserva.quantidade, 2)
        self.assertEqual(reserva.local, self.local)
        self.assertEqual(list(reserva.itens.values_list("equipamento__numero_patrimonio", flat=True)), ["RES-001", "RES-002"])
        self.assertEqual(set(reserva.itens.values_list("equipamento__local_id", flat=True)), {self.local.pk})
        self.assertTrue(RegistroAuditoria.objects.filter(usuario=self.professor, acao=AcaoAuditoria.RESERVA_CRIADA, entidade_id=str(reserva.pk)).exists())

    def test_nao_aloca_equipamento_inativo_em_uso_ou_de_outro_tipo(self):
        self.equipamento.ativo = False; self.equipamento.save(update_fields=["ativo"]); self.equipamento_2.situacao = Equipamento.Situacao.MANUTENCAO; self.equipamento_2.save(update_fields=["situacao"])
        outro_tipo = TipoEquipamento.objects.create(categoria=self.categoria, nome="Projetor multimídia"); outro = self.criar_equipamento("OUT-001", tipo=outro_tipo)
        reserva = criar_reserva(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=1, inicio=self.inicio, fim=self.fim)
        self.assertEqual(set(reserva.itens.values_list("equipamento_id", flat=True)), {self.equipamento_3.pk}); self.assertNotIn(outro.pk, set(reserva.itens.values_list("equipamento_id", flat=True)))

    def test_conflito_ativo_reduz_disponibilidade(self):
        self.salvar_reserva_com_itens(equipamentos=[self.equipamento])
        self.assertEqual(consultar_disponibilidade(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, inicio=self.inicio, fim=self.fim), 2)
        reserva = criar_reserva(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=2, inicio=self.inicio, fim=self.fim)
        self.assertNotIn(self.equipamento.pk, set(reserva.itens.values_list("equipamento_id", flat=True)))

    def test_periodo_adjacente_e_reserva_cancelada_liberam_unidade(self):
        self.salvar_reserva_com_itens(equipamentos=[self.equipamento]); self.salvar_reserva_com_itens(equipamentos=[self.equipamento_2], status=Reserva.Status.CANCELADA)
        reserva = criar_reserva(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=2, inicio=self.fim, fim=self.fim + timedelta(hours=1))
        self.assertEqual(reserva.itens.count(), 2)

    def test_quantidade_insuficiente_nao_cria_reserva_parcial(self):
        outro_local = Local.objects.create(nome="Outro local para reservas")
        equipamento_de_outro_local = self.criar_equipamento(
            "RES-OUTRO-LOCAL",
            local=outro_local,
        )
        with self.assertRaises(ValidationError) as contexto: criar_reserva(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=4, inicio=self.inicio, fim=self.fim)
        self.assertIn("quantidade", contexto.exception.message_dict); self.assertFalse(Reserva.objects.exists()); self.assertFalse(ReservaEquipamento.objects.exists())
        self.assertIn("Há somente 3 unidade(s)", contexto.exception.messages[0])
        self.assertTrue(Equipamento.objects.filter(pk=equipamento_de_outro_local.pk).exists())

    def test_perfil_nao_autorizado_e_rejeitado(self):
        with self.assertRaises(ValidationError): criar_reserva(professor=self.operador, tipo_equipamento=self.tipo, local=self.local, quantidade=1, inicio=self.inicio, fim=self.fim)
        self.assertFalse(Reserva.objects.exists())

    def test_periodo_invalido_e_rejeitado(self):
        sabado = self.inicio + timedelta(days=5)
        with self.assertRaises(ValidationError): criar_reserva(professor=self.professor, tipo_equipamento=self.tipo, local=self.local, quantidade=1, inicio=sabado, fim=sabado + timedelta(hours=1))


class ExpirarReservasVencidasTests(ReservaBaseTests):
    def setUp(self):
        super().setUp()
        self.equipamento_2 = self.criar_equipamento("RES-002")

    def test_expira_exatamente_no_limite_e_audita_uma_vez(self):
        agora = self.inicio + Reserva.TOLERANCIA_RETIRADA
        reserva = self.salvar_reserva_com_itens(
            inicio=self.inicio,
            fim=self.fim,
        )

        primeira_execucao = expirar_reservas_vencidas(agora=agora)
        segunda_execucao = expirar_reservas_vencidas(agora=agora)

        reserva.refresh_from_db()
        self.assertEqual(primeira_execucao, 1)
        self.assertEqual(segunda_execucao, 0)
        self.assertEqual(reserva.status, Reserva.Status.EXPIRADA)
        self.assertEqual(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.RESERVA_EXPIRADA,
                entidade="reservas.Reserva",
                entidade_id=str(reserva.pk),
            ).count(),
            1,
        )

    def test_nao_expira_antes_da_tolerancia(self):
        agora = self.inicio + Reserva.TOLERANCIA_RETIRADA - timedelta(seconds=1)
        reserva = self.salvar_reserva_com_itens()

        quantidade = expirar_reservas_vencidas(agora=agora)

        reserva.refresh_from_db()
        self.assertEqual(quantidade, 0)
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)

    def test_retirada_vinculada_impede_expiracao(self):
        reserva = self.salvar_reserva_com_itens()
        Movimentacao.objects.create(
            equipamento=self.equipamento,
            operador=self.operador,
            destinatario=self.professor,
            tipo=Movimentacao.Tipo.RETIRADA,
            reserva=reserva,
        )

        quantidade = expirar_reservas_vencidas(
            agora=self.inicio + Reserva.TOLERANCIA_RETIRADA
        )

        reserva.refresh_from_db()
        self.assertEqual(quantidade, 0)
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)

    def test_expiracao_libera_todo_o_lote_na_consulta_de_disponibilidade(self):
        self.salvar_reserva_com_itens(
            equipamentos=[self.equipamento, self.equipamento_2]
        )
        agora = self.inicio + Reserva.TOLERANCIA_RETIRADA
        consulta_inicio = agora + timedelta(minutes=1)
        consulta_fim = consulta_inicio + timedelta(minutes=30)

        with (
            patch("reservas.services.timezone.now", return_value=agora),
            patch("reservas.models.timezone.now", return_value=agora),
        ):
            disponiveis = consultar_disponibilidade(
                professor=self.professor,
                tipo_equipamento=self.tipo,
                local=self.local,
                inicio=consulta_inicio,
                fim=consulta_fim,
            )

        self.assertEqual(disponiveis, 2)
        self.assertFalse(Reserva.objects.filter(status=Reserva.Status.ATIVA).exists())


class CancelarReservaServiceTests(ReservaBaseTests):
    def test_professor_cancela_reserva_propria_com_auditoria(self):
        reserva = self.salvar_reserva_com_itens(); cancelada = cancelar_reserva(professor=self.professor, reserva=reserva)
        self.assertEqual(cancelada.status, Reserva.Status.CANCELADA); self.assertTrue(RegistroAuditoria.objects.filter(usuario=self.professor, acao=AcaoAuditoria.RESERVA_CANCELADA, entidade_id=str(reserva.pk)).exists())

    def test_professor_nao_cancela_reserva_de_outro_professor(self):
        outro = get_user_model().objects.create_user(username="outro-professor", password="senha-segura-123"); outro.groups.add(Group.objects.get(name=GRUPO_PROFESSOR)); reserva = self.salvar_reserva_com_itens(professor=outro)
        with self.assertRaisesMessage(ValidationError, "A reserva só pode ser cancelada pelo próprio Professor."): cancelar_reserva(professor=self.professor, reserva=reserva)
        reserva.refresh_from_db(); self.assertEqual(reserva.status, Reserva.Status.ATIVA)

    def test_post_direto_nao_cancela_reserva_que_ja_expirou(self):
        agora = timezone.now()
        inicio = agora - Reserva.TOLERANCIA_RETIRADA
        reserva = self.salvar_reserva_com_itens(
            inicio=inicio,
            fim=inicio + timedelta(hours=2),
        )

        with (
            patch("reservas.services.timezone.now", return_value=agora),
            self.assertRaisesMessage(ValidationError, "Esta reserva já expirou"),
        ):
            cancelar_reserva(professor=self.professor, reserva=reserva)

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.EXPIRADA)

    def test_nao_cancela_reserva_com_retirada_vinculada(self):
        reserva = self.salvar_reserva_com_itens()
        Movimentacao.objects.create(
            equipamento=self.equipamento,
            operador=self.operador,
            destinatario=self.professor,
            tipo=Movimentacao.Tipo.RETIRADA,
            reserva=reserva,
        )

        with self.assertRaisesMessage(ValidationError, "retirada registrada"):
            cancelar_reserva(professor=self.professor, reserva=reserva)

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)


class ReservaFrontendTests(ReservaBaseTests):
    def setUp(self):
        super().setUp(); self.equipamento_2 = self.criar_equipamento("RES-002"); registrar_aceite_vigente(self.professor); registrar_aceite_vigente(self.operador); self.client.force_login(self.professor)

    def test_sidebar_do_professor_exibe_apenas_modulos_do_perfil(self):
        resposta = self.client.get(reverse("inventario:equipamento_lista")); self.assertContains(resposta, "Portal do Professor"); self.assertContains(resposta, "Equipamentos"); self.assertContains(resposta, "Minhas Reservas"); self.assertNotContains(resposta, "Visão geral"); self.assertNotContains(resposta, "Movimentações")

    def test_documentos_legais_ficam_no_menu_do_usuario(self):
        conteudo = self.client.get(reverse("inventario:equipamento_lista")).content.decode(); self.assertIn('class="user-menu-panel"', conteudo); self.assertIn("Termos de Uso", conteudo); self.assertIn("Política de Privacidade", conteudo); self.assertNotIn('class="sidebar-legal-links"', conteudo)

    def test_lista_mostra_somente_reservas_do_professor_autenticado(self):
        propria = self.salvar_reserva_com_itens(); outro = get_user_model().objects.create_user(username="professor-lista", password="senha-segura-123"); outro.groups.add(Group.objects.get(name=GRUPO_PROFESSOR)); outro_tipo = TipoEquipamento.objects.create(categoria=self.categoria, nome="Projetor de outro professor"); outro_equipamento = self.criar_equipamento("OUT-001", tipo=outro_tipo); reserva = Reserva.objects.create(professor=outro, tipo_equipamento=outro_tipo, local=self.local, quantidade=1, inicio=self.inicio, fim=self.fim); ReservaEquipamento.objects.create(reserva=reserva, equipamento=outro_equipamento)
        resposta = self.client.get(reverse("reservas:reserva_lista")); self.assertContains(resposta, propria.tipo_equipamento.nome); self.assertNotContains(resposta, outro_tipo.nome)

    def test_lista_prioriza_reserva_com_data_mais_proxima(self):
        proxima = self.salvar_reserva_com_itens()
        distante_inicio = self.inicio + timedelta(days=7)
        distante = self.salvar_reserva_com_itens(inicio=distante_inicio, fim=distante_inicio + timedelta(hours=2))
        passado_recente_inicio = timezone.now() - timedelta(days=1)
        passado_recente = self.salvar_reserva_com_itens(
            inicio=passado_recente_inicio,
            fim=passado_recente_inicio + timedelta(hours=1),
        )
        passado_antigo_inicio = timezone.now() - timedelta(days=5)
        passado_antigo = self.salvar_reserva_com_itens(
            inicio=passado_antigo_inicio,
            fim=passado_antigo_inicio + timedelta(hours=1),
        )
        resposta = self.client.get(reverse("reservas:reserva_lista"))
        ids_exibidos = [reserva.pk for reserva in resposta.context["pagina"].object_list]
        self.assertEqual(
            ids_exibidos[:4],
            [proxima.pk, distante.pk, passado_recente.pk, passado_antigo.pk],
        )

    def test_operador_nao_acessa_telas_de_reserva(self):
        self.client.force_login(self.operador)
        for nome_url in ("reservas:reserva_lista", "reservas:reserva_nova", "reservas:reserva_disponibilidade", "reservas:reserva_feriados"):
            with self.subTest(nome_url=nome_url): self.assertEqual(self.client.get(reverse(nome_url)).status_code, 403)

    def test_acao_reservar_preseleciona_tipo_modelo(self):
        resposta = self.client.get(reverse("reservas:reserva_nova"), {"tipo": self.tipo.pk, "local": self.local.pk}); self.assertEqual(resposta.status_code, 200); self.assertEqual(resposta.context["form"].initial["tipo_equipamento"], self.tipo); self.assertEqual(resposta.context["form"].initial["local"], self.local)

    def test_formulario_separa_data_e_horarios_sem_containers_de_regras(self):
        resposta = self.client.get(reverse("reservas:reserva_nova"))
        self.assertContains(resposta, 'name="data_reserva"')
        self.assertContains(resposta, 'name="hora_inicio"')
        self.assertContains(resposta, 'name="hora_fim"')
        self.assertContains(resposta, "Equipamento")
        self.assertContains(resposta, "Local")
        self.assertContains(resposta, "Data")
        self.assertContains(resposta, "Início")
        self.assertContains(resposta, "Término")
        self.assertContains(resposta, "(Disponível: --)")
        self.assertContains(resposta, "data-reservation-location")
        self.assertContains(resposta, "disabled data-reservation-quantity")
        self.assertContains(resposta, "reservation-quantity-field is-disabled")
        self.assertContains(resposta, "data-reservation-error-for")
        self.assertNotContains(resposta, "novalidate")
        self.assertNotContains(resposta, "required-mark")
        self.assertNotContains(resposta, "A data atual é permitida")
        self.assertNotContains(resposta, "Informe o horário em que")
        self.assertNotContains(resposta, "O término deve ser posterior")
        self.assertNotContains(resposta, "Antes de reservar")
        self.assertNotContains(resposta, "Disponibilidade para o período")
        self.assertContains(resposta, "data-reservation-confirm-dialog")
        self.assertContains(resposta, "data-reservation-holiday-notice")
        self.assertContains(resposta, "form-card reservation-form-card")
        self.assertContains(resposta, "data-reservation-calendar")
        self.assertContains(resposta, "data-reservation-calendar-days")
        self.assertContains(resposta, "Feriado nacional")
        self.assertContains(resposta, "Indisponível")
        self.assertContains(resposta, "Confira os dados antes de confirmar a reserva.")

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_endpoint_lista_feriados_do_ano_para_o_calendario(self, consultar_feriados):
        consultar_feriados.return_value = ConsultaFeriados(
            feriados=(Feriado(data=date(2026, 9, 7), nome="Independência do Brasil"),),
            completa=True,
            anos_indisponiveis=(),
        )

        resposta = self.client.get(reverse("reservas:reserva_feriados"), {"ano": "2026"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.json(),
            {
                "completa": True,
                "feriados": [
                    {"data": "2026-09-07", "nome": "Independência do Brasil"},
                ],
            },
        )
        consultar_feriados.assert_called_once_with(date(2026, 1, 1), date(2026, 12, 31))

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_endpoint_do_calendario_mantem_datas_disponiveis_se_api_falhar(self, consultar_feriados):
        consultar_feriados.return_value = ConsultaFeriados(
            feriados=(),
            completa=False,
            anos_indisponiveis=(2026,),
        )

        resposta = self.client.get(reverse("reservas:reserva_feriados"), {"ano": "2026"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"completa": False, "feriados": []})

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_endpoint_do_calendario_rejeita_ano_invalido_sem_consultar_api(self, consultar_feriados):
        resposta = self.client.get(reverse("reservas:reserva_feriados"), {"ano": "ano-invalido"})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json(), {"erro": "Informe um ano válido."})
        consultar_feriados.assert_not_called()

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_endpoint_informa_disponibilidade_e_feriado_antes_da_confirmacao(self, consultar_feriados):
        consultar_feriados.return_value = ConsultaFeriados(
            feriados=(
                Feriado(data=self.inicio.date(), nome="Feriado de teste"),
            ),
            completa=True,
            anos_indisponiveis=(),
        )
        self.salvar_reserva_com_itens(equipamentos=[self.equipamento])

        resposta = self.client.get(
            reverse("reservas:reserva_disponibilidade"),
            {
                "tipo_equipamento": self.tipo.pk,
                "local": self.local.pk,
                "data_reserva": self.inicio.strftime("%Y-%m-%d"),
                "hora_inicio": self.inicio.strftime("%H:%M"),
                "hora_fim": self.fim.strftime("%H:%M"),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.json(),
            {
                "disponiveis": 1,
                "consulta_feriados": {
                    "completa": True,
                    "feriados": [
                        {
                            "data": self.inicio.date().isoformat(),
                            "nome": "Feriado de teste",
                        }
                    ],
                },
            },
        )
        consultar_feriados.assert_called_once_with(
            self.inicio.date(),
            self.fim.date(),
        )

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_endpoint_permite_continuar_quando_consulta_de_feriados_falha(self, consultar_feriados):
        consultar_feriados.return_value = ConsultaFeriados(
            feriados=(),
            completa=False,
            anos_indisponiveis=(self.inicio.year,),
        )

        resposta = self.client.get(
            reverse("reservas:reserva_disponibilidade"),
            {
                "tipo_equipamento": self.tipo.pk,
                "local": self.local.pk,
                "data_reserva": self.inicio.strftime("%Y-%m-%d"),
                "hora_inicio": self.inicio.strftime("%H:%M"),
                "hora_fim": self.fim.strftime("%H:%M"),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["consulta_feriados"]["completa"], False)
        self.assertGreater(resposta.json()["disponiveis"], 0)

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_endpoint_rejeita_periodo_invalido_antes_da_brasilapi(self, consultar_feriados):
        sabado = self.inicio + timedelta(days=5)
        resposta = self.client.get(reverse("reservas:reserva_disponibilidade"), {"tipo_equipamento": self.tipo.pk, "local": self.local.pk, "data_reserva": sabado.strftime("%Y-%m-%d"), "hora_inicio": "09:00", "hora_fim": "10:00"})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("sábado ou domingo", resposta.json()["erro"])
        consultar_feriados.assert_not_called()

    def test_criacao_pela_tela_vincula_professor_quantidade_e_itens(self):
        resposta = self.client.post(reverse("reservas:reserva_nova"), {"tipo_equipamento": self.tipo.pk, "local": self.local.pk, "quantidade": 2, "data_reserva": self.inicio.strftime("%Y-%m-%d"), "hora_inicio": self.inicio.strftime("%H:%M"), "hora_fim": self.fim.strftime("%H:%M")}, follow=True)
        self.assertRedirects(resposta, reverse("reservas:reserva_lista")); reserva = Reserva.objects.get(); self.assertEqual(reserva.professor, self.professor); self.assertEqual(reserva.local, self.local); self.assertEqual(reserva.quantidade, 2); self.assertEqual(reserva.itens.count(), 2); self.assertContains(resposta, self.local.nome); self.assertContains(resposta, 'data-auto-dismiss="true"')

    def test_quantidade_indisponivel_retorna_erro_sem_reserva_parcial(self):
        resposta = self.client.post(reverse("reservas:reserva_nova"), {"tipo_equipamento": self.tipo.pk, "local": self.local.pk, "quantidade": 3, "data_reserva": self.inicio.strftime("%Y-%m-%d"), "hora_inicio": self.inicio.strftime("%H:%M"), "hora_fim": self.fim.strftime("%H:%M")})
        self.assertEqual(resposta.status_code, 200); self.assertContains(resposta, "Há somente 2 unidade(s)"); self.assertFalse(Reserva.objects.exists())

    @patch("reservas.views.consultar_feriados_no_periodo")
    def test_periodo_invalido_na_tela_nao_consulta_api(self, consultar_feriados):
        sabado = self.inicio + timedelta(days=5); resposta = self.client.post(reverse("reservas:reserva_nova"), {"tipo_equipamento": self.tipo.pk, "local": self.local.pk, "quantidade": 1, "data_reserva": sabado.strftime("%Y-%m-%d"), "hora_inicio": "09:00", "hora_fim": "10:00"}); self.assertContains(resposta, "sábado ou domingo"); self.assertFalse(Reserva.objects.exists()); consultar_feriados.assert_not_called()

    def test_hora_final_exibe_mensagem_simplificada(self):
        resposta = self.client.post(reverse("reservas:reserva_nova"), {"tipo_equipamento": self.tipo.pk, "local": self.local.pk, "quantidade": 1, "data_reserva": self.inicio.strftime("%Y-%m-%d"), "hora_inicio": self.inicio.strftime("%H:%M"), "hora_fim": self.inicio.strftime("%H:%M")})
        self.assertContains(resposta, "A hora final deve ser posterior ao inicio da reserva")
        self.assertNotContains(resposta, "A data e a hora final devem ser posteriores ao início da reserva.")

    def test_cancelamento_pela_tela_altera_reserva_propria(self):
        reserva = self.salvar_reserva_com_itens(); resposta = self.client.post(reverse("reservas:reserva_cancelar", args=(reserva.pk,)), follow=True); self.assertRedirects(resposta, reverse("reservas:reserva_lista")); reserva.refresh_from_db(); self.assertEqual(reserva.status, Reserva.Status.CANCELADA)

    def test_cancelamento_de_reserva_alheia_retorna_404(self):
        outro = get_user_model().objects.create_user(username="professor-cancelamento", password="senha-segura-123"); outro.groups.add(Group.objects.get(name=GRUPO_PROFESSOR)); reserva = self.salvar_reserva_com_itens(professor=outro); resposta = self.client.post(reverse("reservas:reserva_cancelar", args=(reserva.pk,))); self.assertEqual(resposta.status_code, 404); reserva.refresh_from_db(); self.assertEqual(reserva.status, Reserva.Status.ATIVA)

    def test_cancelamento_exige_post(self):
        reserva = self.salvar_reserva_com_itens(); self.assertEqual(self.client.get(reverse("reservas:reserva_cancelar", args=(reserva.pk,))).status_code, 405)

    def test_lista_sincroniza_e_exibe_reserva_expirada_sem_cancelamento(self):
        inicio = timezone.now() - Reserva.TOLERANCIA_RETIRADA - timedelta(minutes=1)
        reserva = self.salvar_reserva_com_itens(
            inicio=inicio,
            fim=inicio + timedelta(hours=2),
        )

        resposta = self.client.get(
            reverse("reservas:reserva_lista"),
            {"status": Reserva.Status.EXPIRADA},
        )

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.EXPIRADA)
        self.assertContains(resposta, "Expirada")
        self.assertNotContains(
            resposta,
            reverse("reservas:reserva_cancelar", args=(reserva.pk,)),
        )
