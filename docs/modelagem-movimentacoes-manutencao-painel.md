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

1. O Operador seleciona o tipo/modelo e o local de retirada. Quando existir apenas um local para aquele tipo, o sistema o preenche automaticamente.
2. O sistema consulta as unidades físicas ativas e disponíveis e mostra a quantidade e os números de patrimônio.
3. O Operador informa a quantidade. O sistema sugere essa quantidade de unidades, ordenadas por patrimônio, e permite trocar unidades pela lista de seleção.
4. O Operador informa um destinatário e uma observação opcional para toda a entrega e confere o resumo com os patrimônios selecionados.
5. O servidor exige quantidade positiva, patrimônios distintos e exatamente a quantidade informada, todos do mesmo tipo/modelo e local.
6. O servidor revalida a autorização, o destinatário e os patrimônios conferidos sob bloqueio. Não substitui silenciosamente uma unidade que ficou indisponível.
7. Em uma única transação, cria uma movimentação de retirada e seu evento de auditoria para cada equipamento e altera todas as unidades para `EM_USO`.
8. O sistema confirma a quantidade entregue. Se qualquer unidade ou gravação falhar, nenhuma retirada ou atualização parcial permanece salva.

### Fluxos impedidos

A retirada não é concluída quando:

- o usuário não pertence ao grupo Operador;
- o equipamento está inativo;
- o equipamento não está disponível;
- o destinatário está inativo ou não possui perfil funcional válido;
- alguma etapa da gravação falha.

Nesses casos, nenhuma movimentação parcial deve permanecer salva e a situação do equipamento não deve ser alterada.

### Correspondência com o modelo atual

O modelo `Movimentacao` preserva referências para equipamento, Operador e destinatário, tipos controlados de retirada e devolução, data e hora, retirada de origem, observação e uma referência opcional para a reserva de origem. O RF-05 implementa a retirada sem reserva em lote em `/movimentacoes/retirada/`, com formulário, autorização no servidor e testes em `movimentacoes/tests.py`.

O serviço `registrar_retirada_sem_reserva` reconsulta a autorização do Operador e o destinatário funcional ativo, bloqueia os patrimônios selecionados com `select_for_update()`, em ordem de chave primária, e revalida tipo/modelo, local, `ativo` e `DISPONIVEL`. Todas as movimentações `RETIRADA`, alterações para `EM_USO` e eventos de auditoria `RETIRADA_REGISTRADA` são gravados na mesma transação. O modelo continua representando uma unidade física por movimentação; uma confirmação de 30 equipamentos gera 30 movimentações com o mesmo `lote_retirada`, identificado por UUID gerado no servidor. Isso permite reconhecer a entrega original e devolver todas ou somente parte das unidades. Operador e data/hora vêm do servidor; `reserva` e `retirada_origem` permanecem vazios. Superusers técnicos não são selecionáveis, mesmo quando possuem grupo funcional.

O Django Admin permite somente consultar movimentações, sem inclusão, edição ou exclusão direta. Essa restrição impede contornar a autorização funcional e a gravação consistente da retirada.

**Limite de disponibilidade deste incremento:** os critérios documentados para retirada sem reserva são equipamento ativo e situação `DISPONIVEL`. Não há decisão sobre como uma retirada sem previsão de devolução interage com reservas ativas ou futuras. Este fluxo não consulta nem altera reservas e não acrescenta bloqueios por período, tipo/modelo ou local inativo. Essa interação precisa ser definida ao integrar os fluxos futuros.

**Validação de concorrência:** o teste com duas conexões simultâneas exige um banco com suporte a `select_for_update`, como PostgreSQL. Ele é ignorado no SQLite, que não oferece esse bloqueio por linha. Os testes em SQLite verificam revalidação de estado, segunda retirada, autorização, entradas inválidas e rollback, mas não comprovam a serialização concorrente em PostgreSQL.

### Critério de aceite do fluxo

