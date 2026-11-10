# Requisitos Funcionais

Os requisitos funcionais descrevem as operações definidas para o SIGEE. Para cada requisito, são apresentados os atores envolvidos, as condições de execução, o fluxo principal, as regras relacionadas e os critérios utilizados para verificar seu atendimento.

## RF01 - Autenticar usuários, recuperar o acesso e aplicar autorização por perfil

<b>Descrição:</b> O sistema deve permitir que usuários cadastrados acessem suas funcionalidades por meio de nome de usuário e senha. Também deve oferecer recuperação de senha pelo endereço de e-mail cadastrado e restringir as operações conforme o perfil funcional do usuário.

<b>Atores:</b> Administrador, Operador e Professor.

<b>Pré-condições:</b> O usuário deve possuir uma conta cadastrada e ativa. Para executar operações funcionais, sua conta deve estar vinculada a um dos perfis autorizados.

<b>Fluxo principal:</b> O usuário informa suas credenciais na página de acesso. O sistema valida os dados e inicia a sessão. Ao solicitar uma operação, o sistema verifica se o perfil do usuário possui a permissão correspondente. Caso esqueça a senha, o usuário solicita sua redefinição pelo e-mail cadastrado e utiliza o vínculo recebido para cadastrar uma nova senha.

<b>Regras de negócio:</b> O cadastro de contas é realizado por um Administrador, sem opção de cadastro público (RN-18). Cada conta funcional pertence exclusivamente a Administrador, Operador ou Professor. Novos administradores são comuns; somente o Administrador principal desativa ou reativa outros administradores comuns. A conta principal não pode ser desativada pelo fluxo funcional nem anonimizada enquanto exerce essa função (RN-18).

<b>Pós-condições:</b> Após a autenticação, o usuário acessa somente as funcionalidades permitidas ao seu perfil. Após a recuperação, a nova senha passa a ser utilizada no acesso.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dado um usuário ativo com credenciais válidas, quando ele realizar o acesso, então o sistema deve iniciar sua sessão.
- <b>CA-02:</b> Dadas credenciais inválidas ou uma conta inativa, quando houver uma tentativa de acesso, então o sistema deve recusá-la.
- <b>CA-03: </b>Dado um usuário autenticado, quando ele tentar executar uma operação não permitida ao seu perfil, então o sistema deve impedir a operação.
- <b>CA-04:</b> Dado um e-mail cadastrado, quando o usuário concluir o procedimento de recuperação de senha, então deve conseguir acessar o sistema com a nova senha.
- <b>CA-05:</b> Dado um Administrador comum, quando ele tentar desativar ou reativar outro Administrador, então o sistema deve impedir a operação; o Administrador principal deve conseguir alterar a situação de administradores comuns, preservadas as demais restrições de gestão de contas.

## RF02 - Cadastrar e gerenciar equipamentos do inventário

<b>Descrição:</b> O sistema deve permitir ao Administrador cadastrar equipamentos individualmente ou por importação de arquivo CSV, além de alterar seus dados e excluir ou inativar registros conforme a existência de histórico relacionado. Cada unidade física deve possuir número de patrimônio único, tipo/modelo, categoria, local e situação.

<b>Ator: </b>Administrador.

<b>Pré-condições:</b> O Administrador deve estar autenticado e autorizado. As categorias e os locais utilizados no cadastro devem estar disponíveis para seleção. O tipo/modelo é informado pelo nome; o sistema cria ou reutiliza o registro correspondente à categoria e ao nome informados.

<b>Fluxo principal:</b> O Administrador escolhe o cadastro individual ou a importação por CSV, informa os dados dos equipamentos e confirma a operação. O sistema valida os campos e os números de patrimônio antes de gravar os registros. Posteriormente, o Administrador pode alterar os dados de um equipamento. Ao solicitar sua remoção, o sistema verifica se existem registros relacionados para decidir entre exclusão e inativação.

<b>Regras de negócio:</b> Cada número de patrimônio identifica um único equipamento (RN-01). Equipamentos com registros relacionados devem ser inativados, preservando seu histórico (RN-06). Na importação por CSV, o lote somente deve ser gravado se todas as linhas forem válidas.

<b>Pós-condições:</b> Os equipamentos válidos são registrados ou atualizados. Uma importação inválida não grava parte do lote. Na remoção, o equipamento é excluído ou inativado de acordo com a existência de histórico.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dados os campos válidos de um equipamento, quando o Administrador confirmar o cadastro, então a unidade deve constar no inventário.
- <b>CA-02:</b> Dado um número de patrimônio já cadastrado, quando houver uma nova tentativa de cadastro com esse número, então o sistema deve recusá-la.
- <b>CA-03:</b> Dado um arquivo CSV com ao menos uma linha inválida, quando o Administrador solicitar a importação, então nenhum equipamento do lote deve ser gravado.
- <b>CA-04:</b> Dado um equipamento com registros relacionados, quando o Administrador solicitar sua remoção, então o sistema deve inativá-lo e preservar o histórico.
- <b>CA-05:</b> Dado um usuário sem permissão de gerenciamento do inventário, quando ele tentar realizar essas operações, então o sistema deve impedi-las.

