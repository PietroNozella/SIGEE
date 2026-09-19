import json
from datetime import datetime, time, timedelta
from io import BytesIO, StringIO
from unittest.mock import call, patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Categoria, Equipamento, Local
from usuarios.permissoes import GRUPO_OPERADOR, GRUPO_PROFESSOR

from .brasilapi import (
    BRASILAPI_TIMEOUT_SEGUNDOS,
    ConsultaBrasilAPIError,
    ConsultaFeriados,
    Feriado,
    consultar_feriados_do_ano,
    consultar_feriados_no_periodo,
)
from .models import Reserva
from .services import criar_reserva


class RespostaHTTPFake(BytesIO):
    def __init__(self, conteudo, status=200):
        super().__init__(conteudo)
        self.status = status

    def getcode(self):
        return self.status


def resposta_json(conteudo, status=200):
    return RespostaHTTPFake(
        json.dumps(conteudo, ensure_ascii=False).encode("utf-8"),
        status=status,
    )


class ReservaBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.categoria = Categoria.objects.create(nome="Categoria para reservas")
        cls.local = Local.objects.create(nome="Local para reservas")
        cls.professor = get_user_model().objects.create_user(
            username="professor-reservas",
            password="senha-segura-123",
        )
        cls.professor.groups.add(Group.objects.get(name=GRUPO_PROFESSOR))
        cls.operador = get_user_model().objects.create_user(
            username="operador-reservas",
            password="senha-segura-123",
        )
        cls.operador.groups.add(Group.objects.get(name=GRUPO_OPERADOR))

    def setUp(self):
        self.equipamento = Equipamento.objects.create(
            numero_patrimonio=f"RES-{Equipamento.objects.count() + 1:03d}",
            nome="Notebook para reserva",
            categoria=self.categoria,
            local=self.local,
        )
        self.inicio = self.proxima_segunda()
        self.fim = self.inicio + timedelta(hours=2)

    @staticmethod
    def proxima_segunda():
        agora_local = timezone.localtime()
        dias_ate_segunda = (7 - agora_local.weekday()) % 7
        if dias_ate_segunda == 0:
            dias_ate_segunda = 7
        proxima_data = agora_local.date() + timedelta(days=dias_ate_segunda)
        return timezone.make_aware(datetime.combine(proxima_data, time(9, 0)))

    def nova_reserva(self, **alteracoes):
        dados = {
            "professor": self.professor,
            "equipamento": self.equipamento,
            "inicio": self.inicio,
            "fim": self.fim,
        }
        dados.update(alteracoes)
        return Reserva(**dados)


