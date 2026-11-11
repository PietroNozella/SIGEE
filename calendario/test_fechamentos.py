from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from manutencoes.services import abrir_manutencao
from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.models import Movimentacao
from movimentacoes.services import criar_conferencia_retirada, registrar_retirada_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.models import Reserva
from reservas.services import criar_reserva, expirar_reservas_vencidas, resumo_entrega

from .fechamentos import decidir_reserva_afetada, registrar_fechamento
from .models import AlteracaoCalendario, CalendarioEscolar, FechamentoEscolar, ReservaAfetadaFechamento
from .services import dias_para_agendamento


class FechamentoEscolarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario, quantidade=2)

    def setUp(self):
        self.admin = self.cenario["administrador"]
        self.operador = self.cenario["operador"]
        self.professor = self.cenario["professor"]
        self.antes = self.reserva.inicio - timedelta(minutes=10)
        self.data = timezone.localdate(self.reserva.inicio)
        self.url_fechamento = reverse("calendario:fechamento_novo")
        self.url_entrega = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
        self.url_reserva = reverse("reservas:reserva_detalhe", args=[self.reserva.pk])
        relogio = patch("django.utils.timezone.now", return_value=self.antes)
        self.relogio = relogio.start()
        self.addCleanup(relogio.stop)
        self.client.force_login(self.admin)

    def versao(self):
        return CalendarioEscolar.objects.values_list("versao", flat=True).first() or 1

    def fechar(self):
        resposta = self.client.post(self.url_fechamento, {
            "data": self.data.isoformat(), "motivo": "Interrupção de energia", "versao": self.versao(),
        })
        fechamento = FechamentoEscolar.objects.latest("pk")
        self.assertRedirects(resposta, reverse("calendario:fechamento_detalhe", args=[fechamento.pk]))
        return fechamento

    def habilitar_manutencao_excepcional(self):
        resposta = self.client.post(reverse("calendario:politica_fechamento"), {
            "permite_manter": "on", "motivo": "Permitir atendimento confirmado", "versao": self.versao(),
        })
        self.assertEqual(resposta.status_code, 302)

    def test_fechamento_suspende_entrega_e_nova_reserva_e_professor_ve_cancelamento(self):
        self.client.force_login(self.operador)
        token = self.client.get(self.url_entrega).context["form"].initial["conferencia"]
        self.client.force_login(self.admin)
        fechamento = self.fechar()
        self.assertFalse(dias_para_agendamento()[self.data.isoformat()]["aberto"])
        self.assertContains(self.client.get(reverse("calendario:fechamento_detalhe", args=[fechamento.pk])), f"Reserva #{self.reserva.pk}")
        with self.assertRaisesMessage(ValidationError, "A escola está fechada"):
            criar_reserva(
                professor=self.professor, tipo_equipamento=self.reserva.tipo_equipamento, local=self.reserva.local,
                quantidade=1, inicio=self.reserva.inicio, fim=self.reserva.fim,
                turma=self.reserva.turma, disciplina=self.reserva.disciplina, atividade=self.reserva.atividade,
            )

        self.client.force_login(self.operador)
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            resposta = self.client.post(self.url_entrega, {"conferencia": token})
        self.assertContains(resposta, "A entrega está suspensa por fechamento")
        self.assertNotContains(resposta, "Confirmar entrega da reserva")
        self.assertFalse(Movimentacao.objects.exists())

        self.client.force_login(self.admin)
        impacto = fechamento.reservas_afetadas.get(reserva=self.reserva)
        url = reverse("calendario:decisao_fechamento", args=[impacto.pk])
        dados = {"decisao": "CANCELADA", "motivo": "Escola sem atendimento"}
        apos = self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA
        with patch("django.utils.timezone.now", return_value=apos):
            self.client.force_login(self.admin)
            self.assertEqual(expirar_reservas_vencidas(), 0)
            self.assertEqual(self.client.post(url, dados).status_code, 302)
            self.assertEqual(self.client.post(url, dados).status_code, 200)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.CANCELADA)
        self.assertEqual(self.reserva.cancelada_por, self.admin)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_CANCELADA).count(), 1)
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_EXPIRADA).exists())

        self.client.force_login(self.professor)
        detalhe = self.client.get(self.url_reserva)
        self.assertContains(detalhe, "Cancelada por fechamento da escola")
        self.assertContains(detalhe, "Escola sem atendimento")
        self.assertContains(detalhe, "Fazer nova reserva")

    def test_manter_exige_politica_e_atendimento_e_preserva_condicoes(self):
        fechamento = self.fechar()
        impacto = fechamento.reservas_afetadas.get()
        dados = {"usuario": self.admin, "impacto_id": impacto.pk, "decisao": "MANTIDA", "motivo": "Haverá plantão"}
        with self.assertRaisesMessage(ValidationError, "exige política"):
            decidir_reserva_afetada(**dados, atendimento_confirmado=True)
        self.habilitar_manutencao_excepcional()
        url = reverse("calendario:decisao_fechamento", args=[impacto.pk])
        self.assertContains(
            self.client.post(url, {"decisao": "MANTIDA", "motivo": "Haverá plantão"}),
            "atendimento excepcional confirmado",
        )
        antes = Reserva.objects.values().get(pk=self.reserva.pk)
        self.assertEqual(self.client.post(url, {
            "decisao": "MANTIDA", "motivo": "Haverá plantão", "atendimento_confirmado": "on",
        }).status_code, 302)
        self.assertEqual(Reserva.objects.values().get(pk=self.reserva.pk), antes)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_MANTIDA_FECHAMENTO).count(), 1)

        self.client.force_login(self.operador)
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            resposta = self.client.get(self.url_entrega)
            self.assertContains(resposta, "Mantida com atendimento excepcional")
            token = resposta.context["form"].initial["conferencia"]
            self.assertEqual(self.client.post(self.url_entrega, {"conferencia": token}).status_code, 302)
            self.assertEqual(self.client.post(self.url_entrega, {"conferencia": token}).status_code, 302)
        self.assertEqual(Movimentacao.objects.filter(tipo=Movimentacao.Tipo.RETIRADA).count(), 2)

    def test_fechamento_apos_entrega_parcial_bloqueia_complemento_e_preserva_devolucao(self):
        self.cenario["equipamento"].delete()
        self.reserva.fim += timedelta(days=1)
        self.reserva.save(update_fields=["fim"])
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            abrir_manutencao(
                administrador=self.operador, equipamento_id=self.unidades[1].pk, descricao_problema="Não liga",
            )
            primeira, = registrar_entrega_conferida(
                operador=self.operador, reserva_id=self.reserva.pk, professor_informado=True,
            )

        agora = self.reserva.inicio + timedelta(minutes=2)
        with patch("django.utils.timezone.now", return_value=agora):
            fechamento = self.fechar()
            impacto = fechamento.reservas_afetadas.get()

        Equipamento.objects.create(
            numero_patrimonio="SUBSTITUTO-FECHAMENTO", tipo=self.reserva.tipo_equipamento, local=self.reserva.local,
        )
        with patch("django.utils.timezone.now", return_value=agora + timedelta(days=1)):
            self.client.force_login(self.admin)
            detalhe = reverse("calendario:fechamento_detalhe", args=[fechamento.pk])
            self.assertContains(self.client.get(reverse("calendario:calendario_escola")), detalhe)
            with self.assertRaisesMessage(ValidationError, "tem retirada registrada"):
                decidir_reserva_afetada(
                    usuario=self.admin, impacto_id=impacto.pk, decisao="CANCELADA", motivo="Sem atendimento",
                )
            with self.assertRaisesMessage(ValidationError, "suspensa por fechamento"):
                registrar_entrega_conferida(operador=self.operador, reserva_id=self.reserva.pk)
            self.client.force_login(self.operador)
            resposta = self.client.post(reverse("movimentacoes:devolucao_registrar", args=[primeira.pk]), {
                "retiradas": [primeira.pk],
            })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Movimentacao.objects.filter(tipo=Movimentacao.Tipo.RETIRADA).count(), 1)
        self.assertTrue(Movimentacao.objects.filter(retirada_origem=primeira, tipo=Movimentacao.Tipo.DEVOLUCAO).exists())
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.ATIVA)

    def test_reabertura_restaura_calendario_e_novo_fechamento_exige_nova_decisao(self):
        self.habilitar_manutencao_excepcional()
        fechamento = self.fechar()
        impacto = fechamento.reservas_afetadas.get()
        decidir_reserva_afetada(
            usuario=self.admin, impacto_id=impacto.pk, decisao="MANTIDA",
            motivo="Atendimento organizado", atendimento_confirmado=True,
        )
        self.assertEqual(self.client.post(reverse("calendario:fechamento_reabrir", args=[fechamento.pk]), {
            "motivo": "Energia restabelecida", "versao": self.versao(),
        }).status_code, 302)
        self.assertTrue(dias_para_agendamento()[self.data.isoformat()]["aberto"])
        novo = self.fechar()
        self.assertNotEqual(fechamento.pk, novo.pk)
        self.assertEqual(novo.reservas_afetadas.get().decisao, ReservaAfetadaFechamento.Decisao.PENDENTE)
        impacto.refresh_from_db()
        self.assertEqual(impacto.decisao, ReservaAfetadaFechamento.Decisao.MANTIDA)

    def test_fechamento_e_decisao_exigem_administrador_com_permissao(self):
        fechamento = self.fechar()
        decisao_url = reverse("calendario:decisao_fechamento", args=[fechamento.reservas_afetadas.get().pk])
        for usuario in (self.professor, self.operador):
            self.client.force_login(usuario)
            self.assertEqual(self.client.post(self.url_fechamento).status_code, 403)
            self.assertEqual(self.client.post(decisao_url).status_code, 403)

    def test_falha_na_auditoria_reverte_fechamento_e_impactos(self):
        with patch("calendario.fechamentos.registrar_evento", side_effect=RuntimeError("falha")):
            with self.assertRaisesMessage(RuntimeError, "falha"):
                registrar_fechamento(usuario=self.admin, data=self.data, motivo="Fechamento", versao=self.versao())
        self.assertFalse(FechamentoEscolar.objects.exists())
        self.assertFalse(ReservaAfetadaFechamento.objects.exists())
        self.assertFalse(AlteracaoCalendario.objects.exists())
        self.assertEqual(self.versao(), 1)

    def preparar_entrega_parcial(self):
        self.cenario["equipamento"].delete()
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio):
            abrir_manutencao(
                administrador=self.operador, equipamento_id=self.unidades[1].pk, descricao_problema="Não liga",
            )
            self.client.force_login(self.operador)
            token = self.client.get(self.url_entrega).context["form"].initial["conferencia"]
            self.assertEqual(self.client.post(self.url_entrega, {"conferencia": token, "professor_informado": "on"}).status_code, 302)
        self.relogio.return_value = self.reserva.inicio + timedelta(minutes=2)
        return Movimentacao.objects.get(reserva=self.reserva, tipo="RETIRADA"), token

    def test_encerramento_do_saldo_preserva_custodia_reenvio_e_devolucao(self):
        retirada, token = self.preparar_entrega_parcial()
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio + timedelta(minutes=2)):
            self.client.force_login(self.admin)
            fechamento = self.fechar()
            impacto = fechamento.reservas_afetadas.get()
            url = reverse("calendario:decisao_fechamento", args=[impacto.pk])
            self.assertContains(self.client.get(url), "Encerrar saldo de entrega")
            self.assertEqual(self.client.post(url, {"decisao": "ENCERRADA", "motivo": "Sem atendimento para o complemento"}).status_code, 302)
            impacto.refresh_from_db()
            self.assertEqual(impacto.decisao, "ENCERRADA")
            self.assertEqual(impacto.decidido_por, self.admin)
            self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.SALDO_ENTREGA_ENCERRADO).count(), 1)
            etapa = Reserva.objects.com_etapa().get(pk=self.reserva.pk)
            self.assertEqual(etapa.etapa, "EM_USO")
            self.assertFalse(etapa.tem_entrega_pendente)
            resumo = resumo_entrega(self.reserva)
            self.assertEqual((resumo["pendentes"], resumo["nao_atendidas"]), (0, 1))

            self.client.force_login(self.operador)
            resposta = self.client.get(self.url_entrega)
            self.assertNotContains(resposta, "Confirmar entrega complementar")
            self.assertNotContains(resposta, "Pendente de substituição")
            self.assertContains(resposta, "Não atendido — saldo encerrado")
            self.assertEqual(self.client.post(self.url_entrega, {"conferencia": token, "professor_informado": "on"}).status_code, 302)
            self.assertEqual(Movimentacao.objects.filter(reserva=self.reserva, tipo="RETIRADA").count(), 1)
            self.assertEqual(self.client.post(reverse("movimentacoes:devolucao_registrar", args=[retirada.pk]), {"retiradas": [retirada.pk]}).status_code, 302)
            self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, "ENCERRADA")
            self.client.force_login(self.professor)
            self.assertContains(self.client.get(self.url_reserva), "Saldo de entrega encerrado")
            contexto = reverse("pedagogico:utilizacao_reserva", args=[self.reserva.pk])
            self.assertContains(self.client.post(contexto, {
                "turma": self.reserva.turma_id, "disciplina": self.reserva.disciplina_id, "atividade": self.reserva.atividade_id,
            }), "A devolução integral encerrou")

    def test_saldo_pode_ser_encerrado_apos_prazo_e_devolucao_integral(self):
        retirada, _ = self.preparar_entrega_parcial()
        self.client.force_login(self.admin)
        fechamento = self.fechar()
        impacto = fechamento.reservas_afetadas.get()
        with patch("django.utils.timezone.now", return_value=self.reserva.fim + timedelta(days=1)):
            self.client.force_login(self.operador)
            self.client.post(reverse("movimentacoes:devolucao_registrar", args=[retirada.pk]), {"retiradas": [retirada.pk]})
            self.client.force_login(self.admin)
            detalhe = reverse("calendario:fechamento_detalhe", args=[fechamento.pk])
            self.assertContains(self.client.get(reverse("calendario:calendario_escola")), detalhe)
            url = reverse("calendario:decisao_fechamento", args=[impacto.pk])
            self.assertContains(self.client.get(detalhe), url)
            self.assertEqual(self.client.post(url, {"decisao": "ENCERRADA", "motivo": "Complemento não realizado"}).status_code, 302)
            self.assertNotContains(self.client.get(detalhe), url)
        self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, "ENCERRADA")

    def test_reabertura_nao_restaura_complemento_encerrado_nem_substitui_unidade(self):
        self.preparar_entrega_parcial()
        self.client.force_login(self.admin)
        fechamento = self.fechar()
        decidir_reserva_afetada(usuario=self.admin, impacto_id=fechamento.reservas_afetadas.get().pk, decisao="ENCERRADA", motivo="Complemento dispensado")
        self.client.post(reverse("calendario:fechamento_reabrir", args=[fechamento.pk]), {"motivo": "Energia restabelecida", "versao": self.versao()})
        Equipamento.objects.create(numero_patrimonio="APTO-APOS-ENCERRAMENTO", tipo=self.reserva.tipo_equipamento, local=self.reserva.local)
        with patch("django.utils.timezone.now", return_value=self.reserva.inicio + timedelta(minutes=5)):
            self.client.force_login(self.operador)
            resposta = self.client.get(self.url_entrega)
            self.assertContains(resposta, "O saldo de entrega foi encerrado")
            self.assertFalse(self.reserva.substituicoes.exists())
            token = resposta.context["form"].initial["conferencia"]
            self.assertContains(self.client.post(self.url_entrega, {"conferencia": token}), "saldo de entrega desta reserva foi encerrado")
        self.assertEqual(Movimentacao.objects.filter(reserva=self.reserva, tipo="RETIRADA").count(), 1)

    def test_encerramento_resolve_saldo_em_todos_os_fechamentos_pendentes(self):
        self.reserva.fim += timedelta(days=2)
        self.reserva.save(update_fields=["fim"])
        self.preparar_entrega_parcial()
        self.client.force_login(self.admin)
        primeiro = self.fechar()
        segundo = registrar_fechamento(usuario=self.admin, data=self.data + timedelta(days=1), motivo="Fechamento prolongado", versao=self.versao())
        decidir_reserva_afetada(usuario=self.admin, impacto_id=primeiro.reservas_afetadas.get().pk, decisao="ENCERRADA", motivo="Complemento dispensado")
        self.assertEqual(ReservaAfetadaFechamento.objects.filter(reserva=self.reserva, decisao="ENCERRADA").count(), 2)
        with self.assertRaisesMessage(ValidationError, "já foi resolvida"):
            decidir_reserva_afetada(usuario=self.admin, impacto_id=segundo.reservas_afetadas.get().pk, decisao="MANTIDA", motivo="Tentativa", atendimento_confirmado=True)

    def test_encerramento_exige_entrega_parcial_e_motivo(self):
        fechamento = self.fechar()
        impacto = fechamento.reservas_afetadas.get()
        with self.assertRaisesMessage(ValidationError, "exige uma entrega parcial"):
            decidir_reserva_afetada(usuario=self.admin, impacto_id=impacto.pk, decisao="ENCERRADA", motivo="Sem retirada")
        with self.assertRaisesMessage(ValidationError, "Informe o motivo"):
            decidir_reserva_afetada(usuario=self.admin, impacto_id=impacto.pk, decisao="ENCERRADA", motivo=" ")
        impacto.refresh_from_db()
        self.assertEqual(impacto.decisao, "PENDENTE")