## RF03 - Consultar e filtrar equipamentos

<b>Descrição:</b> O sistema deve permitir a consulta dos equipamentos cadastrados e a aplicação de filtros por texto, categoria, local e situação.

<b>Atores:</b> Administrador, Operador e Professor.

<b>Pré-condições:</b> O usuário deve estar autenticado e possuir permissão para consultar o inventário.

<b>Fluxo principal:</b> O usuário acessa a consulta do inventário, informa um ou mais filtros e solicita a pesquisa. O sistema apresenta os equipamentos correspondentes aos critérios informados.

<b>Regras de negócio:</b> A consulta deve respeitar as permissões do perfil do usuário. A situação apresentada para cada equipamento deve corresponder ao registro do inventário.

<b>Pós-condições:</b> O usuário visualiza os equipamentos que atendem aos filtros aplicados.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dado um equipamento cadastrado, quando o usuário aplicar um filtro correspondente aos seus dados, então o equipamento deve aparecer no resultado.
- <b>CA-02:</b> Dados dois ou mais filtros, quando o usuário realizar a consulta, então o resultado deve atender aos critérios informados em conjunto.
- <b>CA-03:</b> Dado um usuário sem permissão de consulta, quando ele tentar acessar o inventário, então o sistema deve impedir o acesso.

## RF04 - Reservar equipamentos

<b>Descrição:</b> O sistema deve permitir ao Professor reservar uma quantidade de equipamentos de um mesmo tipo/modelo e local para um período definido, com turma, disciplina e atividade pedagógica obrigatórias e observação opcional. O sistema deve verificar a disponibilidade e alocar as unidades físicas que compõem a reserva.

<b>Ator: </b>Professor.

<b>Pré-condições:</b> O Professor deve estar autenticado, ativo e autorizado. O tipo/modelo e o local devem estar ativos e possuir equipamentos disponíveis para o período solicitado. Turma, disciplina e atividade devem estar ativas para uma nova associação.

<b>Fluxo principal:</b> O Professor seleciona o tipo/modelo, o local de retirada, a data, os horários e a quantidade desejada. No mesmo preenchimento, o Professor informa a turma, a disciplina e a atividade pedagógica previstas para a utilização dos equipamentos. Essas informações ficam vinculadas à reserva e são preservadas no registro da utilização correspondente. O sistema consulta as unidades disponíveis, verifica conflitos com outras reservas e valida o período. Havendo unidades suficientes, registra uma única reserva vinculada ao Professor autenticado e associa a ela os equipamentos físicos alocados.

<b>Regras de negócio:</b> Somente equipamentos ativos e disponíveis do tipo/modelo e local selecionados podem ser alocados (RN-02). Reservas com períodos sobrepostos não podem utilizar a mesma unidade física; a margem acordada após o uso deve ser respeitada, inclusive na substituição por manutenção (RN-03). A reserva pertence ao Professor que a criou (RN-07). Uma reserva ativa sem retirada vence ao completar 30 minutos do horário inicial; os fluxos que sincronizam expiração persistem a mudança e liberam a disponibilidade (RN-11). O Professor pode cancelar sua reserva ativa, sem retirada e antes do limite de tolerância (RN-12). O planejamento pedagógico é obrigatório na nova reserva e cria utilizações por unidade somente na entrega (RN-15). O início não pode estar no passado; a antecedência máxima e o calendário de uso e atendimento configurado pelo Administrador devem ser respeitados (RN-19). A quantidade também respeita a cota opcional por professor e tipo, somando compromissos simultâneos em todos os locais (RN-20).

