# Banco de dados: proteção no Supabase e atualização de instalações

## Decisão e escopo

Atende a RF01, RNF01 e RS-01/RS-02/RS-10: a autorização funcional continua no
Django, que se conecta diretamente ao PostgreSQL. As roles da Data API `anon` e
`authenticated` não representam os perfis Administrador, Operador e Professor.
Elas não precisam acessar as tabelas internas do SIGEE.

A proteção restringe o acesso das roles da Data API às tabelas internas do Django. A configuração efetiva de cada ambiente é conferida pelos procedimentos abaixo; a existência do script não comprova sua aplicação no banco.

O script [proteger-acesso-banco-supabase.sql](sql/proteger-acesso-banco-supabase.sql):

- habilita RLS nas tabelas Django de `public`, sem `FORCE` e sem políticas públicas;
- revoga os privilégios de `anon` e `authenticated` em tabelas e sequências;
- retira os privilégios padrão dessas roles em futuras tabelas e sequências que
  `postgres` criar em `public`;
- verifica privilégios efetivos, incluindo herança, `PUBLIC` e colunas, antes do
  commit; qualquer erro cancela a transação inteira.

**Limitação do catálogo atual:** a lista de prefixos aceita pelo SQL ainda não inclui `calendario_`. Depois de aplicar as migrations do calendário, o script rejeita esses objetos e aborta a transação antes da proteção. É necessário adequar e verificar o catálogo de objetos do próprio script antes de reaplicá-lo a um banco com essas tabelas. Não remover a validação de escopo nem assumir que as novas tabelas já estão protegidas.

Não altera dados, autenticação Django, permissões funcionais, `service_role` ou os
schemas internos do Supabase. O script exige a role `postgres`. Antes da aplicação, conferir a role usada pelo backend e sua compatibilidade com RLS, inclusive a condição de proprietária ou `BYPASSRLS`.

## Pré-requisitos do script de proteção

O script exige **PostgreSQL 17 ou superior**, pois verifica também o privilégio `MAINTAIN`, além da role `postgres` e das roles `anon` e `authenticated` do Supabase. Conferir a versão na conexão de destino antes da execução:

```sql
SHOW server_version;
SELECT current_user;
```

Esse pré-requisito de versão pertence ao script de proteção. Não é necessário executar esse SQL no PostgreSQL local utilizado somente pelos testes do Django, onde as roles da Data API podem não existir.

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

Após migrations que criem tabelas, conferir primeiro se os objetos estão contemplados no catálogo do script; o prefixo `calendario_` permanece uma limitação da versão atual. Depois da adequação e verificação em ambiente isolado, executar novamente a conferência e o script
controlado para habilitar RLS nos novos objetos. A alteração dos privilégios
padrão já impede os grants automáticos de tabelas/sequências criadas por
`postgres`; RLS de novas tabelas não é habilitada automaticamente por este script.

Os defaults de `supabase_admin` permanecem intactos. Objetos criados pelo painel
ou por outra role exigem nova revisão. Funções futuras também precisam de revisão
específica: o privilégio `EXECUTE` recebido de `PUBLIC` não é resolvido por revogar
grants de funções apenas no schema. O script rejeita views, materialized views e outros objetos fora de seu escopo em `public`; funções exigem conferência específica.

A configuração global da Data API não é alterada pelo SQL. Se não houver uso de
REST/GraphQL da plataforma, desabilitar a Data API no painel é uma camada
complementar; seu estado e o Security Advisor devem ser conferidos no ambiente
autenticado. Investigação de acessos anteriores depende dos logs disponíveis.

## Atualização de bancos existentes

