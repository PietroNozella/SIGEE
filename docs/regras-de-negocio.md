# Regras de negócio

Este documento registra as 18 regras de negócio confirmadas para o SIGEE. Elas representam o comportamento esperado do sistema e devem ser vinculadas à implementação, aos testes e às evidências conforme o desenvolvimento avançar.

- **RN-01 — Unicidade do número de patrimônio:** cada número de patrimônio identifica um único equipamento.
- **RN-02 — Disponibilidade para reserva e retirada:** somente equipamento disponível pode ser reservado ou retirado.
- **RN-03 — Prevenção de conflito de reservas:** reservas conflitantes para o mesmo período são impedidas.
- **RN-04 — Registro e atualização de movimentações:** retirada e devolução registram a movimentação e atualizam a situação do equipamento.
- **RN-05 — Indisponibilidade durante manutenção:** equipamento em manutenção permanece indisponível até a conclusão da intervenção.
- **RN-06 — Inativação com preservação do histórico:** equipamento com registros relacionados é inativado em vez de excluído definitivamente.
- **RN-07 — Reserva exclusiva por professores:** somente usuários com perfil Professor podem reservar equipamentos.
- **RN-08 — Retirada e devolução por operador:** somente usuários com perfil autorizado de Operador podem registrar retirada e devolução física.
- **RN-09 — Retirada com ou sem reserva prévia:** equipamento disponível pode ser retirado sem reserva, desde que a movimentação seja registrada com as informações necessárias à rastreabilidade.
- **RN-10 — Devolução vinculada à retirada:** a devolução exige uma retirada em aberto correspondente; depois dela, o equipamento retorna à situação disponível, salvo outro impedimento registrado.
- **RN-11 — Reserva vencida:** quando o período da reserva é ultrapassado sem retirada registrada, a reserva deixa de bloquear a disponibilidade conforme a política de tolerância definida pelo sistema.
- **RN-12 — Cancelamento de reserva:** o Professor pode cancelar uma reserva própria enquanto a retirada não tiver sido registrada.
- **RN-13 — Identificação dos responsáveis:** toda retirada registra o usuário que realizou a operação, o destinatário, a data e a hora.
- **RN-14 — Devolução com necessidade de manutenção:** problema identificado na devolução pode encaminhar o equipamento diretamente para manutenção, mantendo-o indisponível.
- **RN-15 — Registro do contexto pedagógico:** utilização com finalidade pedagógica pode ser associada a turma, disciplina e atividade pedagógica.
- **RN-16 — Vinculação pedagógica com ou sem reserva:** a associação pedagógica pode ser registrada em utilizações originadas de reserva ou de retirada sem reserva, preservando a movimentação.
- **RN-17 — Indicadores baseados em registros pedagógicos:** indicadores pedagógicos são calculados somente a partir de registros efetivamente vinculados a turma, disciplina e atividade pedagógica.
- **RN-18 — Cadastro controlado de usuários:** o SIGEE não permite cadastro público; novas contas de Administrador, Operador e Professor são criadas por um Administrador. O primeiro Administrador é configurado por meio de uma conta técnica de Django Superuser.

## Implicações da RN-18

- A tela pública de autenticação apresenta somente o login, sem seleção manual de perfil e sem opção de criar conta.
- O Django Superuser é uma conta técnica e não representa o perfil funcional Administrador do SIGEE.
- O perfil é atribuído por um Administrador e não pode ser escolhido livremente pelo usuário.
- O sistema pode possuir mais de um Administrador funcional sem conceder privilégios de superuser.

## Pendência de detalhamento

A duração da tolerância mencionada na `RN-11` ainda precisa ser definida antes da implementação dessa regra. Nenhum valor foi presumido neste documento.