<b>Pós-condições:</b> A reserva válida é registrada com a quantidade solicitada e com as unidades físicas correspondentes. Solicitações inválidas não geram reserva.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dadas unidades suficientes do mesmo tipo/modelo e local, quando o Professor solicitar um período válido, então o sistema deve registrar uma única reserva com a quantidade e as unidades correspondentes.
- <b>CA-02:</b> Dada uma quantidade superior à disponibilidade do período, quando o Professor tentar confirmar a reserva, então o sistema deve recusá-la.
- <b>CA-03:</b> Dada uma unidade já alocada em reserva com período sobreposto, quando houver nova solicitação para o mesmo período, então essa unidade não deve ser alocada novamente.
- <b>CA-04: </b>Dado um horário inicial no passado, uma data inicial além de 15 dias corridos após a data local atual ou um período fora do calendário escolar, quando o Professor tentar reservar, então o sistema deve impedir o registro, inclusive por envio direto de dados.
- <b>CA-05:</b> Dada uma reserva própria ativa, sem retirada e antes de completar os 30 minutos de tolerância, quando o Professor solicitar seu cancelamento, então o sistema deve cancelá-la. Após o limite, a reserva deve expirar, sem receber cancelamento.
- <b>CA-06:</b> Dada uma reserva ativa sem retirada e com 30 minutos ou mais decorridos do horário inicial, quando um fluxo sincronizar as reservas vencidas, então a reserva deve expirar integralmente e deixar de bloquear a disponibilidade.
- <b>CA-07:</b> Dada uma reserva com contexto pedagógico completo, quando o Operador confirmar a entrega, então o sistema deve criar uma utilização por unidade retirada com turma, disciplina e atividade vinculadas à reserva.
- <b>CA-08:</b> Dada uma nova reserva sem turma, disciplina ou atividade pedagógica, quando o Professor tentar confirmar o agendamento, então o sistema deve recusar o registro sem alocar parcialmente os equipamentos.
- <b>CA-09:</b> Dada uma reserva ativa, no prazo e sem retirada, quando um Operador com permissão específica informar o motivo e confirmar a desistência comunicada pelo Professor, então toda a reserva deve ser cancelada, liberando somente seu compromisso de disponibilidade e preservando patrimônios, responsável, motivo, data e auditoria.
- <b>CA-10:</b> Dada uma entrega registrada após a abertura da tela de cancelamento operacional, quando o Operador confirmar o cancelamento, então o servidor deve recusá-lo sem alterar a entrega. No limite dos 30 minutos sem retirada, deve persistir somente a expiração.
- <b>CA-11:</b> Dado um cancelamento operacional concluído, quando um usuário autorizado consultar o detalhe da reserva, então deve visualizar motivo, responsável e data. Reenvios não devem sobrescrever esses dados nem duplicar a auditoria de sucesso.
- <b>CA-12:</b> Dado um Administrador com a permissão de calendário, quando configurar uma semana habitual ou exceção por data, então deve informar motivo, com registro do responsável e dos valores anteriores e novos. Professor e Operador não podem alterar essas regras.
- <b>CA-13:</b> Dado um sábado liberado para uso e atendimento, quando o Professor solicitar um agendamento válido, então o sistema deve permitir a reserva. Uma exceção de fechamento deve impedir novos agendamentos na finalidade afetada.
- <b>CA-14:</b> Dadas faixas distintas de uso e atendimento, quando o período atravessar uma pausa de uso ou os horários previstos de retirada e devolução estiverem fora do atendimento, então a nova reserva deve ser recusada.
- <b>CA-15:</b> Dada uma mudança de calendário que afete compromissos existentes, quando o Administrador consultar o calendário, então as reservas incompatíveis devem ser identificadas sem cancelamento ou remarcação automática e com preservação das condições acordadas.
- <b>CA-16:</b> Dado um fechamento ou horário de atendimento encerrado, quando um Operador autorizado registrar uma devolução física válida, então o calendário não deve impedir a regularização.
- <b>CA-17:</b> Dada uma reserva com margem acordada de 5 minutos e término às 10h, quando outra solicitação disputar as mesmas unidades, então o início às 10h04 deve ser recusado e às 10h05 deve ser aceito se não houver outro impedimento. Unidades distintas não compartilham essa margem.
- <b>CA-18:</b> Dada uma alteração do intervalo pelo Administrador, quando novas reservas forem confirmadas, então devem guardar o novo valor sem reescrever as existentes. Reservas legadas recebem margem zero, sem modificar período, status ou condições de calendário; motivo e valores anterior e novo ficam no histórico.
- <b>CA-19:</b> Dado um equipamento em manutenção ou uma disputa simultânea, quando o sistema alocar ou substituir unidades, então deve revalidar a margem no servidor e impedir conflitos, sem entregar unidade ainda não devolvida e conferida. A devolução antecipada não remove a margem já acordada.

