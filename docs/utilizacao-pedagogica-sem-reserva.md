# Utilização pedagógica sem reserva — entrega de 14/10

**Estado em 13/10/2026:** implementado e validado na branch `feat/utilizacao-sem-reserva`. Revisão do Diego, integração e validação publicada pendentes. O incremento atende ao fluxo sem reserva do RF-10 e à RN-16; RF-11 continua pendente.

## Comportamento aprovado

- Professor ativo, exclusivamente no grupo Professor e sem Superuser, associa o contexto somente às próprias retiradas. Operador continua responsável pela movimentação física.
- Vínculo opcional; Turma, Disciplina e Atividade obrigatórias ao salvar; Observação opcional. Um formulário aplica os dados a todas as unidades do lote.
- Criação e edição permitidas enquanto existir uma unidade pendente. Devolução parcial permite corrigir também as unidades já devolvidas. Devolução integral encerra criação e edição, mantendo consulta.
- Novas escolhas usam cadastros ativos; uma referência já vinculada pode ser mantida após inativação. Não há exclusão do contexto nem preenchimento automático de utilizações antigas.

## Interface e integridade

`GET /pedagogico/utilizacoes/` reúne retiradas próprias com e sem reserva, inclusive encerradas, em páginas de dez grupos ordenados do mais recente ao mais antigo. Reserva identifica o grupo com reserva; UUID identifica o lote sem reserva. Registros antigos sem ambos são individuais, sem inferir lotes por destinatário ou horário. O agrupamento legado da tela de devolução permanece como antes.

`GET/POST /pedagogico/retiradas/<retirada_id>/utilizacao/` oferece consulta e gravação sem reserva. Acesso exige `view_utilizacaopedagogica`; gravação exige também `add` ou `change`. Professor e unidades são derivados no servidor. Retirada alheia, inexistente, com reserva ou movimentação de devolução retorna 404. Lote com destinatários inconsistentes não é exposto no detalhe nem recebe gravação.

O acesso com reserva continua em `/pedagogico/reservas/<reserva_id>/utilizacao/` e em Minhas Reservas. Os dois fluxos reutilizam formulário, template e gravação transacional. `UtilizacaoPedagogica` continua único por retirada física, com referências `PROTECT`. Não foram acrescentados campos, migrations ou dependências. Indicadores futuros precisam explicitar se contam unidades ou lotes.

O serviço bloqueia todas as retiradas em ordem de ID, reconsulta devoluções e cadastros e grava associações e auditorias de sucesso atomicamente. Falha de validação ou integridade desfaz a gravação; sua auditoria referencia a retirada de entrada. Reenvio sem mudança preserva IDs e datas sem novos eventos. Gravações concorrentes são serializadas; prevalece a última gravação válida.

Histórico de Administrador/Operador consulta o contexto da retirada original, inclusive na devolução. A exportação inclui utilizações sem reserva com `reserva_id: null`; anonimização preserva os vínculos. Professor não recebeu acesso ao histórico geral.

## Verificação em 13/10

| Ambiente | Resultado |
|---|---|
| Suíte completa em SQLite | 394 testes em 36,233 s: 381 aprovados e 13 ignorados, dependentes de bloqueio real de banco |
| PostgreSQL 17.6 isolado | 252 testes de pedagogia, movimentações, reservas e manutenção em 41,797 s: todos aprovados, sem ignorados |
| Verificações Django | `check`, `makemigrations --check --dry-run` e `migrate --check` aprovados; `axes.W006` continua intencionalmente silenciado |

O incremento acrescenta 18 testes em `pedagogico/test_utilizacao_sem_reserva.py`, incluindo dois de concorrência: gravações simultâneas e gravação simultânea à devolução integral. Os cenários cobrem ciclo completo, propriedade, perfis, permissões por ação, CSRF, lotes separados, registros antigos individuais, paginação, cadastros inativos, rollback, reenvio, manutenção, inativação, histórico, exportação e anonimização. Dois testes antigos foram ajustados para permitir o novo comportamento sem enfraquecer a proteção dos cadastros administrativos.

O PostgreSQL foi criado em contêiner temporário sem volumes, com acesso somente em `127.0.0.1:55433`. O banco de testes foi criado e removido pelo Django. Nenhum banco publicado foi acessado.

## Conferência da interface

Banco sintético separado em `.tmp/sem-reserva-ui.sqlite3`, com Professor e Operador em sessões distintas. Cenários iniciais com e sem reserva preparados por serviços. Pela interface foram conferidos lista unificada, criação do contexto das três unidades por teclado (Tab e Enter), rejeição de Turma vazia com demais campos preservados e foco em `form-errors`, devolução parcial de uma unidade, correção da observação com duas pendências, devolução das demais e consulta sem formulário. O histórico preservou a observação corrigida nas três retiradas e três devoluções.

Desktop: 1440 × 900. Celular: 390 × 844. Formulário e lista com largura de página de 390 pixels; tabela de 760 pixels com rolagem própria em contêiner de 356 pixels. As sessões registraram a ausência preexistente de `/favicon.ico`; uma navegação de teste para URL incorreta de devolução também retornou 404 e foi corrigida.

- [Lista desktop](evidencias/utilizacao-sem-reserva-lista-desktop.png)
- [Formulário no celular](evidencias/utilizacao-sem-reserva-form-mobile.png)
- [Erro no celular](evidencias/utilizacao-sem-reserva-mobile-erro.png)
- [Consulta após devolução integral](evidencias/utilizacao-sem-reserva-encerrada-mobile.png)

## Banco local e fechamento

Foi conferido backup SQLite por API de backup e `PRAGMA integrity_check` em `.tmp/backups/db-before-sem-reserva-20261013-115613.sqlite3`. A migration preexistente `manutencoes.0001_initial` e `configurar_perfis` foram aplicados somente ao SQLite local; não restaram migrations pendentes. O incremento não altera o esquema. Bancos, sessões, scripts e backup temporários não integram a entrega versionada.

Próximo fechamento: revisão do Diego, integração e validação do ambiente publicado. A implementação local não comprova esses três passos nem permite marcar a entrega pessoal como integralmente concluída.
