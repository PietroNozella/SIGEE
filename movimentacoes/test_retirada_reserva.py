from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from reservas.models import Reserva, ReservaEquipamento
from reservas.services import cancelar_reserva, expirar_reservas_vencidas

from .models import Movimentacao
from .services import registrar_devolucoes, registrar_retirada_reserva
from .tests import criar_cenario


def criar_reserva_alocada(cenario, quantidade=3):
    equipamento = cenario["equipamento"]
    agora = timezone.localtime()
    inicio = (agora + timedelta(days=(7 - agora.weekday()) % 7 or 7)).replace(
        hour=9, minute=0, second=0, microsecond=0,
    )
    unidades = [Equipamento.objects.create(
        numero_patrimonio=f"RESERVA-{indice:02}", tipo=equipamento.tipo, local=equipamento.local,
    ) for indice in range(quantidade)]
    reserva = Reserva.objects.create(
        professor=cenario["professor"], tipo_equipamento=equipamento.tipo, local=equipamento.local,
        quantidade=quantidade, inicio=inicio, fim=inicio + timedelta(hours=2),
    )
    ReservaEquipamento.objects.bulk_create(ReservaEquipamento(reserva=reserva, equipamento=item) for item in unidades)
    return reserva, unidades


class RetiradaReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.reserva, cls.unidades = criar_reserva_alocada(cls.cenario)

    def setUp(self):
        self.operador = self.cenario["operador"]
        self.url = reverse("movimentacoes:retirada_reserva_registrar", args=[self.reserva.pk])
        self.lista = reverse("movimentacoes:retirada_reserva_lista")
        self.client.force_login(self.operador)
        self.agora = self.reserva.inicio + timedelta(minutes=10)
        self.relogio = patch("movimentacoes.services.timezone.now", return_value=self.agora)
        self.relogio.start()
        self.addCleanup(self.relogio.stop)

    def retirar(self, **alteracoes):
        return registrar_retirada_reserva(**{
            "operador": self.operador, "reserva_id": self.reserva.pk,
            "observacao": "Lote entregue.", **alteracoes,
        })

    def assert_sem_retirada(self):
        self.assertFalse(Movimentacao.objects.filter(reserva=self.reserva).exists())
        self.assertEqual(Equipamento.objects.filter(
            pk__in=[item.pk for item in self.unidades], situacao="DISPONIVEL",
        ).count(), 3)
        self.assertFalse(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.RETIRADA_REGISTRADA, resultado="SUCESSO",
        ).exists())

    def test_lote_valido_preserva_alocacoes_professor_reserva_e_audita_unidades(self):
        antes = Reserva.objects.values().get(pk=self.reserva.pk)
        ids_itens = list(self.reserva.itens.order_by("pk").values())
        resposta = self.client.post(self.url, {"observacao": "Conferido."}, follow=True)
        self.assertRedirects(resposta, reverse("movimentacoes:devolucao_lista"))
        self.assertContains(resposta, "3 equipamento(s) em uso")
        retiradas = list(Movimentacao.objects.filter(reserva=self.reserva))
        self.assertEqual(len(retiradas), 3)
        self.assertEqual({item.equipamento_id for item in retiradas}, {item.pk for item in self.unidades})
        self.assertEqual({item.destinatario_id for item in retiradas}, {self.reserva.professor_id})
        self.assertEqual({item.operador_id for item in retiradas}, {self.operador.pk})
        self.assertEqual({item.tipo for item in retiradas}, {"RETIRADA"})
        self.assertEqual({item.data_hora for item in retiradas}, {self.agora})
        self.assertEqual({item.observacao for item in retiradas}, {"Conferido."})
        self.assertTrue(all(item.retirada_origem_id is None for item in retiradas))
        self.assertEqual(len({item.lote_retirada for item in retiradas}), 1)
        self.assertIsNotNone(retiradas[0].lote_retirada)
        self.assertEqual(Reserva.objects.values().get(pk=self.reserva.pk), antes)
        self.assertEqual(list(self.reserva.itens.order_by("pk").values()), ids_itens)
        self.assertEqual(Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades], situacao="EM_USO").count(), 3)
        self.assertEqual(set(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.RETIRADA_REGISTRADA, resultado="SUCESSO",
        ).values_list("entidade_id", flat=True)), {str(item.pk) for item in retiradas})

    def test_campos_adulterados_nao_substituem_vinculos_nem_quantidade(self):
        self.client.post(self.url, {
            "reserva": 999999, "reserva_id": 999999, "destinatario": self.operador.pk,
            "professor": self.cenario["administrador"].pk, "equipamentos": [self.cenario["equipamento"].pk],
            "operador": self.cenario["professor"].pk, "quantidade": 1,
            "tipo": "DEVOLUCAO", "data_hora": "2000-01-01", "lote_retirada": "adulterado",
        })
        self.assertEqual(Movimentacao.objects.filter(
            reserva=self.reserva, destinatario=self.cenario["professor"], operador=self.operador,
            tipo="RETIRADA", data_hora=self.agora,
        ).count(), 3)
        self.cenario["equipamento"].refresh_from_db()
        self.assertEqual(self.cenario["equipamento"].situacao, "DISPONIVEL")

    def test_perfis_sem_autorizacao_negados_na_url_e_servico(self):
        tecnico = get_user_model().objects.create_user(username="tecnico-reserva", is_superuser=True)
        tecnico.groups.add(Group.objects.get(name="Operador"))
        multiplo = get_user_model().objects.create_user(username="multiplo-reserva")
        multiplo.groups.add(*Group.objects.filter(name__in=("Professor", "Operador")))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo-reserva")
        for usuario in (self.cenario["administrador"], self.cenario["professor"], tecnico, multiplo, sem_grupo):
            registrar_aceite_vigente(usuario)
            usuario.user_permissions.add(Permission.objects.get(codename="add_movimentacao"))
            self.client.force_login(usuario)
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.client.get(self.lista).status_code, 403)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    self.retirar(operador=usuario)
        self.assert_sem_retirada()

    def test_sem_permissao_ou_operador_inativo_nao_registra(self):
        grupo = Group.objects.get(name="Operador")
        permissao = Permission.objects.get(codename="add_movimentacao")
        grupo.permissions.remove(permissao)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.retirar()
        grupo.permissions.add(permissao)
        get_user_model().objects.filter(pk=self.operador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.retirar()
        self.assert_sem_retirada()

    def test_anonimo_csrf_get_e_reserva_inexistente(self):
        antes = list(Movimentacao.objects.values())
        self.assertContains(self.client.get(self.url), "RESERVA-00")
        self.assertEqual(list(Movimentacao.objects.values()), antes)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.operador)
        self.assertEqual(cliente.post(self.url).status_code, 403)
        inexistente = reverse("movimentacoes:retirada_reserva_registrar", args=[999999])
        self.assertEqual(self.client.post(inexistente).status_code, 404)
        with self.assertRaisesMessage(ValidationError, "não existe"):
            self.retirar(reserva_id=999999)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assert_sem_retirada()

    def test_cancelada_ou_expirada_nao_gera_retirada(self):
        for status in ("CANCELADA", "EXPIRADA"):
            Reserva.objects.filter(pk=self.reserva.pk).update(status=status)
            with self.subTest(status=status), self.assertRaisesMessage(ValidationError, "cancelada ou expirada"):
                self.retirar()
        self.assert_sem_retirada()

    def test_segunda_retirada_nao_gera_movimentacoes_ou_auditorias_adicionais(self):
        self.retirar()
        antes = list(Movimentacao.objects.values())
        with self.assertRaisesMessage(ValidationError, "já possui retirada"):
            self.retirar()
        self.assertEqual(list(Movimentacao.objects.values()), antes)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RETIRADA_REGISTRADA, resultado="SUCESSO").count(), 3)

    def test_nao_permite_antes_do_inicio_e_permite_no_inicio(self):
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio - timedelta(microseconds=1)):
            with self.assertRaisesMessage(ValidationError, "a partir do início"):
                self.retirar()
        self.assert_sem_retirada()
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio):
            self.assertEqual(len(self.retirar()), 3)

    def test_permite_imediatamente_antes_do_limite(self):
        limite = self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA
        with patch("movimentacoes.services.timezone.now", return_value=limite - timedelta(microseconds=1)):
            self.assertEqual(len(self.retirar()), 3)

    def test_no_limite_expira_sem_retirar_e_audita_expiracao_uma_vez(self):
        limite = self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA
        with patch("movimentacoes.services.timezone.now", return_value=limite):
            resposta = self.client.post(self.url)
            self.assertContains(resposta, "expirou após os 30 minutos")
            self.assertContains(resposta, "Expirada")
            self.assertEqual(expirar_reservas_vencidas(), 0)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, "EXPIRADA")
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_EXPIRADA).count(), 1)
        self.assert_sem_retirada()

    def test_equipamento_indisponivel_ou_inativo_impede_todo_lote(self):
        unidade = self.unidades[-1]
        for dados in ({"situacao": "EM_USO"}, {"situacao": "MANUTENCAO"}, {"ativo": False}):
            Equipamento.objects.filter(pk=unidade.pk).update(**dados)
            with self.subTest(dados=dados), self.assertRaisesMessage(ValidationError, "Nenhuma alteração"):
                self.retirar()
            self.assertFalse(Movimentacao.objects.exists())
            Equipamento.objects.filter(pk=unidade.pk).update(situacao="DISPONIVEL", ativo=True)
        self.assert_sem_retirada()

    def test_tipo_local_divergentes_ou_alocacao_incompleta_impedem_lote(self):
        unidade = self.unidades[-1]
        outro_local = Local.objects.create(nome="Outro local")
        outro_tipo = TipoEquipamento.objects.create(nome="Outro tipo", categoria=unidade.tipo.categoria)
        for dados in ({"local": outro_local}, {"tipo": outro_tipo}):
            Equipamento.objects.filter(pk=unidade.pk).update(**dados)
            with self.assertRaises(ValidationError):
                self.retirar()
            Equipamento.objects.filter(pk=unidade.pk).update(local=self.reserva.local, tipo=self.reserva.tipo_equipamento)
        self.reserva.itens.filter(equipamento=unidade).delete()
        with self.assertRaisesMessage(ValidationError, "quantidade"):
            self.retirar()
        self.assert_sem_retirada()

    def test_professor_inativo_tecnico_ou_com_perfil_alterado_impede_retirada(self):
        professor = self.cenario["professor"]
        for campo in ("is_active", "is_superuser"):
            get_user_model().objects.filter(pk=professor.pk).update(**{campo: campo == "is_superuser"})
            with self.assertRaisesMessage(ValidationError, "Professor desta reserva"):
                self.retirar()
            get_user_model().objects.filter(pk=professor.pk).update(is_active=True, is_superuser=False)
        professor.groups.add(Group.objects.get(name="Operador"))
        with self.assertRaises(ValidationError):
            self.retirar()
        self.assert_sem_retirada()

    def test_rollback_lote_inclusive_primeira_auditoria_se_segunda_unidade_falhar(self):
        from auditoria.services import registrar_evento
        chamadas = 0

        def gravar_e_falhar(**dados):
            nonlocal chamadas
            registrar_evento(**dados)
            chamadas += 1
            if chamadas == 2:
                raise IntegrityError("Falha após auditoria da segunda unidade")

        with patch("movimentacoes.services.registrar_evento", side_effect=gravar_e_falhar):
            self.assertContains(self.client.post(self.url), "Nenhuma alteração foi salva")
        self.assert_sem_retirada()
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, "ATIVA")

    def test_rollback_se_atualizacao_do_equipamento_falhar(self):
        with patch("movimentacoes.services.Equipamento.save", side_effect=IntegrityError):
            self.assertContains(self.client.post(self.url), "Nenhuma alteração foi salva")
        self.assert_sem_retirada()

    def test_retirada_impede_cancelamento_e_expiracao_inclusive_apos_devolucao(self):
        retiradas = self.retirar()
        with self.assertRaisesMessage(ValidationError, "já possui retirada"):
            cancelar_reserva(professor=self.cenario["professor"], reserva=self.reserva)
        self.assertEqual(expirar_reservas_vencidas(agora=self.reserva.inicio + timedelta(hours=3)), 0)
        registrar_devolucoes(operador=self.operador, retirada_id=retiradas[0].pk, retiradas_ids=[r.pk for r in retiradas])
        self.assertEqual(expirar_reservas_vencidas(agora=self.reserva.inicio + timedelta(hours=3)), 0)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, "ATIVA")

    def test_cancelamento_apos_abrir_tela_e_revalidado(self):
        self.client.get(self.url)
        cancelar_reserva(professor=self.cenario["professor"], reserva=self.reserva)
        self.assertContains(self.client.post(self.url), "cancelada ou expirada")
        self.assert_sem_retirada()

    def test_expiracao_apos_abrir_tela_e_revalidada(self):
        self.client.get(self.url)
        with patch("movimentacoes.services.timezone.now", return_value=self.reserva.inicio + Reserva.TOLERANCIA_RETIRADA):
            self.assertEqual(expirar_reservas_vencidas(), 1)
            self.assertContains(self.client.post(self.url), "cancelada ou expirada")
        self.assert_sem_retirada()

    def test_devolucao_pela_interface_e_parcial_preserva_cada_reserva_e_origem(self):
        retiradas = self.retirar()
        url = reverse("movimentacoes:devolucao_registrar", args=[retiradas[0].pk])
        self.assertContains(self.client.get(url), f"Reserva #{self.reserva.pk}")
        self.client.post(url, {"retiradas": [retiradas[0].pk, retiradas[1].pk]})
        self.assertEqual(Movimentacao.objects.filter(reserva=self.reserva, tipo="DEVOLUCAO").count(), 2)
        self.unidades[-1].refresh_from_db()
        self.assertEqual(self.unidades[-1].situacao, "EM_USO")
        self.client.post(url, {"retiradas": [retiradas[2].pk]})
        for retirada in retiradas:
            devolucao = retirada.devolucoes.get()
            self.assertEqual(devolucao.reserva_id, self.reserva.pk)
            self.assertEqual(devolucao.destinatario_id, self.reserva.professor_id)
        self.assertEqual(Equipamento.objects.filter(pk__in=[e.pk for e in self.unidades], situacao="DISPONIVEL").count(), 3)

    def test_lista_busca_reserva_professor_tipo_patrimonio_e_pagina(self):
        for busca in (str(self.reserva.pk), "professor", "Projetor RF-05", "RESERVA-01"):
            resposta = self.client.get(self.lista, {"busca": busca})
            self.assertEqual([item.pk for item in resposta.context["pagina"]], [self.reserva.pk])
        for _ in range(15):
            Reserva.objects.create(
                professor=self.reserva.professor, tipo_equipamento=self.reserva.tipo_equipamento,
                local=self.reserva.local, quantidade=1, inicio=self.reserva.inicio, fim=self.reserva.fim,
            )
        resposta = self.client.get(self.lista, {"busca": "professor", "pagina": 2})
        self.assertEqual(len(resposta.context["pagina"]), 1)
        self.assertContains(resposta, "busca=professor&amp;pagina=1")


