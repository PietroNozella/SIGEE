from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente
from reservas.models import Reserva

from .models import Movimentacao
from .services import grupos_devolucao, registrar_devolucao, registrar_devolucoes, registrar_retirada_sem_reserva, retiradas_abertas
from .tests import criar_cenario


def retirar(cenario, equipamentos=None):
    equipamento = cenario["equipamento"]
    unidades = equipamentos if equipamentos is not None else [equipamento]
    return registrar_retirada_sem_reserva(
        operador=cenario["operador"], tipo_equipamento=equipamento.tipo,
        local=equipamento.local, quantidade=len(unidades), equipamentos=unidades,
        destinatario=cenario["professor"], observacao="Observação original da retirada.",
    )


class DevolucaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.retirada = retirar(cls.cenario)[0]
        cls.outro_operador = get_user_model().objects.create_user(username="outro-operador")
        cls.outro_operador.groups.add(Group.objects.get(name="Operador"))
        registrar_aceite_vigente(cls.outro_operador)

    def setUp(self):
        self.operador = self.cenario["operador"]
        self.equipamento = self.cenario["equipamento"]
        self.url = reverse("movimentacoes:devolucao_registrar", args=[self.retirada.pk])
        self.lista = reverse("movimentacoes:devolucao_lista")
        self.client.force_login(self.operador)

    def devolver(self, **dados):
        return registrar_devolucao(
            **{"operador": self.operador, "retirada_id": self.retirada.pk, **dados},
        )

    def assert_aberta(self, situacao=Equipamento.Situacao.EM_USO):
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, situacao)
        self.assertFalse(self.retirada.devolucoes.exists())
        self.assertTrue(retiradas_abertas().filter(pk=self.retirada.pk).exists())
        self.assertFalse(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).exists())

    def test_devolucao_valida_pela_tela_grava_vinculo_situacao_e_auditoria(self):
        antes = timezone.now()
        resposta = self.client.post(self.url, {"retiradas": [self.retirada.pk], "observacao": "Recebido na secretaria."}, follow=True)
        self.assertRedirects(resposta, self.lista)
        self.assertContains(resposta, "Devolução de 1 equipamento(s) registrada com sucesso")
        self.assertContains(resposta, 'data-auto-dismiss="true"')
        devolucao = self.retirada.devolucoes.get()
        self.assertEqual(devolucao.tipo, Movimentacao.Tipo.DEVOLUCAO)
        self.assertEqual(devolucao.equipamento, self.equipamento)
        self.assertEqual(devolucao.destinatario, self.retirada.destinatario)
        self.assertEqual(devolucao.operador, self.operador)
        self.assertEqual(devolucao.observacao, "Recebido na secretaria.")
        self.assertIsNone(devolucao.reserva_id)
        self.assertEqual(devolucao.lote_retirada, self.retirada.lote_retirada)
        self.assertLessEqual(antes, devolucao.data_hora)
        self.assertLessEqual(devolucao.data_hora, timezone.now())
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, Equipamento.Situacao.DISPONIVEL)
        self.assertFalse(retiradas_abertas().filter(pk=self.retirada.pk).exists())
        evento = RegistroAuditoria.objects.get(acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA)
        self.assertEqual(evento.usuario, self.operador)
        self.assertEqual(evento.entidade_id, str(devolucao.pk))
        self.assertEqual(evento.resultado, RegistroAuditoria.Resultado.SUCESSO)

    def test_outro_operador_pode_devolver_sem_alterar_retirada_original(self):
        original = Movimentacao.objects.values().get(pk=self.retirada.pk)
        self.client.force_login(self.outro_operador)
        self.assertRedirects(self.client.post(self.url, {"retiradas": [self.retirada.pk]}), self.lista)
        devolucao = self.retirada.devolucoes.get()
        self.assertEqual(devolucao.operador, self.outro_operador)
        self.assertEqual(devolucao.observacao, "")
        self.assertEqual(Movimentacao.objects.values().get(pk=self.retirada.pk), original)

    def test_dados_adulterados_nao_substituem_referencias_nem_hora(self):
        equipamento_estranho = Equipamento.objects.create(
            numero_patrimonio="PAT-OUTRO", tipo=self.equipamento.tipo, local=self.equipamento.local,
        )
        resposta = self.client.post(self.url, {
            "retiradas": [self.retirada.pk],
            "equipamento": equipamento_estranho.pk,
            "destinatario": self.cenario["administrador"].pk,
            "operador": self.outro_operador.pk,
            "tipo": "RETIRADA", "data_hora": "2000-01-01T00:00:00",
            "retirada_origem": 999999, "reserva": 999999,
            "lote_retirada": "00000000-0000-0000-0000-000000000000",
        })
        self.assertRedirects(resposta, self.lista)
        devolucao = self.retirada.devolucoes.get()
        self.assertEqual(devolucao.equipamento_id, self.retirada.equipamento_id)
        self.assertEqual(devolucao.destinatario_id, self.retirada.destinatario_id)
        self.assertEqual(devolucao.operador_id, self.operador.pk)
        self.assertEqual(devolucao.tipo, Movimentacao.Tipo.DEVOLUCAO)
        self.assertIsNone(devolucao.reserva_id)
        self.assertEqual(devolucao.retirada_origem_id, self.retirada.pk)
        self.assertEqual(devolucao.lote_retirada, self.retirada.lote_retirada)
        self.assertGreater(devolucao.data_hora, self.retirada.data_hora)
        equipamento_estranho.refresh_from_db()
        self.assertEqual(equipamento_estranho.situacao, Equipamento.Situacao.DISPONIVEL)

    def test_reserva_original_e_preservada_sem_alterar_seu_estado(self):
        inicio = timezone.now() + timedelta(days=2)
        reserva = Reserva.objects.create(
            professor=self.cenario["professor"], tipo_equipamento=self.equipamento.tipo,
            local=self.equipamento.local, inicio=inicio, fim=inicio + timedelta(hours=1),
        )
        # Representa o vínculo futuro; não implementa retirada com reserva.
        Movimentacao.objects.filter(pk=self.retirada.pk).update(reserva=reserva)
        original = Movimentacao.objects.values().get(pk=self.retirada.pk)
        reserva_original = Reserva.objects.values().get(pk=reserva.pk)
        devolucao = self.devolver()
        self.assertEqual(devolucao.reserva_id, reserva.pk)
        self.assertEqual(Movimentacao.objects.values().get(pk=self.retirada.pk), original)
        self.assertEqual(Reserva.objects.values().get(pk=reserva.pk), reserva_original)

    def test_acesso_direto_e_servico_negados_a_outros_perfis(self):
        tecnico = get_user_model().objects.create_user(username="tecnico", is_superuser=True)
        tecnico.groups.add(Group.objects.get(name="Operador"))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo")
        multiplo = get_user_model().objects.create_user(username="multiplo")
        multiplo.groups.add(*Group.objects.filter(name__in=("Professor", "Operador")))
        permissao = Permission.objects.get(codename="add_movimentacao")
        usuarios = [self.cenario["administrador"], self.cenario["professor"], tecnico, sem_grupo, multiplo]
        for usuario in usuarios:
            registrar_aceite_vigente(usuario)
            usuario.user_permissions.add(permissao)
            self.client.force_login(usuario)
            for url in (self.lista, self.url):
                for metodo in ("get", "post"):
                    # A listagem é somente GET; autorização é verificada no GET.
                    if url == self.lista and metodo == "post":
                        continue
                    with self.subTest(usuario=usuario.username, url=url, metodo=metodo):
                        self.assertEqual(getattr(self.client, metodo)(url).status_code, 403)
            with self.assertRaises(PermissionDenied):
                self.devolver(operador=usuario)
        self.assert_aberta()

    def test_operador_sem_permissao_tem_acesso_negado_e_link_oculto(self):
        Group.objects.get(name="Operador").permissions.remove(
            Permission.objects.get(codename="add_movimentacao"),
        )
        self.assertEqual(self.client.get(self.lista).status_code, 403)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        inventario = self.client.get(reverse("inventario:equipamento_lista"))
        self.assertNotContains(inventario, f'href="{self.lista}"')
        with self.assertRaises(PermissionDenied):
            self.devolver()
        self.assert_aberta()

    def test_operador_inativado_e_revalidado_pelo_servico(self):
        get_user_model().objects.filter(pk=self.operador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.devolver()
        self.assert_aberta()

    def test_anonimo_redirecionado_para_login(self):
        self.client.logout()
        for url in (self.lista, self.url):
            self.assertRedirects(self.client.get(url), reverse("login") + "?next=" + url)
        self.assert_aberta()

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.operador)
        self.assertEqual(cliente.post(self.url).status_code, 403)
        self.assert_aberta()

    def test_get_confere_dados_e_sidebar_sem_gravar(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "PAT-RF05")
        self.assertContains(resposta, "professor")
        self.assertContains(resposta, "Observação original da retirada.")
        self.assertContains(resposta, 'name="observacao"')
        for campo in ("equipamento", "destinatario", "operador", "retirada_origem", "data_hora", "reserva"):
            self.assertNotContains(resposta, f'name="{campo}"')
        self.assertContains(resposta, "Registrar devolução")
        self.assertContains(resposta, f'href="{self.lista}">Em uso</a>')
        lista = self.client.get(self.lista)
        self.assertContains(lista, "<h1>Em uso</h1>", html=True)
        self.assert_aberta()

    def test_retirada_inexistente_na_url_e_no_servico_nao_altera_dados(self):
        inexistente = reverse("movimentacoes:devolucao_registrar", args=[999999])
        self.assertEqual(self.client.get(inexistente).status_code, 404)
        self.assertEqual(self.client.post(inexistente).status_code, 404)
        with self.assertRaisesMessage(ValidationError, "não existe"):
            self.devolver(retirada_id=999999)
        self.assert_aberta()

    def test_devolucao_nao_pode_ser_usada_como_retirada(self):
        devolucao = self.devolver()
        url = reverse("movimentacoes:devolucao_registrar", args=[devolucao.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        with self.assertRaisesMessage(ValidationError, "não existe"):
            self.devolver(retirada_id=devolucao.pk)
        self.assertEqual(Movimentacao.objects.filter(tipo=Movimentacao.Tipo.DEVOLUCAO).count(), 1)

    def test_segunda_devolucao_e_tela_aberta_antes_da_primeira_nao_alteram_dados(self):
        self.client.get(self.url)
        devolucao = self.devolver()
        estado = Equipamento.objects.values().get(pk=self.equipamento.pk)
        with self.assertRaisesMessage(ValidationError, "já foi devolvida"):
            self.devolver()
        resposta = self.client.post(self.url, {"retiradas": [self.retirada.pk], "observacao": "Duplicada"})
        self.assertContains(resposta, "Todas as unidades deste grupo já foram devolvidas")
        self.assertNotContains(resposta, '<button class="btn btn-primary-sigee" type="submit">Confirmar devolução')
        self.assertEqual(list(self.retirada.devolucoes.all()), [devolucao])
        self.assertEqual(Equipamento.objects.values().get(pk=self.equipamento.pk), estado)
        self.assertEqual(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA, resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).count(), 1)

    def test_devolucao_individual_nao_devolve_outro_item_do_lote(self):
        unidades = [Equipamento.objects.create(
            numero_patrimonio=f"PAT-LOTE-{indice}", tipo=self.equipamento.tipo, local=self.equipamento.local,
        ) for indice in range(2)]
        retiradas = retirar(self.cenario, unidades)
        self.devolver(retirada_id=retiradas[0].pk)
        unidades[0].refresh_from_db()
        unidades[1].refresh_from_db()
        self.assertEqual(unidades[0].situacao, Equipamento.Situacao.DISPONIVEL)
        self.assertEqual(unidades[1].situacao, Equipamento.Situacao.EM_USO)
        self.assertFalse(retiradas[1].devolucoes.exists())
        self.assertTrue(retiradas_abertas().filter(pk=retiradas[1].pk).exists())

    def test_inatividade_do_destinatario_nao_impede_preservar_a_identidade_original(self):
        get_user_model().objects.filter(pk=self.retirada.destinatario_id).update(is_active=False)
        devolucao = self.devolver()
        self.assertEqual(devolucao.destinatario_id, self.retirada.destinatario_id)

    def test_devolucao_nao_libera_equipamento_em_manutencao(self):
        Equipamento.objects.filter(pk=self.equipamento.pk).update(situacao=Equipamento.Situacao.MANUTENCAO)
        resposta = self.client.post(self.url, {"retiradas": [self.retirada.pk]}, follow=True)
        self.assertContains(resposta, "mantiveram seu impedimento")
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, Equipamento.Situacao.MANUTENCAO)
        self.assertTrue(self.retirada.devolucoes.exists())

    def test_devolucao_nao_reativa_equipamento_inativo(self):
        Equipamento.objects.filter(pk=self.equipamento.pk).update(ativo=False)
        resposta = self.client.post(self.url, {"retiradas": [self.retirada.pk]}, follow=True)
        self.assertContains(resposta, "mantiveram seu impedimento")
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)
        self.assertEqual(self.equipamento.situacao, Equipamento.Situacao.EM_USO)
        self.assertTrue(self.retirada.devolucoes.exists())

    def test_lista_busca_por_patrimonio_tipo_e_destinatario_e_oculta_devolvidas(self):
        for busca in ("PAT-RF05", "Projetor RF-05", "professor"):
            with self.subTest(busca=busca):
                self.assertContains(self.client.get(self.lista, {"busca": busca}), "PAT-RF05")
        self.assertContains(self.client.get(self.lista, {"busca": "inexistente"}), "Nenhuma retirada encontrada")
        self.devolver()
        resposta = self.client.get(self.lista)
        self.assertContains(resposta, "Nenhuma retirada em aberto")
        self.assertNotContains(resposta, "PAT-RF05")

    def test_paginacao_preserva_busca_e_ordem_das_retiradas(self):
        unidades = [Equipamento.objects.create(
            numero_patrimonio=f"PAG-{indice:02}", tipo=self.equipamento.tipo, local=self.equipamento.local,
        ) for indice in range(16)]
        retiradas = [retirar(self.cenario, [unidade])[0] for unidade in unidades]
        resposta = self.client.get(self.lista, {"busca": "PAG-", "pagina": 2})
        self.assertEqual([item["retirada_id"] for item in resposta.context["pagina"]], [retiradas[-1].pk])
        self.assertContains(resposta, "busca=PAG-&amp;pagina=1")
        self.assertContains(resposta, "Mostrando 16–16 de 16")

    def test_rollback_se_falhar_salvamento_da_movimentacao(self):
        with patch("movimentacoes.services.Movimentacao.save", side_effect=IntegrityError):
            self.assertContains(self.client.post(self.url, {"retiradas": [self.retirada.pk]}), "Nenhuma alteração foi salva")
        self.assert_aberta()

    def test_rollback_se_falhar_atualizacao_do_equipamento(self):
        with patch("movimentacoes.services.Equipamento.save", side_effect=IntegrityError):
            self.assertContains(self.client.post(self.url, {"retiradas": [self.retirada.pk]}), "Nenhuma alteração foi salva")
        self.assert_aberta()

    def test_rollback_inclusive_auditoria_se_falhar_apos_grava_la(self):
        from auditoria.services import registrar_evento

        def gravar_e_falhar(**dados):
            registrar_evento(**dados)
            raise IntegrityError("Falha após auditoria")

        with patch("movimentacoes.services.registrar_evento", side_effect=gravar_e_falhar):
            self.assertContains(self.client.post(self.url, {"retiradas": [self.retirada.pk]}), "Nenhuma alteração foi salva")
        self.assert_aberta()

    def test_banco_impede_duas_devolucoes_mesmo_sem_servico(self):
        self.devolver()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Movimentacao.objects.create(
                tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem=self.retirada,
                equipamento=self.equipamento, destinatario=self.retirada.destinatario,
                operador=self.operador,
            )
        self.assertEqual(self.retirada.devolucoes.count(), 1)

    def test_banco_exige_origem_para_devolucao(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Movimentacao.objects.create(
                tipo=Movimentacao.Tipo.DEVOLUCAO, equipamento=self.equipamento,
                destinatario=self.retirada.destinatario, operador=self.operador,
            )
        self.assert_aberta()


class ConcorrenciaDevolucaoTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_solicitacoes_simultaneas_registram_uma_unica_devolucao(self):
        cenario = criar_cenario()
        retirada = retirar(cenario)[0]
        barreira = Barrier(2)

        def tentar_devolver():
            connections.close_all()
            try:
                operador = get_user_model().objects.get(pk=cenario["operador"].pk)
                barreira.wait(timeout=10)
                try:
                    registrar_devolucao(operador=operador, retirada_id=retirada.pk)
                except ValidationError as erro:
                    self.assertIn("já foi devolvida", str(erro))
                    return "ja_devolvida"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tentativas = [executor.submit(tentar_devolver) for _ in range(2)]
            resultados = [tentativa.result(timeout=20) for tentativa in tentativas]

        self.assertCountEqual(resultados, ["sucesso", "ja_devolvida"])
        self.assertEqual(retirada.devolucoes.count(), 1)
        cenario["equipamento"].refresh_from_db()
        self.assertEqual(cenario["equipamento"].situacao, Equipamento.Situacao.DISPONIVEL)
        self.assertEqual(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).count(), 1)
