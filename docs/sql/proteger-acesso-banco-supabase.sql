-- Executar com a role postgres, depois de salvar ACLs e flags de RLS.
-- PostgreSQL 17 ou superior (a verificacao inclui o privilegio MAINTAIN).
-- O acesso funcional continua no Django; anon/authenticated nao usam estas tabelas.
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';

DO $protecao$
DECLARE
    objeto record;
BEGIN
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'Execute com a role postgres usada pelas migrations.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
          AND (
              c.relkind NOT IN ('r', 'p', 'S')
              OR pg_get_userbyid(c.relowner) <> 'postgres'
              OR c.relname !~ '^(auth_|django_|axes_|inventario_|reservas_|movimentacoes_|manutencoes_|pedagogico_|auditoria_|legal_)'
          )
    ) THEN
        RAISE EXCEPTION 'Ha objetos fora do escopo Django em public; revise antes de executar.';
    END IF;

    FOR objeto IN
        SELECT c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'S')
        ORDER BY c.relname
    LOOP
        IF objeto.relkind = 'S' THEN
            EXECUTE format('REVOKE ALL PRIVILEGES ON SEQUENCE public.%I FROM anon, authenticated', objeto.relname);
        ELSE
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', objeto.relname);
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', objeto.relname);
        END IF;
    END LOOP;
END
$protecao$;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;

DO $verificacao$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN (VALUES ('anon'), ('authenticated')) AS papel(nome)
        WHERE n.nspname = 'public' AND (
            (c.relkind IN ('r', 'p') AND (
                NOT c.relrowsecurity
                OR has_table_privilege(papel.nome, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
                OR has_any_column_privilege(papel.nome, c.oid, 'SELECT,INSERT,UPDATE,REFERENCES')
            ))
            OR (c.relkind = 'S' AND has_sequence_privilege(papel.nome, c.oid, 'USAGE,SELECT,UPDATE'))
        )
    ) THEN
        RAISE EXCEPTION 'Persistem privilegios efetivos ou tabelas sem RLS; transacao cancelada.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_default_acl d
        CROSS JOIN LATERAL aclexplode(d.defaclacl) a
        WHERE d.defaclrole = 'postgres'::regrole
          AND d.defaclnamespace IN (0, 'public'::regnamespace)
          AND d.defaclobjtype IN ('r', 'S')
          AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
    ) THEN
        RAISE EXCEPTION 'Persistem privilegios padrao publicos de tabelas/sequencias de postgres.';
    END IF;
END
$verificacao$;

COMMIT;
