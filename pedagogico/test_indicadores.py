from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.test import TestCase
from django.urls import reverse

from inventario.models import Equipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from movimentacoes.services import (
    registrar_devolucoes, registrar_retirada_reserva, registrar_retirada_sem_reserva,
)
from reservas.models import Reserva, ReservaEquipamento
from usuarios.permissoes import pode_consultar_indicadores_pedagogicos

from .models import AtividadePedagogica, Disciplina, Turma, UtilizacaoPedagogica
from .services import salvar_contexto_reserva, salvar_contexto_retirada
from .test_utilizacao import preparar_utilizacao


class IndicadoresPedagogicosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario, cls.reserva, cls.unidades, cls.retiradas, cls.escolhas = preparar_utilizacao()

    def setUp(self):
        self.url = reverse("pedagogico:indicadores")
        self.client.force_login(self.cenario["administrador"])

    def salvar(self, reserva=None, **escolhas):
        return salvar_contexto_reserva(
            professor=self.cenario["professor"], reserva_id=(reserva or self.reserva).pk,
            **{**self.escolhas, **escolhas},
        )

    def devolver(self, retiradas=None):
        retiradas = self.retiradas if retiradas is None else retiradas
        registrar_devolucoes(
            operador=self.cenario["operador"], retirada_id=retiradas[0].pk,
            retiradas_ids=[item.pk for item in retiradas],
        )

    def retirar_novamente(self, indice=1, unidades=None):
        unidades = [self.unidades[0]] if unidades is None else unidades
        inicio = self.reserva.inicio + timedelta(days=7 * indice)
        reserva = Reserva.objects.create(
            professor=self.cenario["professor"], tipo_equipamento=self.reserva.tipo_equipamento,
            local=self.reserva.local, quantidade=len(unidades), inicio=inicio, fim=inicio + timedelta(hours=1),
        )
        ReservaEquipamento.objects.bulk_create(
            ReservaEquipamento(reserva=reserva, equipamento=unidade) for unidade in unidades
        )
        with patch("movimentacoes.services.timezone.now", return_value=inicio):
            retiradas = registrar_retirada_reserva(operador=self.cenario["operador"], reserva_id=reserva.pk)
        return reserva, retiradas

    def retirar_sem_reserva(self, unidades=None):
        unidades = self.unidades if unidades is None else unidades
        return registrar_retirada_sem_reserva(
            operador=self.cenario["operador"], destinatario=self.cenario["professor"],
            tipo_equipamento=self.reserva.tipo_equipamento, local=self.reserva.local,
            quantidade=len(unidades), equipamentos=unidades,
        )

    def test_sem_contexto_exibe_zeros_mesmo_com_retiradas_e_cadastros(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 0, "retiradas": 0, "equipamentos": 0})
        self.assertContains(resposta, "Nenhuma utilização pedagógica registrada")
        self.assertNotContains(resposta, "Turma RF-10")

    def test_lote_conta_unidades_com_contexto_e_exclui_retiradas_sem_contexto(self):
        self.salvar()
        Movimentacao.objects.create(
            tipo="RETIRADA", equipamento=self.cenario["equipamento"],
            operador=self.cenario["operador"], destinatario=self.cenario["professor"],
        )
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 1, "retiradas": 3, "equipamentos": 3})
        for grupo in resposta.context["grupos"]:
            linhas = list(grupo["pagina"])
            self.assertEqual(len(linhas), 1)
            self.assertEqual(linhas[0]["utilizacoes"], 1)
            self.assertEqual(linhas[0]["retiradas"], 3)
            self.assertEqual(linhas[0]["equipamentos"], 3)
            self.assertContains(resposta, self.escolhas[grupo["campo"]].nome)

    def test_equipamento_reutilizado_aumenta_retiradas_sem_duplicar_patrimonio(self):
        self.salvar()
        self.devolver()
        reserva, _ = self.retirar_novamente()
        self.salvar(reserva)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 2, "retiradas": 4, "equipamentos": 3})
        for grupo in resposta.context["grupos"]:
            linha = list(grupo["pagina"])[0]
            self.assertEqual((linha["utilizacoes"], linha["retiradas"], linha["equipamentos"]), (2, 4, 3))

    def test_agrupamentos_independentes_preservam_cadastros_sem_uso_fora_da_tabela(self):
        self.salvar()
        self.devolver()
        reserva, _ = self.retirar_novamente()
        escolhas = {
            "turma": Turma.objects.create(nome="Outra turma"),
            "disciplina": Disciplina.objects.create(nome="Outra disciplina"),
            "atividade": AtividadePedagogica.objects.create(nome="Outra atividade"),
        }
        self.salvar(reserva, **escolhas)
        Turma.objects.create(nome="Turma sem uso")
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 2, "retiradas": 4, "equipamentos": 3})
        for grupo in resposta.context["grupos"]:
            linhas = list(grupo["pagina"])
            por_nome = {linha["nome"]: linha for linha in linhas}
            self.assertEqual(len(por_nome), 2)
            for cadastro, quantidade in ((self.escolhas[grupo["campo"]], 3), (escolhas[grupo["campo"]], 1)):
                linha = por_nome[cadastro.nome]
                self.assertEqual((linha["utilizacoes"], linha["retiradas"], linha["equipamentos"]), (1, quantidade, quantidade))
        self.assertNotContains(resposta, "Turma sem uso")

    def test_duas_reservas_de_trinta_unidades_contam_dois_usos_e_preservam_distintos(self):
        self.devolver()
        unidades = [*self.unidades, *[
            Equipamento.objects.create(
                numero_patrimonio=f"INDICADORES-30-{indice:02}",
                tipo=self.reserva.tipo_equipamento, local=self.reserva.local,
            ) for indice in range(27)
        ]]
        primeira, retiradas = self.retirar_novamente(unidades=unidades)
        self.salvar(primeira)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 1, "retiradas": 30, "equipamentos": 30})
        for grupo in resposta.context["grupos"]:
            linha = list(grupo["pagina"])[0]
            self.assertEqual((linha["utilizacoes"], linha["retiradas"], linha["equipamentos"]), (1, 30, 30))
        self.devolver(retiradas[:29])
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 1, "retiradas": 30, "equipamentos": 30})
        self.devolver(retiradas[29:])
        segunda, _ = self.retirar_novamente(indice=2, unidades=unidades)
        self.salvar(segunda)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 2, "retiradas": 60, "equipamentos": 30})
        for grupo in resposta.context["grupos"]:
            linha = list(grupo["pagina"])[0]
            self.assertEqual((linha["utilizacoes"], linha["retiradas"], linha["equipamentos"]), (2, 60, 30))

    def test_reserva_sem_retirada_nao_aumenta_utilizacoes(self):
        self.salvar()
        Reserva.objects.create(
            professor=self.cenario["professor"], tipo_equipamento=self.reserva.tipo_equipamento,
            local=self.reserva.local, quantidade=30,
            inicio=self.reserva.inicio + timedelta(days=7), fim=self.reserva.fim + timedelta(days=7),
        )
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 1, "retiradas": 3, "equipamentos": 3})

    def test_lote_sem_reserva_de_trinta_e_reserva_com_mesmas_unidades(self):
        self.devolver()
        unidades = [*self.unidades, *[
            Equipamento.objects.create(
                numero_patrimonio=f"INDICADORES-SEM-RESERVA-{indice:02}",
                tipo=self.reserva.tipo_equipamento, local=self.reserva.local,
            ) for indice in range(27)
        ]]
        retiradas = self.retirar_sem_reserva(unidades)
        self.client.force_login(self.cenario["professor"])
        url = reverse("pedagogico:utilizacao_retirada", args=[retiradas[0].pk])
        self.assertRedirects(self.client.post(url, {
            campo: registro.pk for campo, registro in self.escolhas.items()
        }), url)
        self.client.force_login(self.cenario["administrador"])
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 1, "retiradas": 30, "equipamentos": 30})
        for grupo in resposta.context["grupos"]:
            linha = list(grupo["pagina"])[0]
            self.assertEqual((linha["utilizacoes"], linha["retiradas"], linha["equipamentos"]), (1, 30, 30))
        self.devolver(retiradas[:29])
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 1, "retiradas": 30, "equipamentos": 30})
        self.devolver(retiradas[29:])
        reserva, _ = self.retirar_novamente(unidades=unidades)
        self.salvar(reserva)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 2, "retiradas": 60, "equipamentos": 30})
        for grupo in resposta.context["grupos"]:
            linha = list(grupo["pagina"])[0]
            self.assertEqual((linha["utilizacoes"], linha["retiradas"], linha["equipamentos"]), (2, 60, 30))

    def test_lotes_sem_reserva_do_mesmo_professor_ficam_separados(self):
        self.devolver()
        primeira = self.retirar_sem_reserva()
        salvar_contexto_retirada(
            professor=self.cenario["professor"], retirada_id=primeira[0].pk, **self.escolhas,
        )
        self.devolver(primeira)
        segunda = self.retirar_sem_reserva()
        salvar_contexto_retirada(
            professor=self.cenario["professor"], retirada_id=segunda[0].pk, **self.escolhas,
        )
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 2, "retiradas": 6, "equipamentos": 3})
        self.devolver(segunda)
        Equipamento.objects.filter(pk__in=[unidade.pk for unidade in self.unidades]).update(ativo=False)
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 2, "retiradas": 6, "equipamentos": 3})
        self.client.force_login(self.cenario["professor"])
        self.assertEqual(self.client.get(reverse("pedagogico:utilizacao_lista")).context["pagina"].paginator.count, 3)

    def test_retiradas_antigas_sem_lote_sao_individuais(self):
        self.devolver()
        retiradas = self.retirar_sem_reserva()
        Movimentacao.objects.filter(pk__in=[item.pk for item in retiradas]).update(lote_retirada=None)
        Movimentacao.objects.filter(pk__in=[item.pk for item in retiradas]).update(data_hora=retiradas[0].data_hora)
        for retirada in retiradas:
            salvar_contexto_retirada(
                professor=self.cenario["professor"], retirada_id=retirada.pk, **self.escolhas,
            )
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 3, "retiradas": 3, "equipamentos": 3})
        for grupo in resposta.context["grupos"]:
            self.assertEqual(list(grupo["pagina"])[0]["utilizacoes"], 3)
        self.client.force_login(self.cenario["professor"])
        self.assertEqual(self.client.get(reverse("pedagogico:utilizacao_lista")).context["pagina"].paginator.count, 4)

    def test_lote_sem_reserva_sem_contexto_nao_entra_nos_indicadores(self):
        self.salvar()
        self.devolver()
        retiradas = self.retirar_sem_reserva()
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 1, "retiradas": 3, "equipamentos": 3})
        salvar_contexto_retirada(
            professor=self.cenario["professor"], retirada_id=retiradas[0].pk, **self.escolhas,
        )
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 2, "retiradas": 6, "equipamentos": 3})

    def test_edicao_do_contexto_sem_reserva_move_grupo_sem_criar_utilizacao(self):
        self.salvar()
        self.devolver()
        retiradas = self.retirar_sem_reserva()
        salvar_contexto_retirada(
            professor=self.cenario["professor"], retirada_id=retiradas[0].pk, **self.escolhas,
        )
        outra = Disciplina.objects.create(nome="Disciplina sem reserva corrigida")
        salvar_contexto_retirada(
            professor=self.cenario["professor"], retirada_id=retiradas[0].pk,
            **{**self.escolhas, "disciplina": outra},
        )
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 2, "retiradas": 6, "equipamentos": 3})
        linhas = list(next(grupo["pagina"] for grupo in resposta.context["grupos"] if grupo["campo"] == "disciplina"))
        self.assertEqual({linha["nome"]: linha["utilizacoes"] for linha in linhas}, {
            self.escolhas["disciplina"].nome: 1, outra.nome: 1,
        })

    def test_ordenacao_prioriza_frequencia_dos_usos_em_vez_do_tamanho_do_lote(self):
        self.salvar()
        self.devolver()
        escolhas = {
            "turma": Turma.objects.create(nome="Outra turma"),
            "disciplina": Disciplina.objects.create(nome="Outra disciplina"),
            "atividade": AtividadePedagogica.objects.create(nome="Outra atividade"),
        }
        for indice in (1, 2):
            reserva, retiradas = self.retirar_novamente(indice)
            self.salvar(reserva, **escolhas)
            self.devolver(retiradas)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 3, "retiradas": 5, "equipamentos": 3})
        for grupo in resposta.context["grupos"]:
            linhas = list(grupo["pagina"])
            self.assertEqual([linha["utilizacoes"] for linha in linhas], [2, 1])
            self.assertEqual([linha["retiradas"] for linha in linhas], [2, 3])
            self.assertEqual(linhas[0]["nome"], escolhas[grupo["campo"]].nome)

    def test_devolucao_parcial_integral_e_inativacao_preservam_totais(self):
        self.salvar()
        self.devolver(self.retiradas[:1])
        self.assertEqual(self.client.get(self.url).context["totais"], {"utilizacoes": 1, "retiradas": 3, "equipamentos": 3})
        self.devolver(self.retiradas[1:])
        Equipamento.objects.filter(pk__in=[item.pk for item in self.unidades]).update(ativo=False)
        for registro in self.escolhas.values():
            registro.ativo = False
            registro.save(update_fields=["ativo"])
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 1, "retiradas": 3, "equipamentos": 3})
        self.assertContains(resposta, "Cadastro inativo", count=3)

    def test_edicao_do_contexto_atualiza_consolidacao_sem_nova_utilizacao(self):
        self.salvar()
        disciplina = Disciplina.objects.create(nome="Disciplina corrigida")
        self.salvar(disciplina=disciplina)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 1, "retiradas": 3, "equipamentos": 3})
        self.assertEqual(UtilizacaoPedagogica.objects.count(), 3)
        grupo = next(grupo for grupo in resposta.context["grupos"] if grupo["campo"] == "disciplina")
        self.assertEqual(list(grupo["pagina"])[0]["nome"], disciplina.nome)
        self.assertNotContains(resposta, self.escolhas["disciplina"].nome)

    def test_paginacao_independente_e_desempate_por_nome(self):
        self.devolver()
        for indice in range(1, 13):
            reserva, retiradas = self.retirar_novamente(indice)
            escolhas = {
                "turma": Turma.objects.create(nome=f"Turma {indice:02}"),
                "disciplina": Disciplina.objects.create(nome=f"Disciplina {indice:02}"),
                "atividade": AtividadePedagogica.objects.create(nome=f"Atividade {indice:02}"),
            }
            self.salvar(reserva, **escolhas)
            self.devolver(retiradas)
        resposta = self.client.get(self.url, {"pagina_turma": 2, "pagina_disciplina": 1})
        self.assertEqual(resposta.context["totais"], {"utilizacoes": 12, "retiradas": 12, "equipamentos": 1})
        turmas, disciplinas, atividades = resposta.context["grupos"]
        self.assertEqual([linha["nome"] for linha in turmas["pagina"]], ["Turma 11", "Turma 12"])
        self.assertEqual(len(disciplinas["pagina"]), 10)
        self.assertEqual(len(atividades["pagina"]), 10)
        self.assertContains(resposta, "pagina_turma=2&amp;pagina_disciplina=2#heading-disciplina")
        for numero, esperado in (("invalido", 1), ("-1", 2), ("999", 2)):
            pagina = self.client.get(self.url, {"pagina_turma": numero}).context["grupos"][0]["pagina"]
            self.assertEqual(pagina.number, esperado)

    def test_nomes_escapados_e_dados_pessoais_ausentes_das_tabelas(self):
        self.escolhas["turma"].nome = "<script>alert('turma')</script>"
        self.escolhas["turma"].save(update_fields=["nome"])
        self.salvar()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "&lt;script&gt;")
        self.assertNotContains(resposta, "<script>alert")
        self.assertNotContains(resposta, self.cenario["professor"].username)

    def test_perfis_incompativeis_negados_mesmo_com_permissao_individual(self):
        permissao = Permission.objects.get(content_type__app_label="pedagogico", codename="view_utilizacaopedagogica")
        tecnico = get_user_model().objects.create_user(username="tecnico-indicadores", is_superuser=True)
        tecnico.groups.add(Group.objects.get(name="Administrador"))
        sem_grupo = get_user_model().objects.create_user(username="sem-grupo-indicadores")
        multiplos = get_user_model().objects.create_user(username="multiplos-indicadores")
        multiplos.groups.add(Group.objects.get(name="Administrador"), Group.objects.get(name="Operador"))
        for usuario in (self.cenario["operador"], self.cenario["professor"], tecnico, sem_grupo, multiplos):
            with self.subTest(usuario=usuario.username):
                usuario.user_permissions.add(permissao)
                registrar_aceite_vigente(usuario)
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url).status_code, 405)
                lista = self.client.get(reverse("inventario:equipamento_lista"))
                self.assertNotContains(lista, f'href="{self.url}"', status_code=lista.status_code)

    def test_administrador_sem_permissao_nao_acessa_nem_ve_link(self):
        grupo = Group.objects.get(name="Administrador")
        grupo.permissions.remove(Permission.objects.get(content_type__app_label="pedagogico", codename="view_utilizacaopedagogica"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("inventario:painel")), f'href="{self.url}"')

    def test_anonimo_e_conta_inativa_nao_acessam(self):
        self.assertFalse(pode_consultar_indicadores_pedagogicos(AnonymousUser()))
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")
        administrador = self.cenario["administrador"]
        administrador.is_active = False
        administrador.save(update_fields=["is_active"])
        self.assertFalse(pode_consultar_indicadores_pedagogicos(administrador))
        self.client.force_login(administrador)
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_consulta_nao_altera_registros_e_menu_destaca_apenas_indicadores(self):
        self.salvar()
        antes = list(UtilizacaoPedagogica.objects.values())
        movimentacoes = list(Movimentacao.objects.values())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{self.url}" aria-current="page"')
        self.assertContains(resposta, 'aria-current="page"', count=1)
        self.assertContains(self.client.get(reverse("inventario:painel")), f'href="{self.url}"')
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(list(UtilizacaoPedagogica.objects.values()), antes)
        self.assertEqual(list(Movimentacao.objects.values()), movimentacoes)
