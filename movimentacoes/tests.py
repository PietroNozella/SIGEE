from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from usuarios.permissoes import GRUPOS_FUNCIONAIS

from .forms import RetiradaSemReservaForm
from .models import Movimentacao
from .services import equipamentos_disponiveis_para_retirada, registrar_retirada_sem_reserva


def criar_cenario():
    call_command("configurar_perfis", stdout=StringIO())
    usuarios = {}
    for nome in GRUPOS_FUNCIONAIS:
        usuario = get_user_model().objects.create_user(username=nome.lower())
        usuario.groups.add(Group.objects.get(name=nome))
        registrar_aceite_vigente(usuario)
        usuarios[nome.lower()] = usuario
    tipo = TipoEquipamento.objects.create(
        categoria=Categoria.objects.create(nome="Categoria RF-05"),
        nome="Projetor RF-05",
    )
    usuarios["equipamento"] = Equipamento.objects.create(
        numero_patrimonio="PAT-RF05",
        tipo=tipo,
        local=Local.objects.create(nome="Local RF-05"),
    )
    return usuarios


class RetiradaSemReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nome, objeto in criar_cenario().items():
            setattr(cls, nome, objeto)
        cls.sem_grupo = get_user_model().objects.create_user(username="sem-grupo")
        cls.tecnico = get_user_model().objects.create_user(
            username="tecnico", is_superuser=True, is_staff=True,
        )
        cls.multiplos = get_user_model().objects.create_user(username="multiplos")
        cls.multiplos.groups.add(*Group.objects.filter(name__in=GRUPOS_FUNCIONAIS[:2]))
        cls.inativo = get_user_model().objects.create_user(username="inativo", is_active=False)
        cls.inativo.groups.add(Group.objects.get(name="Professor"))
        cls.grupo_estranho = get_user_model().objects.create_user(username="outro-grupo")
        cls.grupo_estranho.groups.add(Group.objects.create(name="Grupo externo"))
        for usuario in (cls.sem_grupo, cls.tecnico, cls.multiplos, cls.grupo_estranho):
            registrar_aceite_vigente(usuario)

    def setUp(self):
        self.url = reverse("movimentacoes:retirada_sem_reserva")
        self.client.force_login(self.operador)
        self.dados = {
            "tipo_equipamento": self.equipamento.tipo_id,
            "local": self.equipamento.local_id,
            "quantidade": 1,
            "equipamentos": [self.equipamento.pk],
            "destinatario": self.professor.pk,
            "observacao": "Entrega na secretaria.",
        }

    def retirar(self, **kwargs):
        dados = {
            "operador": self.operador,
            "tipo_equipamento": self.equipamento.tipo,
            "local": self.equipamento.local,
            "quantidade": 1,
            "equipamentos": [self.equipamento],
            "destinatario": self.professor,
        }
        equipamento = kwargs.pop("equipamento", None)
        if equipamento is not None:
            dados.update(tipo_equipamento=equipamento.tipo, local=equipamento.local, equipamentos=[equipamento])
        dados.update(kwargs)
        return registrar_retirada_sem_reserva(**dados)[0]

    def assert_sem_retirada(self, situacao=Equipamento.Situacao.DISPONIVEL):
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, situacao)
        self.assertFalse(Movimentacao.objects.exists())
        self.assertFalse(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.RETIRADA_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).exists())

    def test_retirada_pela_tela_define_operador_hora_tipo_e_situacao_no_servidor(self):
        antes = timezone.now()
        resposta = self.client.post(self.url, {
            **self.dados,
            "operador": self.administrador.pk,
            "data_hora": "2000-01-01T00:00:00",
            "tipo": Movimentacao.Tipo.DEVOLUCAO,
            "reserva": "999",
            "retirada_origem": "999",
        }, follow=True)
        self.assertRedirects(resposta, reverse("movimentacoes:devolucao_lista"))
        self.assertContains(resposta, "Retirada de 1 equipamento(s) registrada com sucesso")
        self.assertContains(resposta, 'data-auto-dismiss="true"')
        retirada = Movimentacao.objects.get()
        self.assertEqual(retirada.operador, self.operador)
        self.assertEqual(retirada.destinatario, self.professor)
        self.assertEqual(retirada.equipamento, self.equipamento)
        self.assertEqual(retirada.tipo, Movimentacao.Tipo.RETIRADA)
        self.assertEqual(retirada.observacao, self.dados["observacao"])
        self.assertIsNone(retirada.reserva_id)
        self.assertIsNone(retirada.retirada_origem_id)
        self.assertLessEqual(antes, retirada.data_hora)
        self.assertLessEqual(retirada.data_hora, timezone.now())
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, Equipamento.Situacao.EM_USO)
        evento = RegistroAuditoria.objects.get(acao=AcaoAuditoria.RETIRADA_REGISTRADA)
        self.assertEqual(evento.usuario, self.operador)
        self.assertEqual(evento.entidade_id, str(retirada.pk))
        self.assertEqual(evento.resultado, RegistroAuditoria.Resultado.SUCESSO)

    def test_destinatarios_dos_tres_perfis_e_observacao_vazia_sao_aceitos(self):
        for destinatario in (self.administrador, self.operador, self.professor):
            with self.subTest(perfil=destinatario.username):
                equipamento = Equipamento.objects.create(
                    numero_patrimonio=f"PAT-{destinatario.username}",
                    tipo=self.equipamento.tipo, local=self.equipamento.local,
                )
                retirada = self.retirar(equipamento=equipamento, destinatario=destinatario)
                self.assertEqual(retirada.destinatario, destinatario)
                self.assertEqual(retirada.observacao, "")
                equipamento.refresh_from_db()
                self.assertEqual(equipamento.situacao, Equipamento.Situacao.EM_USO)

    def test_acesso_direto_negado_a_outros_perfis_mesmo_com_permissao_avulsa(self):
        permissao = Permission.objects.get(codename="add_movimentacao")
        self.tecnico.groups.add(Group.objects.get(name="Operador"))
        for usuario in (self.administrador, self.professor, self.sem_grupo,
                        self.tecnico, self.multiplos, self.grupo_estranho):
            usuario.user_permissions.add(permissao)
            self.client.force_login(usuario)
            for metodo in ("get", "post"):
                with self.subTest(usuario=usuario.username, metodo=metodo):
                    resposta = getattr(self.client, metodo)(self.url, self.dados)
                    self.assertEqual(resposta.status_code, 403)
                    self.assert_sem_retirada()
            with self.assertRaises(PermissionDenied):
                self.retirar(operador=usuario)

    def test_operador_sem_permissao_recebe_403_e_link_fica_oculto(self):
        grupo = Group.objects.get(name="Operador")
        grupo.permissions.remove(Permission.objects.get(codename="add_movimentacao"))
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        self.assertNotContains(resposta, 'href="' + self.url + '"')
        with self.assertRaises(PermissionDenied):
            self.retirar()
        self.assert_sem_retirada()

    def test_operador_inativado_e_revalidado_no_servico(self):
        get_user_model().objects.filter(pk=self.operador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.retirar()
        self.assert_sem_retirada()

    def test_anonimo_e_redirecionado_para_login(self):
        self.client.logout()
        for metodo in ("get", "post"):
            dados = self.dados if metodo == "post" else {}
            resposta = getattr(self.client, metodo)(self.url, dados)
            self.assertRedirects(resposta, reverse("login") + "?next=" + self.url)
        self.assert_sem_retirada()

    def test_navegacao_do_operador_agrupa_retiradas_em_reservas_sem_gravar(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Registrar retirada")
        navegacao = resposta.content.decode().split('<nav class="sidebar-navigation"')[1].split("</nav>")[0]
        self.assertEqual(navegacao.count('<a '), 4)
        for opcao in ("Equipamentos", "Reservas", "Em uso", "Histórico"):
            self.assertIn(opcao, navegacao)
        self.assertIn(f'href="{reverse("movimentacoes:retirada_reserva_lista")}" aria-current="page"', navegacao)
        self.assertNotIn(f'href="{self.url}"', navegacao)
        for opcao in ("Visão geral", "Registrar retirada", "Registrar devolução", "Manutenções", "Gestão educacional",
                      "Uso pedagógico", "Turmas", "Disciplinas", "Atividades",
                      "Administração", "Usuários", "Configurações", "Auditoria"):
            self.assertNotIn(opcao, navegacao)
        reservas = self.client.get(reverse("movimentacoes:retirada_reserva_lista"))
        self.assertContains(reservas, f'href="{self.url}">Registrar retirada</a>')
        self.assert_sem_retirada()

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.operador)
        self.assertEqual(cliente.post(self.url, self.dados).status_code, 403)
        self.assert_sem_retirada()

    def test_formulario_oferece_somente_equipamento_ativo_disponivel(self):
        for ativo, situacao in ((False, Equipamento.Situacao.DISPONIVEL),
                               (True, Equipamento.Situacao.EM_USO),
                               (True, Equipamento.Situacao.MANUTENCAO)):
            Equipamento.objects.create(
                numero_patrimonio=f"PAT-{ativo}-{situacao}",
                tipo=self.equipamento.tipo, local=self.equipamento.local,
                ativo=ativo, situacao=situacao,
            )
        self.assertEqual(list(equipamentos_disponiveis_para_retirada(tipo_equipamento=self.equipamento.tipo, local=self.equipamento.local)),
                         [self.equipamento])

    def test_equipamento_invalido_no_post_e_no_servico_nao_altera_dados(self):
        for ativo, situacao in ((False, Equipamento.Situacao.DISPONIVEL),
                               (True, Equipamento.Situacao.EM_USO),
                               (True, Equipamento.Situacao.MANUTENCAO)):
            with self.subTest(ativo=ativo, situacao=situacao):
                Equipamento.objects.filter(pk=self.equipamento.pk).update(
                    ativo=ativo, situacao=situacao,
                )
                resposta = self.client.post(self.url, self.dados)
                self.assertContains(resposta, "Revise os campos indicados")
                with self.assertRaises(ValidationError):
                    self.retirar()
                self.assert_sem_retirada(situacao)

    def test_destinatarios_invalidos_nao_sao_oferecidos_nem_aceitos(self):
        self.tecnico.groups.add(Group.objects.get(name="Professor"))
        self.assertCountEqual(
            RetiradaSemReservaForm().fields["destinatario"].queryset,
            [self.administrador, self.operador, self.professor],
        )
        for usuario in (self.sem_grupo, self.tecnico, self.multiplos,
                        self.inativo, self.grupo_estranho):
            with self.subTest(destinatario=usuario.username):
                resposta = self.client.post(self.url, {**self.dados, "destinatario": usuario.pk})
                self.assertContains(resposta, "Selecione um destinatário ativo")
                with self.assertRaises(ValidationError):
                    self.retirar(destinatario=usuario)
                self.assert_sem_retirada()

    def test_grupo_adicional_invalida_destinatario(self):
        self.professor.groups.add(Group.objects.get(name="Grupo externo"))
        with self.assertRaises(ValidationError):
            self.retirar()
        self.assert_sem_retirada()

    def test_destinatario_inativado_apos_validacao_e_reconsultado(self):
        form = RetiradaSemReservaForm(self.dados)
        self.assertTrue(form.is_valid())
        get_user_model().objects.filter(pk=self.professor.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.retirar(destinatario=form.cleaned_data["destinatario"])
        self.assert_sem_retirada()

    def test_ids_inexistentes_e_formulario_vazio_nao_gravam(self):
        for dados in ({}, {**self.dados, "equipamentos": [999999]},
                      {**self.dados, "destinatario": 999999}):
            resposta = self.client.post(self.url, dados)
            self.assertContains(resposta, "Revise os campos indicados")
            self.assert_sem_retirada()

    def test_estado_alterado_apos_validacao_retorna_erro_na_tela(self):
        def retirar_apos_mudanca(**kwargs):
            Equipamento.objects.filter(pk=self.equipamento.pk).update(
                situacao=Equipamento.Situacao.MANUTENCAO,
            )
            return registrar_retirada_sem_reserva(**kwargs)

        with patch("movimentacoes.views.registrar_retirada_sem_reserva",
                   side_effect=retirar_apos_mudanca):
            resposta = self.client.post(self.url, self.dados)
        self.assertContains(resposta, "não está disponível para retirada. Revise o lote.")
        self.assertContains(resposta, 'aria-invalid="true"')
        self.assertContains(resposta, 'aria-describedby="id_equipamentos_error"')
        self.assert_sem_retirada(Equipamento.Situacao.MANUTENCAO)

    def test_segunda_retirada_e_rejeitada_preservando_primeira(self):
        primeira = self.retirar()
        with self.assertRaises(ValidationError):
            self.retirar()
        resposta = self.client.post(self.url, self.dados)
        self.assertContains(resposta, "Revise os campos indicados")
        self.assertEqual(list(Movimentacao.objects.all()), [primeira])
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, Equipamento.Situacao.EM_USO)

    def test_falha_na_atualizacao_do_equipamento_desfaz_movimentacao(self):
        with patch("inventario.models.Equipamento.save", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.retirar()
        self.assert_sem_retirada()

    def test_falha_na_auditoria_desfaz_movimentacao_e_situacao(self):
        with patch("movimentacoes.services.registrar_evento", side_effect=IntegrityError("falha")):
            with self.assertRaises(IntegrityError):
                self.retirar()
        self.assert_sem_retirada()


    def test_falha_de_integridade_na_tela_exibe_erro_e_preserva_consistencia(self):
        for alvo in ("inventario.models.Equipamento.save",
                     "movimentacoes.services.registrar_evento"):
            with self.subTest(falha=alvo):
                with patch(alvo, side_effect=IntegrityError("falha")):
                    resposta = self.client.post(self.url, self.dados)
                self.assertContains(resposta, "Nenhuma alteração foi salva.")
                self.assert_sem_retirada()


    def test_admin_tecnico_consulta_mas_nao_contorna_fluxo_de_gravacao(self):
        retirada = self.retirar()
        self.client.force_login(self.tecnico)
        lista = reverse("admin:movimentacoes_movimentacao_changelist")
        self.assertContains(self.client.get(lista, {"q": "Projetor RF-05"}), "PAT-RF05")
        detalhe = reverse("admin:movimentacoes_movimentacao_change", args=[retirada.pk])
        self.assertEqual(self.client.get(detalhe).status_code, 200)
        for rota in (
            reverse("admin:movimentacoes_movimentacao_add"),
            reverse("admin:movimentacoes_movimentacao_delete", args=[retirada.pk]),
        ):
            self.assertEqual(self.client.get(rota).status_code, 403)
            self.assertEqual(self.client.post(rota, self.dados).status_code, 403)
        self.assertEqual(self.client.post(detalhe, self.dados).status_code, 403)
        self.assertEqual(Movimentacao.objects.count(), 1)
        retirada.refresh_from_db()
        self.assertEqual(retirada.destinatario, self.professor)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.situacao, Equipamento.Situacao.EM_USO)


    def criar_unidades(self, quantidade):
        return [Equipamento.objects.create(
            numero_patrimonio=f"LOTE-{indice:03d}",
            tipo=self.equipamento.tipo, local=self.equipamento.local,
        ) for indice in range(quantidade)]

    def dados_lote(self, unidades):
        return {**self.dados, "quantidade": len(unidades),
                "equipamentos": [item.pk for item in unidades]}

    def test_tela_registra_30_equipamentos_de_uma_vez(self):
        unidades = self.criar_unidades(30)
        resposta = self.client.post(self.url, self.dados_lote(unidades), follow=True)
        self.assertContains(resposta, "Retirada de 30 equipamento(s) registrada com sucesso")
        self.assertCountEqual(
            Movimentacao.objects.values_list("equipamento_id", flat=True),
            [item.pk for item in unidades],
        )
        self.assertEqual(Equipamento.objects.filter(
            pk__in=[item.pk for item in unidades], situacao=Equipamento.Situacao.EM_USO,
        ).count(), 30)
        self.assertEqual(Movimentacao.objects.filter(
            operador=self.operador, destinatario=self.professor,
            tipo=Movimentacao.Tipo.RETIRADA, reserva=None, retirada_origem=None,
            observacao=self.dados["observacao"],
        ).count(), 30)
        self.assertEqual(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.RETIRADA_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).count(), 30)

    def test_troca_de_unidade_grava_exatamente_os_patrimonios_conferidos(self):
        unidades = self.criar_unidades(3)
        selecionadas = [unidades[0], unidades[2]]
        self.assertEqual(self.client.post(self.url, self.dados_lote(selecionadas)).status_code, 302)
        self.assertCountEqual(Movimentacao.objects.values_list("equipamento_id", flat=True),
                              [item.pk for item in selecionadas])
        unidades[1].refresh_from_db()
        self.assertEqual(unidades[1].situacao, Equipamento.Situacao.DISPONIVEL)

    def test_lote_rejeita_quantidade_invalida_duplicatas_e_ids_inexistentes(self):
        unidades = self.criar_unidades(2)
        for alteracoes in (
            {"quantidade": 0}, {"quantidade": -1}, {"quantidade": 3},
            {"equipamentos": [unidades[0].pk, unidades[0].pk]},
            {"equipamentos": [unidades[0].pk, 999999]},
            {"equipamentos": []},
        ):
            with self.subTest(entrada=alteracoes):
                resposta = self.client.post(self.url, {**self.dados_lote(unidades), **alteracoes})
                self.assertContains(resposta, "Revise os campos indicados")
                self.assert_sem_retirada()
        with self.assertRaises(ValidationError):
            registrar_retirada_sem_reserva(
                operador=self.operador, destinatario=self.professor,
                tipo_equipamento=self.equipamento.tipo, local=self.equipamento.local,
                quantidade=2, equipamentos=[unidades[0], unidades[0]],
            )
        self.assert_sem_retirada()

    def test_lote_nao_aceita_outro_tipo_ou_local(self):
        unidades = self.criar_unidades(2)
        outro_local = Local.objects.create(nome="Outro local RF-05")
        outro_tipo = TipoEquipamento.objects.create(categoria=self.equipamento.tipo.categoria,
                                                    nome="Outro modelo RF-05")
        for campo, valor in (("local", outro_local), ("tipo", outro_tipo)):
            with self.subTest(campo=campo):
                Equipamento.objects.filter(pk=unidades[1].pk).update(**{campo: valor})
                resposta = self.client.post(self.url, self.dados_lote(unidades))
                self.assertContains(resposta, "Todos os patrimônios devem pertencer")
                self.assert_sem_retirada()
                Equipamento.objects.filter(pk=unidades[1].pk).update(
                    local=self.equipamento.local, tipo=self.equipamento.tipo,
                )

    def test_uma_unidade_indisponivel_impede_todo_o_lote(self):
        unidades = self.criar_unidades(3)
        Equipamento.objects.filter(pk=unidades[-1].pk).update(situacao=Equipamento.Situacao.EM_USO)
        resposta = self.client.post(self.url, self.dados_lote(unidades))
        self.assertContains(resposta, "LOTE-002 está inativo ou não está disponível")
        self.assert_sem_retirada()
        self.assertEqual(Equipamento.objects.filter(
            pk__in=[item.pk for item in unidades[:2]], situacao=Equipamento.Situacao.DISPONIVEL,
        ).count(), 2)

    def test_falha_no_meio_do_lote_desfaz_gravacoes_anteriores(self):
        unidades = self.criar_unidades(3)
        salvar_original = Equipamento.save

        def salvar_ou_falhar(equipamento, *args, **kwargs):
            if equipamento.pk == unidades[1].pk:
                raise IntegrityError("falha na segunda unidade")
            return salvar_original(equipamento, *args, **kwargs)

        with patch.object(Equipamento, "save", salvar_ou_falhar):
            resposta = self.client.post(self.url, self.dados_lote(unidades))
        self.assertContains(resposta, "Nenhuma alteração foi salva.")
        self.assert_sem_retirada()
        self.assertEqual(Equipamento.objects.filter(
            pk__in=[item.pk for item in unidades], situacao=Equipamento.Situacao.DISPONIVEL,
        ).count(), 3)

    def test_consulta_protegida_filtra_unidades_e_informa_patrimonios(self):
        unidades = self.criar_unidades(3)
        Equipamento.objects.filter(pk=unidades[1].pk).update(ativo=False)
        Equipamento.objects.filter(pk=unidades[2].pk).update(situacao=Equipamento.Situacao.MANUTENCAO)
        rota = reverse("movimentacoes:retirada_disponibilidade")
        resposta = self.client.get(rota, {"tipo_equipamento": self.equipamento.tipo_id})
        dados = resposta.json()
        self.assertEqual(dados["local"], self.equipamento.local_id)
        self.assertEqual(dados["disponiveis"], 2)
        self.assertCountEqual([item["id"] for item in dados["equipamentos"]],
                              [self.equipamento.pk, unidades[0].pk])
        self.assertIn("LOTE-000", [item["patrimonio"] for item in dados["equipamentos"]])
        self.assert_sem_retirada()
        self.assertEqual(self.client.post(rota, self.dados).status_code, 405)
        for usuario in (self.administrador, self.professor, self.tecnico, self.multiplos):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(rota, {"tipo_equipamento": self.equipamento.tipo_id}).status_code, 403)

    def test_consulta_nao_escolhe_local_quando_ha_mais_de_um(self):
        outra = Equipamento.objects.create(
            numero_patrimonio="OUTRO-LOCAL", tipo=self.equipamento.tipo,
            local=Local.objects.create(nome="Outro ponto de retirada"),
        )
        rota = reverse("movimentacoes:retirada_disponibilidade")
        dados = self.client.get(rota, {"tipo_equipamento": self.equipamento.tipo_id}).json()
        self.assertIsNone(dados["local"])
        self.assertEqual(dados["equipamentos"], [])
        dados = self.client.get(rota, {"tipo_equipamento": self.equipamento.tipo_id,
                                       "local": outra.local_id}).json()
        self.assertEqual([item["id"] for item in dados["equipamentos"]], [outra.pk])

    def test_consulta_sem_javascript_sugere_quantidade_e_preserva_destinatario(self):
        unidades = self.criar_unidades(3)
        resposta = self.client.post(self.url, {**self.dados_lote(unidades[:2]),
                                               "acao": "consultar"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context["selecionados"]), 2)
        self.assertEqual(resposta.context["form"].initial["destinatario"], str(self.professor.pk))
        self.assertContains(resposta, "LOTE-000")
        self.assert_sem_retirada()

    def test_consulta_invalida_preserva_formulario_completo(self):
        resposta = self.client.post(self.url, {"acao": "consultar"})
        self.assertContains(resposta, "Revise os campos indicados")
        self.assertContains(resposta, 'id="id_destinatario"')
        self.assert_sem_retirada()

    def test_inativacao_do_tipo_ou_local_nao_acrescenta_bloqueio_fisico(self):
        TipoEquipamento.objects.filter(pk=self.equipamento.tipo_id).update(ativo=False)
        Local.objects.filter(pk=self.equipamento.local_id).update(ativo=False)
        self.assertEqual(self.client.post(self.url, self.dados).status_code, 302)


class ConcorrenciaRetiradaTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_duas_retiradas_simultaneas_gravam_apenas_uma(self):
        cenario = criar_cenario()
        barreira = Barrier(2)
        segunda = Equipamento.objects.create(
            numero_patrimonio="CONCORRENTE-002",
            tipo=cenario["equipamento"].tipo, local=cenario["equipamento"].local,
        )

        def tentar_retirar():
            try:
                operador = get_user_model().objects.get(pk=cenario["operador"].pk)
                destinatario = get_user_model().objects.get(pk=cenario["professor"].pk)
                equipamento = Equipamento.objects.get(pk=cenario["equipamento"].pk)
                outra_unidade = Equipamento.objects.get(pk=segunda.pk)
                barreira.wait(timeout=10)
                try:
                    registrar_retirada_sem_reserva(
                        operador=operador, tipo_equipamento=equipamento.tipo, local=equipamento.local,
                        quantidade=2, equipamentos=[equipamento, outra_unidade], destinatario=destinatario,
                    )
                except ValidationError:
                    return "indisponivel"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tentativas = [executor.submit(tentar_retirar) for _ in range(2)]
            resultados = [tentativa.result(timeout=20) for tentativa in tentativas]

        self.assertCountEqual(resultados, ["sucesso", "indisponivel"])
        self.assertEqual(Movimentacao.objects.count(), 2)
        cenario["equipamento"].refresh_from_db()
        self.assertEqual(cenario["equipamento"].situacao, Equipamento.Situacao.EM_USO)
        self.assertEqual(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.RETIRADA_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).count(), 2)