- <b>CA-20:</b> Dado um tipo sem cota configurada, quando o Professor solicitar uma reserva, então não deve haver limite adicional por professor além da disponibilidade física e demais regras. O Administrador pode ativar um limite inteiro positivo por tipo ou desativá-lo, com motivo e histórico.
- <b>CA-21:</b> Dado um tipo com cota ativa, quando um Professor reservar, então o sistema deve considerar o maior total de unidades simultaneamente comprometidas em suas reservas ativas desse tipo, somando todos os locais e impedindo contornar o limite com solicitações menores. Períodos adjacentes não se sobrepõem; reservas canceladas ou expiradas não consomem cota. O servidor revalida o saldo na confirmação, inclusive em disputas concorrentes e formulários adulterados.
- <b>CA-22:</b> Dada uma redução ou desativação da cota, quando o sistema consultar ou entregar uma reserva já confirmada, então deve preservar seu compromisso e o limite registrado na confirmação. As reservas existentes continuam contando no cálculo de novas solicitações simultâneas. Não há autorização para exceder a cota neste incremento.

## RF05 - Registrar retirada e devolução

<b>Descrição:</b> O sistema deve permitir ao Operador registrar a entrega dos equipamentos de uma reserva válida e sua devolução total ou parcial, preservando os vínculos físicos e atualizando a situação de cada unidade. Toda nova retirada exige reserva; registros anteriores sem reserva permanecem disponíveis para devolução e consulta.

<b>Ator: </b>Operador.

<b>Pré-condições:</b> O Operador deve estar autenticado, ativo e autorizado. A entrega exige reserva ativa, contexto pedagógico completo e patrimônios aptos ainda não entregues. A primeira entrega respeita a tolerância; a complementação de um saldo por manutenção é permitida até o fim do período reservado. O destinatário é o Professor proprietário ativo, definido pelo servidor. A primeira confirmação ocorre a partir do início e antes de completar 30 minutos de tolerância. Para devolver, deve existir retirada em aberto das unidades selecionadas.

<b>Fluxo principal:</b> O Operador localiza a reserva e confere os patrimônios alocados. O sistema revalida o prazo, o Professor, o contexto e a disponibilidade e tenta substituir unidades em manutenção por outras do mesmo tipo/local sem conflito no período. Sem substituto suficiente, permite entregar as unidades aptas após comunicação ao Professor e confirmação dessa comunicação, mantendo o saldo de entrega. Na mesma transação, grava as retiradas, cria as utilizações pedagógicas por unidade, atualiza os equipamentos para em uso e registra a auditoria. Na devolução, qualquer Operador autorizado confere o lote, seleciona todas ou parte das unidades recebidas e descreve problemas por patrimônio quando necessário. O sistema grava as devoluções, preserva cada retirada de origem e atualiza as situações; unidades com problema geram manutenção na mesma transação.

<b>Regras de negócio:</b> Retirada e devolução geram movimentação e atualização de situação (RN-04), exclusivamente por Operador autorizado (RN-08). A entrega exige reserva e Professor proprietário, admite substituição por manutenção e pode ser parcial ou complementar; somente as unidades efetivamente entregues geram retirada (RN-09 e RN-13). Cada devolução exige uma retirada em aberto, não pode ser repetida e pode ser registrada por outro Operador (RN-10). Problema descrito na devolução abre manutenção pendente por unidade (RN-14). Nova retirada sem reserva é recusada; os registros legados preservam seus vínculos.

<b>Pós-condições:</b> Após a entrega, todas as unidades alocadas ficam em uso. Após devolução parcial, somente as unidades recebidas têm a pendência encerrada, e as demais continuam em uso. Unidade ativa sem impedimento retorna à disponibilidade; unidade com problema segue para manutenção. A devolução não reativa equipamento inativo nem libera manutenção já existente. Uma falha desfaz toda a confirmação e suas auditorias de sucesso.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dada uma reserva elegível no prazo de entrega, quando o Operador confirmar a retirada, então todas as unidades alocadas devem registrar o Professor proprietário, as movimentações, as utilizações pedagógicas, a situação em uso e a auditoria na mesma transação.
- <b>CA-02:</b> Dadas unidades com retiradas em aberto, quando qualquer Operador autorizado confirmar sua devolução sem problema, então o sistema deve registrar uma devolução por unidade, preservar a origem e devolver à disponibilidade somente os equipamentos ativos sem impedimento.
- <b>CA-03:</b> Dada uma seleção com unidades normais e com problema descrito, quando o Operador confirmar a devolução, então somente as unidades com problema devem gerar manutenção pendente e permanecer indisponíveis.
- <b>CA-04:</b> Dada uma unidade sem retirada em aberto ou já devolvida, quando houver tentativa de devolução, então o sistema deve recusá-la sem duplicar registros ou gravar parcialmente as demais unidades selecionadas.
- <b>CA-05:</b> Dado um usuário sem o perfil de Operador ou sem a permissão exigida, quando ele tentar registrar retirada ou devolução, então o sistema deve impedir a operação.
- <b>CA-06:</b> Dada uma reserva antes do início ou com 30 minutos ou mais decorridos sem retirada, quando o Operador tentar entregá-la, então o sistema deve impedir a retirada; no segundo caso, deve preservar a expiração legítima.
- <b>CA-07:</b> Dado um lote com unidades pendentes, quando o Operador devolver somente parte delas, então as unidades não recebidas devem permanecer em uso, com quantidade pendente explícita.
- <b>CA-08:</b> Dada uma tentativa de nova retirada sem reserva, quando a operação for solicitada, então o sistema deve recusá-la. Retiradas legadas sem reserva continuam aceitando devolução.
- <b>CA-09:</b> Dada uma reserva já entregue, quando houver nova tentativa de entrega, então o sistema deve recusá-la sem duplicar movimentações.
- <b>CA-10:</b> Dada uma falha de gravação em qualquer unidade da entrega ou devolução, quando a transação for encerrada, então nenhuma alteração parcial da confirmação deve permanecer salva.

