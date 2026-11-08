# Matriz de acesso

O SIGEE aplica autenticação por sessão e autorização por grupos e permissões do Django. O servidor verifica também a propriedade dos registros do Professor e a autoridade do Administrador sobre a conta alvo.

## Perfis

- Cada conta funcional pertence exclusivamente a Administrador, Operador ou Professor.
- `contas.User` utiliza UUID na tabela `auth_user`.
- O Administrador principal pertence ao mesmo grupo Administrador; `is_administrador_principal` distingue sua autoridade sobre administradores comuns.
- O Superuser é uma conta técnica de configuração/manutenção e não representa um perfil funcional.
- Nas rotas que exigem grupo funcional, estar autenticado ou receber uma permissão individual não substitui essa associação.

## Ações por perfil

| Ação | Administrador | Operador | Professor |
|---|:---:|:---:|:---:|
| Autenticar e encerrar sessão | Sim | Sim | Sim |
| Consultar os próprios dados da conta, sem edição | Sim | Sim | Sim |
| Consultar equipamentos | Sim | Sim | Sim |
| Cadastrar, importar, editar, excluir ou inativar equipamentos | Sim | Não | Não |
| Cadastrar e consultar contas funcionais | Sim | Não | Não |
| Desativar/reativar Professores e Operadores | Sim | Não | Não |
| Desativar/reativar administradores comuns | Somente o principal | Não | Não |
| Desativar a conta principal ou a própria conta | Não | Não | Não |
| Manter turmas, disciplinas e atividades | Sim | Não | Não |
| Consultar auditoria | Sim | Não | Não |
| Consultar painel e indicadores pedagógicos | Sim | Não | Não |
| Criar, acompanhar e cancelar reserva própria | Não | Não | Sim |
| Consultar reservas para acompanhamento | Sim, todas | Sim, para entrega | Somente próprias |
| Confirmar entrega integral, parcial por manutenção ou complementar | Não | Sim | Não |
| Registrar nova retirada sem reserva | Não | Não | Não |
| Consultar Em uso | Todos os registros | Todos os registros | Somente próprios |
| Registrar devolução total ou parcial | Não | Sim | Não |
| Indicar problema na devolução | Não | Sim | Não |
| Abrir manualmente e consultar manutenção | Sim | Sim | Não |
| Iniciar e concluir manutenção | Sim | Não | Não |
| Consultar Histórico | Todos os registros encerrados | Todos os registros encerrados | Somente próprios |
| Gravar contexto pedagógico da reserva ou de retirada legada | Não | Não | Somente próprios, até a devolução integral |

O cancelamento exige ausência de retirada e reserva ativa no prazo válido. A edição do contexto sem retirada exige reserva ativa antes do limite de tolerância. A consulta não concede ações de entrega, devolução ou manutenção.

A matriz descreve os acessos concedidos pela configuração oficial de perfis. As rotas de listagem, cadastro, edição, importação e exclusão do inventário verificam autenticação e permissões do Django, sem exigir diretamente um grupo funcional. Por isso, uma permissão individual correspondente também autoriza essas operações, e o Superuser técnico pode acessá-las. As demais áreas aplicam as verificações de perfil indicadas abaixo; o acesso técnico ao inventário não representa um quarto perfil funcional.

## Configuração executável

`python manage.py configurar_perfis` cria os grupos ausentes e substitui suas permissões pela definição de `PERMISSOES_POR_GRUPO` em [usuarios/permissoes.py](../../usuarios/permissoes.py). Execute depois de `migrate`; o comando é idempotente.

| Grupo | Permissões |
|---|---|
| Administrador | `inventario`: view/add/change/delete de equipamento e `view_resumo_inventario`; `contas`: add/view/change de user; `auditoria.view_registroauditoria`; `movimentacoes.view_movimentacao`; `reservas.view_reserva`; `manutencoes`: view/add/change de manutencao; `pedagogico`: view/add/change de turma, disciplina e atividadepedagogica, e view de utilizacaopedagogica. |
| Operador | `inventario.view_equipamento`; `movimentacoes.add_movimentacao` e `movimentacoes.view_movimentacao`; `manutencoes.view_manutencao` e `manutencoes.add_manutencao`. |
| Professor | `inventario.view_equipamento`; `reservas.add_reserva`, `view_reserva`, `change_reserva`; `pedagogico.view_utilizacaopedagogica`, `add_utilizacaopedagogica`, `change_utilizacaopedagogica`. |

