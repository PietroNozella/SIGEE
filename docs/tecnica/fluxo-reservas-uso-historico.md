# Fluxo de reservas, uso e histórico

O fluxo organiza o empréstimo em Reservas, Em uso e Histórico. A classificação deriva da situação da reserva e das movimentações, sem um segundo estado de empréstimo mantido manualmente.

![Processo de reserva, entrega, devolução e manutenção](../diagramas/bpmn.png)

## Responsabilidades

| Etapa | Professor | Operador | Administrador |
|---|---|---|---|
| Reservas | Cria e acompanha as próprias reservas, informa contexto e cancela quando permitido | Confere e entrega unidades aptas; acompanha o saldo, complementa a entrega e registra desistência confirmada do Professor | Consulta |
| Em uso | Consulta seus empréstimos pendentes e corrige o contexto | Registra devoluções parciais ou integrais e problemas por patrimônio | Consulta |
| Histórico | Consulta somente seus registros encerrados | Consulta registros encerrados | Consulta registros encerrados |

## Reserva e entrega

1. O Professor consulta disponibilidade por tipo/modelo, local e período e informa uma quantidade positiva, turma, disciplina e atividade. A observação é opcional.
2. O servidor valida perfil, período, antecedência de até 15 dias corridos pela data local, calendário de uso e atendimento, referências ativas, disponibilidade, intervalo entre usos e cota opcional por professor e tipo; aloca unidades físicas compatíveis e grava uma única reserva com seus itens. O cálculo da cota considera o pico simultâneo em todos os locais, sem incluir a margem de preparação. A reserva preserva o calendário, o intervalo e a cota vigentes na confirmação.
3. O Professor cancela a reserva própria enquanto está ativa, sem retirada e antes de vencer a tolerância. Reservas sem retirada expiram integralmente ao completar 30 minutos do início; a rotina é acionada nos fluxos que sincronizam expiração. Reservas suspensas aguardando decisão por fechamento emergencial não expiram automaticamente enquanto essa pendência existir. O fim de uma reserva curta já impede entrega, mesmo antes da expiração persistida por tolerância.
4. O Operador confere as unidades aptas. A conferência tenta substituir patrimônios em manutenção por unidades do mesmo tipo/local livres no período. Sem substituto suficiente, permite entrega parcial após comunicação ao Professor, mantendo o saldo explícito. A primeira entrega exige reserva ativa, contexto completo e equipamentos ativos e disponíveis, a partir do início e antes do menor limite entre o término da reserva e a tolerância.
5. A transação grava retiradas, situações `EM_USO`, utilizações pedagógicas por unidade e auditoria. A repetição não reentrega uma unidade. O lote passa para Em uso; o saldo não entregue continua acessível em Reservas e pode ser complementado até o fim do período. Após esse prazo, o saldo é apresentado como não atendido e as devoluções físicas permanecem abertas.

Toda nova retirada exige reserva. As rotas e o serviço antigos de retirada sem reserva recusam novas operações. O fim do horário agendado não representa devolução física nem encerra o empréstimo.

A situação disponível não substitui a verificação da custódia: reservas, substituições e entregas excluem patrimônios com retirada sem devolução, mesmo diante de uma situação cadastral inconsistente. A edição cadastral também recusa sua disponibilização.

O cadastro funcional não permite atribuir `EM_USO` sem retirada em aberto nem alterar a situação enquanto houver custódia. Tipo/modelo e local não podem ser alterados enquanto a unidade tiver reserva ativa com término futuro ou retirada em aberto. A correção de descrição e patrimônio continua permitida; uma alteração desses dados invalida conferências anteriores.

A tela de conferência emite uma confirmação assinada pelo Django, vinculada ao Operador, à reserva, ao conjunto exibido e a um UUID de lote. A preparação da tela pode substituir unidades em manutenção; a confirmação não faz novas substituições. Sob os bloqueios transacionais, a entrega compara o retrato conferido com os patrimônios e dados atuais. Mudanças exigem conferir novamente a lista, sem gravar a entrega desatualizada.

Reenviar a mesma confirmação após sucesso consulta somente as retiradas daquele lote. Não cria complemento, utilizações ou auditorias de sucesso adicionais, inclusive após surgir um substituto ou depois de devolução e término do prazo. A autorização atual do Operador continua obrigatória. Uma entrega complementar exige nova conferência. Nenhuma tabela nova é necessária para esse controle.

## Cancelamento operacional

O Operador com `reservas.cancelar_reserva_operacional` acessa um formulário separado da entrega para registrar a desistência comunicada pelo Professor. Exige motivo e confirmação da comunicação. Não atende ausência presumida, disputa por equipamentos ou exceção administrativa ainda não definida.