- <b>CA-11:</b> Dada uma unidade em manutenção, quando houver substituto do mesmo tipo/local livre em todo o período, então o sistema deve atualizar a alocação e preservar o histórico da troca.
- <b>CA-12:</b> Dada uma falta de substituto, quando o Operador confirmar que informou o Professor, então deve ser possível entregar somente as unidades aptas, manter o saldo e complementá-lo até o fim do período, sem duplicar retiradas nem criar devolução para unidades não entregues.
- <b>CA-13:</b> Dado um patrimônio com retirada sem devolução, quando houver tentativa de disponibilização cadastral ou nova entrega, então o sistema deve recusá-la, mesmo que a situação armazenada esteja inconsistente.
- <b>CA-14:</b> Dada uma conferência cuja lista ou dados patrimoniais mudaram antes da confirmação, quando o Operador confirmar, então nenhuma entrega deve ser registrada e uma nova conferência deve ser exigida.
- <b>CA-15:</b> Dada uma confirmação de entrega já processada, quando ela for reenviada pelo Operador ainda autorizado, então somente a operação original deve ser reconhecida, sem incorporar novos patrimônios ou repetir os efeitos da entrega.

## RF06 - Consultar o histórico de movimentações

<b>Descrição:</b> O sistema deve permitir a consulta de reservas encerradas, canceladas ou expiradas e das retiradas e devoluções relacionadas, preservando datas, responsáveis, destinatários, patrimônios e contexto pedagógico. Retiradas legadas encerradas sem reserva também permanecem consultáveis.

<b>Atores:</b> Administrador, Operador e Professor.

<b>Pré-condições:</b> O usuário deve estar autenticado, ativo e autorizado. O Professor consulta somente registros próprios.

<b>Fluxo principal:</b> O usuário acessa o Histórico, aplica filtros e consulta os grupos encerrados. O sistema apresenta uma linha por reserva, com acesso aos patrimônios, movimentações e contexto; reservas canceladas ou expiradas aparecem mesmo sem retirada. Os registros legados encerrados sem reserva são identificados separadamente. Enquanto existe unidade pendente, o lote permanece em Em uso. O fim do horário reservado não substitui a devolução física.

<b>Regras de negócio:</b> Movimentações e vínculos são preservados (RN-04, RN-10 e RN-13). Administrador e Operador consultam o escopo global; o Professor permanece restrito às próprias reservas e retiradas destinadas à sua conta. Propriedade é aplicada antes de filtros e paginação. Consultar não concede permissão para editar ou excluir o histórico.

<b>Pós-condições:</b> O usuário visualiza os registros autorizados sem alterar seu conteúdo. As rotinas de expiração acionadas pela consulta podem atualizar reservas vencidas sem retirada e registrar sua auditoria.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dado um lote integralmente devolvido, quando o usuário autorizado consultar o Histórico, então a reserva e suas movimentações devem estar disponíveis com tipos, datas, horários, patrimônios e responsáveis.
- <b>CA-02:</b> Dada uma devolução registrada por Operador diferente daquele que realizou a retirada, quando o histórico for consultado, então cada movimentação deve identificar seu respectivo responsável.
- <b>CA-03:</b> Dado um usuário sem permissão de consulta ao histórico, quando ele tentar acessá-lo, então o sistema deve impedir o acesso.
- <b>CA-04:</b> Dado um Professor, quando ele consultar ou filtrar o Histórico, então deve visualizar somente seus registros; reservas e retiradas alheias não devem ser expostas.
- <b>CA-05:</b> Dada uma reserva cancelada ou expirada sem retirada, quando o usuário autorizado consultar o Histórico, então ela deve aparecer sem movimentações inventadas.
- <b>CA-06:</b> Dado um lote com devolução parcial e unidades pendentes, quando o usuário consultar as etapas, então ele deve permanecer em Em uso até a devolução integral.

