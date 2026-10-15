from datetime import datetime, time, timedelta, timezone as datetime_timezone
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legal.services import registrar_aceite_vigente
from manutencoes.models import Manutencao
from movimentacoes.models import Movimentacao
from pedagogico.models import AtividadePedagogica, Disciplina, Turma, UtilizacaoPedagogica
from reservas.models import Reserva
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

    def retirada(self, equipamento, instante=None, **campos):
        registro = Movimentacao.objects.create(
            equipamento=equipamento, operador=self.operador, destinatario=self.professor,
            tipo=Movimentacao.Tipo.RETIRADA, **campos,
        )
        if instante:
            Movimentacao.objects.filter(pk=registro.pk).update(data_hora=instante)
        return registro

    def manutencao(self, equipamento, instante, estado=Manutencao.Estado.PENDENTE):
        campos = {}
        agora = timezone.now()
        if estado != Manutencao.Estado.PENDENTE:
            campos.update(iniciado_por=self.admin, data_inicio=agora + timedelta(seconds=1))
        if estado == Manutencao.Estado.CONCLUIDA:
            campos.update(
                concluido_por=self.admin, data_conclusao=agora + timedelta(seconds=2),
                resultado=Manutencao.Resultado.REPARADO, descricao_solucao="Reparo realizado",
            )
        registro = Manutencao.objects.create(
            equipamento=equipamento, aberto_por=self.admin, descricao_problema="Falha de teste",
            estado=estado, **campos,
        )
        Manutencao.objects.filter(pk=registro.pk).update(data_abertura=instante)
        return registro

    def test_categorias_somam_ativos_mesmo_com_tipo_categoria_ou_local_inativo(self):
        outra = Categoria.objects.create(nome="Categoria sem cadastro ativo", ativo=False)
        tipo = TipoEquipamento.objects.create(categoria=outra, nome="Tipo inativo", ativo=False)
        self.local.ativo = False
        self.local.save(update_fields=["ativo"])
        for indice, situacao in enumerate(Equipamento.Situacao.values):
            self.equipamento(f"CAT-{indice}", situacao=situacao)
            self.equipamento(f"EXCLUIDO-{indice}", situacao=situacao, ativo=False)
        Equipamento.objects.create(numero_patrimonio="OUTRO", tipo=tipo, local=self.local)
        resposta = self.client.get(self.url)
        linhas = resposta.context["situacao_por_categoria"]
        self.assertEqual(len(linhas), 2)
        self.assertEqual(sum(item["total"] for item in linhas), resposta.context["indicadores"]["ativos"])
        for chave in ("disponiveis", "em_uso", "manutencao"):
            self.assertEqual(sum(item[chave] for item in linhas), resposta.context["indicadores"][chave])
        self.assertEqual([item["indisponiveis"] for item in linhas], [2, 0])
        self.assertContains(resposta, "Somente equipamentos ativos; inativos excluídos")
        self.assertContains(resposta, "não indica disponibilidade para uma reserva futura")

    @patch("inventario.views.timezone.now")
    def test_retiradas_periodo_local_limites_e_dias_sem_registros(self, agora):
        # Em UTC já é dia 15; em São Paulo ainda é dia 14.
        agora.return_value = datetime(2026, 10, 15, 1, 30, tzinfo=datetime_timezone.utc)
        fuso = timezone.get_default_timezone()
        hoje = timezone.localdate(timezone=fuso)
        inicio = timezone.make_aware(datetime.combine(hoje - timedelta(days=29), time.min), fuso)
        fim = timezone.make_aware(datetime.combine(hoje + timedelta(days=1), time.min), fuso)
        equipamento = self.equipamento("DATAS")
        for instante in (inicio - timedelta(microseconds=1), inicio,
                         fim - timedelta(microseconds=1), fim):
            self.retirada(equipamento, instante)
        # 01:00 UTC pertence ao dia anterior no fuso da aplicação.
        self.retirada(equipamento, datetime(2026, 9, 30, 1, tzinfo=datetime_timezone.utc))
        resposta = self.client.get(self.url)
        dias = resposta.context["retiradas_diarias"]
        self.assertEqual(len(dias), 30)
        self.assertEqual(dias[0]["dia"], inicio.date())
        self.assertEqual(dias[-1]["dia"], hoje)
        self.assertEqual(dias[0]["total"], 1)
        self.assertEqual(dias[-1]["total"], 1)
        self.assertEqual(sum(item["total"] == 0 for item in dias), 27)
        totais = {item["dia"].isoformat(): item["total"] for item in dias}
        self.assertEqual(totais["2026-09-29"], 1)
        self.assertEqual(totais["2026-09-30"], 0)
        self.assertEqual(resposta.context["total_retiradas"], 3)
        self.assertEqual(resposta.context["fim_periodo"].isoformat(), "2026-10-14")

    def test_retiradas_contam_unidades_lotes_reuso_e_independem_de_contexto(self):
        agora = timezone.now()
        reserva = Reserva.objects.create(
            professor=self.professor, tipo_equipamento=self.tipo, local=self.local,
            quantidade=3, inicio=agora, fim=agora + timedelta(hours=1),
        )
        unidades = [self.equipamento(f"LOTE-{indice}") for indice in range(3)]
        com_reserva = [self.retirada(item, reserva=reserva) for item in unidades]
        lote = uuid4()
        sem_reserva = [self.retirada(item, lote_retirada=lote) for item in unidades]
        self.retirada(unidades[0])  # Uma nova retirada da mesma unidade também conta.
        for retirada in (com_reserva[0], sem_reserva[0]):
            UtilizacaoPedagogica.objects.create(
                movimentacao=retirada, professor=self.professor,
                turma=Turma.objects.create(nome=f"Turma {retirada.pk}"),
                disciplina=Disciplina.objects.create(nome=f"Disciplina {retirada.pk}"),
                atividade=AtividadePedagogica.objects.create(nome=f"Atividade {retirada.pk}"),
            )
        Movimentacao.objects.create(
            equipamento=unidades[0], operador=self.operador, destinatario=self.professor,
            tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem=sem_reserva[0],
        )
        Equipamento.objects.filter(pk__in=[item.pk for item in unidades]).update(ativo=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["total_retiradas"], 7)
        self.assertEqual(resposta.context["retiradas_diarias"][-1]["total"], 7)
        self.assertEqual(resposta.context["indicadores"]["ativos"], 0)
        self.assertEqual(len(resposta.context["movimentacoes_recentes"]), 8)

    def test_novos_paineis_vazios_nao_fabricam_dados(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["situacao_por_categoria"], [])
        self.assertEqual(len(resposta.context["retiradas_diarias"]), 30)
        self.assertTrue(all(item["total"] == 0 for item in resposta.context["retiradas_diarias"]))
        self.assertEqual(list(resposta.context["manutencoes_abertas"]), [])
        self.assertContains(resposta, "Nenhuma retirada registrada no período")
        self.assertContains(resposta, "Nenhuma manutenção em aberto")
        self.assertContains(resposta, "Consultar tabela dos 30 dias")

    def test_manutencoes_apenas_abertas_cinco_mais_antigas_com_desempate(self):
        inicio = timezone.now() - timedelta(days=10)
        registros = []
        for indice in range(7):
            equipamento = self.equipamento(f"MAN-{indice}", ativo=indice != 0)
            registro = self.manutencao(
                equipamento, inicio + timedelta(days=indice // 2),
                Manutencao.Estado.EM_ANDAMENTO if indice % 2 else Manutencao.Estado.PENDENTE,
            )
            registros.append(registro)
        concluida = self.manutencao(
            self.equipamento("CONCLUIDO"), inicio - timedelta(days=1), Manutencao.Estado.CONCLUIDA,
        )
        resposta = self.client.get(self.url)
        self.assertEqual([item.pk for item in resposta.context["manutencoes_abertas"]],
                         [item.pk for item in registros[:5]])
        for registro in registros[:5]:
            self.assertContains(resposta, reverse("manutencoes:manutencao_detalhe", args=[registro.pk]))
        self.assertNotContains(resposta, reverse("manutencoes:manutencao_detalhe", args=[concluida.pk]))
        self.assertNotContains(resposta, "CONCLUIDO")
        self.assertContains(resposta, "Pendente")
        self.assertContains(resposta, "Em andamento")

    def test_sem_permissao_de_manutencao_nao_consulta_nem_expoe_registros(self):
        registro = self.manutencao(self.equipamento("RESTRITO"), timezone.now())
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(codename="view_manutencao"))
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["manutencoes_abertas"]), [])
        self.assertFalse(any('FROM "manutencoes_manutencao"' in item["sql"] for item in consultas))
        self.assertNotContains(resposta, "RESTRITO")
        self.assertNotContains(resposta, reverse("manutencoes:manutencao_detalhe", args=[registro.pk]))
        self.assertContains(resposta, "Consulta de manutenções restrita")
        self.assertFalse(grupo.permissions.filter(codename="view_manutencao").exists())

    def test_filtro_de_categoria_atualiza_todos_os_paineis(self):
        outra = Categoria.objects.create(nome="Outra categoria")
        outro_tipo = TipoEquipamento.objects.create(categoria=outra, nome="Outro tipo")
        selecionado = self.equipamento("SELECIONADO")
        excluido = Equipamento.objects.create(numero_patrimonio="FORA", tipo=outro_tipo, local=self.local)
        for equipamento in (selecionado, excluido):
            self.retirada(equipamento)
            self.manutencao(equipamento, timezone.now())
        resposta = self.client.get(self.url, {"categoria": self.tipo.categoria_id})
        self.assertEqual(resposta.context["indicadores"]["ativos"], 1)
        self.assertEqual(len(resposta.context["situacao_por_categoria"]), 1)
        self.assertEqual(resposta.context["total_retiradas"], 1)
        self.assertEqual([item.equipamento_id for item in resposta.context["manutencoes_abertas"]], [selecionado.pk])
        self.assertEqual([item.equipamento_id for item in resposta.context["movimentacoes_recentes"]], [selecionado.pk])
        self.assertContains(resposta, "Limpar filtro")

    def test_categoria_invalida_ignorada_e_categoria_vazia_preservada(self):
        self.equipamento("PRESENTE")
        for valor in ("invalida", "999999", "-1", "9" * 5000):
            with self.subTest(valor=valor[:20]):
                resposta = self.client.get(self.url, {"categoria": valor})
                self.assertIsNone(resposta.context["categoria_selecionada"])
                self.assertEqual(resposta.context["indicadores"]["ativos"], 1)
        vazia = Categoria.objects.create(nome="Categoria vazia")
        resposta = self.client.get(self.url, {"categoria": vazia.pk})
        self.assertEqual(resposta.context["categoria_selecionada"], vazia)
        self.assertEqual(resposta.context["indicadores"]["ativos"], 0)
        self.assertEqual(resposta.context["total_retiradas"], 0)

    def test_consultas_de_dados_sao_constantes_sem_repeticao_por_registro(self):
        def consultas_de_dados():
            with CaptureQueriesContext(connection) as consultas:
                self.client.get(self.url)
            tabelas = ("inventario_categoria", "inventario_equipamento", "movimentacoes_movimentacao",
                       "manutencoes_manutencao")
            return [item["sql"] for item in consultas
                    if any(f'FROM "{tabela}"' in item["sql"] for tabela in tabelas)]

        self.assertEqual(len(consultas_de_dados()), 6)
        for indice in range(12):
            equipamento = self.equipamento(f"CONSULTAS-{indice}")
            self.retirada(equipamento)
            self.manutencao(equipamento, timezone.now())
        self.assertEqual(len(consultas_de_dados()), 6)

    def test_barras_diarias_e_detalhes_preservam_dados_sem_javascript(self):
        self.retirada(self.equipamento("SEM-JS"))
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, 'id="day-select"')
        self.assertContains(resposta, 'data-day-feedback hidden')
        self.assertNotContains(resposta, 'Consultar um dia')
        self.assertContains(resposta, 'class="activity-record"')
        self.assertContains(resposta, "operador-painel")
        self.assertContains(resposta, "professor-painel")
        self.assertContains(resposta, "Consultar tabela dos 30 dias")
        self.assertContains(resposta, "Como as retiradas são contadas")