class ReservaModelTests(ReservaBaseTests):
    def test_reserva_valida_em_dia_util(self):
        reserva = self.nova_reserva()

        reserva.full_clean()
        reserva.save()

        self.assertEqual(reserva.professor, self.professor)
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)

    def test_somente_professor_funcional_pode_reservar(self):
        reserva = self.nova_reserva(professor=self.operador)

        with self.assertRaises(ValidationError) as contexto:
            reserva.full_clean()

        self.assertIn("professor", contexto.exception.message_dict)

    def test_usuario_com_multiplos_grupos_nao_e_professor_funcional(self):
        usuario = get_user_model().objects.create_user(
            username="professor-com-dois-grupos",
            password="senha-segura-123",
        )
        usuario.groups.add(
            Group.objects.get(name=GRUPO_PROFESSOR),
            Group.objects.get(name=GRUPO_OPERADOR),
        )
        reserva = self.nova_reserva(professor=usuario)

        with self.assertRaises(ValidationError) as contexto:
            reserva.full_clean()

        self.assertIn("professor", contexto.exception.message_dict)

    def test_inicio_no_passado_e_bloqueado(self):
        inicio = timezone.now() - timedelta(hours=2)
        reserva = self.nova_reserva(inicio=inicio, fim=inicio + timedelta(hours=1))

        with self.assertRaises(ValidationError) as contexto:
            reserva.full_clean()

        self.assertIn("inicio", contexto.exception.message_dict)

    def test_data_atual_e_permitida_quando_horario_ainda_nao_passou(self):
        agora = self.inicio - timedelta(minutes=30)
        reserva = self.nova_reserva()

        with patch("reservas.models.timezone.now", return_value=agora):
            reserva.full_clean()

    def test_inicio_no_sabado_e_bloqueado(self):
        sabado = self.inicio + timedelta(days=5)
        reserva = self.nova_reserva(inicio=sabado, fim=sabado + timedelta(hours=1))

        with self.assertRaises(ValidationError) as contexto:
            reserva.full_clean()

        self.assertIn(NON_FIELD_ERRORS, contexto.exception.message_dict)
        self.assertIn(
            "sábado ou domingo",
            contexto.exception.message_dict[NON_FIELD_ERRORS][0],
        )

    def test_periodo_que_atravessa_fim_de_semana_e_bloqueado(self):
        sexta = self.inicio + timedelta(days=4)
        segunda_seguinte = self.inicio + timedelta(days=7)
        reserva = self.nova_reserva(inicio=sexta, fim=segunda_seguinte)

        with self.assertRaises(ValidationError) as contexto:
            reserva.full_clean()

        self.assertIn(NON_FIELD_ERRORS, contexto.exception.message_dict)

    def test_fim_deve_ser_posterior_ao_inicio(self):
        reserva = self.nova_reserva(fim=self.inicio)

        with self.assertRaises(ValidationError) as contexto:
            reserva.full_clean()

        self.assertIn("fim", contexto.exception.message_dict)

    def test_equipamento_inativo_ou_indisponivel_e_bloqueado(self):
        cenarios = (
            {"ativo": False, "situacao": Equipamento.Situacao.DISPONIVEL},
            {"ativo": True, "situacao": Equipamento.Situacao.MANUTENCAO},
        )

        for indice, alteracoes in enumerate(cenarios):
            with self.subTest(alteracoes=alteracoes):
                equipamento = Equipamento.objects.create(
                    numero_patrimonio=f"IND-{indice}",
                    nome="Equipamento indisponível",
                    categoria=self.categoria,
                    local=self.local,
                    **alteracoes,
                )
                reserva = self.nova_reserva(equipamento=equipamento)

                with self.assertRaises(ValidationError) as contexto:
                    reserva.full_clean()

                self.assertIn("equipamento", contexto.exception.message_dict)

    def test_conflito_com_reserva_ativa_e_bloqueado(self):
        Reserva.objects.create(
            professor=self.professor,
            equipamento=self.equipamento,
            inicio=self.inicio,
            fim=self.fim,
        )
        reserva_conflitante = self.nova_reserva(
            inicio=self.inicio + timedelta(minutes=30),
            fim=self.fim + timedelta(minutes=30),
        )

        with self.assertRaises(ValidationError) as contexto:
            reserva_conflitante.full_clean()

        self.assertIn(NON_FIELD_ERRORS, contexto.exception.message_dict)
        self.assertIn(
            "reserva ativa nesse período",
            contexto.exception.message_dict[NON_FIELD_ERRORS][0],
        )

    def test_periodos_adjacentes_nao_entram_em_conflito(self):
        Reserva.objects.create(
            professor=self.professor,
            equipamento=self.equipamento,
            inicio=self.inicio,
            fim=self.fim,
        )
        reserva_adjacente = self.nova_reserva(
            inicio=self.fim,
            fim=self.fim + timedelta(hours=1),
        )

        reserva_adjacente.full_clean()

    def test_reserva_cancelada_nao_bloqueia_periodo(self):
        Reserva.objects.create(
            professor=self.professor,
            equipamento=self.equipamento,
            inicio=self.inicio,
            fim=self.fim,
            status=Reserva.Status.CANCELADA,
        )
        nova_reserva = self.nova_reserva()

        nova_reserva.full_clean()

    def test_banco_exige_fim_posterior_ao_inicio(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Reserva.objects.create(
                    professor=self.professor,
                    equipamento=self.equipamento,
                    inicio=self.inicio,
                    fim=self.inicio,
                )

    def test_equipamento_com_reserva_e_inativado_em_vez_de_excluido(self):
        reserva = Reserva.objects.create(
            professor=self.professor,
            equipamento=self.equipamento,
            inicio=self.inicio,
            fim=self.fim,
        )

        self.equipamento.delete()

        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())