## RF07 - Gerenciar manutenção

<b>Descrição:</b> O sistema deve registrar e acompanhar as intervenções de manutenção dos equipamentos. A manutenção pode ser aberta pelo Administrador ou pelo Operador, inclusive fora da devolução, ou gerada a partir de um problema informado na devolução. O Operador consulta o andamento; início e conclusão são administrativos.

<b>Atores:</b> Administrador e Operador.

<b>Pré-condições:</b> Para a abertura manual, o Administrador ou Operador deve estar autenticado e autorizado, e o equipamento deve estar ativo e disponível. Para a abertura a partir da devolução, deve existir uma retirada em aberto e uma ocorrência descrita pelo Operador.

<b>Fluxo principal:</b> O Administrador ou Operador abre uma manutenção manualmente ou o sistema a cria como pendente após uma devolução com problema. A abertura tenta substituir a unidade nas reservas ativas ainda não atendidas; sem substituto, preserva as reservas e sinaliza a falta. O equipamento passa a ficar indisponível. O Administrador acompanha a intervenção, altera seu estado para em andamento e, ao concluí-la, registra a descrição da solução ou conclusão e o resultado. Se foi reparado, o equipamento recebe a situação disponível, sem desfazer uma inativação independente; somente a unidade ativa volta a ficar disponível para uso. Caso não tenha possibilidade de reparo, é inativado com preservação do histórico.

<b>Regras de negócio:</b> A manutenção segue os estados pendente, em andamento e concluída. Enquanto estiver pendente ou em andamento, o equipamento permanece em manutenção e indisponível. A conclusão exige descrição e classificação do resultado (RN-05). A ocorrência identificada na devolução deve ser descrita pelo Operador e gerar uma manutenção pendente (RN-14).

<b>Pós-condições:</b> A intervenção fica registrada no histórico do equipamento. O reparo atualiza a situação para disponível e preserva o estado ativo ou inativo da unidade. O resultado sem possibilidade de reparo inativa o equipamento. Nenhuma conclusão remove o histórico.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dada uma devolução com problema descrito, quando o Operador confirmá-la, então o sistema deve criar uma manutenção pendente e tornar o equipamento indisponível.
- <b>CA-02:</b> Dada uma manutenção pendente ou em andamento, quando houver tentativa de reservar ou retirar o equipamento, então o sistema deve impedir sua utilização.
- <b>CA-03:</b> Dada uma manutenção em andamento, quando o Administrador concluir a intervenção com resultado de reparo e descrição da solução, então o equipamento deve receber a situação disponível. Uma unidade ativa volta a ficar disponível para uso; uma unidade inativada por outro motivo deve permanecer inativa.
- <b>CA-04:</b> Dada uma manutenção em andamento, quando o Administrador concluir que o equipamento não pode ser reparado e registrar a conclusão, então o equipamento deve ser inativado sem perda do histórico.
- <b>CA-05:</b> Dada uma tentativa de conclusão sem a descrição exigida, quando o Administrador confirmar a operação, então o sistema deve recusá-la.

## RF08 - Exibir painel resumido do inventário

O Operador acessa um início próprio com situação atual dos equipamentos, entregas do dia, pendências de entrega e devoluções previstas ou vencidas. Cada lista apresenta até cinco reservas e informa o total. Unidades inativas ficam fora dos indicadores operacionais. A disponibilidade atual não substitui a consulta de reservas futuras. O painel analítico e os filtros descritos a seguir permanecem exclusivos do Administrador.

<b>Descrição:</b> O sistema deve apresentar ao Administrador um resumo do uso e da situação do acervo, com indicadores, gráficos, reservas e pendências. O painel deve permitir filtros por categoria e pelos últimos 7, 30 ou 90 dias, com 30 dias como padrão.

<b>Ator:</b> Administrador.

<b>Pré-condições:</b> O Administrador deve estar autenticado e autorizado a visualizar o painel.

<b>Fluxo principal:</b> O Administrador acessa o painel e aplica os filtros. O sistema apresenta a situação do acervo, as retiradas diárias, os equipamentos distintos utilizados, a comparação com o período anterior, até cinco tipos mais retirados, as etapas das reservas e até dez movimentações recentes. Conforme as permissões, também apresenta manutenções abertas e devoluções vencidas, com até cinco registros por lista.

<b>Regras de negócio:</b> O período inclui o dia atual e considera o fuso horário da aplicação. Cada retirada conta uma unidade física; equipamentos distintos contam uma única vez no período. A comparação utiliza o intervalo anterior de mesma duração. A situação do acervo considera os ativos, com inativos em total separado; os históricos dos inativos são preservados. A situação atual e as pendências independem do período selecionado. Reservas são consideradas pelo início no período. A categoria se aplica a todos os conjuntos, respeitadas as permissões de consulta.

