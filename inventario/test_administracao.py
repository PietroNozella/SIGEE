from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from manutencoes.models import Manutencao
from manutencoes.services import abrir_manutencao, concluir_manutencao, iniciar_manutencao
from movimentacoes.fixtures_testes import criar_retirada_legada
from movimentacoes.models import Movimentacao
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.forms import DisponibilidadeReservaForm, ReservaForm
from reservas.models import Reserva
from reservas.services import cancelar_reserva, criar_reserva

from .forms import EquipamentoForm
from .models import Categoria, Equipamento, Local
from .services import reativar_equipamento


class AdministracaoInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()

    def setUp(self):
        self.admin = self.cenario["administrador"]
        self.equipamento = self.cenario["equipamento"]
        self.client.force_login(self.admin)

    def dados_equipamento(self, **alteracoes):
        return {
            "numero_patrimonio": self.equipamento.numero_patrimonio,
            "nome": self.equipamento.tipo.nome, "categoria": self.equipamento.tipo.categoria_id,
            "local": self.equipamento.local_id, "situacao": "DISPONIVEL", "descricao": "Conferido",
            **alteracoes,
        }

    def inativar(self):
        self.equipamento.ativo = False
        self.equipamento.save(update_fields=("ativo",))
        return reverse("inventario:equipamento_reativar", args=[self.equipamento.pk])

    def test_reativacao_confirmada_preserva_reserva_historica_e_permite_novo_uso(self):
        anterior, unidades = criar_reserva_alocada(self.cenario, quantidade=1)
        self.equipamento = unidades[0]
        anterior.status = Reserva.Status.CANCELADA
        anterior.save(update_fields=("status",))
        self.client.post(reverse("inventario:equipamento_excluir", args=[self.equipamento.pk]))
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)
        url = reverse("inventario:equipamento_reativar", args=[self.equipamento.pk])
        self.assertContains(self.client.get(url), "Confirmar reativação")
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)
        for _ in range(2):
            self.assertRedirects(self.client.post(url), reverse("inventario:equipamento_lista"))
        self.equipamento.refresh_from_db()
        self.assertTrue(self.equipamento.ativo)
        self.assertTrue(anterior.itens.filter(equipamento=self.equipamento).exists())
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.EQUIPAMENTO_REATIVADO).count(), 1)

        # A reserva nova deve utilizar a unidade reativada, não a unidade auxiliar do cenário.
        Equipamento.objects.exclude(pk=self.equipamento.pk).update(ativo=False)
        with patch("django.utils.timezone.now", return_value=anterior.inicio - timedelta(hours=1)):
            nova = criar_reserva(
                professor=self.cenario["professor"], tipo_equipamento=self.equipamento.tipo,
                local=self.equipamento.local, quantidade=1, inicio=anterior.inicio, fim=anterior.fim,
                turma=anterior.turma, disciplina=anterior.disciplina, atividade=anterior.atividade,
            )
        self.assertEqual(nova.itens.get().equipamento_id, self.equipamento.pk)
        with patch("django.utils.timezone.now", return_value=nova.inicio):
            self.client.force_login(self.cenario["operador"])
            entrega = reverse("movimentacoes:retirada_reserva_registrar", args=[nova.pk])
            token = self.client.get(entrega).context["form"].initial["conferencia"]
            self.assertEqual(self.client.post(entrega, {"conferencia": token}).status_code, 302)
            retirada = Movimentacao.objects.get(reserva=nova, tipo="RETIRADA")
            devolucao = reverse("movimentacoes:devolucao_registrar", args=[retirada.pk])
            self.assertEqual(self.client.post(devolucao, {"retiradas": [retirada.pk]}).status_code, 302)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, "DISPONIVEL")
        self.assertTrue(retirada.devolucoes.exists())

    def test_reativacao_exige_perfil_permissao_e_csrf(self):
        url = self.inativar()
        for perfil in ("professor", "operador"):
            usuario = self.cenario[perfil]
            usuario.user_permissions.add(Permission.objects.get(content_type__app_label="inventario", codename="change_equipamento"))
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url).status_code, 403)
            with self.assertRaises(PermissionDenied):
                reativar_equipamento(administrador=usuario, equipamento_id=self.equipamento.pk)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url).status_code, 403)
        self.admin.groups.clear()
        with self.assertRaises(PermissionDenied):
            reativar_equipamento(administrador=self.admin, equipamento_id=self.equipamento.pk)

    def test_reativacao_bloqueia_manutencao_e_sem_reparo_mesmo_com_situacao_editada(self):
        manutencao = abrir_manutencao(administrador=self.admin, equipamento_id=self.equipamento.pk, descricao_problema="Não liga")
        self.inativar()
        with self.assertRaisesMessage(ValidationError, "Conclua a manutenção"):
            reativar_equipamento(administrador=self.admin, equipamento_id=self.equipamento.pk)
        iniciar_manutencao(administrador=self.admin, manutencao_id=manutencao.pk)
        concluir_manutencao(administrador=self.admin, manutencao_id=manutencao.pk,
                           resultado=Manutencao.Resultado.SEM_REPARO, descricao_solucao="Placa irrecuperável")
        self.equipamento.refresh_from_db()
        self.client.post(reverse("inventario:equipamento_editar", args=[self.equipamento.pk]), self.dados_equipamento())
        with self.assertRaisesMessage(ValidationError, "sem possibilidade de reparo"):
            reativar_equipamento(administrador=self.admin, equipamento_id=self.equipamento.pk)
        self.assertFalse(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.EQUIPAMENTO_REATIVADO).exists())

    def test_reativacao_bloqueia_custodia(self):
        retiradas = criar_retirada_legada(operador=self.cenario["operador"], destinatario=self.cenario["professor"], equipamentos=[self.equipamento])
        self.inativar()
        with self.assertRaisesMessage(ValidationError, "devolução física"):
            reativar_equipamento(administrador=self.admin, equipamento_id=self.equipamento.pk)
        self.assertTrue(Movimentacao.objects.filter(pk=retiradas[0].pk).exists())

    def test_reativacao_falha_sem_mutacao_quando_auditoria_falha(self):
        self.inativar()
        with patch("inventario.services.registrar_evento", side_effect=ValueError("Auditoria indisponível")):
            with self.assertRaises(ValueError):
                reativar_equipamento(administrador=self.admin, equipamento_id=self.equipamento.pk)
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)

    def test_formulario_impede_atribuir_manutencao_e_preserva_registro_legado(self):
        dados = self.dados_equipamento(situacao="MANUTENCAO")
        self.assertFalse(EquipamentoForm(data={**dados, "numero_patrimonio": "NOVO"}).is_valid())
        self.assertFalse(EquipamentoForm(data=dados, instance=self.equipamento).is_valid())
        self.equipamento.situacao = "MANUTENCAO"
        self.equipamento.save(update_fields=("situacao",))
        self.assertTrue(EquipamentoForm(data=dados, instance=self.equipamento).is_valid())
        self.assertFalse(Manutencao.objects.exists())

    def test_csv_com_manutencao_recusa_lote_inteiro(self):
        cabecalho = "numero_patrimonio;nome;descricao;categoria;local;situacao\n"
        prefixo = f";{self.equipamento.tipo.nome};;{self.equipamento.tipo.categoria.nome};{self.equipamento.local.nome};"
        arquivo = SimpleUploadedFile("equipamentos.csv", (cabecalho + "CSV-1" + prefixo + "DISPONIVEL\nCSV-2" + prefixo + "MANUTENCAO\n").encode())
        resposta = self.client.post(reverse("inventario:equipamento_importar"), {"arquivo": arquivo})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Equipamento.objects.filter(numero_patrimonio__startswith="CSV-").exists())

    def test_categorias_e_locais_tem_ciclo_completo_sem_apagar_vinculos(self):
        for cadastro, modelo, atual in (("categorias", Categoria, self.equipamento.tipo.categoria), ("locais", Local, self.equipamento.local)):
            with self.subTest(cadastro=cadastro):
                lista = reverse(f"inventario:{cadastro}_lista")
                self.assertContains(self.client.get(lista), "Cadastrar")
                dados = {"nome": f"Novo {cadastro}", "descricao": "Uso pedagógico"}
                self.assertRedirects(self.client.post(reverse(f"inventario:{cadastro}_novo"), dados), lista)
                novo = modelo.objects.get(nome=dados["nome"])
                self.assertEqual(self.client.post(reverse(f"inventario:{cadastro}_novo"), dados).status_code, 200)
                self.assertRedirects(self.client.post(reverse(f"inventario:{cadastro}_editar", args=[novo.pk]), {**dados, "nome": f"Corrigido {cadastro}"}), lista)
                url = reverse(f"inventario:{cadastro}_inativar", args=[atual.pk])
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertRedirects(self.client.post(url), lista)
                self.equipamento.refresh_from_db()
                self.assertTrue(self.equipamento.ativo)
                atual.refresh_from_db()
                self.assertFalse(atual.ativo)
                self.assertContains(self.client.get(lista, {"situacao": "inativos", "busca": atual.nome}), atual.nome)
                for _ in range(2):
                    self.assertRedirects(self.client.post(reverse(f"inventario:{cadastro}_reativar", args=[atual.pk])), lista)
                atual.refresh_from_db()
                self.assertTrue(atual.ativo)
                self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.CADASTRO_INVENTARIO_SITUACAO_ALTERADA, entidade=modelo._meta.label).count(), 2)

    def test_cadastros_exigem_perfil_permissoes_e_csrf(self):
        for cadastro, modelo, atual in (("categorias", Categoria, self.equipamento.tipo.categoria), ("locais", Local, self.equipamento.local)):
            for perfil in ("professor", "operador"):
                usuario = self.cenario[perfil]
                usuario.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventario", content_type__model=modelo._meta.model_name))
                self.client.force_login(usuario)
                for rota in ("lista", "novo"):
                    self.assertEqual(self.client.get(reverse(f"inventario:{cadastro}_{rota}")).status_code, 403)
                self.assertEqual(self.client.post(reverse(f"inventario:{cadastro}_inativar", args=[atual.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse(f"inventario:{cadastro}_novo"), {"nome": "Injetado"}).status_code, 403)
            csrf = Client(enforce_csrf_checks=True)
            csrf.force_login(self.admin)
            self.assertEqual(csrf.post(reverse(f"inventario:{cadastro}_inativar", args=[atual.pk])).status_code, 403)
        self.assertFalse(Categoria.objects.filter(nome="Injetado").exists())

    def test_referencias_inativas_podem_ser_mantidas_mas_nao_escolhidas_em_novo_cadastro(self):
        Categoria.objects.filter(pk=self.equipamento.tipo.categoria_id).update(ativo=False)
        Local.objects.filter(pk=self.equipamento.local_id).update(ativo=False)
        dados = self.dados_equipamento()
        self.assertTrue(EquipamentoForm(data=dados, instance=self.equipamento).is_valid())
        self.assertFalse(EquipamentoForm(data={**dados, "numero_patrimonio": "NOVO"}).is_valid())
        url = self.inativar()
        self.assertContains(self.client.post(url, follow=True), "a categoria e o local")
        self.equipamento.refresh_from_db()
        self.assertFalse(self.equipamento.ativo)

    def test_categoria_inativa_bloqueia_novas_reservas_e_preserva_entrega_confirmada(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        tipo = self.equipamento.tipo
        tipo.categoria  # Carrega a referência para exercitar uma seleção anterior à inativação.
        self.client.post(reverse("inventario:categorias_inativar", args=[tipo.categoria_id]))
        for formulario in (ReservaForm(), DisponibilidadeReservaForm()):
            self.assertFalse(formulario.fields["tipo_equipamento"].queryset.filter(pk=tipo.pk).exists())
        with patch("django.utils.timezone.now", return_value=reserva.inicio - timedelta(hours=1)):
            with self.assertRaises(ValidationError):
                criar_reserva(professor=self.cenario["professor"], tipo_equipamento=tipo,
                              local=reserva.local, quantidade=1, inicio=reserva.inicio, fim=reserva.fim,
                              turma=reserva.turma, disciplina=reserva.disciplina, atividade=reserva.atividade)
        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            self.client.force_login(self.cenario["operador"])
            url = reverse("movimentacoes:retirada_reserva_registrar", args=[reserva.pk])
            conferencia = self.client.get(url).context["form"].initial["conferencia"]
            self.assertEqual(self.client.post(url, {"conferencia": conferencia}).status_code, 302)
        self.assertEqual(Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA").count(), 1)

    def test_filtro_de_inativos_e_menu_destacam_cadastro_correto(self):
        self.inativar()
        resposta = self.client.get(reverse("inventario:equipamento_lista"), {"atividade": "inativos"})
        self.assertContains(resposta, self.equipamento.numero_patrimonio)
        self.assertContains(resposta, reverse("inventario:equipamento_reativar", args=[self.equipamento.pk]))
        resposta = self.client.get(reverse("inventario:categorias_lista"))
        self.assertEqual(resposta.content.decode().count('aria-current="page"'), 1)

    def test_local_inativo_preserva_cancelamento_de_reserva_confirmada(self):
        reserva, _ = criar_reserva_alocada(self.cenario, quantidade=1)
        self.client.post(reverse("inventario:locais_inativar", args=[reserva.local_id]))
        with patch("django.utils.timezone.now", return_value=reserva.inicio - timedelta(hours=1)):
            cancelar_reserva(professor=self.cenario["professor"], reserva=reserva)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "CANCELADA")


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaReativacaoTests(TransactionTestCase):
    def test_reativacoes_concorrentes_auditam_uma_unica_transicao(self):
        cenario = criar_cenario()
        equipamento = cenario["equipamento"]
        equipamento.ativo = False
        equipamento.save(update_fields=("ativo",))
        barreira = Barrier(2)

        def reativar():
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                reativar_equipamento(administrador=cenario["administrador"], equipamento_id=equipamento.pk)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tarefas = [executor.submit(reativar) for _ in range(2)]
            for tarefa in tarefas:
                tarefa.result(timeout=30)
        equipamento.refresh_from_db()
        self.assertTrue(equipamento.ativo)
        self.assertEqual(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.EQUIPAMENTO_REATIVADO).count(), 1)

    def test_edicao_de_tipo_e_primeira_reserva_na_mesma_categoria_nao_travam(self):
        from reservas.services import _equipamentos_disponiveis

        cenario = criar_cenario()
        anterior, _ = criar_reserva_alocada(cenario, quantidade=1)
        anterior.status = "CANCELADA"
        anterior.save(update_fields=("status",))
        equipamento = cenario["equipamento"]
        unidade_bloqueada, categoria_bloqueada = Event(), Event()
        iniciar_formulario = EquipamentoForm.__init__

        def aguardar_categoria(formulario, *args, **kwargs):
            iniciar_formulario(formulario, *args, **kwargs)
            if formulario.is_bound and formulario.data.get("nome") == "Tipo corrigido":
                unidade_bloqueada.set()
                self.assertTrue(categoria_bloqueada.wait(timeout=10))

        def sinalizar_categoria(*args, **kwargs):
            if kwargs.get("bloquear"):
                categoria_bloqueada.set()
            return _equipamentos_disponiveis(*args, **kwargs)

        def editar():
            connections.close_all()
            try:
                cliente = Client()
                cliente.force_login(cenario["administrador"])
                resposta = cliente.post(reverse("inventario:equipamento_editar", args=[equipamento.pk]), {
                    "numero_patrimonio": equipamento.numero_patrimonio, "nome": "Tipo corrigido",
                    "categoria": equipamento.tipo.categoria_id, "local": equipamento.local_id,
                    "situacao": "DISPONIVEL", "descricao": "Conferido",
                })
                self.assertEqual(resposta.status_code, 302)
            finally:
                connections.close_all()

        def reservar():
            connections.close_all()
            try:
                self.assertTrue(unidade_bloqueada.wait(timeout=10))
                try:
                    reserva = criar_reserva(
                        professor=cenario["professor"], tipo_equipamento=equipamento.tipo, local=equipamento.local,
                        quantidade=1, inicio=anterior.inicio, fim=anterior.fim,
                        turma=anterior.turma, disciplina=anterior.disciplina, atividade=anterior.atividade,
                    )
                except ValidationError as erro:
                    self.assertIn("quantidade", erro.message_dict)
                else:
                    self.assertFalse(reserva.itens.exclude(equipamento__tipo_id=reserva.tipo_equipamento_id).exists())
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", return_value=anterior.inicio - timedelta(hours=1)), \
                patch.object(EquipamentoForm, "__init__", aguardar_categoria), \
                patch("reservas.services._equipamentos_disponiveis", sinalizar_categoria):
            with ThreadPoolExecutor(max_workers=2) as executor:
                tarefas = [executor.submit(editar), executor.submit(reservar)]
                for tarefa in tarefas:
                    tarefa.result(timeout=25)
        equipamento.refresh_from_db()
        self.assertEqual(equipamento.tipo.nome, "Tipo corrigido")
