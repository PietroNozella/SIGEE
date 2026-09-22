# Modelagem de movimentações, manutenção e painel

Este documento registra as decisões de domínio que antecedem a implementação dos fluxos de movimentação, manutenção e painel do SIGEE. Uma decisão documentada aqui não representa uma funcionalidade já implementada; o estado executável deve ser confirmado pelo código, pelas migrations e pelos testes.

## Retirada sem reserva

### Rastreabilidade

- **Requisitos funcionais:** RF-05 e RF-06.
- **Regras de negócio:** RN-02, RN-04, RN-08, RN-09 e RN-13.
- **Perfil autorizado:** Operador.

### Decisão sobre o destinatário

O destinatário de uma retirada sem reserva pode ser qualquer usuário funcional ativo do SIGEE. Portanto, podem receber um equipamento usuários dos grupos Administrador, Operador ou Professor.

Uma conta técnica de Django Superuser não é considerada um destinatário funcional somente por possuir privilégios técnicos. Para ser selecionável, a conta deve estar ativa e pertencer exatamente a um dos grupos funcionais do SIGEE, conforme a RN-18.

### Pré-condições

1. O usuário que registra a operação está autenticado e pertence ao grupo Operador.
2. O equipamento está ativo e com situação `DISPONIVEL`.
3. O destinatário está ativo e pertence exatamente a um grupo funcional.

### Dados registrados

- equipamento;
- Operador que realizou a entrega;
- destinatário;
- tipo `RETIRADA`;
- data e hora do registro;
- observação, quando necessária.

### Fluxo principal

1. O Operador seleciona um equipamento disponível.
2. O Operador seleciona o destinatário entre os usuários funcionais ativos.
3. O sistema valida novamente a autorização e a disponibilidade no servidor.
4. O sistema cria a movimentação de retirada.
5. O sistema altera a situação do equipamento para `EM_USO`.
6. O sistema confirma a operação e mantém o registro disponível para consulta no histórico.

### Fluxos impedidos

A retirada não é concluída quando:

- o usuário não pertence ao grupo Operador;
- o equipamento está inativo;
- o equipamento não está disponível;
- o destinatário está inativo ou não possui perfil funcional válido;
- alguma etapa da gravação falha.

Nesses casos, nenhuma movimentação parcial deve permanecer salva e a situação do equipamento não deve ser alterada.

### Correspondência com o modelo atual

O modelo `Movimentacao` já possui referências para equipamento, Operador e destinatário, além de tipo, data e hora, retirada de origem e observação. A implementação do fluxo ainda precisa acrescentar validações explícitas, escolhas controladas para o tipo de movimentação, atualização consistente da situação do equipamento, permissões, interface e testes.

### Critério de aceite do fluxo

Um Operador consegue registrar pela interface a retirada sem reserva de um equipamento ativo e disponível para qualquer usuário funcional ativo. A movimentação preserva equipamento, Operador, destinatário, tipo, data e hora, e o equipamento passa para `EM_USO`. Tentativas sem autorização ou com equipamento ou destinatário inválido não alteram os dados.

## Devolução

### Rastreabilidade

- **Requisitos funcionais:** RF-05 e RF-06.
- **Regras de negócio:** RN-04, RN-08, RN-10 e RN-14.
- **Perfil autorizado:** Operador.

### Decisão sobre o Operador

Qualquer Operador autorizado pode registrar a devolução. Não é necessário que seja o mesmo Operador que registrou a retirada, pois cada movimentação preserva separadamente quem realizou a respectiva operação.

Essa decisão permite a continuidade do atendimento entre turnos sem perder a rastreabilidade da retirada e da devolução.

### Pré-condições

1. O usuário que registra a devolução está autenticado e pertence ao grupo Operador.
2. Existe uma retirada em aberto para o equipamento.
3. A retirada ainda não possui uma devolução vinculada.

Uma retirada é considerada aberta enquanto não existir uma movimentação do tipo `DEVOLUCAO` que a referencie por meio de `retirada_origem`.

### Dados registrados

- equipamento devolvido;
- Operador que recebeu e registrou a devolução;
- destinatário da retirada original;
- tipo `DEVOLUCAO`;
- data e hora do registro;
- retirada de origem;
- observação, quando necessária.

### Fluxo principal sem necessidade de manutenção

1. O Operador seleciona uma retirada em aberto.
2. O sistema identifica o equipamento e o destinatário a partir da retirada original.
3. O sistema valida novamente a autorização e confirma que a retirada permanece aberta.
4. O sistema cria a movimentação de devolução vinculada à retirada.
5. O sistema altera a situação do equipamento para `DISPONIVEL`.
6. O sistema confirma a operação e preserva os dois registros no histórico.

### Fluxos impedidos

A devolução não é concluída quando:

- o usuário não pertence ao grupo Operador;
- não existe retirada em aberto correspondente;
- a retirada já possui uma devolução;
- a retirada e o equipamento informado não correspondem;
- alguma etapa da gravação falha.

Nesses casos, nenhuma movimentação parcial deve permanecer salva e a situação do equipamento não deve ser alterada.

