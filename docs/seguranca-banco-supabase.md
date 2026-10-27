# Proteção do banco do SIGEE no Supabase

## Decisão e escopo

Atende a RF-01, RNF-01 e RS-01/RS-02/RS-10: a autorização funcional continua no
Django, que se conecta diretamente ao PostgreSQL. As roles da Data API `anon` e
`authenticated` não representam os perfis Administrador, Operador e Professor.
Elas não precisam acessar as tabelas internas do SIGEE.

A conferência de 26/10/2026 encontrou 28 tabelas em `public`, sem RLS e com
permissões amplas para essas duas roles, além de 26 sequências acessíveis. Isso
demonstra uma configuração insegura; não comprova acesso indevido ou vazamento.

O script [proteger-acesso-banco-supabase.sql](sql/proteger-acesso-banco-supabase.sql):

- habilita RLS nas tabelas Django de `public`, sem `FORCE` e sem políticas públicas;
- revoga os privilégios de `anon` e `authenticated` em tabelas e sequências;
- retira os privilégios padrão dessas roles em futuras tabelas e sequências que
  `postgres` criar em `public`;
- verifica privilégios efetivos, incluindo herança, `PUBLIC` e colunas, antes do
  commit; qualquer erro cancela a transação inteira.

Não altera dados, autenticação Django, permissões funcionais, `service_role` ou os
schemas internos do Supabase. A conexão configurada usa `postgres` com
`BYPASSRLS`. Antes de reutilizar o script com outra conexão, conferir se a role
consegue executar as operações do Django com RLS habilitada.

## Aplicação controlada

1. Confirmar o projeto e a role da conexão, os objetos em `public` e a ausência de
   dependências da aplicação na Data API.
2. Guardar, fora do versionamento, as flags de RLS, grants de tabelas, sequências e
   colunas, privilégios padrão e um SQL de reversão que restaure o estado exato.
   O registro deve conter somente metadados, sem senhas ou conteúdo das tabelas.
3. Testar o script e a reversão em PostgreSQL isolado. Em seguida, aplicar o script
   completo numa conexão PostgreSQL do projeto correto. O script exige
   `current_user = postgres`, limita a espera por locks a três segundos e rejeita
   objetos fora dos prefixos dos módulos Django.
4. Conferir RLS e ausência de privilégios efetivos para as duas roles, incluindo
   colunas e sequências. Verificar também que uma consulta sem retorno de dados,
   executada como cada role da API, recebe `permission denied`.
5. Validar consultas e operações pela conexão Django e conferir o ambiente
   publicado. Registrar separadamente testes isolados, consultas ao banco real e
   verificações HTTP; uma página pública respondendo não comprova os fluxos
   autenticados.

Se houver erro, a aplicação é revertida pela própria transação. Uma reversão
posterior deve usar o registro específico da execução; ela reabre as permissões
anteriores e não deve ser aplicada apenas para silenciar um problema não relacionado.

## Novas migrations e limites

Após migrations que criem tabelas, executar novamente a conferência e o script
controlado para habilitar RLS nos novos objetos. A alteração dos privilégios
padrão já impede os grants automáticos de tabelas/sequências criadas por
`postgres`; RLS de novas tabelas não é habilitada automaticamente por este script.

Os defaults de `supabase_admin` permanecem intactos. Objetos criados pelo painel
ou por outra role exigem nova revisão. Funções futuras também precisam de revisão
específica: o privilégio `EXECUTE` recebido de `PUBLIC` não é resolvido por revogar
grants de funções apenas no schema. A conferência inicial não encontrou funções,
views ou materialized views em `public`.

A configuração global da Data API não é alterada pelo SQL. Se não houver uso de
REST/GraphQL da plataforma, desabilitar a Data API no painel é uma camada
complementar; seu estado e o Security Advisor devem ser conferidos no ambiente
autenticado. Investigação de acessos anteriores depende dos logs disponíveis.

## Evidências da aplicação em 26/10/2026

- O ensaio em PostgreSQL 17.6 isolado confirmou idempotência, restauração exata
  dos metadados pelo SQL de reversão, preservação dos grants de outras roles,
  cancelamento integral diante de privilégio residual por coluna concedido a
  `PUBLIC` e os defaults de novas tabelas e sequências. A suíte Django passou com
  456 testes, sem falhas, erros ou casos ignorados, no banco de testes com a
  proteção aplicada.
- A transação foi aplicada ao projeto `bwpisbipjresjikxwrdv`, mantendo as 28
  tabelas com RLS e retirando os acessos das duas roles às 26 sequências. As
  verificações de privilégios efetivos retornaram zero objetos vulneráveis no
  escopo auditado.
- Em uma conexão independente ao banco real, as 56 consultas de verificação das
  roles da API foram negadas e as 28 consultas do backend foram permitidas.
  Todas usaram `LIMIT 0`, sem retornar conteúdo das tabelas.
- O ORM Django consultou os 27 modelos gerenciados registrados, incluindo
  relações intermediárias, em transação somente leitura e com TLS no cliente.
  A condição de chave primária nula garantiu retorno vazio. A tabela adicional
  `django_migrations` integra a verificação SQL das 28 tabelas.
- O registro de ACLs/flags, a reversão específica e os resultados estão em
  `.tmp/backups/seguranca-supabase-20261026T232902Z/`, fora do versionamento.
  Não foram alterados registros da aplicação.
- No ambiente publicado, login, termos e política responderam HTTP 200. As
  consultas anônimas de inventário, reservas, histórico, manutenção e indicadores
  redirecionaram ao login com HTTP 302. Não houve login nem alteração de registros
  durante essa conferência HTTP.

A identidade exata da conexão do deployment Vercel não foi obtida: a sessão
disponível do CLI estava inválida. A checagem dos papéis existentes no banco
confirmou que as roles com login e acesso às tabelas auditadas tinham
`BYPASSRLS`. Isso sustenta a compatibilidade das conexões diretas verificadas,
mas não identifica por si só a role exata da conexão publicada. Em 27/10/2026,
a [validação autenticada dos três perfis](evidencias-seguranca.md#login-e-permissões-no-ambiente-publicado--27102026)
confirmou login, menus, permissões em 48 consultas GET e logout no ambiente
publicado, com contas temporárias de QA. Os fluxos completos de gravação do
domínio permanecem fora desse recorte. O estado do Security Advisor e a
configuração global da Data API continuam dependendo de acesso ao painel.

## Referências

- [Supabase: segurança da Data API](https://supabase.com/docs/guides/api/securing-your-api).
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
- [PostgreSQL: privilégios padrão](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html).
