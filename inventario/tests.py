from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from usuarios.permissoes import GRUPO_ADMINISTRADOR

from .forms import EquipamentoForm
from .models import Categoria, Equipamento, Local, TipoEquipamento


class EquipamentoRN01Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Notebook Dell")
        cls.local = Local.objects.get(nome="Laboratório de informática")
        cls.usuario = get_user_model().objects.create_user(
            username="usuario-inventario",
            password="senha-segura-123",
        )
        cls.usuario.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        registrar_aceite_vigente(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)

    def dados_equipamento(self, patrimonio):
        return {"numero_patrimonio": patrimonio, "nome": "Notebook Dell", "descricao": "Equipamento para uso pedagógico.", "categoria": self.categoria.pk, "local": self.local.pk, "situacao": Equipamento.Situacao.DISPONIVEL}

    def criar_equipamento(self, patrimonio, **dados):
        nome = dados.pop("nome", "Notebook existente")
        categoria = dados.pop("categoria", self.categoria)
        tipo = dados.pop("tipo", None) or TipoEquipamento.objects.get_or_create(categoria=categoria, nome=nome)[0]
        return Equipamento.objects.create(numero_patrimonio=patrimonio, tipo=tipo, local=dados.pop("local", self.local), **dados)

    def test_patrimonio_novo_e_validado_e_salvo(self):
        formulario = EquipamentoForm(data=self.dados_equipamento("PAT-001"))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        equipamento = formulario.save()
        self.assertEqual(equipamento.numero_patrimonio, "PAT-001")
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_formulario_rejeita_patrimonio_duplicado(self):
        self.criar_equipamento("PAT-001")
        formulario = EquipamentoForm(data=self.dados_equipamento("PAT-001"))
        self.assertFalse(formulario.is_valid())
        self.assertTrue(formulario.has_error("numero_patrimonio", code="unique"))
        self.assertIn(Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO, formulario.errors["numero_patrimonio"])
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_modelo_rejeita_patrimonio_duplicado_antes_de_salvar(self):
        self.criar_equipamento("PAT-001")
        duplicado = Equipamento(numero_patrimonio="PAT-001", tipo=self.tipo, local=self.local)
        with self.assertRaisesMessage(ValidationError, Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO):
            duplicado.full_clean()
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_banco_impede_patrimonio_duplicado(self):
        self.criar_equipamento("PAT-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.criar_equipamento("PAT-001", nome="Outro notebook")
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_listagem_exibe_estado_vazio_e_acao_de_cadastro(self):
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Nenhum equipamento cadastrado")
        self.assertContains(resposta, reverse("inventario:equipamento_novo"))

    def test_listagem_exibe_indicadores_calculados_com_dados_reais(self):
        self.criar_equipamento("PAT-001", nome="Notebook disponível", situacao=Equipamento.Situacao.DISPONIVEL)
        self.criar_equipamento("PAT-002", nome="Notebook em uso", situacao=Equipamento.Situacao.EM_USO)
        self.criar_equipamento("PAT-003", nome="Notebook em manutenção", situacao=Equipamento.Situacao.MANUTENCAO)
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        self.assertEqual(resposta.context["indicadores"], {"total": 3, "disponiveis": 1, "em_uso": 1, "manutencao": 1})
        self.assertContains(resposta, "Em uso")
        self.assertNotContains(resposta, "Reservados")

    def test_listagem_filtra_por_texto_categoria_local_e_situacao(self):
        outra_categoria = Categoria.objects.get(nome="Projetor")
        outro_local = Local.objects.get(nome="Sala multimídia")
        self.criar_equipamento("PAT-001", nome="Notebook Dell", situacao=Equipamento.Situacao.DISPONIVEL)
        self.criar_equipamento("PAT-002", nome="Projetor Epson", categoria=outra_categoria, local=outro_local, situacao=Equipamento.Situacao.MANUTENCAO)
        resposta = self.client.get(reverse("inventario:equipamento_lista"), {"busca": "Epson", "categoria": outra_categoria.pk, "local": outro_local.pk, "situacao": Equipamento.Situacao.MANUTENCAO})
        self.assertContains(resposta, "PAT-002")
        self.assertNotContains(resposta, "PAT-001")

    def test_tela_de_cadastro_exibe_campos_do_equipamento_form(self):
        resposta = self.client.get(reverse("inventario:equipamento_novo"))
        self.assertEqual(resposta.status_code, 200)
        for texto in ("Número de patrimônio", "Tipo/modelo do equipamento", "Categoria", "Local", "Situação", "Notebook", "Sala-01", "csrfmiddlewaretoken"):
            self.assertContains(resposta, texto)

    def test_post_cadastra_patrimonio_novo_e_confirma_sucesso(self):
        resposta = self.client.post(reverse("inventario:equipamento_novo"), self.dados_equipamento("PAT-001"), follow=True)
        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertContains(resposta, "Equipamento cadastrado com sucesso.")
        self.assertEqual(Equipamento.objects.count(), 1)

    def test_post_duplicado_exibe_mensagem_e_nao_cria_registro(self):
        self.criar_equipamento("PAT-001")
        resposta = self.client.post(reverse("inventario:equipamento_novo"), self.dados_equipamento("PAT-001"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO)
        self.assertContains(resposta, 'aria-invalid="true"')
        self.assertEqual(Equipamento.objects.count(), 1)


class ExclusaoEquipamentoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Notebook educacional")
        cls.local = Local.objects.create(nome="Sala de tecnologia")
        cls.administrador = get_user_model().objects.create_user(username="administrador-inventario", password="senha-segura-123")
        cls.administrador.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        cls.operador = get_user_model().objects.create_user(username="operador", password="senha-segura-123")
        cls.destinatario = get_user_model().objects.create_user(username="professor", password="senha-segura-123")
        registrar_aceite_vigente(cls.administrador)

    def setUp(self):
        self.client.force_login(self.administrador)

    def criar_equipamento(self, patrimonio):
        return Equipamento.objects.create(numero_patrimonio=patrimonio, tipo=self.tipo, local=self.local)

    def test_exclui_definitivamente_equipamento_sem_historico(self):
        equipamento = self.criar_equipamento("PAT-001")
        equipamento.delete()
        self.assertFalse(Equipamento.objects.filter(pk=equipamento.pk).exists())

    def test_inativa_equipamento_com_movimentacao(self):
        equipamento = self.criar_equipamento("PAT-002")
        equipamento.situacao = Equipamento.Situacao.EM_USO
        equipamento.save(update_fields=["situacao", "data_atualizacao"])
        movimentacao = Movimentacao.objects.create(equipamento=equipamento, operador=self.operador, destinatario=self.destinatario, tipo="RETIRADA")
        equipamento.delete()
        equipamento.refresh_from_db()
        self.assertFalse(equipamento.ativo)
        self.assertEqual(equipamento.situacao, Equipamento.Situacao.EM_USO)
        self.assertEqual(movimentacao.equipamento_id, equipamento.pk)
        self.assertTrue(Movimentacao.objects.filter(pk=movimentacao.pk).exists())

    def test_segunda_exclusao_de_equipamento_inativo_preserva_historico(self):
        equipamento = self.criar_equipamento("PAT-003")
        movimentacao = Movimentacao.objects.create(equipamento=equipamento, operador=self.operador, destinatario=self.destinatario, tipo="RETIRADA")
        equipamento.delete()
        equipamento.delete()
        equipamento.refresh_from_db()
        self.assertFalse(equipamento.ativo)
        self.assertEqual(equipamento.movimentacoes.count(), 1)
        self.assertTrue(Movimentacao.objects.filter(pk=movimentacao.pk).exists())

    def test_exclusao_em_lote_do_admin_aplica_a_regra(self):
        sem_historico = self.criar_equipamento("PAT-004")
        com_historico = self.criar_equipamento("PAT-005")
        Movimentacao.objects.create(equipamento=com_historico, operador=self.operador, destinatario=self.destinatario, tipo="RETIRADA")
        admin.site._registry[Equipamento].delete_queryset(request=None, queryset=Equipamento.objects.filter(pk__in=[sem_historico.pk, com_historico.pk]))
        self.assertFalse(Equipamento.objects.filter(pk=sem_historico.pk).exists())
        com_historico.refresh_from_db()
        self.assertFalse(com_historico.ativo)
        self.assertEqual(com_historico.movimentacoes.count(), 1)

    def test_exclusao_por_queryset_aplica_a_regra(self):
        equipamento = self.criar_equipamento("PAT-006")
        movimentacao = Movimentacao.objects.create(equipamento=equipamento, operador=self.operador, destinatario=self.destinatario, tipo="RETIRADA")

        Equipamento.objects.filter(pk=equipamento.pk).delete()

        equipamento.refresh_from_db()
        self.assertFalse(equipamento.ativo)
        self.assertTrue(Movimentacao.objects.filter(pk=movimentacao.pk).exists())

    def test_post_exclui_equipamento_sem_historico(self):
        equipamento = self.criar_equipamento("PAT-007")

        resposta = self.client.post(reverse("inventario:equipamento_excluir", args=[equipamento.pk]), follow=True)

        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertContains(resposta, "Equipamento excluído com sucesso.")
        self.assertFalse(Equipamento.objects.filter(pk=equipamento.pk).exists())

    def test_lista_renderiza_modal_para_exclusao_sem_historico(self):
        equipamento = self.criar_equipamento("PAT-CONF-001")

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, 'id="modal-exclusao"')
        self.assertContains(resposta, 'data-delete-trigger')
        self.assertContains(resposta, 'data-equipamento-nome="Notebook educacional"')
        self.assertContains(resposta, 'data-equipamento-patrimonio="PAT-CONF-001"')
        self.assertContains(resposta, 'data-possui-historico="false"')
        self.assertNotContains(resposta, 'onclick="return confirm(')

    def test_lista_indica_historico_para_modal_de_exclusao(self):
        equipamento = self.criar_equipamento("PAT-CONF-002")
        Movimentacao.objects.create(
            equipamento=equipamento,
            operador=self.operador,
            destinatario=self.destinatario,
            tipo="RETIRADA",
        )

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, 'data-possui-historico="true"')

    def test_post_inativa_equipamento_com_historico_e_exibe_estado(self):
        equipamento = self.criar_equipamento("PAT-008")
        Movimentacao.objects.create(equipamento=equipamento, operador=self.operador, destinatario=self.destinatario, tipo="RETIRADA")

        resposta = self.client.post(reverse("inventario:equipamento_excluir", args=[equipamento.pk]), follow=True)

        equipamento.refresh_from_db()
        self.assertFalse(equipamento.ativo)
        self.assertContains(resposta, "histórico de movimentações preservado")
        self.assertContains(resposta, "Inativo")

    def test_exclusao_por_get_nao_e_permitida(self):
        equipamento = self.criar_equipamento("PAT-009")

        resposta = self.client.get(reverse("inventario:equipamento_excluir", args=[equipamento.pk]))

        self.assertEqual(resposta.status_code, 405)
        self.assertTrue(Equipamento.objects.filter(pk=equipamento.pk).exists())


class ImportacaoEquipamentosCSVTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Notebook CSV")
        cls.local = Local.objects.get(nome="Laboratório de informática")
        cls.usuario = get_user_model().objects.create_user(
            username="usuario-importacao",
            password="senha-segura-123",
        )
        cls.usuario.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        registrar_aceite_vigente(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)

    def arquivo_csv(self, conteudo, nome="equipamentos.csv"):
        return SimpleUploadedFile(
            nome,
            conteudo.encode("utf-8"),
            content_type="text/csv",
        )

    def cabecalho(self, delimitador=";"):
        return delimitador.join(
            (
                "numero_patrimonio",
                "nome",
                "descricao",
                "categoria",
                "local",
                "situacao",
            )
        )

    def linha_valida(self, patrimonio, delimitador=";"):
        return delimitador.join(
            (
                patrimonio,
                "Notebook educacional",
                "Uso em sala de aula",
                self.categoria.nome,
                self.local.nome,
                Equipamento.Situacao.DISPONIVEL,
            )
        )

    def importar(self, conteudo, nome="equipamentos.csv"):
        return self.client.post(
            reverse("inventario:equipamento_importar"),
            {"arquivo": self.arquivo_csv(conteudo, nome)},
        )

    def test_listagem_exibe_acao_de_importacao(self):
        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, "Importar CSV")
        self.assertContains(resposta, reverse("inventario:equipamento_importar"))

    def test_tela_de_importacao_exibe_instrucoes_e_modelo(self):
        resposta = self.client.get(reverse("inventario:equipamento_importar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Importar equipamentos")
        self.assertContains(resposta, "multipart/form-data")
        self.assertContains(resposta, "Baixar modelo CSV")

    def test_modelo_csv_contem_cabecalhos_esperados(self):
        resposta = self.client.get(reverse("inventario:equipamento_modelo_csv"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", resposta["Content-Disposition"])
        self.assertEqual(
            resposta.content.decode("utf-8-sig"),
            self.cabecalho() + "\n",
        )

    def test_importa_lote_valido_separado_por_ponto_e_virgula(self):
        conteudo = "\n".join(
            (
                self.cabecalho(),
                self.linha_valida("PAT-CSV-001"),
                self.linha_valida("PAT-CSV-002"),
            )
        )

        resposta = self.importar(conteudo, nome="equipamentos.CSV")

        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertEqual(Equipamento.objects.count(), 2)
        self.assertTrue(
            Equipamento.objects.filter(numero_patrimonio="PAT-CSV-001").exists()
        )

    def test_importa_lote_valido_separado_por_virgula(self):
        conteudo = "\n".join(
            (
                self.cabecalho(","),
                self.linha_valida("PAT-CSV-003", ","),
            )
        )

        resposta = self.importar(conteudo)

        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertTrue(
            Equipamento.objects.filter(numero_patrimonio="PAT-CSV-003").exists()
        )

    def test_erro_em_uma_linha_impede_importacao_do_lote(self):
        linha_invalida = self.linha_valida("PAT-CSV-005").replace(
            self.categoria.nome,
            "Categoria inexistente",
        )
        conteudo = "\n".join(
            (
                self.cabecalho(),
                self.linha_valida("PAT-CSV-004"),
                linha_invalida,
            )
        )

        resposta = self.importar(conteudo)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Linha 3: Categoria não encontrada.")
        self.assertEqual(Equipamento.objects.count(), 0)

    def test_rejeita_patrimonio_duplicado_no_banco_sem_salvar_lote(self):
        Equipamento.objects.create(
            numero_patrimonio="PAT-CSV-006",
            tipo=self.tipo,
            local=self.local,
        )
        conteudo = "\n".join(
            (
                self.cabecalho(),
                self.linha_valida("PAT-CSV-006"),
                self.linha_valida("PAT-CSV-007"),
            )
        )

        resposta = self.importar(conteudo)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO)
        self.assertFalse(
            Equipamento.objects.filter(numero_patrimonio="PAT-CSV-007").exists()
        )

    def test_rejeita_patrimonio_duplicado_no_arquivo(self):
        conteudo = "\n".join(
            (
                self.cabecalho(),
                self.linha_valida("PAT-CSV-008"),
                self.linha_valida("PAT-CSV-008"),
            )
        )

        resposta = self.importar(conteudo)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Linha 3: Número de patrimônio duplicado no arquivo.")
        self.assertEqual(Equipamento.objects.count(), 0)

    def test_rejeita_situacao_invalida_sem_salvar_lote(self):
        linha_invalida = self.linha_valida("PAT-CSV-009").replace(
            Equipamento.Situacao.DISPONIVEL,
            "INDISPONIVEL",
        )
        conteudo = "\n".join(
            (
                self.cabecalho(),
                self.linha_valida("PAT-CSV-010"),
                linha_invalida,
            )
        )

        resposta = self.importar(conteudo)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Linha 3: Situação:")
        self.assertEqual(Equipamento.objects.count(), 0)

    def test_rejeita_cabecalhos_invalidos(self):
        conteudo = "patrimonio;nome\nPAT-CSV-011;Notebook"

        resposta = self.importar(conteudo)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Os cabeçalhos devem ser:")
        self.assertEqual(Equipamento.objects.count(), 0)

    def test_rejeita_arquivo_com_mais_de_mil_equipamentos(self):
        conteudo = "\n".join(
            [self.cabecalho()]
            + [self.linha_valida(f"PAT-LIMITE-{indice}") for indice in range(1001)]
        )

        resposta = self.importar(conteudo)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            "O arquivo CSV pode conter no máximo 1.000 equipamentos.",
        )
        self.assertEqual(Equipamento.objects.count(), 0)


class AutenticacaoTests(TestCase):
    SENHA = "senha-segura-123"

    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.usuario = get_user_model().objects.create_user(
            username="administrador",
            password=cls.SENHA,
            first_name="Administrador",
            last_name="SIGEE",
        )
        cls.usuario.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        registrar_aceite_vigente(cls.usuario)

    def test_tela_de_login_usa_formulario_do_django_e_csrf(self):
        resposta = self.client.get(reverse("login"))

        self.assertEqual(resposta.status_code, 200)
        self.assertIsInstance(resposta.context["view"], LoginView)
        self.assertIsInstance(resposta.context["form"], AuthenticationForm)
        self.assertContains(resposta, 'name="username"')
        self.assertContains(resposta, 'name="password"')
        self.assertContains(resposta, 'name="csrfmiddlewaretoken"')

    def test_senha_e_armazenada_com_hash_do_django(self):
        self.assertNotEqual(self.usuario.password, self.SENHA)
        self.assertTrue(self.usuario.check_password(self.SENHA))

    def test_login_correto_inicia_sessao_e_redireciona_para_listagem(self):
        resposta = self.client.post(
            reverse("login"),
            {"username": self.usuario.username, "password": self.SENHA},
        )

        self.assertRedirects(
            resposta,
            reverse("inventario:equipamento_lista"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            self.usuario.pk,
        )

    def test_credenciais_invalidas_exibem_a_mesma_mensagem_neutra(self):
        tentativas = (
            {"username": self.usuario.username, "password": "senha-incorreta"},
            {"username": "usuario-inexistente", "password": "senha-incorreta"},
        )

        for credenciais in tentativas:
            with self.subTest(username=credenciais["username"]):
                resposta = self.client.post(reverse("login"), credenciais)

                self.assertEqual(resposta.status_code, 200)
                self.assertContains(
                    resposta,
                    "Nome de usuário ou senha inválidos.",
                    count=1,
                )
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_todas_as_paginas_do_inventario_exigem_autenticacao(self):
        rotas = (
            ("get", reverse("inventario:equipamento_lista")),
            ("get", reverse("inventario:equipamento_novo")),
            ("get", reverse("inventario:equipamento_importar")),
            ("get", reverse("inventario:equipamento_modelo_csv")),
            ("post", reverse("inventario:equipamento_excluir", args=[999])),
        )

        for metodo, rota in rotas:
            with self.subTest(rota=rota):
                resposta = getattr(self.client, metodo)(rota)
                destino = f'{reverse("login")}?next={rota}'

                self.assertRedirects(
                    resposta,
                    destino,
                    fetch_redirect_response=False,
                )
                self.assertIsInstance(resposta.wsgi_request.user, AnonymousUser)

    def test_login_preserva_next_e_retorna_a_pagina_solicitada(self):
        destino = reverse("inventario:equipamento_importar")
        resposta_restrita = self.client.get(destino)

        self.assertEqual(
            resposta_restrita.url,
            f'{reverse("login")}?next={destino}',
        )
        resposta_login = self.client.get(resposta_restrita.url)
        self.assertContains(
            resposta_login,
            f'<input type="hidden" name="next" value="{destino}">',
            html=True,
        )

        resposta_login = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.username,
                "password": self.SENHA,
                "next": destino,
            },
        )

        self.assertRedirects(
            resposta_login,
            destino,
            fetch_redirect_response=False,
        )

    def test_base_exibe_usuario_autenticado_e_logout_por_post(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, "Administrador SIGEE")
        self.assertContains(resposta, self.usuario.username)
        self.assertContains(
            resposta,
            f'<form class="logout-form" method="post" action="{reverse("logout")}">',
            html=False,
        )
        self.assertContains(resposta, "data-logout-trigger")
        self.assertContains(resposta, "data-logout-dialog")
        self.assertContains(resposta, "Tem certeza de que deseja encerrar sua sessão no SIGEE?")
        self.assertContains(resposta, "Sim, sair")

    def test_logout_aceita_somente_post_e_impede_retorno_direto(self):
        self.client.force_login(self.usuario)

        resposta_get = self.client.get(reverse("logout"))
        self.assertEqual(resposta_get.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

        resposta_post = self.client.post(reverse("logout"))
        self.assertIs(resposta_post.resolver_match.func.view_class, LogoutView)
        self.assertRedirects(
            resposta_post,
            reverse("login"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

        rota_protegida = reverse("inventario:equipamento_lista")
        resposta_retorno = self.client.get(rota_protegida)
        destino = f'{reverse("login")}?next={rota_protegida}'
        self.assertRedirects(
            resposta_retorno,
            destino,
            fetch_redirect_response=False,
        )