Um Operador consegue selecionar tipo/modelo, local e quantidade, conferir ou trocar os patrimônios sugeridos e registrar a retirada sem reserva do lote para um único usuário funcional ativo. Cada movimentação preserva equipamento, Operador, destinatário, tipo, data e hora; todos os equipamentos passam para `EM_USO`. Quantidade inválida, seleção duplicada, tipo/local divergente, indisponibilidade ou falha em qualquer parte do lote impedem alterações parciais. A interface mantém consulta e seleção por formulário também sem JavaScript.

## Retirada vinculada à reserva

O Operador localiza a reserva em `/movimentacoes/retirada/reservas/` e confere os patrimônios em `/movimentacoes/retirada/reservas/<reserva_id>/`. A entrega é integral, usa as unidades já alocadas e tem como destinatário o Professor proprietário, ativo e com perfil funcional válido. Esses vínculos, o Operador e a data/hora são obtidos no servidor.

O serviço `registrar_retirada_reserva` bloqueia a mesma `Reserva` usada pelo cancelamento e pela expiração, revalida seu estado e impede retirada duplicada. A retirada exige reserva ativa e unidades ativas, disponíveis e compatíveis com o tipo/local. Só é permitida a partir do início e antes de completar os 30 minutos de tolerância; ao atingir o limite, a reserva expira com auditoria, sem retirar equipamentos.

Uma transação grava as retiradas, a atualização para `EM_USO` e a auditoria de cada unidade. O lote preserva a reserva e continua compatível com devolução individual, total ou parcial. Os testes estão em `movimentacoes/test_retirada_reserva.py`; concorrência exige validação em PostgreSQL.

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
5. O sistema altera a situação do equipamento para `DISPONIVEL` quando não existe outro impedimento documentado.
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

A devolução básica está implementada em `/movimentacoes/devolucao/`: a lista pagina grupos com unidades pendentes, por reserva quando vinculada ou pelo identificador da retirada em lote. A busca por patrimônio, tipo/modelo ou destinatário localiza o grupo inteiro; não reduz o lote às unidades encontradas pelo filtro. O resumo informa total, devolvidas e pendentes. Em `/movimentacoes/devolucao/<retirada_id>/`, o Operador confere todos os patrimônios, inicialmente com as unidades abertas marcadas, e desmarca as que não foram recebidas. Pode devolver todas, parte ou uma única unidade. A observação opcional vale para a confirmação inteira. A interface com JavaScript mostra um resumo final com quantidade e patrimônios; sem JavaScript, a seleção e a gravação continuam funcionando pelo formulário.

**Registros anteriores:** a migration `0004` acrescenta `lote_retirada` opcional, sem atribuir retroativamente um UUID aos registros antigos. Proximidade de horário, mesmo tipo ou mesmo destinatário não comprovam que duas movimentações pertencem à mesma entrega. Retiradas antigas sem reserva e sem lote aparecem como “Pendências anteriores” por destinatário, com aviso explícito e data individual de cada unidade. Elas não se misturam aos novos lotes ou às reservas. Ao existir reserva vinculada, ela identifica o grupo.

O serviço `registrar_devolucoes` reconsulta a autorização funcional, exige seleção não vazia e sem duplicatas, bloqueia as retiradas selecionadas e a referência do grupo em ordem de chave primária, verifica que pertencem ao grupo e que continuam abertas, e bloqueia os equipamentos também em ordem estável. Cada devolução obtém equipamento, destinatário, reserva e identificador de lote exclusivamente de sua retirada original; campos extras enviados pelo navegador não os substituem. Operador e data/hora vêm do servidor. O registro original e a reserva não são alterados. A inativação posterior do destinatário não impede receber o equipamento nem apaga sua identidade original. `registrar_devolucao` reutiliza esse serviço para receber apenas uma unidade.

