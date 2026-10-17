from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from auditoria.models import RegistroAuditoria
from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from movimentacoes.models import Movimentacao
from usuarios.services import alterar_situacao_usuario

from .models import Reserva, ReservaEquipamento


class ConsultaAdministrativaReservasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.admin = cls.usuario("admin-consulta", "Administrador")
        cls.professor = cls.usuario("professor-consulta", "Professor")
        cls.outro_professor = cls.usuario("outro-professor", "Professor")
        cls.operador = cls.usuario("operador-consulta", "Operador")
        cls.categoria = Categoria.objects.create(nome="Categoria da consulta")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Projetor de teste")
        cls.local = Local.objects.create(nome="Sala de recursos")
        cls.unidades = [Equipamento.objects.create(
            tipo=cls.tipo, local=cls.local, numero_patrimonio=f"CONSULTA-{indice}",
        ) for indice in range(2)]

    @classmethod
    def usuario(cls, nome, grupo=None, **campos):
        usuario = get_user_model().objects.create_user(username=nome, **campos)
        if grupo:
            usuario.groups.add(Group.objects.get(name=grupo))
        registrar_aceite_vigente(usuario)
        return usuario

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("reservas:reserva_consulta")

    def reserva(self, **campos):
        inicio = timezone.now() + timedelta(days=2)
        dados = dict(professor=self.professor, tipo_equipamento=self.tipo, local=self.local,
                     quantidade=2, inicio=inicio, fim=inicio + timedelta(hours=1))
        dados.update(campos)
        reserva = Reserva.objects.create(**dados)
        ReservaEquipamento.objects.bulk_create([
            ReservaEquipamento(reserva=reserva, equipamento=unidade) for unidade in self.unidades
        ])
        return reserva

    def test_administrador_consulta_todos_professores_e_patrimonios_sem_acoes(self):
        primeira = self.reserva()
        segunda = self.reserva(professor=self.outro_professor, status=Reserva.Status.CANCELADA)
        Movimentacao.objects.create(
            reserva=primeira, equipamento=self.unidades[0], operador=self.operador,
            destinatario=self.professor, tipo=Movimentacao.Tipo.RETIRADA,
        )
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertSetEqual({r.pk for r in resposta.context["pagina"]}, {primeira.pk, segunda.pk})
        for texto in (self.professor.username, self.outro_professor.username,
                      "CONSULTA-0", "CONSULTA-1", "Registrada", "Sem registro", "Cancelada"):
            self.assertContains(resposta, texto)
        self.assertContains(resposta, f'href="{self.url}" aria-current="page"')
        self.assertNotContains(resposta, reverse("reservas:reserva_nova"))
        for registro in (primeira, segunda):
            self.assertNotContains(resposta, reverse("reservas:reserva_cancelar", args=[registro.pk]))
            self.assertNotContains(resposta, reverse("movimentacoes:retirada_reserva_registrar", args=[registro.pk]))

    def test_busca_por_professor_local_equipamento_numero_e_patrimonio_sem_duplicar(self):
        self.professor.first_name, self.professor.last_name = "Maria", "Silva"
        self.professor.save(update_fields=["first_name", "last_name"])
        registro = self.reserva()
        self.reserva(professor=self.outro_professor, status=Reserva.Status.CANCELADA)
        for busca in ("Maria Silva", self.professor.username, self.local.nome, self.tipo.nome,
                      str(registro.pk), "CONSULTA-"):
            with self.subTest(busca=busca):
                resposta = self.client.get(self.url, {"busca": busca, "status": Reserva.Status.ATIVA})
                self.assertEqual([r.pk for r in resposta.context["pagina"]], [registro.pk])
        resposta = self.client.get(self.url, {"busca": "9" * 5000, "status": "invalido"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["status"], "")

    def test_reservas_de_professor_desativado_permanecem_consultaveis(self):
        registro = self.reserva(status=Reserva.Status.CANCELADA)
        alterar_situacao_usuario(
            administrador=self.admin, usuario_id=self.professor.pk, ativo=False,
        )
        self.professor.refresh_from_db()
        self.assertFalse(self.professor.is_active)

        resposta = self.client.get(self.url, {"busca": self.professor.username})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([reserva.pk for reserva in resposta.context["pagina"]], [registro.pk])
        self.assertContains(resposta, self.professor.username)
        self.assertContains(resposta, "Cancelada")
        self.assertContains(resposta, reverse("usuarios:usuario_lista"))
        registro.refresh_from_db()
        self.assertEqual(registro.status, Reserva.Status.CANCELADA)

    def test_paginacao_ordem_e_filtro_preservados(self):
        inicio = timezone.now() + timedelta(days=2)
        registros = [self.reserva(inicio=inicio, fim=inicio + timedelta(hours=1)) for _ in range(17)]
        self.reserva(status=Reserva.Status.EXPIRADA)
        filtros = {"status": Reserva.Status.ATIVA, "busca": self.tipo.nome}
        primeira = self.client.get(self.url, filtros)
        self.assertEqual([r.pk for r in primeira.context["pagina"]],
                         [r.pk for r in reversed(registros[-15:])])
        self.assertEqual(primeira.context["pagina"].paginator.count, 17)
        self.assertIn("status=ATIVA", primeira.context["parametros_paginacao"])
        segunda = self.client.get(self.url, {**filtros, "pagina": 2})
        self.assertEqual([r.pk for r in segunda.context["pagina"]], [registros[1].pk, registros[0].pk])
        expiradas = self.client.get(self.url, {"status": Reserva.Status.EXPIRADA})
        self.assertEqual(expiradas.context["pagina"].paginator.count, 1)

    def test_consulta_nao_atualiza_nem_expira_reservas_e_recusa_post(self):
        inicio = timezone.now() - timedelta(hours=2)
        registro = self.reserva(inicio=inicio, fim=inicio + timedelta(hours=1))
        auditorias = RegistroAuditoria.objects.count()
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                             for q in consultas))
        registro.refresh_from_db()
        self.assertEqual(registro.status, Reserva.Status.ATIVA)
        self.assertEqual(RegistroAuditoria.objects.count(), auditorias)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_perfis_incorretos_negados_mesmo_com_permissao_individual(self):
        outros = [self.professor, self.operador, self.usuario("sem-grupo"),
                  self.usuario("tecnico", is_superuser=True), self.usuario("multiplo", "Administrador")]
        outros[-1].groups.add(Group.objects.get(name="Operador"))
        permissao = Permission.objects.get(content_type__app_label="reservas", codename="view_reserva")
        for usuario in outros:
            with self.subTest(usuario=usuario.username):
                usuario.user_permissions.add(permissao)
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                resposta = self.client.get(reverse("inventario:equipamento_lista"))
                self.assertNotContains(resposta, self.url, status_code=resposta.status_code)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f'{reverse("login")}?next={self.url}',
                             fetch_redirect_response=False)

    def test_sem_permissao_nao_consulta_nem_visualiza_link(self):
        Group.objects.get(name="Administrador").permissions.remove(
            Permission.objects.get(content_type__app_label="reservas", codename="view_reserva"),
        )
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("inventario:equipamento_lista")), self.url)

    def test_administrador_nao_cria_cancela_ou_confirma_entrega(self):
        registro = self.reserva()
        for codename in ("add_reserva", "change_reserva"):
            self.admin.user_permissions.add(Permission.objects.get(
                content_type__app_label="reservas", codename=codename,
            ))
        self.admin.user_permissions.add(Permission.objects.get(codename="add_movimentacao"))
        urls = [reverse("reservas:reserva_nova"),
                reverse("reservas:reserva_cancelar", args=[registro.pk]),
                reverse("movimentacoes:retirada_reserva_registrar", args=[registro.pk])]
        for url in urls:
            self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("reservas:reserva_lista")).status_code, 403)
        registro.refresh_from_db()
        self.assertEqual(registro.status, Reserva.Status.ATIVA)
        self.assertEqual(Reserva.objects.count(), 1)
        self.assertFalse(Movimentacao.objects.exists())

    def test_vazio_e_quantidade_de_consultas_constante(self):
        self.assertContains(self.client.get(self.url), "Nenhuma reserva encontrada")
        def numero_consultas():
            with CaptureQueriesContext(connection) as consultas:
                self.client.get(self.url)
            return len(consultas)
        self.reserva()
        inicial = numero_consultas()
        for _ in range(10):
            self.reserva()
        self.assertEqual(numero_consultas(), inicial)


class MigrationPermissaoConsultaReservasTests(TestCase):
    def test_migration_aditiva_idempotente_preserva_permissoes_existentes(self):
        grupo = Group.objects.get(name="Administrador")
        consulta = Permission.objects.get(content_type__app_label="reservas", codename="view_reserva")
        grupo.permissions.remove(consulta)
        outra = Permission.objects.get(codename="view_equipamento")
        grupo.permissions.add(outra)
        antes = set(Group.permissions.through.objects.values_list("group_id", "permission_id"))
        migration = import_module("usuarios.migrations.0003_permissao_consulta_reservas_administrador")
        for _ in range(2):
            migration.vincular_permissao_consulta_reservas(apps, SimpleNamespace(connection=connection))
        depois = set(Group.permissions.through.objects.values_list("group_id", "permission_id"))
        self.assertSetEqual(depois, antes | {(grupo.pk, consulta.pk)})
