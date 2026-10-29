# Fluxo de reservas, uso e histórico

Regra aprovada pelo responsável pelo projeto em 29/10/2026. Este documento descreve a alteração local; não comprova publicação ou migração em produção.

## Responsabilidades e etapas

| Etapa | Professor | Operador | Administrador |
| --- | --- | --- | --- |
| Reservas | Cria e acompanha suas reservas; informa turma, disciplina e atividade; cancela quando permitido | Confere e entrega o lote integral | Consulta |
| Em uso | Consulta seus empréstimos pendentes | Registra devoluções parciais ou integrais e problemas por patrimônio | Consulta |
| Histórico | Consulta somente seus registros encerrados | Consulta os registros encerrados | Consulta os registros encerrados |

- Toda nova retirada exige uma reserva válida. O serviço e as duas rotas antigas sem reserva recusam novas operações.
- A entrega confirmada pelo Operador move o registro de Reservas para Em uso. Uma segunda entrega é rejeitada.
- A devolução parcial mantém o lote em Em uso, com a quantidade pendente explícita. A devolução integral o apresenta somente no Histórico.
- Reservas canceladas ou expiradas aparecem no Histórico mesmo sem movimentações. Mantém-se a tolerância existente de 30 minutos para retirada.
- O fim do horário agendado não representa uma devolução física nem encerra o empréstimo automaticamente.
- A devolução com defeito encerra a pendência daquela unidade e abre manutenção. A manutenção continua separadamente sob responsabilidade do Administrador.

## Contexto pedagógico e dados anteriores

O planejamento fica vinculado à reserva. Turma, disciplina e atividade são obrigatórias para novas reservas; observação é opcional. Consultar disponibilidade não exige preencher planejamento.

Na entrega, o sistema cria as utilizações por unidade na mesma transação. Portanto, agendar uma reserva não aumenta os indicadores de uso realizado. Correções enquanto houver unidades pendentes sincronizam reserva e utilizações. Depois da devolução integral, o contexto fica somente para consulta.

As migrations `reservas.0005` e `reservas.0006` adicionam campos e uma restrição de contexto completo ou totalmente ausente. A recuperação copia apenas contextos históricos uniformes existentes, sem alterar ou inventar utilizações. Reservas antigas sem contexto precisam ser completadas pelo Professor antes da entrega.

Retiradas antigas sem reserva não são excluídas nem convertidas artificialmente em reservas. Pendências ainda permitem devolução; lotes encerrados ficam identificados no Histórico. A edição pedagógica de legados segue limitada ao Professor destinatário e ao período anterior à devolução integral.

## Consultas e proteção

`ReservaQuerySet.com_etapa()` centraliza a classificação, calculada a partir das retiradas/devoluções e do cancelamento/expiração. Não há um segundo estado de empréstimo atualizado manualmente.

O Histórico apresenta uma linha por reserva, com detalhes de patrimônios, movimentações e contexto. A busca inclui professor, operador e patrimônio. O período considera a data das movimentações; sem retirada, considera a data reservada. As consultas do Professor aplicam propriedade antes de filtros e paginação. Consultar Em uso não concede permissão de entregar ou devolver.

A ordem de bloqueio para reservas vinculadas é reserva antes das retiradas. A criação bloqueia o Professor com `no_key=True`, preservando a serialização com inativação sem impedir referências de entrega concorrentes. Os testes PostgreSQL incluem essas disputas.

## Verificação e aplicação

Comandos do projeto, sem acesso ao banco publicado:

```powershell
.\.venv\Scripts\python.exe manage.py check --settings=config.settings_testes
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings_testes
.\.venv\Scripts\python.exe manage.py test --settings=config.settings_testes --noinput
git diff --check
```

SQLite não comprova bloqueios concorrentes. A validação também deve executar a suíte em PostgreSQL isolado. Foi exercitado no navegador local o cadastro com contexto, entrega, devolução parcial/integral e consulta de Professor, Operador e Administrador, com dados sintéticos e relógio de teste controlado.

Resultado final em 29/10/2026: **447 testes aprovados em PostgreSQL 17.6, sem casos ignorados** (100,139 segundos). A execução inclui os testes de concorrência e as regressões de busca/paginação. `check`, `makemigrations --check --dry-run`, `node --check static/inventario/js/sigee.js` e `git diff --check` passaram. A consulta no navegador também foi conferida em 1280 × 900 e 390 × 844, sem transbordamento horizontal da página; tabelas largas usam rolagem própria.

Antes de publicar, preparar backup e aplicar as duas migrations no ambiente correto, coordenando com a nova versão do código. A migração `0005` cria `observacao_pedagogica` como `NOT NULL`, sem default persistente de banco: a versão antiga não fornece essa coluna ao criar reservas. Portanto, manter a manutenção até promover a versão nova. Uma recuperação com código antigo precisa tratar também esse default, além de reconciliar o contexto. Reverter a migration `0005` remove o planejamento registrado nas novas colunas; Git não recupera esses dados.

Na aplicação em PostgreSQL com dados existentes, definir `SET CONSTRAINTS ALL IMMEDIATE` depois de aplicar `0005` e antes de executar `0006`. Isso evita eventos diferidos das novas FKs entre o backfill e a criação do CHECK na mesma transação. O procedimento operacional aplica ambas numa transação curta e confere preservação dos dados e das permissões antes do commit.

## Limite deste recorte

A separação de dados entre administradores/instituições não está implementada nesta alteração. Administrador e Operador continuam usando o escopo global atual; o Professor permanece restrito aos próprios registros. A implantação desse isolamento exige um recorte próprio de autorização, vínculos e migração dos dados.

Monografia, dados de produção e credenciais existentes não são alterados por estes ajustes.

## Envio ao GitHub

O envio do código para a `main` foi autorizado em 29/10/2026. Como o projeto Vercel acompanha essa branch e não possui comando de migração configurado no build, `vercel.json` desativa temporariamente o deploy automático da `main` com `git.deploymentEnabled.main = false`. A região `gru1` é preservada; o envio do código não deve substituir a versão publicada antes da preparação do banco.

Para ativar o fluxo em produção: preparar backup, aplicar e conferir as migrations `reservas.0005` e `reservas.0006`, remover essa suspensão do deploy automático e publicar a versão validada. A suspensão pode ser desfeita removendo o bloco `git` de `vercel.json`; isso não executa nem desfaz migrações por si só.

Em 29/10/2026, foi autorizada a aplicação e publicação sem repetir a suíte de testes. O bloco de suspensão foi removido neste incremento; o push dessa remoção ocorre somente depois do backup e do commit das migrações. A versão nova deve ficar `READY` e ser promovida explicitamente antes de retomar o acesso ao projeto.