Estas orientações são aplicáveis a bancos que ainda usam o esquema anterior. Instalações novas seguem `migrate` e a preparação de perfis descritos no [README](../../README.md#preparação-e-inicialização). Conferir destino, backup e migrations aplicadas antes de atualizar. O código versionado não comprova a situação do banco publicado.

### Usuários com identificador numérico

Para um banco ainda com IDs numéricos, manter a aplicação em manutenção, preparar backup e executar na ordem:

```powershell
python manage.py migrate contas 0001 --settings=config.settings_preparacao_uuid
python manage.py migrate
python manage.py configurar_perfis
```

A configuração de preparação é exclusiva do primeiro comando. A conversão preserva contas e vínculos, encerra sessões e invalida links antigos de recuperação. A reversão exige restaurar o backup e a versão anterior do código. O Administrador principal é designado pelo comando descrito em [Autenticação](../tecnica/autenticacao.md#administrador-principal-de-reserva); migrations não promovem contas existentes.

### Planejamento pedagógico na reserva

`reservas.0005` adiciona turma, disciplina, atividade e observação pedagógica e recupera somente contextos históricos uniformes. `reservas.0006` exige contexto completo ou totalmente ausente. A ausência total preserva reservas legadas, que o Professor completa antes da entrega.

Na atualização de PostgreSQL com dados existentes, coordenar migrations e publicação da nova versão. A coluna `observacao_pedagogica` é `NOT NULL`, sem default persistente no banco; o código anterior não fornece essa coluna. Manter manutenção durante a transição. Reverter `0005` remove os dados das novas colunas; o histórico Git não recupera esses dados.

Quando `0005` e `0006` são aplicadas na mesma transação PostgreSQL, executar `SET CONSTRAINTS ALL IMMEDIATE` entre elas para descarregar eventos diferidos das novas FKs antes da criação do CHECK. Conferir preservação dos dados, perfis e migrations antes de liberar o acesso. Uma recuperação com código anterior também exige tratar o default dessa coluna e reconciliar o contexto.

### Cancelamento operacional de reserva

`reservas.0008` acrescenta motivo, responsável e data de cancelamento, com restrição de completude quando esses metadados estiverem presentes. Reservas existentes mantêm os campos vazios; não há inferência de autoria ou motivo. O motivo possui default persistente vazio para preservar inserções pela versão anterior durante a preparação da atualização.

`usuarios.0005` cria a permissão específica de cancelamento operacional e a acrescenta ao grupo Operador sem substituir as demais concessões. A configuração oficial em `configurar_perfis` também inclui essa permissão. Aplicar as migrations antes de disponibilizar o código que consulta os novos campos e executar `configurar_perfis` somente após as migrations.

A mudança não cria tabelas novas. Validar o upgrade em banco isolado com reservas existentes e o fluxo de cancelamento versus entrega antes de publicar. A reversão da migration de campos elimina os metadados; preservar backup e registros antes de qualquer reversão. Reverter código não desfaz cancelamentos nem as novas alocações que a liberação tornou possíveis.

O histórico de implantação registra que, em 09/11/2026, também estavam pendentes `reservas.0007`, `movimentacoes.0005` e `usuarios.0004`, aplicadas junto das duas migrations de cancelamento após backup `pg_dump` e proteção da nova tabela de substituições. Nessa atualização foi mantido um default SQL `false` em `movimentacoes_movimentacao.professor_informado`: a versão anterior do backend omite essa coluna nos INSERTs. Esse default é uma compatibilidade operacional, ainda não representada por `db_default` no estado Django; conferir sua existência e mantê-lo enquanto houver código antigo em execução, reavaliando-o explicitamente após a atualização de todas as instâncias. O relato histórico não comprova o estado atual de outro ambiente.

### Calendário, intervalo, cotas e fechamentos

As migrations `calendario.0001` a `0003` introduzem regras semanais, faixas, exceções, histórico, intervalo e fechamentos com decisões sobre reservas. `usuarios.0006` concede a permissão de configuração ao grupo Administrador sem substituir as demais concessões. `reservas.0009` a `0011` acrescentam o calendário confirmado, o intervalo após o uso e a cota guardada na reserva; `inventario.0006` acrescenta a cota opcional por tipo/modelo.

Aplicar as migrations compatíveis com a nova versão antes de liberar os fluxos que consultam os campos. Reservas anteriores mantêm calendário confirmado vazio, intervalo zero e cota confirmada nula; a atualização não inventa condições nem reescreve compromissos antigos. O calendário inicial permite segunda a sexta durante todo o dia, para uso e atendimento. A margem padrão para novas reservas é de 5 minutos, não há cota adicional inicialmente e a política de manter entregas em fechamento começa desabilitada.

Em PostgreSQL, `calendario.0003` habilita RLS e revoga privilégios de acesso público e das roles de API encontradas nas duas tabelas novas de fechamento e decisão. Isso não substitui a conferência das tabelas anteriores do calendário nem corrige a lista de prefixos do script geral. Conferir todas as tabelas `calendario_*` no procedimento de proteção, observada a limitação indicada acima. Uma reversão de schema pode remover configurações e históricos; reverter o código não desfaz reservas, cancelamentos ou decisões já registrados.

### Limites de sessão e documentos legais

O controle de sessão não acrescenta tabelas nem requer migration própria. A nova versão usa `DJANGO_SESSION_IDLE_TIMEOUT=1800` e `DJANGO_SESSION_ABSOLUTE_TIMEOUT=28800` como padrões; os limites precisam ser positivos. `DJANGO_SESSION_COOKIE_AGE` passa a ter padrão de 28800 segundos para sessões sem prazo específico, e o login define uma expiração absoluta fixa quando o encerramento ao fechar o navegador está desabilitado. A `DJANGO_SECRET_KEY` existente continua em uso; não há token adicional a cadastrar.

Sessões antigas sem os horários de controle exigem novo login. A Política de Privacidade passa à versão 2.2, de 10/11/2026, enquanto os Termos permanecem na versão 2.0. O fluxo de aceite exige ciência da política atualizada e preserva os aceites anteriores. Validar os fluxos autenticados depois de publicar a versão; uma alteração somente no arquivo `.env.example` não configura o ambiente da hospedagem.

### Configuração da aplicação

`vercel.json` define a região `gru1` e não contém suspensão do deploy da `main` nem comando de migrations. A aplicação usa `DATABASE_URL`; `sslmode=require` exige cifragem, sem equivaler à verificação completa de identidade por `verify-full`. Configurar segredos, hosts, `DEBUG=False` e SMTP no ambiente de destino, sem versionar valores reais. Validar a conexão usada pelo backend, os fluxos autenticados e a recuperação de senha após a publicação.

Após migrations que criam tabelas, repetir a conferência e a proteção de novos objetos somente com um script que os contemple. Os comandos de testes locais usam `config.settings_testes`; o runner de testes não utiliza o banco publicado.

## Testes com PostgreSQL isolado

Os testes locais comuns usam SQLite, conforme o [README](../../README.md#testes). Para executar os cenários com bloqueio de linha, utilize uma instalação PostgreSQL local dedicada a testes. Os comandos abaixo usam PowerShell, com o ambiente virtual ativado e os executáveis PostgreSQL disponíveis no `PATH`.

### Preparar a conexão local

Conecte ao PostgreSQL local com uma conta autorizada a criar roles e bancos:

```powershell
psql -h 127.0.0.1 -U postgres -d postgres
```

No prompt do `psql`, crie uma role e um banco exclusivos para esse uso. Substitua a senha ilustrativa por uma senha local de teste:

```sql
CREATE ROLE sigee_testes LOGIN CREATEDB PASSWORD 'substitua_por_uma_senha_local';
CREATE DATABASE sigee_testes OWNER sigee_testes;
\q
```

A role precisa de `CREATEDB` porque o runner do Django cria o banco temporário `test_sigee_testes`, aplica as migrations e o remove ao final. O banco `sigee_testes` permanece como conexão de referência. Não use a conexão nem as credenciais do ambiente publicado.

### Executar os testes

Em um terminal dedicado, na raiz do repositório e com o ambiente virtual ativado, defina as variáveis abaixo. Na URL, use a senha atribuída à role; caracteres reservados precisam ser codificados para URL.

```powershell
$env:DATABASE_URL = 'postgresql://sigee_testes:substitua_por_uma_senha_local@127.0.0.1:5432/sigee_testes'
$env:DJANGO_DEBUG = 'True'
$env:DJANGO_EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
python manage.py test reservas.test_concorrencia --settings=config.settings
```

Esta execução usa `config.settings` para respeitar a conexão PostgreSQL definida no terminal. `config.settings_testes` sempre substitui o banco por SQLite e, portanto, não serve para essa verificação. `DJANGO_DEBUG=True` desativa o redirecionamento obrigatório para HTTPS no teste local; o backend de e-mail em memória evita envios reais. A chave `DJANGO_SECRET_KEY` continua sendo a chave local preparada conforme o README.

Para executar todos os módulos com a mesma conexão isolada:

```powershell
python manage.py test --settings=config.settings
```

O resultado precisa mostrar a execução dos cenários de concorrência, sem descarte por falta de suporte a bloqueio de linha. Ao concluir, feche o terminal dedicado para descartar as variáveis temporárias. Preparar estas instruções não representa execução ou aprovação dos testes em PostgreSQL.

Os testes concorrentes estão disponíveis para verificação adicional. Nesta etapa, a validação executada utilizou SQLite em memória; 26 cenários dependentes de bloqueio de linha ficaram ignorados. Não há resultado de execução desses cenários no PostgreSQL a declarar.

## Referências

- [Supabase: segurança da Data API](https://supabase.com/docs/guides/api/securing-your-api).
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
- [PostgreSQL: privilégios padrão](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html).