class BrasilAPITests(TestCase):
    @patch("reservas.brasilapi.urlopen")
    def test_consulta_ano_usa_endpoint_timeout_e_converte_resposta(self, urlopen):
        urlopen.return_value = resposta_json(
            [
                {
                    "date": "2026-09-07",
                    "name": "Independência do Brasil",
                    "type": "national",
                    "weekday": "segunda-feira",
                }
            ]
        )

        feriados = consultar_feriados_do_ano(2026)

        self.assertEqual(
            feriados,
            (Feriado(data=datetime(2026, 9, 7).date(), nome="Independência do Brasil"),),
        )
        requisicao = urlopen.call_args.args[0]
        self.assertEqual(
            requisicao.full_url,
            "https://brasilapi.com.br/api/feriados/v1/2026",
        )
        self.assertEqual(
            urlopen.call_args.kwargs["timeout"],
            BRASILAPI_TIMEOUT_SEGUNDOS,
        )

    @patch("reservas.brasilapi.urlopen")
    def test_respostas_invalidas_sao_rejeitadas(self, urlopen):
        respostas_invalidas = (
            {},
            [{"date": "2026-09-07", "type": "national"}],
            [{"date": "2026-09-07", "name": "Feriado", "type": "regional"}],
            [{"date": "data-invalida", "name": "Feriado", "type": "national"}],
            [{"date": "2027-01-01", "name": "Feriado", "type": "national"}],
        )

        for resposta in respostas_invalidas:
            with self.subTest(resposta=resposta):
                urlopen.return_value = resposta_json(resposta)
                with self.assertRaises(ConsultaBrasilAPIError):
                    consultar_feriados_do_ano(2026)

    @patch("reservas.brasilapi.urlopen")
    def test_json_malformado_e_rejeitado(self, urlopen):
        urlopen.return_value = RespostaHTTPFake(b"{json-invalido")

        with self.assertRaises(ConsultaBrasilAPIError):
            consultar_feriados_do_ano(2026)

    @patch("reservas.brasilapi.urlopen")
    def test_status_http_inesperado_e_rejeitado(self, urlopen):
        urlopen.return_value = resposta_json([], status=503)

        with self.assertRaisesMessage(
            ConsultaBrasilAPIError,
            "status HTTP inesperado: 503",
        ):
            consultar_feriados_do_ano(2026)

    @patch("reservas.brasilapi.urlopen", side_effect=URLError("indisponível"))
    def test_erro_de_rede_e_convertido_em_falha_controlada(self, urlopen):
        with self.assertRaisesMessage(
            ConsultaBrasilAPIError,
            "falha de rede ou timeout",
        ):
            consultar_feriados_do_ano(2026)

        urlopen.assert_called_once()

    @patch("reservas.brasilapi.consultar_feriados_do_ano")
    def test_periodo_filtra_datas_de_forma_inclusiva(self, consultar_ano):
        consultar_ano.return_value = (
            Feriado(data=datetime(2026, 8, 1).date(), nome="Fora"),
            Feriado(data=datetime(2026, 9, 7).date(), nome="Independência"),
            Feriado(data=datetime(2026, 10, 12).date(), nome="Aparecida"),
        )

        resultado = consultar_feriados_no_periodo(
            datetime(2026, 9, 7).date(),
            datetime(2026, 10, 12).date(),
        )

        self.assertEqual(
            resultado.feriados,
            (
                Feriado(
                    data=datetime(2026, 9, 7).date(),
                    nome="Independência",
                ),
                Feriado(
                    data=datetime(2026, 10, 12).date(),
                    nome="Aparecida",
                ),
            ),
        )
        self.assertTrue(resultado.completa)

    @patch("reservas.brasilapi.consultar_feriados_do_ano")
    def test_falha_parcial_preserva_outros_anos_sem_bloquear(self, consultar_ano):
        feriado = Feriado(
            data=datetime(2026, 12, 31).date(),
            nome="Feriado de teste",
        )
        consultar_ano.side_effect = (
            (feriado,),
            ConsultaBrasilAPIError("timeout"),
        )

        with self.assertLogs("reservas.brasilapi", level="WARNING"):
            resultado = consultar_feriados_no_periodo(
                datetime(2026, 12, 31).date(),
                datetime(2027, 1, 2).date(),
            )

        self.assertEqual(resultado.feriados, (feriado,))
        self.assertFalse(resultado.completa)
        self.assertEqual(resultado.anos_indisponiveis, (2027,))
        self.assertEqual(consultar_ano.call_args_list, [call(2026), call(2027)])


