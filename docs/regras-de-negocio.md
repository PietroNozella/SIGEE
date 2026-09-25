# Regras de negócio

Este documento registra as 19 regras de negócio confirmadas para o SIGEE. Elas representam o comportamento esperado do sistema e devem ser vinculadas à implementação, aos testes e às evidências conforme o desenvolvimento avançar.

- **RN-01 — Unicidade do número de patrimônio:** cada número de patrimônio identifica um único equipamento.
- **RN-02 — Disponibilidade para reserva e retirada:** somente equipamento físico ativo e disponível pode ser reservado ou retirado. A consulta da reserva é feita pelo tipo/modelo e pelo local de retirada, e a alocação considera somente unidades físicas desse mesmo tipo e local.
- **RN-03 — Prevenção de conflito de reservas:** reservas conflitantes para o mesmo período são impedidas por unidade física alocada; períodos apenas adjacentes não conflitam.
- **RN-04 — Registro e atualização de movimentações:** retirada e devolução registram a movimentação e atualizam a situação do equipamento.
- **RN-05 — Indisponibilidade durante manutenção:** uma manutenção pode ser aberta automaticamente durante uma devolução com problema ou manualmente por um Administrador para um equipamento ativo e disponível. Toda manutenção passa pelos estados `PENDENTE`, `EM_ANDAMENTO` e `CONCLUIDA`. Enquanto a intervenção estiver pendente ou em andamento, o equipamento permanece em `MANUTENCAO` e indisponível para reserva ou retirada. Ao concluir a intervenção, o Administrador registra obrigatoriamente a descrição da solução ou conclusão e classifica o equipamento como reparado, devolvendo-o à situação `DISPONIVEL`, ou como sem possibilidade de reparo, inativando-o com preservação do histórico.
- **RN-06 — Inativação com preservação do histórico:** equipamento com registros relacionados é inativado em vez de excluído definitivamente.
- **RN-07 — Reserva exclusiva e própria por professores:** somente usuários com perfil Professor podem reservar equipamentos, e cada reserva em lote é vinculada ao próprio Professor autenticado que a criou.
- **RN-08 — Retirada e devolução por operador:** somente usuários com perfil autorizado de Operador podem registrar retirada e devolução física.
- **RN-09 — Retirada com ou sem reserva prévia:** equipamento disponível pode ser retirado sem reserva, desde que a movimentação seja registrada com as informações necessárias à rastreabilidade.
- **RN-10 — Devolução vinculada à retirada:** a devolução exige uma retirada em aberto correspondente e pode ser registrada por qualquer Operador autorizado, mesmo que outro Operador tenha registrado a retirada. Depois da devolução, o equipamento retorna à situação disponível, salvo outro impedimento registrado.
- **RN-11 — Reserva vencida:** quando são decorridos 30 minutos do horário inicial sem retirada registrada, a reserva ativa expira integralmente (todo o lote) e deixa de bloquear a disponibilidade. A expiração não se aplica a reservas canceladas e é impedida quando existe movimentação de retirada vinculada à reserva.
- **RN-12 — Cancelamento de reserva:** o Professor pode cancelar uma reserva própria enquanto a retirada não tiver sido registrada.
- **RN-13 — Identificação dos responsáveis:** toda retirada registra o usuário que realizou a operação, o destinatário, a data e a hora. O destinatário pode ser qualquer usuário funcional ativo do SIGEE, independentemente de pertencer ao grupo Administrador, Operador ou Professor.
- **RN-14 — Devolução com necessidade de manutenção:** quando um problema é identificado na devolução, o Operador descreve a ocorrência e encaminha o equipamento para manutenção. O sistema cria automaticamente uma manutenção pendente e mantém o equipamento indisponível para uso e reserva. O acompanhamento e a conclusão da intervenção são responsabilidade de um Administrador.
- **RN-15 — Registro do contexto pedagógico:** utilização com finalidade pedagógica pode ser associada a turma, disciplina e atividade pedagógica.
- **RN-16 — Vinculação pedagógica com ou sem reserva:** a associação pedagógica pode ser registrada em utilizações originadas de reserva ou de retirada sem reserva, preservando a movimentação.
- **RN-17 — Indicadores baseados em registros pedagógicos:** indicadores pedagógicos são calculados somente a partir de registros efetivamente vinculados a turma, disciplina e atividade pedagógica.
- **RN-18 — Cadastro controlado de usuários:** o SIGEE não permite cadastro público; novas contas de Administrador, Operador e Professor são criadas por um Administrador. O primeiro Administrador é configurado por meio de uma conta técnica de Django Superuser.
- **RN-19 — Validade temporal e dias permitidos da reserva:** a data e a hora inicial da reserva não podem estar no passado. A data atual é permitida quando o horário inicial ainda não tiver passado. Reservas cujo período inclua sábado ou domingo são impedidas. Antes da efetivação da reserva, a coincidência com feriado nacional consultado pela BrasilAPI é informada no diálogo de confirmação e não impede a reserva.

## Decisão de modelagem da reserva em lote

`Categoria` representa uma classificação ampla, como Notebook ou Projetor. `TipoEquipamento` identifica o tipo/modelo selecionável, como “Notebook Dell Latitude 5420”, `Local` identifica o ponto de retirada escolhido e `Equipamento` continua representando cada unidade física com patrimônio próprio. Uma solicitação do Professor grava uma única `Reserva` com tipo/modelo, local e quantidade, e cria os vínculos `ReservaEquipamento` somente para unidades compatíveis com esse tipo e local. Essa separação evita que o Professor tenha de repetir a operação para cada patrimônio, impede lotes distribuídos entre locais diferentes e mantém o histórico físico auditável.

## Implicações da RN-18

- A tela pública de autenticação apresenta somente o login, sem seleção manual de perfil e sem opção de criar conta.
- O Django Superuser é uma conta técnica e não representa o perfil funcional Administrador do SIGEE.
- O perfil é atribuído por um Administrador e não pode ser escolhido livremente pelo usuário.
- O sistema pode possuir mais de um Administrador funcional sem conceder privilégios de superuser.
- Cada conta funcional pertence a exatamente um grupo: Administrador, Operador ou Professor.

As ações permitidas para cada grupo estão consolidadas na [Matriz de acesso](matriz-de-acesso.md).