Todas as devoluções selecionadas, alterações dos equipamentos e eventos `DEVOLUCAO_REGISTRADA` de sucesso são gravados na mesma transação. Falhas, seleção de outro lote ou unidade já devolvida impedem a confirmação inteira, sem devolver parcialmente as demais unidades selecionadas. Unidades desmarcadas permanecem pendentes e não são alteradas. A view pode registrar separadamente uma tentativa com resultado `FALHA`, sem manter alterações de negócio. A migration `0003` acrescenta unicidade condicional de `retirada_origem` para `DEVOLUCAO` e uma restrição que exige a origem em toda devolução; a unicidade protege o banco mesmo fora do serviço. O serviço exige que a origem seja uma `RETIRADA`.

**Impedimentos preservados:** a devolução não reativa equipamento inativo (RN-06) e não libera equipamento já em `MANUTENCAO` (RN-05). Nesses casos, registra o recebimento e mantém a situação existente. Para um equipamento ativo sem manutenção, retorna a `DISPONIVEL` (RN-10). Não são acrescentados bloqueios por reservas futuras nem alterações de estado da reserva; a interação entre retirada sem previsão de devolução e reservas continua sendo uma lacuna para a integração futura.

**Validação:** `movimentacoes/test_devolucao.py` cobre sucesso, outro Operador, acesso direto negado, identidade e reserva originais, adulteração, duplicidade, devolução individual do lote, impedimentos existentes e rollback, além das restrições do banco. `movimentacoes/test_devolucao_lote.py` cobre 30 unidades em uma confirmação, recebimento parcial, lotes distintos do mesmo destinatário, busca que preserva o grupo, registros antigos, reserva, seleção inválida e rollback após gravar parte do lote. Os testes concorrentes de movimentações usam conexões independentes e exigem `select_for_update`; são ignorados no SQLite. As verificações locais nesse banco não comprovam concorrência em PostgreSQL nem funcionamento no ambiente publicado.

### Critério de aceite do fluxo

Qualquer Operador autorizado consegue registrar pela interface a devolução correspondente a uma retirada em aberto. O histórico identifica separadamente os Operadores da retirada e da devolução, a nova movimentação referencia a retirada original e, quando não há outro impedimento, o equipamento retorna para `DISPONIVEL`. Uma segunda devolução para a mesma retirada ou uma tentativa sem autorização não altera os dados.

### Fluxo alternativo com necessidade de manutenção

**Pendente neste incremento:** o encaminhamento automático previsto na RN-14 ainda não foi implementado. O formulário atual atende somente à devolução básica, sem abertura de manutenção. Painel e indicadores pedagógicos também permanecem pendentes.

1. Durante a devolução, o Operador informa que o equipamento apresenta um problema.
2. O sistema exige a descrição do problema.
3. O sistema cria a movimentação de devolução vinculada à retirada.
4. O sistema cria automaticamente uma manutenção pendente relacionada ao equipamento e à devolução.
5. O sistema altera a situação do equipamento para `MANUTENCAO`.
6. O sistema confirma a devolução e informa que a manutenção aguarda o acompanhamento de um Administrador.

A movimentação de devolução, a abertura da manutenção e a mudança de situação do equipamento devem ser gravadas como uma única operação consistente. Se qualquer etapa falhar, nenhuma delas deve permanecer salva.

## Consulta do histórico e navegação do Operador

O histórico está implementado em `/movimentacoes/historico/` para Administrador e Operador autorizados. Inclui retiradas com ou sem reserva e devoluções, inclusive encerradas, com patrimônio, equipamento, data/hora, Operador, destinatário e vínculos de origem. Oferece filtros por texto, tipo, período e reserva, paginação de 25 registros e ordenação do mais recente ao mais antigo, sem edição ou exclusão. Os testes estão em `movimentacoes/test_historico.py`.

A sidebar do Operador contém Equipamentos, Reservas, Em uso e Histórico. Em Reservas, Registrar retirada abre a entrega sem reserva. Em uso apresenta lotes pendentes e permite conferir a devolução total ou parcial; não substitui o histórico. Após confirmar uma retirada, o sistema abre Em uso.

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