<b>Pós-condições:</b> O Administrador visualiza um resumo coerente com os registros e os filtros aplicados, sem alterar os dados consultados.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dados registros de inventário, reservas e movimentações, quando o painel for consultado, então os indicadores devem corresponder aos dados armazenados, sem incluir inativos na distribuição dos ativos.
- <b>CA-02:</b> Dados filtros de categoria e período, quando aplicados, então as análises devem respeitar o recorte; sem período informado, devem considerar 30 dias.
- <b>CA-03:</b> Dadas retiradas no período, quando as contagens forem apresentadas, então cada retirada física deve contar no respectivo dia, com zero nos dias sem registros e sem duplicar equipamentos no total de unidades distintas.
- <b>CA-04:</b> Dadas pendências atuais, quando o período for alterado, então as manutenções abertas e as devoluções vencidas devem continuar visíveis na categoria selecionada, conforme as permissões.
- <b>CA-05:</b> Dado um usuário sem perfil de Administrador, quando tentar acessar o painel, então o sistema deve impedir o acesso. As seções de reservas e manutenções devem respeitar suas permissões específicas.

## RF09 - Consultar feriados nacionais durante a reserva

<b>Descrição:</b> O sistema deve informar ao Professor os feriados nacionais durante a escolha do período de reserva, com aviso antes da confirmação. Um feriado permanece selecionável quando atende às regras temporais e ao calendário da escola. Sábados e domingos dependem de liberação nesse calendário; a BrasilAPI não determina o funcionamento institucional.

<b>Ator: </b>Professor.

<b>Pré-condições:</b> O Professor deve estar autenticado e ter iniciado o preenchimento de uma reserva.

<b>Fluxo principal:</b> Ao consultar o calendário, o Professor visualiza os feriados nacionais destacados e identificados por legenda. Se o período escolhido coincidir com um feriado nacional, o sistema informa essa condição no diálogo de confirmação. O Professor pode prosseguir com a reserva se as demais condições de disponibilidade e validade do período forem atendidas.

<b>Regras de negócio:</b> A ocorrência de feriado nacional não impede a reserva. A indisponibilidade da BrasilAPI também não deve bloquear sua conclusão. Datas passadas, antecedência e funcionamento institucional continuam sujeitos às validações locais da reserva (RN-19).

<b>Pós-condições:</b> O Professor recebe a informação sobre o feriado quando disponível e pode confirmar uma reserva válida.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dado um feriado nacional obtido na consulta, quando o Professor visualizar o calendário, então a data deve estar destacada e identificada pela legenda. A seleção deve respeitar o prazo e o calendário escolar, inclusive eventuais liberações de sábado ou domingo; o destaque de feriado não altera essas regras.
- <b>CA-02:</b> Dado um período válido que coincida com feriado nacional, quando o Professor avançar para a confirmação, então o sistema deve apresentar o aviso sem impedir a reserva.
- <b>CA-03:</b> Dada uma falha na consulta à BrasilAPI, quando o Professor solicitar uma reserva válida, então a falha não deve impedir sua conclusão.

## RF10 - Vincular a utilização ao contexto pedagógico

<b>Descrição: </b>O sistema deve exigir turma, disciplina e atividade pedagógica na nova reserva do Professor, com observação opcional, e criar as utilizações por unidade na confirmação da entrega. O Professor pode corrigir o contexto próprio até a devolução integral, preservando a reserva e as movimentações.

<b>Ator:</b> Professor.

<b>Pré-condições:</b> O Professor deve estar autenticado, ativo e autorizado. Para corrigir o planejamento sem retirada, a reserva própria deve estar ativa e antes do limite de tolerância. Após a retirada, deve existir pelo menos uma unidade pendente. Novas escolhas exigem cadastros pedagógicos ativos; uma referência já vinculada pode ser mantida após inativação.

<b>Fluxo principal:</b> O Professor informa o planejamento ao criar a reserva. Na entrega pelo Operador, o sistema cria uma utilização pedagógica para cada unidade retirada na mesma transação. Uma correção posterior aplica o contexto a todo o lote e sincroniza a reserva, inclusive após devolução parcial. Após a devolução integral, quando não há saldo de entrega dentro do período reservado, o contexto fica somente para consulta. Em retiradas legadas sem reserva, o Professor destinatário pode registrar ou corrigir o contexto do próprio lote enquanto há pendências.