class ConcorrenciaFechamentoTests(TransactionTestCase):
    def concorrer(self, primeira, segunda):
        barreira = Barrier(2)

        def executar(operacao):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                return operacao()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(executar, primeira)
            b = executor.submit(executar, segunda)
            return a.result(timeout=30), b.result(timeout=30)

    @skipUnlessDBFeature("has_select_for_update")
    def test_fechamento_e_entrega_disputam_a_mesma_reserva(self):
        cenario = criar_cenario()
        reserva, _ = criar_reserva_alocada(cenario, quantidade=2)
        CalendarioEscolar.objects.create()
        token = criar_conferencia_retirada(reserva=reserva, operador=cenario["operador"], resumo=resumo_entrega(reserva))
        def fechar():
            registrar_fechamento(
                usuario=cenario["administrador"], data=timezone.localdate(reserva.inicio),
                motivo="Fechamento inesperado", versao=1,
            )

        def entregar():
            try:
                registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk, conferencia=token)
            except ValidationError as erro:
                self.assertIn("suspensa por fechamento", str(erro))
                return "suspensa"
            return "entregue"

        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            _, resultado = self.concorrer(fechar, entregar)

        if resultado == "entregue":
            self.assertEqual(Movimentacao.objects.filter(reserva=reserva).count(), 2)
            self.assertFalse(ReservaAfetadaFechamento.objects.filter(reserva=reserva).exists())
        else:
            self.assertEqual(resultado, "suspensa")
            self.assertFalse(Movimentacao.objects.filter(reserva=reserva).exists())
            self.assertEqual(ReservaAfetadaFechamento.objects.get(reserva=reserva).decisao, "PENDENTE")

    @skipUnlessDBFeature("has_select_for_update")
    def test_cancelamento_e_confirmacao_anterior_ao_fechamento_nao_geram_entrega(self):
        cenario = criar_cenario()
        reserva, _ = criar_reserva_alocada(cenario, quantidade=2)
        token = criar_conferencia_retirada(reserva=reserva, operador=cenario["operador"], resumo=resumo_entrega(reserva))
        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            impacto = registrar_fechamento(
                usuario=cenario["administrador"], data=timezone.localdate(reserva.inicio),
                motivo="Fechamento inesperado", versao=1,
            ).reservas_afetadas.get()

            def cancelar():
                decidir_reserva_afetada(
                    usuario=cenario["administrador"], impacto_id=impacto.pk, decisao="CANCELADA", motivo="Sem atendimento",
                )

            def entregar():
                with self.assertRaisesRegex(ValidationError, "suspensa por fechamento|cancelada ou expirada"):
                    registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk, conferencia=token)

            self.concorrer(cancelar, entregar)

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)
        self.assertFalse(Movimentacao.objects.filter(reserva=reserva).exists())
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_CANCELADA).count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_encerramento_e_confirmacao_antiga_preservam_entrega_parcial(self):
        cenario = criar_cenario()
        reserva, unidades = criar_reserva_alocada(cenario, quantidade=2)
        cenario["equipamento"].delete()
        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            abrir_manutencao(administrador=cenario["operador"], equipamento_id=unidades[1].pk, descricao_problema="Não liga")
            registrar_entrega_conferida(operador=cenario["operador"], reserva_id=reserva.pk, professor_informado=True)
            impacto = registrar_fechamento(
                usuario=cenario["administrador"], data=timezone.localdate(reserva.inicio), motivo="Fechamento", versao=1,
            ).reservas_afetadas.get()
            token = criar_conferencia_retirada(reserva=reserva, operador=cenario["operador"], resumo=resumo_entrega(reserva))

            def encerrar():
                decidir_reserva_afetada(usuario=cenario["administrador"], impacto_id=impacto.pk, decisao="ENCERRADA", motivo="Sem complemento")

            def complementar():
                with self.assertRaisesRegex(ValidationError, "suspensa por fechamento|saldo de entrega desta reserva foi encerrado"):
                    registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk, conferencia=token)

            self.concorrer(encerrar, complementar)
        self.assertEqual(Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA").count(), 1)
        self.assertEqual(ReservaAfetadaFechamento.objects.get(pk=impacto.pk).decisao, "ENCERRADA")
        self.assertEqual(Reserva.objects.com_etapa().get(pk=reserva.pk).etapa, "EM_USO")
