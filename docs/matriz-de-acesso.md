# Matriz de acesso

Esta matriz registra as decisões aprovadas para atender ao `RF-01`. As permissões referentes às rotas atuais do inventário e ao cadastro de usuários já estão implementadas; as demais ações continuam planejadas.

## Princípios

- O SIGEE usa o `User` nativo do Django.
- Os perfis funcionais são os grupos `Administrador`, `Operador` e `Professor`.
- Cada conta funcional pertence a exatamente um desses grupos. Uma conta sem grupo pode se autenticar, mas não recebe permissões funcionais.
- O Django Superuser é uma conta técnica, usada para a configuração inicial, e não constitui um quarto perfil funcional.
- A autorização é verificada no servidor com `Groups` e `Permissions`. Nas ações que dependem do proprietário do registro, como cancelar uma reserva, a aplicação também verifica a relação entre o usuário e o objeto.

## Ações por perfil

| Ação | Administrador | Operador | Professor |
|---|:---:|:---:|:---:|
| Autenticar-se e encerrar a sessão | Sim | Sim | Sim |
| Consultar equipamentos e disponibilidade | Sim | Sim | Sim |
| Cadastrar, importar, alterar, excluir ou inativar equipamentos | Sim | Não | Não |
| Cadastrar usuários e atribuir o grupo funcional | Sim | Não | Não |
| Visualizar o painel resumido e os indicadores pedagógicos | Sim | Não | Não |
| Criar reserva | Não | Não | Sim |
| Consultar e cancelar reserva própria | Não | Não | Sim |
| Registrar retirada e devolução | Não | Sim | Não |
| Consultar histórico de movimentações | Sim | Sim | Não |
| Encaminhar equipamento para manutenção durante a devolução | Não | Sim | Não |
| Registrar, alterar e concluir intervenções de manutenção | Sim | Não | Não |
| Vincular a utilização a turma, disciplina e atividade pedagógica | Não | Não | Sim |

## Rastreabilidade

| Decisão | Evidência de requisito |
|---|---|
| Autenticação e autorização por perfil | RF-01, RNF-01 e RS-01 |
| Reserva exclusiva de Professor e cancelamento da própria reserva | RN-07 e RN-12 |
| Retirada e devolução por Operador | RN-08 e RN-13 |
| Encaminhamento para manutenção na devolução | RN-14 |
| Cadastro controlado de contas e separação do Superuser técnico | RN-18 |
| Indicadores e uso pedagógico | RF-08, RF-10 e RF-11 |

## Configuração executável atual

O comando `python manage.py configurar_perfis`, executado depois de `migrate`, aplica exatamente estas permissões:

| Grupo | Permissões atuais |
|---|---|
| Administrador | `view_equipamento`, `add_equipamento`, `change_equipamento`, `delete_equipamento`, `view_resumo_inventario`, `auth.add_user` |
| Operador | `view_equipamento` |
| Professor | `view_equipamento` |

As permissões das funcionalidades futuras serão acrescentadas somente quando suas respectivas rotas forem implementadas.
