from movimentacoes.fixtures_testes import criar_retirada_legada
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente

from .models import Movimentacao
from .services import registrar_devolucao, registrar_retirada_reserva
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
        cls.sem_reserva = criar_retirada_legada(
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

    def registros(self, **filtros):
        from .services import consultar_historico
        return list(consultar_historico(filtros, usuario=self.cenario["operador"]).values_list("pk", flat=True))

    def test_historico_agrupado_nao_exibe_reserva_em_uso(self):
        for perfil in ("professor", "operador", "administrador"):
            self.client.force_login(self.cenario[perfil])
            resposta = self.client.get(self.url)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(len(resposta.context["pagina"]), 0)
            self.assertEqual(resposta.context["pagina_legados"].paginator.count, 1)
            self.assertNotIn(self.com_reserva[0].pk, self.registros())

    def test_registro_legado_tem_retirada_e_devolucao_sem_perder_observacao(self):
        resposta = self.client.get(self.url, {"retirada": self.sem_reserva.pk})
        self.assertEqual({r.pk for r in resposta.context["pagina"]}, {self.sem_reserva.pk, self.devolucao.pk})
        self.assertContains(resposta, "Conferido &lt;script&gt;")
        self.assertNotContains(resposta, "<script>alert(1)</script>")
        self.assertNotContains(resposta, "Excluir")

    def test_professor_consulta_somente_o_proprio_historico(self):
        outro = get_user_model().objects.create_user(username="professor-historico-alheio")
        outro.groups.add(Group.objects.get(name="Professor"))
        registrar_aceite_vigente(outro)
        self.client.force_login(outro)
        resposta = self.client.get(self.url, {"retirada": self.sem_reserva.pk})
        self.assertEqual(len(resposta.context["pagina"]), 0)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["pagina_legados"].paginator.count, 0)

    def test_perfis_incompativeis_nao_consultam_mesmo_com_permissao_avulsa(self):
        tecnico = get_user_model().objects.create_user(username="tecnico-historico", is_superuser=True)
        tecnico.groups.add(Group.objects.get(name="Administrador"))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo-historico")
        multiplo = get_user_model().objects.create_user(username="multiplo-historico")
        multiplo.groups.add(*Group.objects.filter(name__in=("Administrador", "Operador")))
        for usuario in (tecnico, sem_grupo, multiplo):
            registrar_aceite_vigente(usuario)
            usuario.user_permissions.add(Permission.objects.get(codename="view_movimentacao"))
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_filtros_das_movimentacoes_preservam_registros_e_origens(self):
        self.assertEqual(set(self.registros(busca="PAT-RF05")), {self.sem_reserva.pk, self.devolucao.pk})
        self.assertEqual(self.registros(tipo="DEVOLUCAO"), [self.devolucao.pk])
        self.assertEqual(self.registros(reserva=self.reserva.pk), [])
        self.assertEqual(self.registros(busca="inexistente"), [])
        data = timezone.localtime(self.sem_reserva.data_hora).date()
        self.assertEqual(set(self.registros(inicio=data, fim=data)), {self.sem_reserva.pk, self.devolucao.pk})

    def test_filtros_invalidos_nao_alargam_consulta(self):
        for filtros in ({"reserva": "texto"}, {"tipo": "adulterado"}, {"retirada": "-1"},
                        {"inicio": "2026-10-03", "fim": "2026-10-02"}, {"inicio": "data inválida"}):
            resposta = self.client.get(self.url, filtros)
            self.assertTrue(resposta.context["form"].errors)
            self.assertEqual(len(resposta.context["pagina"]), 0)
            self.assertEqual(resposta.context["pagina_legados"].paginator.count, 0)

    def test_anonimo_precisa_login_e_historico_nao_aceita_escrita(self):
        antes = list(Movimentacao.objects.values())
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), reverse("login") + "?next=" + self.url)
        self.assertEqual(list(Movimentacao.objects.values()), antes)

    def test_sem_permissao_nao_consulta_e_link_e_ocultado(self):
        Group.objects.get(name="Operador").permissions.remove(Permission.objects.get(codename="view_movimentacao"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        self.assertNotContains(resposta, f'href="{self.url}"')

    def test_paginacao_preserva_lote_encerrado_e_filtros(self):
        import html
        import re
        from .services import registrar_devolucoes
        equipamento = self.cenario["equipamento"]
        unidades = [Equipamento.objects.create(numero_patrimonio=f"LOTE-HIST-{n}", tipo=equipamento.tipo, local=equipamento.local) for n in range(13)]
        retiradas = criar_retirada_legada(operador=self.cenario["operador"], destinatario=self.cenario["professor"], equipamentos=unidades)
        registrar_devolucoes(operador=self.cenario["operador"], retirada_id=retiradas[0].pk, retiradas_ids=[r.pk for r in retiradas])
        resposta = self.client.get(self.url, {"retirada": retiradas[0].pk})
        link = re.search(r'href="([^"]+)"[^>]*>Próxima', resposta.content.decode()).group(1)
        self.assertIn(f"retirada={retiradas[0].pk}", html.unescape(link))
        segunda = self.client.get(self.url + html.unescape(link))
        self.assertEqual(segunda.context["pagina"].paginator.count, 26)
        self.assertEqual(len(segunda.context["pagina"]), 1)
        self.assertIn(list(segunda.context["pagina"])[0].retirada_origem_id or list(segunda.context["pagina"])[0].pk, [r.pk for r in retiradas])