O serviço recarrega a autorização atual, bloqueia a mesma reserva utilizada na entrega e revalida estado, prazo e ausência de qualquer retirada, inclusive já devolvida. Se a reserva atingir o limite sem retirada nem pendência de decisão por fechamento, persiste a expiração e recusa o cancelamento. Uma pendência de fechamento após a tolerância exige o fluxo administrativo. Dentro do prazo comum, grava `CANCELADA`, motivo, responsável, data e auditoria na mesma transação. A falha na auditoria desfaz o cancelamento. Não há alteração de equipamentos, exclusão de alocações ou criação de movimentações.

O detalhe autorizado mostra os metadados operacionais. O cancelamento próprio do Professor continua no fluxo anterior; registros sem metadados não recebem preenchimento presumido. A exportação assistida inclui os dados da reserva do Professor e as reservas canceladas pelo próprio Operador.

## Devolução

A tela inicial do Operador sinaliza reservas com patrimônios ainda vinculados a uma retirada anterior vencida. O aviso permanece enquanto houver unidade afetada sem devolução; não libera nem substitui automaticamente a custódia física.

Qualquer Operador autorizado recebe todas ou parte das unidades, mesmo quando outro Operador registra a entrega. A confirmação preserva equipamento, destinatário, reserva, lote e retirada de origem de cada unidade. Seleção vazia, repetida, de outro grupo ou já devolvida é rejeitada sem gravação parcial.

Cada devolução referencia uma única retirada; uma restrição no banco impede duplicidade. Movimentações, atualização dos equipamentos, auditoria e eventual manutenção são atômicas. Falha desfaz toda a confirmação. As unidades não recebidas continuam pendentes.

Unidade ativa sem impedimento retorna a `DISPONIVEL`. Equipamento inativo não é reativado pela devolução; equipamento já em manutenção mantém a situação. Um problema informado exige descrição e abre manutenção pendente por patrimônio. A devolução com problema encerra a pendência física daquela unidade, enquanto a intervenção segue sob responsabilidade do Administrador.

## Manutenção

O Administrador e o Operador também abrem manutenção manualmente para unidade ativa e disponível. Existe no máximo uma intervenção pendente ou em andamento por equipamento. A intervenção registra origem opcional na devolução, problema, responsáveis e datas. A abertura tenta substituir as unidades nas reservas ativas afetadas, em ordem de início; cada troca preserva origem, destino, manutenção e responsável. O Operador consulta o andamento; início e conclusão são administrativos.

O ciclo é `PENDENTE` → `EM_ANDAMENTO` → `CONCLUIDA`. A conclusão exige descrição da solução ou da análise e resultado: `REPARADO` atualiza a situação para `DISPONIVEL`, sem desfazer uma inativação independente; somente a unidade ativa volta a ficar disponível para uso. `SEM_REPARO` inativa o equipamento e preserva seu histórico. A situação do equipamento e a intervenção são atualizadas na mesma transação.

## Contexto e indicadores pedagógicos

O Administrador filtra os indicadores por `inicio` e `fim`, ambos opcionais e inclusivos, usando a data local da movimentação de retirada. Sem datas, a consulta inclui todo o histórico com contexto. Um intervalo invertido ou uma data inválida gera erro de validação e não apresenta totais calculados sobre um período alternativo. Tabelas, ranking e totais usam o mesmo recorte, e a paginação preserva os filtros.

Turma, Disciplina e Atividade Pedagógica são cadastros compartilhados mantidos pelo Administrador, com nome único, situação e data de criação; atividade também possui descrição opcional. Há consulta, criação, edição, inativação e reativação, sem exclusão definitiva. Não há cadastro de alunos. Nomes atuais são exibidos pelos vínculos; não há snapshot dos textos.

O Professor corrige o planejamento de reserva própria ativa antes de vencer a tolerância. Após a entrega, corrige o contexto enquanto há pelo menos uma unidade pendente. A devolução parcial permite atualizar também as unidades já devolvidas do lote e sincroniza a reserva; a devolução integral encerra criação e edição quando não há saldo de entrega dentro do período. Novas escolhas exigem cadastros ativos, mas uma referência já vinculada pode ser mantida após inativação.

`UtilizacaoPedagogica` possui vínculo único e protegido à movimentação de retirada. Cada registro representa uma unidade física. A devolução consulta o contexto da retirada original, sem copiá-lo. Gravações e auditorias são transacionais; reenvio sem alteração das utilizações não duplica registros nem seus eventos de sucesso.

O agendamento não aumenta os indicadores. As utilizações efetivas entram no cálculo após a retirada: utilizações contam grupos por reserva, lote ou retirada individual legada; retiradas contam unidades movimentadas; equipamentos distintos contam patrimônios sem duplicação dentro do agrupamento. Devolução e inativação de cadastros preservam as contagens históricas.

## Histórico e registros anteriores

