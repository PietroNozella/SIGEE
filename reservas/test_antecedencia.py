from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from legal.services import registrar_aceite_vigente

from .forms import DisponibilidadeReservaForm, ReservaForm
from .services import consultar_disponibilidade, criar_reserva
from .tests import ReservaBaseTests


class AntecedenciaReservaTests(ReservaBaseTests):
    def setUp(self):
        super().setUp()
        self.agora = timezone.make_aware(datetime(2026, 11, 9, 10))
        relogio = patch("django.utils.timezone.now", return_value=self.agora)
        relogio.start()
        self.addCleanup(relogio.stop)
        registrar_aceite_vigente(self.professor)
        self.client.force_login(self.professor)

    def periodo(self, dias):
        inicio = (self.agora + timedelta(days=dias)).replace(hour=11)
        return inicio, inicio + timedelta(hours=1)

    def dados_http(self, dias):
        inicio, fim = self.periodo(dias)
        return {
            "tipo_equipamento": self.tipo.pk, "local": self.local.pk, "quantidade": 1,
            "data_reserva": inicio.date().isoformat(), "hora_inicio": "11:00", "hora_fim": "12:00",
            **self.contexto_dados,
        }

    def test_hoje_e_quinze_dias_sao_permitidos_sem_confundir_com_duracao(self):
        for dias in (0, 15):
            inicio, fim = self.periodo(dias)
            with self.subTest(dias=dias):
                reserva = criar_reserva(
                    professor=self.professor, tipo_equipamento=self.tipo, local=self.local,
                    quantidade=1, inicio=inicio, fim=fim, **self.contexto,
                )
                self.assertEqual(reserva.inicio, inicio)

    def test_dezesseis_dias_sao_recusados_no_modelo_e_no_servico(self):
        inicio, fim = self.periodo(16)
        with self.assertRaisesMessage(ValidationError, "15 dias corridos"):
            self.nova_reserva(inicio=inicio, fim=fim).full_clean()
        with self.assertRaisesMessage(ValidationError, "15 dias corridos"):
            criar_reserva(
                professor=self.professor, tipo_equipamento=self.tipo, local=self.local,
                quantidade=1, inicio=inicio, fim=fim, **self.contexto,
            )
        with self.assertRaisesMessage(ValidationError, "15 dias corridos"):
            consultar_disponibilidade(
                professor=self.professor, tipo_equipamento=self.tipo, local=self.local, inicio=inicio, fim=fim,
            )

    def test_post_direto_e_api_nao_contornam_o_limite_do_calendario(self):
        dados = self.dados_http(16)
        resposta = self.client.post(reverse("reservas:reserva_nova"), dados)
        self.assertContains(resposta, "15 dias corridos")
        self.assertFalse(self.professor.reservas.exists())
        resposta = self.client.get(reverse("reservas:reserva_disponibilidade"), dados)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("15 dias corridos", str(resposta.json()))

    def test_formularios_usam_os_limites_da_escola(self):
        for form in (ReservaForm(), DisponibilidadeReservaForm()):
            with self.subTest(form=type(form).__name__):
                self.assertEqual(form.fields["data_reserva"].widget.attrs["min"], "2026-11-09")
                self.assertEqual(form.fields["data_reserva"].widget.attrs["max"], "2026-11-24")

    def test_limite_usa_a_data_local_mesmo_quando_utc_ja_virou_o_dia(self):
        agora_utc = datetime(2026, 11, 10, 1, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.now", return_value=agora_utc):
            inicio = timezone.make_aware(datetime(2026, 11, 24, 23))
            self.nova_reserva(inicio=inicio, fim=inicio + timedelta(minutes=30)).full_clean()
            inicio += timedelta(days=1)
            with self.assertRaisesMessage(ValidationError, "15 dias corridos"):
                self.nova_reserva(inicio=inicio, fim=inicio + timedelta(minutes=30)).full_clean()

    def test_reserva_ja_confirmada_alem_do_horizonte_preserva_validade(self):
        inicio, fim = self.periodo(42)
        reserva = self.salvar_reserva_com_itens(inicio=inicio, fim=fim)
        reserva.status = reserva.Status.CANCELADA
        reserva.full_clean()
        reserva.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.inicio, inicio)
        self.assertEqual(reserva.status, reserva.Status.CANCELADA)
