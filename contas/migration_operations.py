"""Conversão única da tabela legada, preservando suas referências e permissões."""

from uuid import uuid4

from django.conf import settings
from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError


class ConverterChaveUsuarioUUID(migrations.AlterField):
    reversible = False
    reduces_to_sql = False

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if settings.AUTH_USER_MODEL != "contas.User":
            raise RuntimeError("Execute a conversão com as configurações normais, sem settings_preparacao_uuid.")
        connection = schema_editor.connection
        if connection.vendor not in ("sqlite", "postgresql"):
            raise RuntimeError("A conversão de usuários suporta somente SQLite e PostgreSQL.")

        antigo = from_state.apps.get_model(app_label, "User")
        novo = to_state.apps.get_model(app_label, "User")
        q = schema_editor.quote_name
        tabela = q(antigo._meta.db_table)
        mapa = "sigee_mapa_usuario_uuid"

        with connection.cursor() as cursor:
            referencias = self._referencias(connection, cursor, antigo._meta.db_table)
            if connection.vendor == "postgresql":
                tabelas = sorted({tabela, *(r[0] for r in referencias)})
                cursor.execute(f"LOCK TABLE {', '.join(tabelas)} IN ACCESS EXCLUSIVE MODE")

            # Detectar referências inconsistentes antes de converter, sem apagá-las.
            for origem, coluna, *_ in referencias:
                cursor.execute(
                    f"SELECT 1 FROM {origem} r LEFT JOIN {tabela} u ON r.{q(coluna)} = u.id "
                    f"WHERE r.{q(coluna)} IS NOT NULL AND u.id IS NULL LIMIT 1"
                )
                if cursor.fetchone():
                    raise RuntimeError(f"Referência de usuário inválida em {origem}.{coluna}; corrija antes de migrar.")

            tipo_uuid = "uuid" if connection.vendor == "postgresql" else "char(32)"
            cursor.execute(
                f"CREATE TEMP TABLE {mapa} (antigo_id bigint PRIMARY KEY, "
                f"novo_id {tipo_uuid} UNIQUE NOT NULL, novo_texto varchar(36) NOT NULL)"
            )
            cursor.execute(f"SELECT id FROM {tabela} ORDER BY id")
            ids = [linha[0] for linha in cursor.fetchall()]
            for inicio in range(0, len(ids), 1000):
                valores = []
                for identificador in ids[inicio:inicio + 1000]:
                    novo_id = uuid4()
                    valores.append((identificador, str(novo_id) if connection.vendor == "postgresql" else novo_id.hex, str(novo_id)))
                cursor.executemany(f"INSERT INTO {mapa} VALUES (%s, %s, %s)", valores)

            if connection.vendor == "postgresql":
                self._converter_postgresql(cursor, q, tabela, referencias, mapa)
            else:
                # O schema editor recompõe também as FKs e tabelas de grupos/permissões.
                schema_editor.alter_field(antigo, antigo._meta.pk, novo._meta.pk)
                for origem, coluna, *_ in [(tabela, "id"), *referencias]:
                    cursor.execute(
                        f"UPDATE {origem} SET {q(coluna)} = "
                        f"(SELECT novo_id FROM {mapa} WHERE antigo_id = {origem}.{q(coluna)}) "
                        f"WHERE {q(coluna)} IS NOT NULL"
                    )
                # Este índice foi criado por SQL na migration usuarios.0001.
                cursor.execute(
                    "CREATE UNIQUE INDEX usuarios_user_email_ci_unique "
                    "ON auth_user (LOWER(email)) WHERE email <> ''"
                )

            self._converter_historico(cursor, mapa)
            # IDs antigos nas sessões e nos links de recuperação deixam de ser válidos.
            cursor.execute("DELETE FROM django_session")
            cursor.execute(f"DROP TABLE {mapa}")

        connection.check_constraints()

    @staticmethod
    def _referencias(connection, cursor, tabela):
        q = connection.ops.quote_name
        if connection.vendor == "postgresql":
            cursor.execute(
                "SELECT n.nspname, t.relname, a.attname, c.conname, "
                "pg_get_constraintdef(c.oid), cardinality(c.conkey) "
                "FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = c.conkey[1] "
                "WHERE c.contype = 'f' AND c.confrelid = %s::regclass "
                "ORDER BY n.nspname, t.relname, c.conname", [tabela],
            )
            referencias = []
            for schema, origem, coluna, nome, definicao, tamanho in cursor.fetchall():
                if tamanho != 1:
                    raise RuntimeError("Há uma FK composta para auth_user; a migração precisa ser revisada.")
                referencias.append((f"{q(schema)}.{q(origem)}", coluna, nome, definicao))
            return referencias

        referencias = []
        for origem in connection.introspection.table_names(cursor):
            for constraint in connection.introspection.get_constraints(cursor, origem).values():
                if constraint["foreign_key"] == (tabela, "id"):
                    referencias.append((q(origem), constraint["columns"][0]))
        return referencias

    @staticmethod
    def _converter_postgresql(cursor, q, tabela, referencias, mapa):
        cursor.execute(
            "CREATE FUNCTION pg_temp.sigee_uuid_usuario(valor bigint) RETURNS uuid "
            f"LANGUAGE SQL STRICT AS 'SELECT novo_id FROM pg_temp.{mapa} WHERE antigo_id = valor'"
        )
        for origem, _, nome, _ in referencias:
            cursor.execute(f"ALTER TABLE {origem} DROP CONSTRAINT {q(nome)}")
        cursor.execute(f"ALTER TABLE {tabela} ALTER COLUMN id DROP IDENTITY IF EXISTS")
        cursor.execute(f"ALTER TABLE {tabela} ALTER COLUMN id DROP DEFAULT")
        for origem, coluna in dict.fromkeys([(tabela, "id"), *((r[0], r[1]) for r in referencias)]):
            cursor.execute(
                f"ALTER TABLE {origem} ALTER COLUMN {q(coluna)} TYPE uuid "
                f"USING pg_temp.sigee_uuid_usuario({q(coluna)})"
            )
        for origem, _, nome, definicao in referencias:
            cursor.execute(f"ALTER TABLE {origem} ADD CONSTRAINT {q(nome)} {definicao}")
        cursor.execute("DROP FUNCTION pg_temp.sigee_uuid_usuario(bigint)")

    @staticmethod
    def _converter_historico(cursor, mapa):
        cursor.execute(
            "UPDATE auditoria_registroauditoria SET entidade_id = "
            f"(SELECT novo_texto FROM {mapa} WHERE CAST(antigo_id AS varchar) = entidade_id), "
            "entidade = 'contas.User' WHERE entidade IN ('auth.User', 'contas.User') "
            f"AND entidade_id IN (SELECT CAST(antigo_id AS varchar) FROM {mapa})"
        )
        cursor.execute(
            "UPDATE auditoria_registroauditoria SET entidade = 'contas.User' "
            "WHERE entidade = 'auth.User' AND entidade_id = ''"
        )
        cursor.execute("SELECT id FROM django_content_type WHERE app_label = 'auth' AND model = 'user'")
        content_type = cursor.fetchone()
        if content_type:
            cursor.execute("SELECT id FROM django_content_type WHERE app_label = 'contas' AND model = 'user'")
            if cursor.fetchone():
                raise RuntimeError("Existem ContentTypes duplicados para User; revise antes de migrar.")
            cursor.execute(
                "UPDATE django_admin_log SET object_id = "
                f"(SELECT novo_texto FROM {mapa} WHERE CAST(antigo_id AS varchar) = object_id) "
                f"WHERE content_type_id = %s AND object_id IN (SELECT CAST(antigo_id AS varchar) FROM {mapa})",
                [content_type[0]],
            )
            # Preserva os IDs das permissões e todos os vínculos individuais e de grupos.
            cursor.execute("UPDATE django_content_type SET app_label = 'contas' WHERE id = %s", [content_type[0]])

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        raise IrreversibleError("A conversão para UUID exige restauração de backup para voltar aos IDs numéricos.")