### Correspondência com o modelo atual

O relacionamento `retirada_origem` do modelo `Movimentacao` permite vincular a devolução à retirada. O campo `operador` da nova movimentação registra quem recebeu a devolução, enquanto o registro original continua identificando quem realizou a retirada.

A implementação ainda deve garantir que uma retirada possua no máximo uma devolução, aplicar a autorização no servidor e salvar a devolução e a mudança de situação do equipamento como uma única operação consistente.

### Critério de aceite do fluxo

Qualquer Operador autorizado consegue registrar pela interface a devolução correspondente a uma retirada em aberto. O histórico identifica separadamente os Operadores da retirada e da devolução, a nova movimentação referencia a retirada original e, quando não há outro impedimento, o equipamento retorna para `DISPONIVEL`. Uma segunda devolução para a mesma retirada ou uma tentativa sem autorização não altera os dados.

### Fluxo alternativo com necessidade de manutenção

1. Durante a devolução, o Operador informa que o equipamento apresenta um problema.
2. O sistema exige a descrição do problema.
3. O sistema cria a movimentação de devolução vinculada à retirada.
4. O sistema cria automaticamente uma manutenção pendente relacionada ao equipamento e à devolução.
5. O sistema altera a situação do equipamento para `MANUTENCAO`.
6. O sistema confirma a devolução e informa que a manutenção aguarda o acompanhamento de um Administrador.

A movimentação de devolução, a abertura da manutenção e a mudança de situação do equipamento devem ser gravadas como uma única operação consistente. Se qualquer etapa falhar, nenhuma delas deve permanecer salva.

## Manutenção

### Rastreabilidade

- **Requisito funcional:** RF-07.
- **Regras de negócio:** RN-05 e RN-14.
- **Perfis envolvidos:** Operador na comunicação do problema durante a devolução e Administrador na abertura manual, no acompanhamento e na conclusão da intervenção.

### Decisão sobre a abertura

Uma manutenção pode ser aberta de duas formas:

1. **Abertura automática:** quando o Operador identifica um problema durante a devolução, descreve a ocorrência e o sistema cria a manutenção pendente vinculada à devolução.
2. **Abertura manual:** quando um defeito é descoberto fora de uma devolução, um Administrador seleciona um equipamento ativo e disponível, descreve o problema e cria a manutenção pendente sem vínculo com movimentação.

Nos dois casos, a abertura impede que o equipamento seja marcado como indisponível sem um registro que explique a origem da manutenção. O Administrador recebe a responsabilidade de acompanhar e encerrar a intervenção.

### Dados confirmados para a abertura

- equipamento;
- devolução que originou o encaminhamento, quando a abertura for automática;
- usuário que abriu ou originou a manutenção: Operador na devolução ou Administrador na abertura manual;
- descrição do problema;
- data e hora da abertura;
- estado inicial `PENDENTE`.

### Efeitos da abertura

- o equipamento permanece ativo, mas assume a situação `MANUTENCAO`;
- o equipamento não pode ser reservado nem retirado;
- a manutenção passa a integrar o histórico do equipamento;
- somente um Administrador pode acompanhar ou concluir a intervenção.

### Estados da manutenção

| Estado | Significado | Responsável pela transição |
|---|---|---|
| `PENDENTE` | O problema foi registrado e aguarda atendimento. | O sistema define este estado em qualquer forma de abertura. |
| `EM_ANDAMENTO` | Um Administrador iniciou o acompanhamento da intervenção. | Administrador. |
| `CONCLUIDA` | A intervenção foi encerrada por um Administrador. | Administrador. |

O estado da manutenção descreve o andamento da intervenção. Ele não substitui a situação do equipamento: enquanto a manutenção estiver `PENDENTE` ou `EM_ANDAMENTO`, o equipamento permanece com situação `MANUTENCAO`.

O histórico deve preservar as datas e os responsáveis pelas mudanças de estado. Uma manutenção concluída continua armazenada e não pode ser excluída como forma de reabrir o equipamento.

### Resultados do encerramento

Ao concluir a manutenção, o Administrador seleciona um dos seguintes resultados:

| Resultado | Efeito na manutenção | Efeito no equipamento |
|---|---|---|
| `REPARADO` | Assume o estado `CONCLUIDA`. | Permanece ativo e retorna para `DISPONIVEL`. |
| `SEM_REPARO` | Assume o estado `CONCLUIDA`. | É inativado e permanece indisponível, com todo o histórico preservado. |

A inativação usa o campo `ativo` já existente em `Equipamento` e segue a RN-06. Não é necessário acrescentar um novo valor à situação do equipamento somente para representar a impossibilidade de reparo.

### Fluxo de encerramento

1. Um Administrador seleciona uma manutenção em andamento.
2. O sistema valida que a intervenção ainda não foi concluída.
3. O Administrador informa se o equipamento foi reparado ou ficou sem possibilidade de reparo e descreve obrigatoriamente a solução ou a conclusão da análise.
4. O sistema altera a manutenção para `CONCLUIDA` e registra a data, a hora e o Administrador responsável.
5. Se o resultado for `REPARADO`, o sistema altera o equipamento para `DISPONIVEL`.
6. Se o resultado for `SEM_REPARO`, o sistema inativa o equipamento sem excluir seus registros.