`ReservaQuerySet.com_etapa()` classifica a reserva como `AGUARDANDO`, `EM_USO`, `ENCERRADA`, `CANCELADA` ou `EXPIRADA`, a partir das retiradas e devoluções. O campo persistido `status` contém somente `ATIVA`, `CANCELADA` e `EXPIRADA`; uma reserva entregue pode continuar com `status=ATIVA` e aparecer encerrada pela classificação derivada.

O Histórico apresenta reservas devolvidas integralmente, canceladas ou expiradas, mesmo sem movimentações, além de legados encerrados sem reserva. A busca inclui Professor, Operador, tipo/modelo e patrimônio. O período considera as movimentações; sem retirada, considera a data reservada. O Professor consulta somente seus registros, com propriedade aplicada antes dos filtros e da paginação. Consultar Em uso não autoriza entregar ou devolver.

Retiradas antigas sem reserva permanecem com suas referências originais. As pendências aceitam devolução; lotes encerrados ficam identificados no Histórico. O Professor destinatário registra ou corrige o contexto enquanto há unidade pendente. Um UUID identifica os lotes existentes; sem UUID e sem reserva, a utilização pedagógica trata cada retirada como individual. O agrupamento de pendências anteriores por destinatário não comprova um lote histórico único.

Reservas antigas sem contexto precisam ser completadas pelo Professor antes da entrega. As migrations `reservas.0005` e `0006` recuperam somente contextos históricos uniformes e exigem contexto completo ou totalmente ausente; não inventam utilizações. As precauções de atualização estão em [Implantação](../implantacao/seguranca-banco-supabase.md#atualização-de-bancos-existentes).

## Integridade e referências

O middleware de sessão interrompe operações expiradas antes da view. O padrão é de 30 minutos de inatividade e 8 horas desde o login; consultas automáticas de disponibilidade, feriados e estado da sessão não renovam esses prazos. Depois de autenticar novamente, o usuário precisa conferir e reenviar qualquer formulário interrompido.

Os serviços usam transações e bloqueios de linha. Os fluxos que alteram ou dependem da configuração bloqueiam o calendário; a alocação também serializa o tipo e a conta do Professor para validar conflitos e cotas. Entrega, devolução, cancelamento e decisão por fechamento revalidam os registros envolvidos sob bloqueio. SQLite não comprova esses bloqueios. A suíte local de 11/11/2026 executou 670 testes em PostgreSQL 17.6 isolado, incluindo os cenários concorrentes, sem falhas nem cenários ignorados; isso não equivale a validação da implantação publicada.

As regras estão em [Regras de negócio](../requisitos/regras-de-negocio.md), e as permissões em [Matriz de acesso](matriz-de-acesso.md). A implementação está em `reservas/models.py`, `reservas/services.py`, `reservas/consultas.py`, `movimentacoes/services.py`, `manutencoes/services.py` e `pedagogico/services.py`. O [README](../../README.md#testes) reúne os comandos de verificação.

Administrador e Operador consultam o escopo global; não há isolamento por instituição. O Professor permanece restrito aos próprios registros.

## Fechamentos e condições confirmadas

Em **Administração → Configurações → Calendário**, somente o Administrador com `calendario.configurar_calendario` altera horários e exceções. Uso e atendimento têm faixas separadas; exceções por data prevalecem sobre a semana habitual. Alterações ordinárias identificam incompatibilidades sem reescrever as condições confirmadas das reservas.

O fechamento emergencial de dia inteiro impede novos agendamentos e suspende entregas pendentes. As reservas afetadas ficam identificadas para decisão explícita, com responsável, motivo e data. Sem retirada, o Administrador pode cancelar, inclusive depois da tolerância enquanto houver decisão pendente. Manter a entrega exige política habilitada, atendimento excepcional confirmado e prazo original ainda válido; a política começa desabilitada. Havendo retirada, não é permitido cancelar a reserva inteira. Devoluções físicas continuam disponíveis, e a reabertura preserva as decisões no histórico.

Após uma entrega parcial, o Administrador pode encerrar o saldo não entregue, inclusive depois do prazo ou da devolução integral. A decisão `ENCERRADA` exige motivo, responsável e data e resolve os impactos ainda pendentes dos fechamentos ativos dessa reserva. Não cancela retiradas nem registra devoluções. A quantidade original, as unidades alocadas, a cota e a margem acordadas são preservadas; não há liberação antecipada adicional de cota. A reabertura não autoriza retomar esse complemento, e a preparação da conferência não substitui mais suas unidades. Uma confirmação já gravada continua podendo ser reenviada sem duplicidade. A reserva permanece Em uso enquanto houver devoluções pendentes e passa para Histórico após o retorno integral, sem exigir esperar o fim previsto.

O histórico das regras fica em `AlteracaoCalendario`; os vínculos de fechamento e decisão ficam em `FechamentoEscolar` e `ReservaAfetadaFechamento`. A implementação está em `calendario/services.py` e `calendario/fechamentos.py`; os testes de fechamento estão em `calendario/test_fechamentos.py`.
