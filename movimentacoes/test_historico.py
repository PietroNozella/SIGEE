from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente

from .models import Movimentacao
from .services import registrar_devolucao, registrar_retirada_reserva, registrar_retirada_sem_reserva
from .test_retirada_reserva import criar_reserva_alocada
from .tests import criar_cenario


class HistoricoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()
        cls.cenario["operador"].first_name = "Maria"
        cls.cenario["operador"].last_name = "Oliveira"
        cls.cenario["operador"].save()
        equipamento = cls.cenario["equipamento"]
        cls.sem_reserva = registrar_retirada_sem_reserva(
            operador=cls.cenario["operador"], tipo_equipamento=equipamento.tipo,
            local=equipamento.local, quantidade=1, equipamentos=[equipamento],
            destinatario=cls.cenario["professor"], observacao="Conferido <script>alert(1)</script>",
        )[0]
        cls.devolucao = registrar_devolucao(operador=cls.cenario["operador"], retirada_id=cls.sem_reserva.pk)
        cls.reserva, _ = criar_reserva_alocada(cls.cenario)
        with patch("movimentacoes.services.timezone.now", return_value=cls.reserva.inicio):
            cls.com_reserva = registrar_retirada_reserva(operador=cls.cenario["operador"], reserva_id=cls.reserva.pk)

    def setUp(self):
        self.url = reverse("movimentacoes:historico_lista")
        self.client.force_login(self.cenario["operador"])

    def ids(self, **filtros):
        resposta = self.client.get(self.url, filtros)
        self.assertEqual(resposta.status_code, 200)
        return [item.pk for item in resposta.context["pagina"]]

    def test_administrador_e_operador_consultam_inclusive_movimentacoes_encerradas(self):
        ids = {self.sem_reserva.pk, self.devolucao.pk, *[item.pk for item in self.com_reserva]}
        for perfil in ("administrador", "operador"):
            self.client.force_login(self.cenario[perfil])
            self.assertEqual(set(self.ids()), ids)
            resposta = self.client.get(self.url)
            self.assertContains(resposta, "PAT-RF05")
            self.assertContains(resposta, "Maria Oliveira")
            self.assertContains(resposta, "professor")
            self.assertContains(resposta, f"Reserva #{self.reserva.pk}")
            self.assertContains(resposta, f"Retirada #{self.sem_reserva.pk}")
            self.assertContains(resposta, f"Devolução #{self.devolucao.pk}")

    def test_professor_superuser_sem_grupo_multiplos_ou_grupo_extra_nao_consultam(self):
        tecnico = get_user_model().objects.create_user(username="tecnico-historico", is_superuser=True)
        tecnico.groups.add(Group.objects.get(name="Administrador"))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo-historico")
        multiplo = get_user_model().objects.create_user(username="multiplo-historico")
        multiplo.groups.add(*Group.objects.filter(name__in=("Administrador", "Operador")))
        extra = get_user_model().objects.create_user(username="extra-historico")
        extra.groups.add(Group.objects.get(name="Operador"), Group.objects.create(name="Externo"))
        for usuario in (self.cenario["professor"], tecnico, sem_grupo, multiplo, extra):
            registrar_aceite_vigente(usuario)
            usuario.user_permissions.add(Permission.objects.get(codename="view_movimentacao"))
            usuario.user_permissions.add(Permission.objects.get(codename="view_equipamento"))
            self.client.force_login(usuario)
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                resposta = self.client.get(reverse("inventario:equipamento_lista"))
                self.assertNotContains(resposta, f'href="{self.url}"')

    def test_sem_permissao_nao_consulta_e_link_e_ocultado(self):
        Group.objects.get(name="Operador").permissions.remove(Permission.objects.get(codename="view_movimentacao"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        self.assertNotContains(resposta, f'href="{self.url}"')

    def test_anonimo_precisa_login_e_rota_nao_aceita_gravacao(self):
        antes = list(Movimentacao.objects.values())
        self.assertEqual(self.client.post(self.url, {"tipo": "RETIRADA"}).status_code, 405)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), reverse("login") + "?next=" + self.url)
        self.assertEqual(list(Movimentacao.objects.values()), antes)

    def test_filtros_patrimonio_tipo_operador_destinatario_e_reserva(self):
        self.assertEqual(set(self.ids(busca="PAT-RF05")), {self.sem_reserva.pk, self.devolucao.pk})
        for busca in ("Projetor RF-05", "Maria Oliveira", "operador", "professor"):
            self.assertEqual(len(self.ids(busca=busca)), 5)
        self.assertEqual(self.ids(tipo="DEVOLUCAO"), [self.devolucao.pk])
        self.assertEqual(set(self.ids(reserva=self.reserva.pk)), {item.pk for item in self.com_reserva})
        self.assertEqual(self.ids(reserva=self.reserva.pk, tipo="DEVOLUCAO"), [])
        self.assertEqual(self.ids(busca="inexistente"), [])

    def test_vinculo_da_retirada_filtra_original_e_devolucao(self):
        self.assertEqual(set(self.ids(retirada=self.sem_reserva.pk)), {self.sem_reserva.pk, self.devolucao.pk})
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'?retirada={self.sem_reserva.pk}#mov-{self.devolucao.pk}')
        self.assertContains(resposta, f'?retirada={self.sem_reserva.pk}#mov-{self.sem_reserva.pk}')

    def test_filtro_de_datas_inclui_dia_no_fuso_local(self):
        data = timezone.localtime(self.sem_reserva.data_hora).date()
        self.assertEqual(set(self.ids(inicio=data.isoformat(), fim=data.isoformat())), {self.sem_reserva.pk, self.devolucao.pk})
        self.assertEqual(self.ids(fim=(data - timedelta(days=1)).isoformat()), [])

    def test_filtros_invalidos_mostram_erro_sem_alargar_consulta(self):
        for filtros in ({"reserva": "texto"}, {"tipo": "adulterado"}, {"retirada": "-1"},
                        {"inicio": "2026-10-03", "fim": "2026-10-02"}, {"inicio": "data inválida"}):
            with self.subTest(filtros=filtros):
                resposta = self.client.get(self.url, filtros)
                self.assertTrue(resposta.context["form"].errors)
                self.assertEqual(len(resposta.context["pagina"]), 0)

    def test_paginacao_e_ordem_estavel_preservam_filtros(self):
        equipamento = self.cenario["equipamento"]
        registros = []
        agora = timezone.now()
        for indice in range(26):
            unidade = Equipamento.objects.create(numero_patrimonio=f"HIST-{indice:02}", tipo=equipamento.tipo, local=equipamento.local)
            registro = Movimentacao.objects.create(
                tipo="RETIRADA", equipamento=unidade, operador=self.cenario["operador"],
                destinatario=self.cenario["professor"],
            )
            registros.append(registro.pk)
        Movimentacao.objects.filter(pk__in=registros).update(data_hora=agora)
        self.assertEqual(self.ids(busca="HIST-"), sorted(registros, reverse=True)[:25])
        resposta = self.client.get(self.url, {"busca": "HIST-", "tipo": "RETIRADA", "pagina": 2})
        self.assertEqual([item.pk for item in resposta.context["pagina"]], [registros[0]])
        self.assertContains(resposta, "busca=HIST-&amp;tipo=RETIRADA&amp;pagina=1")
        self.assertContains(resposta, "Mostrando 26–26 de 26")

    def test_tela_escapa_observacao_e_nao_oferece_edicao_ou_exclusao(self):
        antes = list(Movimentacao.objects.values())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(resposta, "<script>alert(1)</script>")
        self.assertNotContains(resposta, "Editar movimentação")
        self.assertNotContains(resposta, "Excluir movimentação")
        self.assertEqual(list(Movimentacao.objects.values()), antes)
