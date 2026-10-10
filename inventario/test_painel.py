from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from usuarios.permissoes import pode_consultar_painel

from .models import Categoria, Equipamento, Local, TipoEquipamento


class PainelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.tipo = TipoEquipamento.objects.create(
            categoria=Categoria.objects.get(nome="Notebook"), nome="Notebook de teste",
        )
        cls.local = Local.objects.get(nome="Laboratório de informática")
        cls.admin = get_user_model().objects.create_user(username="admin-painel")
        cls.admin.groups.add(Group.objects.get(name="Administrador"))
        cls.operador = get_user_model().objects.create_user(username="operador-painel")
        cls.operador.groups.add(Group.objects.get(name="Operador"))
        cls.professor = get_user_model().objects.create_user(username="professor-painel")
        cls.professor.groups.add(Group.objects.get(name="Professor"))
        for usuario in (cls.admin, cls.operador, cls.professor):
            registrar_aceite_vigente(usuario)

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("inventario:painel")

    def equipamento(self, patrimonio, **campos):
        return Equipamento.objects.create(
            numero_patrimonio=patrimonio, tipo=self.tipo, local=self.local, **campos,
        )

    def test_inventario_vazio_exibe_zeros_e_estados_vazios(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["indicadores"], {
            "ativos": 0, "disponiveis": 0, "em_uso": 0, "manutencao": 0, "inativos": 0,
        })
        self.assertTrue(all(item["percentual"] == 0 for item in resposta.context["distribuicao"]))
        self.assertContains(resposta, "Nenhum equipamento ativo")
        self.assertContains(resposta, "Nenhuma movimentação registrada")

    def test_totais_e_grafico_separam_inativos_em_todas_as_situacoes(self):
        for indice, situacao in enumerate(Equipamento.Situacao.values):
            self.equipamento(f"ATIVO-{indice}", situacao=situacao)
            self.equipamento(f"INATIVO-{indice}", situacao=situacao, ativo=False)
        self.equipamento("ATIVO-EXTRA")
        resposta = self.client.get(self.url, {"situacao": "MANUTENCAO", "busca": "INATIVO"})
        self.assertEqual(resposta.context["indicadores"], {
            "ativos": 4, "disponiveis": 2, "em_uso": 1, "manutencao": 1, "inativos": 3,
        })
        distribuicao = resposta.context["distribuicao"]
        self.assertEqual([item["total"] for item in distribuicao], [2, 1, 1])
        self.assertEqual([item["percentual"] for item in distribuicao], [50, 25, 25])
        self.assertContains(resposta, 'style="width: 50.00%"')

    def test_apenas_inativos_nao_produzem_grafico_com_equipamentos_ativos(self):
        self.equipamento("INATIVO", ativo=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["indicadores"]["inativos"], 1)
        self.assertEqual(resposta.context["indicadores"]["ativos"], 0)
        self.assertContains(resposta, "Nenhum equipamento ativo")
        self.assertNotContains(resposta, 'class="distribution-track"')

    def test_movimentacoes_limitadas_a_dez_com_desempate_e_historico_preservado(self):
        equipamento = self.equipamento("PAT-HISTORICO", ativo=False)
        instante = timezone.now() - timedelta(days=1)
        registros = []
        for indice in range(12):
            registro = Movimentacao.objects.create(
                equipamento=equipamento, operador=self.operador, destinatario=self.professor,
                tipo=Movimentacao.Tipo.RETIRADA,
            )
            Movimentacao.objects.filter(pk=registro.pk).update(
                data_hora=instante if indice < 2 else instante + timedelta(hours=1),
            )
            registros.append(registro)
        devolucao = Movimentacao.objects.create(
            equipamento=equipamento, operador=self.operador, destinatario=self.professor,
            tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem=registros[-1],
        )
        resposta = self.client.get(self.url)
        recentes = list(resposta.context["movimentacoes_recentes"])
        self.assertEqual([registro.pk for registro in recentes],
                         [devolucao.pk] + [registro.pk for registro in reversed(registros[-9:])])
        self.assertContains(resposta, "PAT-HISTORICO", count=10)
        self.assertContains(resposta, "Retirada")
        self.assertContains(resposta, "Devolução")
        self.assertContains(resposta, "operador-painel")
        self.assertContains(resposta, "professor-painel")
        self.assertContains(resposta, timezone.localtime(instante).strftime("%d/%m/%Y"))

    def test_menos_de_dez_movimentacoes_e_texto_livre_escapado(self):
        equipamento = self.equipamento("PAT-ESCAPE")
        self.tipo.nome = "<script>alert('teste')</script>"
        self.tipo.save(update_fields=["nome"])
        Movimentacao.objects.create(
            equipamento=equipamento, operador=self.operador,
            destinatario=self.professor, tipo=Movimentacao.Tipo.RETIRADA,
        )
        resposta = self.client.get(self.url)
        self.assertEqual(len(resposta.context["movimentacoes_recentes"]), 1)
        self.assertContains(resposta, "&lt;script&gt;")
        self.assertNotContains(resposta, "<script>alert")

    def test_perfis_incompativeis_e_permissao_individual_nao_liberam_painel(self):
        permissao = Permission.objects.get(codename="view_resumo_inventario")
        superuser = get_user_model().objects.create_user(username="tecnico", is_superuser=True)
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo")
        multiplos = get_user_model().objects.create_user(username="multiplos")
        multiplos.groups.add(Group.objects.get(name="Administrador"), Group.objects.get(name="Operador"))
        for usuario in (self.operador, self.professor, superuser, sem_grupo, multiplos):
            with self.subTest(usuario=usuario.username):
                usuario.user_permissions.add(permissao)
                registrar_aceite_vigente(usuario)
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                lista = self.client.get(reverse("inventario:equipamento_lista"))
                self.assertNotContains(lista, f'href="{self.url}"', status_code=lista.status_code)

    def test_administrador_sem_permissao_nao_acessa_nem_ve_link(self):
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(codename="view_resumo_inventario"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("inventario:equipamento_lista")),
                              f'href="{self.url}"')

    def test_anonimo_e_conta_inativa_nao_acessam(self):
        self.assertFalse(pode_consultar_painel(AnonymousUser()))
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        self.assertFalse(pode_consultar_painel(self.admin))
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_menu_destaca_somente_painel_e_respeita_permissao_do_historico(self):
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(codename="view_movimentacao"))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{self.url}" aria-current="page"')
        self.assertContains(resposta, 'aria-current="page"', count=1)
        self.assertNotContains(resposta, reverse("movimentacoes:historico_lista"))
        self.assertContains(self.client.get(reverse("inventario:equipamento_lista")),
                            f'href="{self.url}"')

    def test_painel_nao_aceita_post_nem_altera_inventario(self):
        equipamento = self.equipamento("PAT-CONSULTA")
        self.assertEqual(self.client.post(self.url, {"ativo": "False"}).status_code, 405)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        equipamento.refresh_from_db()
        self.assertTrue(equipamento.ativo)
        self.assertEqual(Equipamento.objects.count(), 1)
        self.assertEqual(Movimentacao.objects.count(), 0)