A conclusão da manutenção e a atualização do equipamento devem ser gravadas como uma única operação consistente.

### Dados confirmados para o encerramento

- resultado `REPARADO` ou `SEM_REPARO`;
- descrição obrigatória da solução aplicada ou da conclusão que justificou a ausência de reparo;
- Administrador responsável;
- data e hora da conclusão.

A manutenção não pode assumir o estado `CONCLUIDA` sem resultado e descrição. Uma tentativa inválida não deve alterar a manutenção nem o equipamento.

### Fluxos impedidos

A abertura automática não é concluída quando:

- não existe devolução válida que a origine;
- a descrição do problema não foi informada;
- o usuário que registra a devolução não pertence ao grupo Operador;
- o equipamento já possui uma manutenção ainda não concluída;
- alguma etapa da gravação falha.

A abertura manual não é concluída quando:

- o usuário não pertence ao grupo Administrador;
- o equipamento está inativo;
- o equipamento não está `DISPONIVEL`;
- a descrição do problema não foi informada;
- o equipamento já possui uma manutenção ainda não concluída;
- alguma etapa da gravação falha.

### Critério de aceite da abertura

Ao registrar uma devolução com problema, um Operador informa obrigatoriamente a descrição da ocorrência. O sistema preserva a devolução, cria uma manutenção pendente vinculada ao equipamento e à devolução e mantém o equipamento em `MANUTENCAO`. Fora desse fluxo, um Administrador consegue abrir manualmente uma manutenção pendente para um equipamento ativo e disponível, sem vínculo com devolução. Se qualquer abertura falhar, nenhuma alteração parcial permanece salva.

### Critério de aceite do ciclo

Uma manutenção é criada em `PENDENTE`; um Administrador consegue iniciá-la, alterando-a para `EM_ANDAMENTO`, e concluí-la como `CONCLUIDA` somente após informar o resultado e a descrição da solução ou conclusão. Usuários de outros perfis não conseguem alterar esses estados. O equipamento permanece indisponível enquanto a manutenção não estiver concluída. Depois do encerramento, um item reparado volta a ficar disponível e um item sem reparo é inativado, sempre com preservação do histórico da intervenção.

## Painel administrativo

### Rastreabilidade

- **Requisito funcional:** RF-08.
- **Perfil autorizado:** Administrador.
- **Fontes dos dados:** equipamentos e movimentações persistidos no SIGEE.

Os indicadores pedagógicos por turma, disciplina e atividade pertencem ao RF-11 e não fazem parte deste painel inicial.

### Indicadores numéricos

| Indicador | Regra de cálculo |
|---|---|
| Equipamentos ativos | Quantidade de equipamentos com `ativo=True`. |
| Disponíveis | Equipamentos ativos com situação `DISPONIVEL`. |
| Em uso | Equipamentos ativos com situação `EM_USO`. |
| Em manutenção | Equipamentos ativos com situação `MANUTENCAO`. |
| Inativos | Quantidade de equipamentos com `ativo=False`, independentemente da última situação registrada. |

Os totais são calculados diretamente a partir dos registros atuais. O painel não mantém cópias dos valores em outra entidade, evitando divergência entre o resumo e o inventário.

### Movimentações recentes

O painel apresenta as dez movimentações mais recentes, ordenadas da mais nova para a mais antiga. Cada item exibe:

- equipamento;
- tipo da movimentação;
- data e hora;
- Operador responsável pelo registro;
- destinatário.

Retiradas e devoluções participam da mesma lista. A ausência de dez registros não é erro: o painel exibe somente as movimentações existentes.

### Representação gráfica

O gráfico apresenta a distribuição dos equipamentos ativos entre `DISPONIVEL`, `EM_USO` e `MANUTENCAO`. Os valores do gráfico usam as mesmas consultas dos indicadores numéricos e devem coincidir com os cartões apresentados na mesma página.

Os equipamentos inativos são exibidos em indicador separado e não compõem a distribuição por situação dos itens ativos.

### Autorização

Somente usuários do grupo Administrador com a permissão correspondente podem abrir o painel. A restrição deve ser aplicada no servidor; ocultar o item de navegação para outros perfis não substitui a verificação de autorização na rota.

### Estado atual da implementação

A listagem do inventário já calcula total, disponíveis, em uso e em manutenção para usuários com a permissão `view_resumo_inventario`. Esse comportamento pode ser reaproveitado, mas o painel dedicado, o total de inativos, a lista de movimentações recentes e o gráfico ainda permanecem planejados.

### Critério de aceite

Um Administrador acessa o painel e visualiza os cinco indicadores confirmados, as dez movimentações mais recentes e um gráfico coerente com os equipamentos ativos por situação. Usuários sem autorização recebem resposta `403`, e todos os números apresentados correspondem aos registros persistidos no momento da consulta.