class ConcorrenciaRetiradaReservaTests(TransactionTestCase):
    def executar_disputa(self, segunda_acao):
        cenario = criar_cenario()
        reserva, unidades = criar_reserva_alocada(cenario)
        barreira = Barrier(2)
        agora = reserva.inicio + timedelta(minutes=29)

        def executar(acao):
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                try:
                    return acao(cenario, reserva)
                except ValidationError:
                    return "negada"
            finally:
                connections.close_all()

        def retirar(cenario, reserva):
            operador = get_user_model().objects.get(pk=cenario["operador"].pk)
            registrar_retirada_reserva(operador=operador, reserva_id=reserva.pk)
            return "retirada"

        with patch("movimentacoes.services.timezone.now", return_value=agora):
            with ThreadPoolExecutor(max_workers=2) as executor:
                primeira = executor.submit(executar, retirar)
                segunda = executor.submit(executar, retirar if segunda_acao is None else segunda_acao)
                resultados = [primeira.result(timeout=30), segunda.result(timeout=30)]
        reserva.refresh_from_db()
        quantidade = Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA").count()
        self.assertIn(quantidade, (0, 3))
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RETIRADA_REGISTRADA, resultado="SUCESSO").count(), quantidade)
        self.assertEqual(Equipamento.objects.filter(pk__in=[e.pk for e in unidades], situacao="EM_USO").count(), quantidade)
        if quantidade:
            self.assertEqual(reserva.status, "ATIVA")
        return resultados, reserva, quantidade

    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_retiradas_da_mesma_reserva_entregam_um_unico_lote(self):
        resultados, _, quantidade = self.executar_disputa(None)
        self.assertCountEqual(resultados, ["retirada", "negada"])
        self.assertEqual(quantidade, 3)

    @skipUnlessDBFeature("has_select_for_update")
    def test_cancelamento_e_retirada_serializam_na_mesma_reserva(self):
        def cancelar(cenario, reserva):
            professor = get_user_model().objects.get(pk=cenario["professor"].pk)
            cancelar_reserva(professor=professor, reserva=reserva)
            return "cancelada"

        resultados, reserva, quantidade = self.executar_disputa(cancelar)
        self.assertIn("negada", resultados)
        if quantidade:
            self.assertCountEqual(resultados, ["retirada", "negada"])
        else:
            self.assertEqual(reserva.status, "CANCELADA")
            self.assertCountEqual(resultados, ["negada", "cancelada"])

    @skipUnlessDBFeature("has_select_for_update")
    def test_expiracao_e_retirada_revalidam_estado_apos_bloqueio(self):
        def expirar(cenario, reserva):
            # Relógio da retirada ainda dentro da tolerância; varredura no limite.
            return expirar_reservas_vencidas(agora=reserva.inicio + Reserva.TOLERANCIA_RETIRADA)

        resultados, reserva, quantidade = self.executar_disputa(expirar)
        if quantidade:
            self.assertCountEqual(resultados, ["retirada", 0])
        else:
            self.assertEqual(reserva.status, "EXPIRADA")
            self.assertCountEqual(resultados, ["negada", 1])
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.RESERVA_EXPIRADA).count(), 0 if quantidade else 1)
