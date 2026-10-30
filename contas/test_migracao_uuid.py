"""Migração real de dados legados em processos e banco isolados."""

from contextlib import contextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from django.conf import settings
from django.test import SimpleTestCase


WORKER = """
import json, os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_testes'
from django.conf import settings
settings.DATABASES['default'] = json.loads(sys.stdin.read())
settings.ALLOWED_HOSTS = ['testserver', 'localhost']
if sys.argv[1] in ('legado', 'preparar'):
    settings.AUTH_USER_MODEL = 'auth.User'
django.setup()
from contas.test_migracao_uuid import executar_etapa
executar_etapa(sys.argv[1])
"""


class MigracaoUsuarioUUIDTests(SimpleTestCase):
    def test_converte_banco_legado_e_preserva_contas_e_historico(self):
        with banco_isolado() as banco:
            for etapa in ("legado", "preparar", "falha", "validar"):
                resultado = subprocess.run(
                    [sys.executable, "-c", WORKER, etapa], input=json.dumps(banco),
                    cwd=settings.BASE_DIR, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    capture_output=True, text=True, encoding="utf-8", timeout=90,
                )
                self.assertEqual(resultado.returncode, 0, f"Etapa {etapa}:\n{resultado.stdout}{resultado.stderr}")


@contextmanager
def banco_isolado():
    configuracao = settings.DATABASES["default"].copy()
    if configuracao["ENGINE"] == "django.db.backends.sqlite3":
        with TemporaryDirectory(prefix="sigee-uuid-") as diretorio:
            configuracao["NAME"] = str(Path(diretorio) / "legado.sqlite3")
            yield configuracao
        return

    import psycopg
    from psycopg import sql

    parametros = {chave: configuracao[origem] for chave, origem in (
        ("dbname", "NAME"), ("user", "USER"), ("password", "PASSWORD"), ("host", "HOST"), ("port", "PORT"),
    ) if configuracao.get(origem)}
    parametros.update(configuracao.get("OPTIONS", {}))
    nome = f"test_migracao_uuid_{uuid4().hex}"
    with psycopg.connect(**parametros, autocommit=True) as administrador:
        administrador.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nome)))
        try:
            configuracao["NAME"] = nome
            yield configuracao
        finally:
            administrador.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(nome)))


