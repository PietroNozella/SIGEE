from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from legal.services import registrar_aceite_vigente

from .forms import AtividadePedagogicaForm, DisciplinaForm, TurmaForm
from .models import AtividadePedagogica, Disciplina, Turma


CADASTROS = (
    ("turmas", Turma, TurmaForm),
    ("disciplinas", Disciplina, DisciplinaForm),
    ("atividades", AtividadePedagogica, AtividadePedagogicaForm),
)


class CadastroModelFormTests(TestCase):
    def test_nome_obrigatorio_limites_e_espacos(self):
        for cadastro, modelo, formulario in CADASTROS:
            limite = modelo._meta.get_field("nome").max_length
            for nome in ("", "   ", "a" * (limite + 1)):
                with self.subTest(cadastro=cadastro, nome=nome):
                    form = formulario(data={"nome": nome})
                    self.assertFalse(form.is_valid())
                    self.assertIn("nome", form.errors)
            form = formulario(data={"nome": "  " + "a" * limite + "  "})
            self.assertTrue(form.is_valid(), form.errors)
            registro = form.save()
            self.assertEqual(registro.nome, "a" * limite)
            self.assertTrue(registro.ativo)
            self.assertIsNotNone(registro.data_criacao)

    def test_nome_duplicado_rejeitado_no_form_modelo_e_banco(self):
        for cadastro, modelo, formulario in CADASTROS:
            with self.subTest(cadastro=cadastro):
                modelo.objects.create(nome="Cadastro existente")
                form = formulario(data={"nome": " Cadastro existente "})
                self.assertFalse(form.is_valid())
                self.assertIn("Já existe um cadastro com este nome.", form.errors["nome"])
                with self.assertRaises(ValidationError):
                    modelo(nome=" Cadastro existente ").full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    modelo.objects.create(nome="Cadastro existente")
                self.assertEqual(modelo.objects.count(), 1)

    def test_edicao_preserva_proprio_nome_e_rejeita_nome_de_outro(self):
        for cadastro, modelo, formulario in CADASTROS:
            with self.subTest(cadastro=cadastro):
                registro = modelo.objects.create(nome="Original", ativo=False)
                outro = modelo.objects.create(nome="Outro")
                form = formulario(data={"nome": " Original ", "ativo": True}, instance=registro)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertFalse(form.save().ativo)
                form = formulario(data={"nome": outro.nome}, instance=registro)
                self.assertFalse(form.is_valid())
                registro.refresh_from_db()
                self.assertEqual(registro.nome, "Original")

    def test_atividade_com_descricao_opcional_e_cadastros_independentes(self):
        for _, modelo, formulario in CADASTROS:
            form = formulario(data={"nome": "Mesmo nome", "descricao": "Descrição pedagógica"})
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
        self.assertEqual(AtividadePedagogica.objects.get().descricao, "Descrição pedagógica")
        self.assertTrue(AtividadePedagogicaForm(data={"nome": "Outra atividade"}).is_valid())


class CadastroFluxoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", stdout=StringIO())
        cls.administrador = get_user_model().objects.create_user(username="pedagogico-admin")
        cls.administrador.groups.add(Group.objects.get(name="Administrador"))
        registrar_aceite_vigente(cls.administrador)

    def setUp(self):
        self.client.force_login(self.administrador)

    def url(self, cadastro, acao, registro=None):
        return reverse(f"pedagogico:{cadastro}_{acao}", args=[registro.pk] if registro else [])

    def evento(self, modelo, acao, resultado):
        return RegistroAuditoria.objects.get(entidade=modelo._meta.label, acao=acao, resultado=resultado)

    def test_fluxo_criacao_edicao_inativacao_reativacao_com_auditoria(self):
        for cadastro, modelo, _ in CADASTROS:
            with self.subTest(cadastro=cadastro):
                self.assertEqual(self.client.get(self.url(cadastro, "novo")).status_code, 200)
                resposta = self.client.post(self.url(cadastro, "novo"), {"nome": " Registro ", "descricao": "Descrição preservada", "ativo": False})
                self.assertRedirects(resposta, self.url(cadastro, "lista"))
                registro = modelo.objects.get()
                self.assertEqual(registro.nome, "Registro")
                self.assertTrue(registro.ativo)
                evento = self.evento(modelo, AcaoAuditoria.CADASTRO_PEDAGOGICO_CRIADO, "SUCESSO")
                self.assertEqual(evento.usuario_id, self.administrador.pk)
                self.assertEqual(evento.entidade_id, str(registro.pk))
                criacao = registro.data_criacao
                self.assertContains(self.client.get(self.url(cadastro, "editar", registro)), "Registro")
                self.client.post(self.url(cadastro, "editar", registro), {"nome": "Editado", "descricao": "Descrição preservada"})
                registro.refresh_from_db()
                self.assertEqual(registro.nome, "Editado")
                self.assertEqual(registro.data_criacao, criacao)
                self.evento(modelo, AcaoAuditoria.CADASTRO_PEDAGOGICO_EDITADO, "SUCESSO")
                for acao, ativo in (("inativar", False), ("reativar", True)):
                    self.client.post(self.url(cadastro, acao, registro))
                    registro.refresh_from_db()
                    self.assertEqual(registro.ativo, ativo)
                    self.assertEqual(registro.nome, "Editado")
                    self.assertEqual(registro.data_criacao, criacao)
                self.assertEqual(RegistroAuditoria.objects.filter(entidade=modelo._meta.label, acao=AcaoAuditoria.CADASTRO_PEDAGOGICO_SITUACAO_ALTERADA, resultado="SUCESSO").count(), 2)
                self.assertEqual(modelo.objects.count(), 1)

    def test_dados_invalidos_nao_persistem_preservam_form_e_auditam_falha(self):
        for cadastro, modelo, _ in CADASTROS:
            with self.subTest(cadastro=cadastro):
                modelo.objects.create(nome="Existente")
                resposta = self.client.post(self.url(cadastro, "novo"), {"nome": " Existente ", "descricao": "Texto deve permanecer no formulário"})
                self.assertContains(resposta, "Já existe um cadastro com este nome.")
                self.assertContains(resposta, 'aria-invalid="true"')
                if cadastro == "atividades":
                    self.assertContains(resposta, "Texto deve permanecer no formulário")
                self.assertEqual(modelo.objects.count(), 1)
                evento = self.evento(modelo, AcaoAuditoria.CADASTRO_PEDAGOGICO_CRIADO, "FALHA")
                self.assertEqual(evento.entidade_id, "")
                self.assertNotIn("descricao", evento.__dict__)

    def test_edicao_invalida_preserva_dados_e_situacao(self):
        for cadastro, modelo, _ in CADASTROS:
            with self.subTest(cadastro=cadastro):
                modelo.objects.create(nome="Ocupado")
                registro = modelo.objects.create(nome="Original", ativo=False)
                resposta = self.client.post(self.url(cadastro, "editar", registro), {"nome": " Ocupado ", "ativo": True})
                self.assertContains(resposta, "Já existe um cadastro com este nome.")
                registro.refresh_from_db()
                self.assertEqual(registro.nome, "Original")
                self.assertFalse(registro.ativo)
                self.assertEqual(self.evento(modelo, AcaoAuditoria.CADASTRO_PEDAGOGICO_EDITADO, "FALHA").entidade_id, str(registro.pk))

    def test_situacao_e_idempotente_e_nao_pode_ser_adulterada(self):
        for cadastro, modelo, _ in CADASTROS:
            registro = modelo.objects.create(nome="Situação")
            for _ in range(2):
                self.client.post(self.url(cadastro, "inativar", registro), {"ativo": True})
            registro.refresh_from_db()
            self.assertFalse(registro.ativo)
            self.assertEqual(RegistroAuditoria.objects.filter(entidade=modelo._meta.label, acao=AcaoAuditoria.CADASTRO_PEDAGOGICO_SITUACAO_ALTERADA).count(), 1)

    def test_get_nao_grava_e_situacao_exige_post(self):
        for cadastro, modelo, _ in CADASTROS:
            registro = modelo.objects.create(nome="Consulta")
            antes = RegistroAuditoria.objects.count()
            for acao in ("lista", "novo", "editar"):
                self.assertEqual(self.client.get(self.url(cadastro, acao, registro if acao == "editar" else None)).status_code, 200)
            for acao in ("inativar", "reativar"):
                self.assertEqual(self.client.get(self.url(cadastro, acao, registro)).status_code, 405)
            self.assertEqual(RegistroAuditoria.objects.count(), antes)
            registro.refresh_from_db()
            self.assertTrue(registro.ativo)

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.administrador)
        for cadastro, modelo, _ in CADASTROS:
            registro = modelo.objects.create(nome="CSRF")
            for acao in ("novo", "editar", "inativar", "reativar"):
                url = self.url(cadastro, acao, None if acao == "novo" else registro)
                self.assertEqual(cliente.post(url, {"nome": "Adulterado"}).status_code, 403)
            registro.refresh_from_db()
            self.assertEqual(registro.nome, "CSRF")
            self.assertTrue(registro.ativo)

    def test_busca_filtro_paginacao_e_listagem_de_inativos(self):
        for cadastro, modelo, _ in CADASTROS:
            modelo.objects.bulk_create(modelo(nome=f"Registro {indice:02}", ativo=indice < 11) for indice in range(12))
            resposta = self.client.get(self.url(cadastro, "lista"))
            self.assertEqual(resposta.context["pagina"].paginator.count, 12)
            self.assertEqual(len(resposta.context["pagina"]), 10)
            resposta = self.client.get(self.url(cadastro, "lista"), {"busca": "Registro", "situacao": "ativos", "pagina": 2})
            self.assertEqual(len(resposta.context["pagina"]), 1)
            self.assertContains(resposta, "busca=Registro&amp;situacao=ativos&amp;pagina=1")
            resposta = self.client.get(self.url(cadastro, "lista"), {"situacao": "inativos"})
            self.assertEqual([r.nome for r in resposta.context["pagina"]], ["Registro 11"])
            resposta = self.client.get(self.url(cadastro, "lista"), {"busca": "00", "situacao": "inválida", "pagina": "inválida"})
            self.assertEqual([r.nome for r in resposta.context["pagina"]], ["Registro 00"])

    def test_professor_operador_superuser_e_grupos_invalidos_nao_acessam(self):
        combinacoes = ((), ("Professor",), ("Operador",), ("Administrador", "Professor"), ("Administrador", "Extra"))
        Group.objects.create(name="Extra")
        grupos = Group.objects.in_bulk(field_name="name")
        for indice, nomes in enumerate(combinacoes):
            usuario = get_user_model().objects.create_user(username=f"negado-{indice}")
            usuario.groups.add(*(grupos[nome] for nome in nomes))
            usuario.user_permissions.add(*Permission.objects.filter(content_type__app_label="pedagogico"))
            registrar_aceite_vigente(usuario)
            self._assert_negado(usuario)
        tecnico = get_user_model().objects.create_user(username="tecnico-pedagogico", is_superuser=True)
        tecnico.groups.add(grupos["Administrador"])
        registrar_aceite_vigente(tecnico)
        self._assert_negado(tecnico)

    def _assert_negado(self, usuario):
        self.client.force_login(usuario)
        for cadastro, modelo, _ in CADASTROS:
            registro, _ = modelo.objects.get_or_create(nome="Protegido")
            for acao in ("lista", "novo", "editar", "inativar", "reativar"):
                url = self.url(cadastro, acao, registro if acao not in ("lista", "novo") else None)
                resposta = self.client.get(url) if acao in ("lista", "novo", "editar") else self.client.post(url)
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(resposta.status_code, 403)
                    if acao in ("novo", "editar"):
                        self.assertEqual(self.client.post(url, {"nome": "Adulterado"}).status_code, 403)
            self.assertEqual(modelo.objects.count(), 1)
            registro.refresh_from_db()
            self.assertTrue(registro.ativo)
        navegacao = self.client.get(reverse("inventario:equipamento_lista")).content.decode()
        self.assertNotIn('href="/pedagogico/', navegacao)

    def test_anonimo_e_conta_inativa_nao_acessam(self):
        self.client.logout()
        for cadastro, modelo, _ in CADASTROS:
            self.assertEqual(self.client.get(self.url(cadastro, "lista")).status_code, 302)
        self.administrador.is_active = False
        self.administrador.save(update_fields=("is_active",))
        self.client.force_login(self.administrador)
        self.assertEqual(self.client.post(self.url("turmas", "novo"), {"nome": "Negado"}).status_code, 302)
        self.assertFalse(Turma.objects.exists())

    def test_permissao_por_acao_e_navegacao(self):
        grupo = Group.objects.get(name="Administrador")
        for cadastro, modelo, _ in CADASTROS:
            registro = modelo.objects.create(nome="Restrito")
            for acao, rotas in (("view", ("lista",)), ("add", ("novo",)), ("change", ("editar", "inativar", "reativar"))):
                permissao = Permission.objects.get(content_type__app_label="pedagogico", codename=f"{acao}_{modelo._meta.model_name}")
                grupo.permissions.remove(permissao)
                for rota in rotas:
                    url = self.url(cadastro, rota, registro if rota not in ("lista", "novo") else None)
                    resposta = self.client.post(url, {"nome": "Negado"}) if rota != "lista" else self.client.get(url)
                    self.assertEqual(resposta.status_code, 403)
                if acao == "view":
                    self.assertNotContains(self.client.get(reverse("inventario:equipamento_lista")), f'href="{self.url(cadastro, "lista")}"')
                grupo.permissions.add(permissao)
            self.assertContains(self.client.get(self.url(cadastro, "lista")), f'href="{self.url(cadastro, "lista")}" aria-current="page"')
            self.assertFalse(grupo.permissions.filter(codename=f"delete_{modelo._meta.model_name}", content_type__app_label="pedagogico").exists())

    def test_falha_na_auditoria_desfaz_gravacao_e_registra_falha(self):
        def falhar_no_sucesso(**dados):
            if dados["resultado"] == "SUCESSO":
                raise IntegrityError("Falha de persistência da auditoria")
            return registrar_evento(**dados)

        for cadastro, modelo, _ in CADASTROS:
            with patch("pedagogico.views.registrar_evento", side_effect=falhar_no_sucesso):
                resposta = self.client.post(self.url(cadastro, "novo"), {"nome": "Não persistir"})
                self.assertContains(resposta, "Nenhuma alteração foi gravada")
                self.assertFalse(modelo.objects.exists())
                registro = modelo.objects.create(nome="Original")
                self.client.post(self.url(cadastro, "editar", registro), {"nome": "Não persistir"})
                self.client.post(self.url(cadastro, "inativar", registro))
            registro.refresh_from_db()
            self.assertEqual(registro.nome, "Original")
            self.assertTrue(registro.ativo)
            for acao in (AcaoAuditoria.CADASTRO_PEDAGOGICO_CRIADO, AcaoAuditoria.CADASTRO_PEDAGOGICO_EDITADO, AcaoAuditoria.CADASTRO_PEDAGOGICO_SITUACAO_ALTERADA):
                self.evento(modelo, acao, "FALHA")

    def test_edicao_nao_sobrescreve_situacao_alterada_apos_abrir_formulario(self):
        for cadastro, modelo, formulario in CADASTROS:
            registro = modelo.objects.create(nome="Original")
            salvar_original = formulario.save

            def salvar_apos_inativacao(form, commit=True):
                modelo.objects.filter(pk=registro.pk).update(ativo=False)
                return salvar_original(form, commit=commit)

            with patch.object(formulario, "save", salvar_apos_inativacao):
                self.client.post(self.url(cadastro, "editar", registro), {"nome": "Editado"})
            registro.refresh_from_db()
            self.assertFalse(registro.ativo)
            self.assertEqual(registro.nome, "Editado")

    def test_conflito_surgido_apos_validacao_nao_grava_e_exibe_erro(self):
        for cadastro, modelo, formulario in CADASTROS:
            validar_original = formulario.is_valid

            def validar_com_conflito(form):
                valido = validar_original(form)
                if valido:
                    modelo.objects.create(nome=form.cleaned_data["nome"])
                return valido

            with patch.object(formulario, "is_valid", validar_com_conflito):
                resposta = self.client.post(self.url(cadastro, "novo"), {"nome": "Conflito"})
            self.assertContains(resposta, "Já existe um cadastro com este nome.")
            self.assertEqual(modelo.objects.count(), 1)
            self.assertFalse(RegistroAuditoria.objects.filter(entidade=modelo._meta.label, resultado="SUCESSO").exists())

    def test_registro_inexistente_e_exclusao_sem_rota(self):
        for cadastro, _, _ in CADASTROS:
            for acao in ("editar", "inativar", "reativar"):
                url = reverse(f"pedagogico:{cadastro}_{acao}", args=[999999])
                resposta = self.client.get(url) if acao == "editar" else self.client.post(url)
                self.assertEqual(resposta.status_code, 404)
            self.assertEqual(self.client.post(f"/pedagogico/{cadastro}/1/excluir/").status_code, 404)

    def test_descricao_escapada_na_interface(self):
        AtividadePedagogica.objects.create(nome="Atividade", descricao='<script>alert("x")</script>')
        resposta = self.client.get(self.url("atividades", "lista"))
        self.assertNotContains(resposta, '<script>alert("x")</script>')
        self.assertContains(resposta, "&lt;script&gt;")
