# Matriz de acesso

Esta matriz registra as decisões aprovadas para atender ao `RF-01`. Estão implementadas as permissões do inventário, cadastro de usuários, auditoria, reservas próprias, retirada com ou sem reserva, devolução básica, histórico de movimentações e cadastros de Turma, Disciplina e Atividade Pedagógica. A branch `utilizacao-equipamentos` acrescenta a associação pedagógica de utilizações com reserva. Manutenção, painel dedicado, associação sem reserva e indicadores pedagógicos permanecem planejados.

## Princípios

- O SIGEE usa o `User` nativo do Django.
- Os perfis funcionais são os grupos `Administrador`, `Operador` e `Professor`.
- Cada conta funcional pertence a exatamente um desses grupos. Uma conta sem grupo pode se autenticar, mas não recebe permissões funcionais.
- O Django Superuser é uma conta técnica, usada para a configuração inicial, e não constitui um quarto perfil funcional.
- A autorização é verificada no servidor com `Groups` e `Permissions`. Nas ações que dependem do proprietário do registro, como cancelar uma reserva, a aplicação também verifica a relação entre o usuário e o objeto.
- Uma nova reserva é sempre vinculada pelo servidor ao Professor autenticado; o Professor não pode criar uma reserva em nome de outro usuário.

## Ações por perfil

| Ação | Administrador | Operador | Professor |
|---|:---:|:---:|:---:|
| Autenticar-se e encerrar a sessão | Sim | Sim | Sim |
| Consultar equipamentos e disponibilidade | Sim | Sim | Sim |
| Cadastrar, importar, alterar, excluir ou inativar equipamentos | Sim | Não | Não |
| Cadastrar usuários e atribuir o grupo funcional | Sim | Não | Não |
| Consultar, criar, editar, inativar e reativar turmas, disciplinas e atividades pedagógicas | Sim | Não | Não |
| Consultar registros de auditoria | Sim | Não | Não |
| Visualizar o painel resumido e os indicadores pedagógicos | Sim | Não | Não |
| Criar reserva própria | Não | Não | Sim |
| Consultar e cancelar reserva própria | Não | Não | Sim |
| Consultar reservas para conferir a entrega | Não | Sim | Não |
| Registrar retirada e devolução | Não | Sim | Não |
| Consultar histórico de movimentações | Sim | Sim | Não |
| Encaminhar equipamento para manutenção durante a devolução | Não | Sim | Não |
| Registrar, alterar e concluir intervenções de manutenção | Sim | Não | Não |
| Vincular a utilização a turma, disciplina e atividade pedagógica | Não | Não | Sim |

## Rastreabilidade

| Decisão | Evidência de requisito |
|---|---|
| Autenticação e autorização por perfil | RF-01, RNF-01 e RS-01 |
| Criação por tipo/modelo e local, e cancelamento de reserva própria pelo Professor | RN-02, RN-07 e RN-12 |
| Bloqueio de reserva passada ou em fim de semana | RF-04 e RN-19 |
| Retirada e devolução por Operador | RN-08 e RN-13 |
| Encaminhamento para manutenção na devolução | RN-14 |
| Cadastro controlado de contas e separação do Superuser técnico | RN-18 |
| Consulta controlada dos registros de auditoria | RS-09 e RS-11 |
| Indicadores e uso pedagógico | RF-08, RF-10 e RF-11 |
| Administrador mantém os três cadastros compartilhados, sem exclusão definitiva | Decisão aprovada para a entrega de 09/10; base cadastral para RF-10 |

## Configuração executável atual

O comando `python manage.py configurar_perfis`, executado depois de `migrate`, aplica exatamente estas permissões:

| Grupo | Permissões atuais |
|---|---|
| Administrador | `view_equipamento`, `add_equipamento`, `change_equipamento`, `delete_equipamento`, `view_resumo_inventario`, `auth.add_user`, `auditoria.view_registroauditoria`, `movimentacoes.view_movimentacao`; no app `pedagogico`: `view_turma`, `add_turma`, `change_turma`, `view_disciplina`, `add_disciplina`, `change_disciplina`, `view_atividadepedagogica`, `add_atividadepedagogica`, `change_atividadepedagogica` |
| Operador | `view_equipamento`, `movimentacoes.add_movimentacao` (retirada com ou sem reserva e devolução básica), `movimentacoes.view_movimentacao` |
| Professor | `view_equipamento`, `add_reserva`, `view_reserva`, `change_reserva`; no app `pedagogico`: `view_utilizacaopedagogica`, `add_utilizacaopedagogica`, `change_utilizacaopedagogica` |

As permissões das funcionalidades futuras serão acrescentadas somente quando suas respectivas rotas forem implementadas.

As rotas sob `/pedagogico/turmas/`, `/pedagogico/disciplinas/` e `/pedagogico/atividades/` exigem conta ativa, sem Superuser, pertencente exclusivamente ao grupo Administrador. Consulta exige `view`, criação exige `add`, e edição/inativação/reativação exigem `change` do modelo correspondente. Uma permissão individual não substitui o grupo correto. Não há permissão de exclusão atribuída, rota de exclusão nem registro desses modelos no Django Admin. Os links exigem a permissão de consulta. Os [cenários e resultados](cadastros-pedagogicos.md) incluem bloqueio por acesso direto e por POST.

As rotas `/movimentacoes/retirada/`, `/movimentacoes/retirada/reservas/`, `/movimentacoes/retirada/reservas/<reserva_id>/`, `/movimentacoes/devolucao/` e `/movimentacoes/devolucao/<retirada_id>/` exigem conta ativa, sem privilégios de Superuser, pertencente exclusivamente ao grupo Operador e com `movimentacoes.add_movimentacao`. A verificação ocorre nas views e nos serviços de gravação, inclusive em acesso direto à URL. Qualquer Operador autorizado pode devolver uma unidade, mesmo quando outro Operador registrou a retirada.

A rota `/movimentacoes/historico/` exige conta ativa, sem Superuser, pertencente exclusivamente ao grupo Administrador ou Operador e com `movimentacoes.view_movimentacao`. O histórico permite somente consulta. O encaminhamento para manutenção permanece pendente.

A rota `/pedagogico/reservas/<reserva_id>/utilizacao/` exige conta ativa exclusivamente no grupo Professor, sem Superuser, e `pedagogico.view_utilizacaopedagogica`. Gravação exige adicionalmente `add` na criação ou `change` na edição, com nova conferência no serviço. Somente reservas próprias são acessíveis; reserva alheia retorna 404. O vínculo requer retirada efetiva e pelo menos uma unidade pendente de devolução. A devolução integral encerra criação e edição. Não há permissão de exclusão nem acesso ao histórico geral pelo Professor. Administrador e Operador consultam o contexto pelo histórico existente, sem obter permissão de edição. As [evidências do incremento](utilizacao-pedagogica-reserva.md) registram o recorte e os testes.
