from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from movimentacoes.services import registrar_retirada_reserva
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from pedagogico.models import UtilizacaoPedagogica, Turma
from pedagogico.services import salvar_contexto_reserva
from reservas.models import Reserva
from reservas.services import consultar_disponibilidade, criar_reserva, expirar_reservas_vencidas


class FluxoReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario)

    def escolhas(self):
        return {campo: getattr(self.reserva, campo) for campo in ("turma", "disciplina", "atividade")}

    def entregar(self):
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio):
            self.client.force_login(self.cenario["operador"])
            resposta = self.client.post(reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk]))
        self.assertRedirects(resposta, reverse("movimentacoes:devolucao_lista"))
        return list(Movimentacao.objects.filter(reserva=self.reserva, tipo="RETIRADA").order_by("pk"))

    def devolver(self, retiradas):
        return self.client.post(reverse("movimentacoes:devolucao_registrar", args=[retiradas[0].pk]), {
            "retiradas": [item.pk for item in retiradas],
        })

    def etapa(self, esperada):
        self.assertEqual(Reserva.objects.com_etapa().get(pk=self.reserva.pk).etapa, esperada)
        for perfil in ("professor", "operador", "administrador"):
            self.client.force_login(self.cenario[perfil])
            rota = {"professor": "reservas:reserva_lista", "operador": "movimentacoes:retirada_reserva_lista", "administrador": "reservas:reserva_consulta"}[perfil]
            reservas = self.client.get(reverse(rota))
            self.assertEqual(reservas.status_code, 200)
            self.assertEqual(self.reserva.pk in [r.pk for r in reservas.context["pagina"]], esperada == "AGUARDANDO")
            em_uso = self.client.get(reverse("movimentacoes:devolucao_lista"))
            self.assertEqual(em_uso.status_code, 200)
            self.assertEqual(any(g["retirada"].reserva_id == self.reserva.pk for g in em_uso.context["pagina"]), esperada == "EM_USO")
            historico = self.client.get(reverse("movimentacoes:historico_lista"))
            self.assertEqual(historico.status_code, 200)
            self.assertEqual(self.reserva.pk in [r.pk for r in historico.context["pagina"]], esperada in ("ENCERRADA", "CANCELADA", "EXPIRADA"))

    def test_ciclo_completo_nos_tres_perfis_e_devolucao_parcial(self):
        self.etapa("AGUARDANDO")
        retiradas = self.entregar()
        self.assertEqual(UtilizacaoPedagogica.objects.filter(movimentacao__reserva=self.reserva).count(), 3)
        self.etapa("EM_USO")
        self.client.force_login(self.cenario["operador"])
        self.assertRedirects(self.devolver(retiradas[:1]), reverse("movimentacoes:devolucao_lista"))
        self.etapa("EM_USO")
        self.client.force_login(self.cenario["operador"])
        self.assertRedirects(self.devolver(retiradas[1:]), reverse("movimentacoes:devolucao_lista"))
        self.etapa("ENCERRADA")
        self.assertEqual(Movimentacao.objects.filter(reserva=self.reserva).count(), 6)
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)

    def test_cancelamento_aparece_no_historico_sem_movimentacoes(self):
        self.client.force_login(self.cenario["professor"])
        self.client.post(reverse("reservas:reserva_cancelar", args=[self.reserva.pk]))
        self.etapa("CANCELADA")
        self.assertFalse(Movimentacao.objects.exists())

    def test_expiracao_aparece_no_historico_sem_movimentacoes(self):
        expirar_reservas_vencidas(agora=self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA)
        self.etapa("EXPIRADA")

    def test_horario_final_nao_encerra_emprestimo(self):
        self.entregar()
        expirar_reservas_vencidas(agora=self.reserva.fim + timedelta(days=1))
        self.etapa("EM_USO")

    def test_professor_nao_consulta_reserva_uso_ou_historico_alheios(self):
        retiradas = self.entregar()
        outro = get_user_model().objects.create_user(username="outro-docente")
        outro.groups.add(Group.objects.get(name="Professor"))
        registrar_aceite_vigente(outro)
        self.client.force_login(outro)
        url = reverse("reservas:reserva_detalhe", args=[self.reserva.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(len(self.client.get(reverse("movimentacoes:devolucao_lista")).context["pagina"]), 0)
        self.client.force_login(self.cenario["operador"])
        self.devolver(retiradas)
        self.client.force_login(outro)
        for filtros in ({}, {"reserva": self.reserva.pk}, {"retirada": retiradas[0].pk}, {"busca": self.unidades[0].numero_patrimonio}):
            resposta = self.client.get(reverse("movimentacoes:historico_lista"), filtros)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(len(resposta.context["pagina"]), 0)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_somente_operador_pode_confirmar_entrega_e_devolucao(self):
        for perfil in ("professor", "administrador"):
            self.client.force_login(self.cenario[perfil])
            self.assertEqual(self.client.post(reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])).status_code, 403)
        retiradas = self.entregar()
        for perfil in ("professor", "administrador"):
            self.client.force_login(self.cenario[perfil])
            self.assertEqual(self.devolver(retiradas).status_code, 403)

    def test_contexto_planejado_nao_conta_como_utilizacao_antes_da_entrega(self):
        self.assertFalse(UtilizacaoPedagogica.objects.exists())
        self.client.force_login(self.cenario["administrador"])
        self.assertEqual(self.client.get(reverse("pedagogico:indicadores")).context["totais"]["utilizacoes"], 0)
        self.entregar()
        self.client.force_login(self.cenario["administrador"])
        self.assertEqual(self.client.get(reverse("pedagogico:indicadores")).context["totais"]["utilizacoes"], 1)

    def test_contexto_obrigatorio_na_criacao_por_servico(self):
        with self.assertRaises(ValidationError):
            criar_reserva(professor=self.cenario["professor"], tipo_equipamento=self.reserva.tipo_equipamento,
                          local=self.reserva.local, quantidade=1, inicio=self.reserva.fim, fim=self.reserva.fim + timedelta(hours=1))
        self.assertEqual(Reserva.objects.count(), 1)

    def test_criacao_pela_tela_exige_contexto_e_preserva_dados(self):
        self.client.force_login(self.cenario["professor"])
        inicio = self.reserva.inicio + timedelta(days=7)
        dados = {"tipo_equipamento": self.reserva.tipo_equipamento_id, "local": self.reserva.local_id, "quantidade": 2,
                 "data_reserva": inicio.strftime("%Y-%m-%d"), "hora_inicio": "09:00", "hora_fim": "10:00"}
        url = reverse("reservas:reserva_nova")
        resposta = self.client.post(url, dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("turma", resposta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 1)
        resposta = self.client.post(url, {**dados, **{campo: obj.pk for campo, obj in self.escolhas().items()}, "observacao": "Planejamento de aula"})
        self.assertEqual(resposta.status_code, 302, resposta.context["form"].errors if resposta.status_code == 200 else "")
        self.assertRedirects(resposta, reverse("reservas:reserva_lista"))
        nova = Reserva.objects.exclude(pk=self.reserva.pk).get()
        self.assertEqual(nova.observacao_pedagogica, "Planejamento de aula")
        self.assertFalse(UtilizacaoPedagogica.objects.exists())

    def test_reserva_antiga_exige_completar_contexto_antes_da_entrega(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(turma=None, disciplina=None, atividade=None)
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio):
            with self.assertRaisesMessage(ValidationError, "completar o contexto"):
                registrar_retirada_reserva(operador=self.cenario["operador"], reserva_id=self.reserva.pk)
        self.client.force_login(self.cenario["professor"])
        resposta = self.client.post(reverse("pedagogico:utilizacao_reserva", args=[self.reserva.pk]), {campo: obj.pk for campo, obj in self.escolhas().items()})
        self.assertEqual(resposta.status_code, 302)
        self.entregar()

    def test_correcao_sincroniza_reserva_e_utilizacoes_e_fecha_na_devolucao(self):
        retiradas = self.entregar()
        escolhas = self.escolhas()
        escolhas["turma"] = Turma.objects.create(nome="Outra turma")
        salvar_contexto_reserva(professor=self.cenario["professor"], reserva_id=self.reserva.pk, **escolhas, observacao="Corrigido")
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.turma_id, escolhas["turma"].pk)
        self.assertEqual(set(UtilizacaoPedagogica.objects.values_list("observacao", flat=True)), {"Corrigido"})
        self.devolver(retiradas)
        with self.assertRaisesMessage(ValidationError, "devolução integral"):
            salvar_contexto_reserva(professor=self.cenario["professor"], reserva_id=self.reserva.pk, **self.escolhas(), observacao="Alteração indevida")
        self.assertEqual(set(UtilizacaoPedagogica.objects.values_list("observacao", flat=True)), {"Corrigido"})

    def test_devolucao_antecipada_libera_compromisso_da_reserva(self):
        retiradas = self.entregar()
        self.devolver(retiradas)
        self.assertEqual(consultar_disponibilidade(professor=self.cenario["professor"], tipo_equipamento=self.reserva.tipo_equipamento,
                         local=self.reserva.local, inicio=self.reserva.inicio, fim=self.reserva.fim), 4)

    def test_contexto_incompleto_rejeitado_no_banco(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reserva.objects.filter(pk=self.reserva.pk).update(turma=None)

    def test_migracao_recupera_contexto_sem_criar_novas_utilizacoes(self):
        self.entregar()
        antes = list(UtilizacaoPedagogica.objects.order_by("pk").values())
        Reserva.objects.filter(pk=self.reserva.pk).update(turma=None, disciplina=None, atividade=None)
        migracao = import_module("reservas.migrations.0006_reserva_reserva_contexto_completo_ou_legado")
        migracao.recuperar_contextos_existentes(apps, SimpleNamespace(connection=connection))
        self.reserva.refresh_from_db()
        self.assertIsNotNone(self.reserva.turma_id)
        self.assertEqual(list(UtilizacaoPedagogica.objects.order_by("pk").values()), antes)

    def test_historico_busca_operador_e_nomes_completos_sem_duplicar_reserva(self):
        professor, operador = self.cenario["professor"], self.cenario["operador"]
        professor.first_name, professor.last_name = "Ana", "Costa"
        operador.first_name, operador.last_name = "Paulo", "Silva"
        professor.save(); operador.save()
        retiradas = self.entregar()
        self.devolver(retiradas)
        for busca in (operador.username, "Ana Costa", "Paulo Silva", self.unidades[0].numero_patrimonio):
            resposta = self.client.get(reverse("movimentacoes:historico_lista"), {"busca": busca})
            self.assertEqual([r.pk for r in resposta.context["pagina"]], [self.reserva.pk])

    def test_historico_filtra_data_da_movimentacao_e_nao_do_agendamento(self):
        retiradas = self.entregar()
        self.devolver(retiradas)
        data = self.reserva.inicio + timedelta(days=1)
        Movimentacao.objects.filter(reserva=self.reserva).update(data_hora=data)
        resposta = self.client.get(reverse("movimentacoes:historico_lista"), {"inicio": data.date().isoformat(), "fim": data.date().isoformat(), "tipo": "DEVOLUCAO"})
        self.assertEqual([r.pk for r in resposta.context["pagina"]], [self.reserva.pk])

    def test_formulario_mantem_widgets_de_periodo_e_quantidade(self):
        self.client.force_login(self.cenario["professor"])
        form = self.client.get(reverse("reservas:reserva_nova")).context["form"]
        for campo in ("data_reserva", "hora_inicio", "hora_fim", "quantidade"):
            self.assertNotIn("form-select", form.fields[campo].widget.attrs.get("class", ""))

    def test_detalhe_destaca_somente_a_aba_da_etapa_em_cada_perfil(self):
        import re
        url = reverse("reservas:reserva_detalhe", args=[self.reserva.pk])
        def conferir(aba):
            for perfil in ("professor", "operador", "administrador"):
                self.client.force_login(self.cenario[perfil])
                resposta = self.client.get(url)
                esperado = reverse(aba) if aba else reverse({"professor": "reservas:reserva_lista", "operador": "movimentacoes:retirada_reserva_lista", "administrador": "reservas:reserva_consulta"}[perfil])
                ativos = re.findall(r'<a class="side-nav-item[^\"]*is-active[^\"]*" href="([^\"]+)"', resposta.content.decode())
                self.assertEqual(ativos, [esperado])
        conferir(None)
        retiradas = self.entregar()
        conferir("movimentacoes:devolucao_lista")
        self.client.force_login(self.cenario["operador"])
        self.devolver(retiradas)
        conferir("movimentacoes:historico_lista")