<b>Regras de negócio:</b> O contexto é obrigatório nas novas reservas e sua observação é opcional. Agendamentos não contam como uso realizado; as utilizações são criadas na entrega (RN-15). A compatibilidade sem reserva aplica-se somente às retiradas antigas, sem criar novas retiradas diretas (RN-16). O vínculo pedagógico por retirada é único. Não há exclusão do contexto nem preenchimento automático de utilizações não realizadas.

<b>Pós-condições: </b>O planejamento permanece associado à reserva, e os usos efetivos permanecem vinculados às retiradas correspondentes. Devoluções e inativação de referências não removem o contexto histórico.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dada uma reserva com planejamento completo, quando o Operador confirmar a entrega, então o sistema deve criar uma utilização por unidade com turma, disciplina, atividade e observação da reserva.
- <b>CA-02:</b> Dada uma retirada legada sem reserva do Professor destinatário, com unidade pendente, quando ele registrar ou corrigir seu contexto, então as informações devem ser associadas ao lote sem criar uma reserva ou nova retirada.
- <b>CA-03: </b>Dada uma movimentação com contexto pedagógico, quando seus dados forem consultados, então o vínculo pedagógico e os dados da movimentação devem permanecer preservados.
- <b>CA-04:</b> Dada uma devolução parcial, quando o Professor corrigir o contexto, então a alteração deve abranger todo o lote, incluindo as unidades já devolvidas, e atualizar a reserva vinculada.
- <b>CA-05:</b> Dado um lote integralmente devolvido, quando houver tentativa de criar ou editar seu contexto, então o sistema deve recusá-la e manter a consulta do histórico.
- <b>CA-06:</b> Dada uma referência pedagógica inativada após o vínculo, quando o Professor mantiver essa referência, então o sistema deve preservar o vínculo; uma nova escolha inativa deve ser recusada.

## RF11 - Exibir indicadores de utilização pedagógica

<b>Descrição:</b> O sistema deve apresentar ao Administrador os totais de utilizações, unidades retiradas e equipamentos distintos, tanto no conjunto dos registros com contexto pedagógico quanto nos agrupamentos por turma, disciplina e atividade pedagógica.

<b>Ator:</b> Administrador.

<b>Pré-condições:</b> O Administrador deve estar autenticado e autorizado a consultar os indicadores.

<b>Fluxo principal:</b> O Administrador acessa os indicadores pedagógicos. O sistema considera somente movimentações de retirada com utilização pedagógica associada e apresenta os totais gerais e por turma, disciplina e atividade. Cada agrupamento permite consultar seus resultados paginados.

<b>Regras de negócio:</b> Os indicadores devem ser calculados somente a partir de retiradas efetivamente vinculadas ao contexto pedagógico (RN-17). Uma utilização corresponde a um grupo por reserva, UUID de lote ou retirada individual legada. Unidades retiradas contam as movimentações de retirada, uma por patrimônio movimentado. Equipamentos distintos contam cada equipamento uma única vez no conjunto ou agrupamento consultado. Agendamentos sem retirada não entram nas contagens. Devoluções e inativação de cadastros não eliminam os usos históricos. As definições estão detalhadas no [fluxo de reservas, uso e histórico](../tecnica/fluxo-reservas-uso-historico.md#contexto-e-indicadores-pedagógicos).

<b>Pós-condições:</b> O Administrador visualiza informações consolidadas coerentes com os registros de utilização pedagógica armazenados.

<b>Critérios de aceite:</b>

- <b>CA-01:</b> Dados registros de utilização com contexto pedagógico associado, quando o Administrador consultar os indicadores, então eles devem ser considerados na consolidação correspondente.
- <b>CA-02: </b>Dados registros de utilização sem vínculo pedagógico, quando os indicadores forem calculados, então esses registros não devem compor os resultados pedagógicos.
- <b>CA-03:</b> Dado um usuário sem perfil de Administrador, quando ele tentar acessar os indicadores, então o sistema deve impedir o acesso.
- <b>CA-04:</b> Dada uma reserva entregue com três equipamentos distintos e contexto pedagógico associado, quando os indicadores forem consultados sem outros registros no conjunto, então devem apresentar uma utilização, três unidades retiradas e três equipamentos distintos.
- <b>CA-05:</b> Dada uma reserva ainda sem retirada, quando os indicadores forem consultados, então o agendamento não deve aumentar nenhuma das contagens.
- <b>CA-06:</b> Dados usos com contexto pedagógico, quando os equipamentos forem devolvidos ou um cadastro pedagógico vinculado for inativado, então os registros devem continuar participando das contagens históricas.

Na consulta operacional de reservas e histórico, o Operador visualiza somente a turma do contexto pedagógico. O menu da conta oferece Meus dados, com nome, nome de usuário, e-mail e perfil, em consulta restrita à própria conta e orientação para solicitar correção ou exclusão a um Administrador.