Nenhum grupo recebe exclusão de usuários, movimentações, manutenção ou utilização pedagógica. A exclusão de equipamento sem histórico segue as verificações do inventário.

## Rotas e verificações

| Área | Rotas principais | Controle |
|---|---|---|
| Usuários | `/usuarios/`, `/usuarios/novo/`, `/usuarios/<uuid>/desativar/`, `/usuarios/<uuid>/reativar/` | Administrador com view/add/change conforme a ação; alterações de situação por POST com CSRF e autoridade sobre a conta alvo. |
| Auditoria | `/auditoria/` | Administrador com `view_registroauditoria`; somente consulta. |
| Reservas próprias | `/reservas/`, `/reservas/nova/`, `/reservas/<id>/cancelar/` | Professor proprietário; view/add/change conforme a ação; cancelamento por POST. |
| Detalhe da reserva | `/reservas/<id>/` | Administrador/Operador com `view_movimentacao`; Professor com `view_reserva`, restrito à própria reserva. Somente GET. |
| Reservas administrativas | `/reservas/consulta/` | Administrador com `view_reserva`; GET, sem alteração manual dos registros. A consulta pode persistir expirações e suas auditorias. |
| Entrega | `/movimentacoes/retirada/reservas/`, `/movimentacoes/retirada/reservas/<id>/` | Operador com `add_movimentacao`; nova conferência no serviço. |
| Em uso | `/movimentacoes/devolucao/` | Consulta de Administrador/Operador e do Professor restrito aos próprios registros. |
| Devolução | `/movimentacoes/devolucao/<id>/` | Operador com `add_movimentacao`; confirmação por POST com CSRF. |
| Histórico | `/movimentacoes/historico/` | Administrador/Operador com `view_movimentacao`; Professor com `view_reserva` e propriedade aplicada antes dos filtros. |
| Manutenção | `/manutencoes/` | Administrador com view/add/change; Operador somente view/add. |
| Cadastros pedagógicos | `/pedagogico/turmas/`, `/pedagogico/disciplinas/`, `/pedagogico/atividades/` | Administrador; view/add/change. Inativação e reativação por POST; sem exclusão definitiva. |
| Contexto pedagógico | `/pedagogico/reservas/<id>/utilizacao/`, `/pedagogico/retiradas/<id>/utilizacao/` | Professor proprietário/destinatário com view e add/change ao gravar; retirada sem reserva somente legada. |
| Utilizações próprias | `/pedagogico/utilizacoes/` | Professor com `view_utilizacaopedagogica`; consulta somente das próprias retiradas. |
| Indicadores | `/pedagogico/indicadores/` | Administrador com `view_utilizacaopedagogica`; consulta não concede edição dos contextos do Professor. |

As rotas antigas de nova retirada sem reserva e disponibilidade de retirada retornam acesso negado. Professor recebe 404 ao tentar acessar contexto ou reserva de outro Professor. As listagens de reservas do Professor, do Operador e do Administrador, o detalhe da reserva e o Histórico executam a sincronização de expiração. A consulta de disponibilidade também sincroniza reservas vencidas antes do cálculo.

## Rastreabilidade

As verificações atendem a RF01, RF04 a RF11, RN-07 a RN-18 e RS-01/RS-09/RS-11. Os detalhes de conta principal e desativação estão em [Autenticação](autenticacao.md); as etapas e os legados estão no [Fluxo](fluxo-reservas-uso-historico.md).

O Administrador e o Operador utilizam o escopo global da aplicação. Não há isolamento entre instituições; o Professor permanece restrito aos próprios registros.

O Operador visualiza somente a turma do contexto pedagógico nas reservas e no histórico. A entrega parcial exige confirmação de comunicação ao Professor. O saldo de entrega e as devoluções físicas são apresentados separadamente.