def executar_etapa(etapa):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group, Permission
    from django.contrib.admin.models import LogEntry, CHANGE
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.sessions.models import Session
    from django.core.management import call_command
    from django.core.management.sql import emit_post_migrate_signal
    from django.db import connection, IntegrityError, transaction
    from django.db.migrations.executor import MigrationExecutor
    from django.test import Client
    from django.utils import timezone

    from auditoria.models import RegistroAuditoria
    from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
    from legal.models import AceiteDocumentosLegais
    from manutencoes.models import Manutencao
    from movimentacoes.models import Movimentacao
    from pedagogico.models import AtividadePedagogica, Disciplina, Turma, UtilizacaoPedagogica
    from reservas.models import Reserva, ReservaEquipamento

    User = get_user_model()
    if etapa == "preparar":
        # A mesma etapa operacional indicada para um banco já existente.
        call_command("migrate", "contas", "0001", verbosity=0, interactive=False)
        return

    if etapa == "falha":
        duplicado = ContentType.objects.create(app_label="contas", model="user")
        try:
            call_command("migrate", verbosity=0, interactive=False)
        except RuntimeError as erro:
            assert "ContentTypes duplicados" in str(erro)
        else:
            raise AssertionError("A migração deveria ter rejeitado os ContentTypes duplicados.")
        # A falha ocorre depois da conversão das colunas e referências da auditoria.
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM auth_user ORDER BY id")
            assert [linha[0] for linha in cursor.fetchall()] == [11, 73, 94]
            cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'contas' AND name = '0002_usuario_uuid'")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT usuario_id, entidade, entidade_id FROM auditoria_registroauditoria WHERE acao = 'USUARIO_CADASTRADO'")
            assert cursor.fetchone() == (11, "auth.User", "73")
        assert Session.objects.exists()
        duplicado.delete()
        return

    if etapa == "legado":
        executor = MigrationExecutor(connection)
        executor.migrate([alvo for alvo in executor.loader.graph.leaf_nodes() if alvo[0] != "contas"])
        emit_post_migrate_signal(verbosity=0, interactive=False, db="default")
        assert User._meta.label == "auth.User"
        administrador = User.objects.create_superuser(id=11, username="admin-uuid", password="Senha-UUID-2026!")
        professor = User.objects.create_user(id=73, username="professor-uuid", email="uuid@example.com", password="Senha-UUID-2026!")
        User.objects.create_user(id=94, username="inativo-uuid", is_active=False)
        grupo = Group.objects.create(name="Professor")
        grupo.permissions.add(Permission.objects.get(codename="change_user"))
        professor.groups.add(grupo)
        professor.user_permissions.add(Permission.objects.get(codename="view_user"))
        tipo = TipoEquipamento.objects.create(nome="Teste UUID", categoria=Categoria.objects.first())
        local = Local.objects.first()
        equipamento = Equipamento.objects.create(numero_patrimonio="UUID-001", tipo=tipo, local=local)
        agora = timezone.now()
        reserva = Reserva.objects.create(professor=professor, tipo_equipamento=tipo, local=local, inicio=agora, fim=agora + timedelta(hours=1))
        ReservaEquipamento.objects.create(reserva=reserva, equipamento=equipamento)
        retirada = Movimentacao.objects.create(equipamento=equipamento, operador=administrador, destinatario=professor, tipo="RETIRADA", reserva=reserva)
        UtilizacaoPedagogica.objects.create(movimentacao=retirada, professor=professor, turma=Turma.objects.create(nome="UUID"), disciplina=Disciplina.objects.create(nome="UUID"), atividade=AtividadePedagogica.objects.create(nome="UUID"))
        Manutencao.objects.create(equipamento=equipamento, aberto_por=administrador, descricao_problema="Teste UUID")
        AceiteDocumentosLegais.objects.create(usuario=professor, versao_termos="2.0", versao_privacidade="2.0")
        RegistroAuditoria.objects.create(usuario=administrador, acao="USUARIO_CADASTRADO", resultado="SUCESSO", entidade="auth.User", entidade_id="73")
        LogEntry.objects.create(user=administrador, content_type=ContentType.objects.get_for_model(User), object_id="73", object_repr=professor.username, action_flag=CHANGE)
        cliente = Client()
        cliente.force_login(professor)
        assert Session.objects.exists()
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE auth_user ENABLE ROW LEVEL SECURITY")
        connection.check_constraints()
        return

    call_command("migrate", verbosity=0, interactive=False)
    # Reexecutar migrate não gera UUIDs novos nem altera os dados novamente.
    antes = dict(User.objects.values_list("username", "pk"))
    call_command("migrate", verbosity=0, interactive=False)
    assert antes == dict(User.objects.values_list("username", "pk"))
    assert User.objects.count() == 3
    professor = User.objects.get(username="professor-uuid")
    administrador = User.objects.get(username="admin-uuid")
    assert isinstance(professor.pk, UUID) and professor.pk.version == 4
    assert professor.check_password("Senha-UUID-2026!")
    assert administrador.is_staff and administrador.is_superuser
    assert not User.objects.get(username="inativo-uuid").is_active
    assert professor.email == "uuid@example.com"
    assert professor.has_perm("contas.view_user") and professor.has_perm("contas.change_user")
    assert professor.groups.get().name == "Professor"
    assert not ContentType.objects.filter(app_label="auth", model="user").exists()
    assert not Session.objects.exists()
    assert Reserva.objects.get().professor_id == professor.pk
    assert ReservaEquipamento.objects.count() == 1
    movimentacao = Movimentacao.objects.get()
    assert movimentacao.operador_id == administrador.pk and movimentacao.destinatario_id == professor.pk
    assert UtilizacaoPedagogica.objects.get().professor_id == professor.pk
    manutencao = Manutencao.objects.get()
    assert manutencao.aberto_por_id == administrador.pk and manutencao.iniciado_por_id is None and manutencao.concluido_por_id is None
    assert AceiteDocumentosLegais.objects.get().usuario_id == professor.pk
    evento = RegistroAuditoria.objects.get(acao="USUARIO_CADASTRADO")
    assert evento.usuario_id == administrador.pk and evento.entidade_id == str(professor.pk) and evento.entidade == "contas.User"
    log = LogEntry.objects.get()
    assert log.user_id == administrador.pk and log.object_id == str(professor.pk)
    assert log.content_type.app_label == "contas"
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT data_type, column_default, is_identity FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'auth_user' AND column_name = 'id'")
            assert cursor.fetchone() == ("uuid", None, "NO")
            cursor.execute("SELECT relrowsecurity FROM pg_class WHERE oid = 'auth_user'::regclass")
            assert cursor.fetchone()[0]
    try:
        with transaction.atomic():
            User.objects.create_user(username="email-duplicado", email="UUID@EXAMPLE.COM")
    except IntegrityError:
        pass
    else:
        raise AssertionError("O índice de e-mail único não foi preservado.")
    novo = User.objects.create_user(username="apos-migracao")
    assert isinstance(novo.pk, UUID) and novo.pk != professor.pk
    cliente = Client()
    assert cliente.post("/login/", {"username": "professor-uuid", "password": "Senha-UUID-2026!"}).status_code == 302
    assert cliente.session["_auth_user_id"] == str(professor.pk)
    connection.check_constraints()
