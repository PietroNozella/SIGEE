from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento, Local, TipoEquipamento
from movimentacoes.fixtures_testes import registrar_entrega_conferida
from movimentacoes.test_retirada_reserva import criar_reserva_alocada
from movimentacoes.tests import criar_cenario
from reservas.brasilapi import ConsultaFeriados
from reservas.cotas import cota_no_periodo
from reservas.models import Reserva
from reservas.services import consultar_disponibilidade, criar_reserva

from .models import AlteracaoCalendario, CalendarioEscolar
from .services import salvar_cota


class CotasProfessorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.base, _ = criar_reserva_alocada(cls.cenario, quantidade=1)
        cls.base.status = Reserva.Status.CANCELADA
        cls.base.save(update_fields=["status"])
        for indice in range(8):
            Equipamento.objects.create(numero_patrimonio=f"COTA-{indice}", tipo=cls.base.tipo_equipamento, local=cls.base.local)
        CalendarioEscolar.objects.create(pk=1, intervalo_minutos=0)

    def setUp(self):
        self.admin = self.cenario["administrador"]
        self.professor = self.cenario["professor"]
        self.tipo = self.base.tipo_equipamento
        self.inicio = self.base.inicio
        relogio = patch("django.utils.timezone.now", return_value=self.inicio - timedelta(hours=3))
        relogio.start()
        self.addCleanup(relogio.stop)
        self.client.force_login(self.admin)

    def configurar(self, limite, tipo=None):
        return salvar_cota(usuario=self.admin, tipo_id=(tipo or self.tipo).pk, limite=limite,
            motivo="Distribuição dos equipamentos entre professores.", versao=CalendarioEscolar.objects.get().versao)

    def reservar(self, quantidade=1, inicio=None, fim=None, professor=None, local=None, tipo=None):
        return criar_reserva(professor=professor or self.professor, tipo_equipamento=tipo or self.tipo,
            local=local or self.base.local, quantidade=quantidade, inicio=inicio or self.inicio,
            fim=fim or self.inicio + timedelta(hours=1), turma=self.base.turma, disciplina=self.base.disciplina, atividade=self.base.atividade)

    def saldo(self, inicio=None, fim=None):
        self.tipo.refresh_from_db()
        return cota_no_periodo(professor=self.professor, tipo_equipamento=self.tipo,
            inicio=inicio or self.inicio, fim=fim or self.inicio + timedelta(hours=1))

    def test_sem_cota_inicial_respeita_apenas_estoque_e_guarda_condicao(self):
        self.assertIsNone(self.tipo.cota_por_professor)
        reserva = self.reservar(quantidade=7)
        self.assertEqual(reserva.itens.count(), 7)
        self.assertIsNone(reserva.cota_confirmada)

    def test_exatamente_no_limite_e_divisao_de_pedidos(self):
        self.configurar(3)
        primeira = self.reservar(quantidade=2)
        segunda = self.reservar()
        self.assertEqual(primeira.cota_confirmada, 3)
        self.assertEqual(segunda.cota_confirmada, 3)
        with self.assertRaisesMessage(ValidationError, "pode solicitar mais 0"):
            self.reservar()
        self.assertEqual(Reserva.objects.filter(status="ATIVA").count(), 2)

    def test_pedido_unico_excedente_nao_cria_reserva_nem_itens(self):
        self.configurar(2)
        antes = (Reserva.objects.count(), self.base.itens.model.objects.count())
        with self.assertRaisesMessage(ValidationError, "cota deste tipo é 2"):
            self.reservar(quantidade=3)
        self.assertEqual((Reserva.objects.count(), self.base.itens.model.objects.count()), antes)

    def test_maior_total_simultaneo_nao_soma_horarios_separados(self):
        self.configurar(3)
        meio = self.inicio + timedelta(hours=1)
        fim = meio + timedelta(hours=1)
        self.reservar(quantidade=2, fim=meio)
        self.reservar(quantidade=2, inicio=meio, fim=fim)
        self.assertEqual(self.saldo(fim=fim), {"limite": 3, "comprometidas": 2, "saldo": 1})
        self.reservar(fim=fim)

    def test_sobreposicao_parcial_considera_trecho_mais_ocupado(self):
        self.configurar(5)
        self.reservar(quantidade=2)
        self.reservar(quantidade=2, inicio=self.inicio + timedelta(minutes=30), fim=self.inicio + timedelta(minutes=90))
        self.assertEqual(self.saldo()["saldo"], 1)
        with self.assertRaises(ValidationError):
            self.reservar(quantidade=2)

    def test_eventos_no_mesmo_instante_nao_duplicam_quantidades(self):
        self.configurar(2)
        fim = self.inicio + timedelta(hours=1)
        self.reservar(quantidade=2)
        self.assertEqual(self.saldo(inicio=fim, fim=fim + timedelta(hours=1))["comprometidas"], 0)
        self.reservar(quantidade=2, inicio=fim, fim=fim + timedelta(hours=1))

    def test_mesmo_tipo_em_locais_distintos_compartilha_cota(self):
        self.configurar(2)
        self.reservar(quantidade=2)
        local = Local.objects.create(nome="Segundo local da cota")
        Equipamento.objects.create(numero_patrimonio="COTA-OUTRO-LOCAL", tipo=self.tipo, local=local)
        with self.assertRaises(ValidationError):
            self.reservar(local=local)

    def test_outro_professor_e_outro_tipo_nao_compartilham_cota(self):
        self.configurar(2)
        self.reservar(quantidade=2)
        outro = get_user_model().objects.create_user(username="outro-professor-cota")
        outro.groups.add(Group.objects.get(name="Professor"))
        self.reservar(quantidade=2, professor=outro)
        tipo = TipoEquipamento.objects.create(categoria=self.tipo.categoria, nome="Outro tipo para cota")
        Equipamento.objects.create(numero_patrimonio="COTA-OUTRO-TIPO", tipo=tipo, local=self.base.local)
        self.reservar(tipo=tipo)

    def test_canceladas_e_expiradas_nao_consumem_cota(self):
        self.configurar(2)
        reserva = self.reservar(quantidade=2)
        for status in ["CANCELADA", "EXPIRADA"]:
            with self.subTest(status=status):
                reserva.status = status
                reserva.save(update_fields=["status"])
                self.assertEqual(self.saldo()["saldo"], 2)

    def test_consulta_mostra_saldo_da_cota_mesmo_com_estoque_maior(self):
        self.configurar(3)
        self.reservar(quantidade=2)
        self.assertEqual(consultar_disponibilidade(professor=self.professor, tipo_equipamento=self.tipo,
            local=self.base.local, inicio=self.inicio, fim=self.inicio + timedelta(hours=1)), 1)

    @patch("reservas.views.consultar_feriados_no_periodo", return_value=ConsultaFeriados(feriados=(), completa=True, anos_indisponiveis=()))
    def test_endpoint_explica_limite_e_pedido_adulterado_nao_ultrapassa_cota(self, feriados):
        self.configurar(2)
        self.reservar()
        self.client.force_login(self.professor)
        dados = {"tipo_equipamento": self.tipo.pk, "local": self.base.local.pk,
            "data_reserva": self.inicio.strftime("%Y-%m-%d"), "hora_inicio": "09:00", "hora_fim": "10:00"}
        resposta = self.client.get(reverse("reservas:reserva_disponibilidade"), dados)
        self.assertEqual(resposta.json()["disponiveis"], 1)
        self.assertEqual(resposta.json()["cota"], {"limite": 2, "comprometidas": 1, "saldo": 1})
        resposta = self.client.post(reverse("reservas:reserva_nova"), {**dados, "quantidade": 2,
            "turma": self.base.turma_id, "disciplina": self.base.disciplina_id, "atividade": self.base.atividade_id,
            "cota_confirmada": "", "ignorar_cota": "1", "cota_por_professor": "100"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "cota deste tipo é 2")
        self.assertEqual(Reserva.objects.filter(status="ATIVA").count(), 1)

    def test_reducao_preserva_reserva_e_retirada_confirmadas(self):
        reserva = self.reservar(quantidade=3)
        self.configurar(1)
        reserva.refresh_from_db()
        self.assertIsNone(reserva.cota_confirmada)
        self.assertEqual(reserva.quantidade, 3)
        self.assertEqual(reserva.status, "ATIVA")
        with self.assertRaises(ValidationError):
            self.reservar()
        with patch("django.utils.timezone.now", return_value=reserva.inicio):
            entregas = registrar_entrega_conferida(operador=self.cenario["operador"], reserva_id=reserva.pk)
        self.assertEqual(len(entregas), 3)

    def test_desativacao_permite_novas_sem_reescrever_snapshot(self):
        self.configurar(1)
        primeira = self.reservar()
        self.configurar(None)
        nova = self.reservar(quantidade=3)
        primeira.refresh_from_db()
        self.assertEqual(primeira.cota_confirmada, 1)
        self.assertIsNone(nova.cota_confirmada)

    def test_admin_salva_e_desativa_com_motivo_historico_e_auditoria(self):
        url = reverse("calendario:cota", args=[self.tipo.pk])
        resposta = self.client.post(url, {"cota_por_professor": 4, "motivo": "Distribuir projetores", "versao": 1})
        self.assertRedirects(resposta, reverse("calendario:cotas"))
        alteracao = AlteracaoCalendario.objects.get()
        self.assertIsNone(alteracao.anterior["limite"])
        self.assertEqual(alteracao.novo["limite"], 4)
        self.assertEqual(alteracao.usuario, self.admin)
        self.assertTrue(RegistroAuditoria.objects.filter(acao=AcaoAuditoria.CALENDARIO_ALTERADO, entidade_id=str(alteracao.pk)).exists())
        self.assertRedirects(self.client.post(url, {"cota_por_professor": "", "motivo": "Retirar limite", "versao": 2}), reverse("calendario:cotas"))
        self.tipo.refresh_from_db()
        self.assertIsNone(self.tipo.cota_por_professor)

    def test_valores_invalidos_e_motivo_ausente_nao_salvam(self):
        url = reverse("calendario:cota", args=[self.tipo.pk])
        for valor in ["0", "-1", "1.5", "abc", "2147483648"]:
            with self.subTest(valor=valor):
                resposta = self.client.post(url, {"cota_por_professor": valor, "motivo": "Teste", "versao": 1})
                self.assertIn("cota_por_professor", resposta.context["form"].errors)
        resposta = self.client.post(url, {"cota_por_professor": 3, "motivo": " ", "versao": 1})
        self.assertIn("motivo", resposta.context["form"].errors)
        self.assertFalse(AlteracaoCalendario.objects.exists())
        for limite in [0, -1, 2147483648]:
            with self.assertRaises(ValidationError):
                self.configurar(limite)

    def test_versao_antiga_e_falha_de_auditoria_nao_deixam_alteracao_parcial(self):
        self.configurar(2)
        with self.assertRaisesMessage(ValidationError, "outro Administrador"):
            salvar_cota(usuario=self.admin, tipo_id=self.tipo.pk, limite=3, motivo="Teste", versao=1)
        with patch("calendario.services.registrar_evento", side_effect=RuntimeError("Sem auditoria")):
            with self.assertRaises(RuntimeError):
                self.configurar(4)
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.cota_por_professor, 2)
        self.assertEqual(AlteracaoCalendario.objects.count(), 1)
        self.assertEqual(CalendarioEscolar.objects.get().versao, 2)

    def test_apenas_admin_com_permissao_pode_configurar(self):
        for nome in ["professor", "operador"]:
            usuario = self.cenario[nome]
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("calendario:cotas")).status_code, 403)
            self.assertEqual(self.client.post(reverse("calendario:cota", args=[self.tipo.pk]), {}).status_code, 403)
            with self.assertRaises(PermissionDenied):
                salvar_cota(usuario=usuario, tipo_id=self.tipo.pk, limite=2, motivo="Teste", versao=1)
        self.admin.groups.get().permissions.remove(Permission.objects.get(codename="configurar_calendario"))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("calendario:cotas")).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.configurar(2)

    def test_lista_busca_tipo_e_categoria_e_main_mostra_cota_ativa(self):
        self.assertContains(self.client.get(reverse("calendario:cotas")), "Sem cota adicional")
        self.configurar(2)
        self.assertContains(self.client.get(reverse("calendario:cotas"), {"busca": self.tipo.nome}), "2 unidades simultâneas")
        self.assertContains(self.client.get(reverse("calendario:cotas"), {"busca": "inexistente"}), "Nenhum tipo encontrado")
        self.assertContains(self.client.get(reverse("calendario:calendario_escola"), {"secao": "reservas"}), "1 tipo ativo com cota")