class CriarReservaServiceTests(ReservaBaseTests):
    @patch("reservas.services.consultar_feriados_no_periodo")
    def test_cria_reserva_propria_com_aviso_e_auditoria(self, consultar_feriados):
        feriado = Feriado(data=self.inicio.date(), nome="Feriado de teste")
        consultar_feriados.return_value = ConsultaFeriados(
            feriados=(feriado,),
            completa=True,
            anos_indisponiveis=(),
        )

        resultado = criar_reserva(
            professor=self.professor,
            equipamento=self.equipamento,
            inicio=self.inicio,
            fim=self.fim,
        )

        self.assertEqual(resultado.reserva.professor, self.professor)
        self.assertEqual(resultado.consulta_feriados.feriados, (feriado,))
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                usuario=self.professor,
                acao=AcaoAuditoria.RESERVA_CRIADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="reservas.Reserva",
                entidade_id=str(resultado.reserva.pk),
            ).exists()
        )

    @patch("reservas.services.consultar_feriados_no_periodo")
    def test_indisponibilidade_da_api_nao_impede_reserva(self, consultar_feriados):
        consultar_feriados.return_value = ConsultaFeriados(
            feriados=(),
            completa=False,
            anos_indisponiveis=(self.inicio.year,),
        )

        resultado = criar_reserva(
            professor=self.professor,
            equipamento=self.equipamento,
            inicio=self.inicio,
            fim=self.fim,
        )

        self.assertTrue(Reserva.objects.filter(pk=resultado.reserva.pk).exists())
        self.assertFalse(resultado.consulta_feriados.completa)

    @patch("reservas.services.consultar_feriados_no_periodo")
    def test_perfil_nao_autorizado_e_rejeitado_antes_da_api(
        self,
        consultar_feriados,
    ):
        with self.assertRaises(ValidationError):
            criar_reserva(
                professor=self.operador,
                equipamento=self.equipamento,
                inicio=self.inicio,
                fim=self.fim,
            )

        consultar_feriados.assert_not_called()
        self.assertFalse(Reserva.objects.exists())
    @patch("reservas.services.consultar_feriados_no_periodo")
    def test_dado_local_invalido_e_rejeitado_antes_da_api(
        self,
        consultar_feriados,
    ):
        sabado = self.inicio + timedelta(days=5)

        with self.assertRaises(ValidationError):
            criar_reserva(
                professor=self.professor,
                equipamento=self.equipamento,
                inicio=sabado,
                fim=sabado + timedelta(hours=1),
            )

        consultar_feriados.assert_not_called()
        self.assertFalse(Reserva.objects.exists())
