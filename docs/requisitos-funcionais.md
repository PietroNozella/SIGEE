# Requisitos funcionais

Este documento registra o baseline aprovado de requisitos funcionais do SIGEE. A presença de um requisito não significa que ele já esteja implementado; o estado real da aplicação deve ser comprovado pelo código, pelos testes e pelas evidências do repositório.

| ID | Requisito | Critério de aceite |
|---|---|---|
| RF-01 | Autenticar usuários, recuperar o acesso e aplicar autorização por perfil. | Usuários válidos acessam o sistema, podem redefinir a senha pelo e-mail único cadastrado e cada perfil executa somente as ações permitidas. |
| RF-02 | Cadastrar e gerenciar o inventário. | Equipamentos físicos possuem patrimônio único, tipo/modelo, categoria, local e situação válidos. Categoria representa a classificação ampla; tipo/modelo identifica o conjunto de unidades selecionável para reserva. O cadastro pode ser unitário ou por CSV; na importação, o lote só é salvo se todas as linhas forem válidas. |
| RF-03 | Consultar e filtrar equipamentos. | Filtros por texto, categoria, local e situação retornam resultados coerentes. Para o Operador, a consulta inicial agrupa as unidades por tipo/modelo; ao expandir um tipo/modelo na mesma página, uma lista recolhível exibe todas as suas unidades físicas que correspondem aos filtros, com patrimônio, local e situação. |
| RF-04 | Reservar equipamentos. | Professor autenticado seleciona um tipo/modelo, local de retirada, data, horários e quantidade. O sistema informa as unidades disponíveis naquele local e aloca equipamentos físicos do mesmo tipo e local automaticamente em uma única reserva vinculada à própria conta. Conflitos, indisponibilidade, início no passado e períodos que incluam sábado ou domingo são bloqueados. No calendário, datas passadas e fins de semana aparecem como indisponíveis e não podem ser selecionados. A data atual é aceita quando o horário inicial ainda não passou. |
| RF-05 | Registrar retirada e devolução. | Operador autorizado registra as movimentações e a situação do equipamento é atualizada corretamente. Na retirada sem reserva, seleciona tipo/modelo, local e quantidade, confere os patrimônios sugeridos e pode trocar unidades antes de confirmar o lote; a gravação é integral e atômica. Na devolução básica, qualquer Operador autorizado confere as unidades da retirada ou reserva e confirma todas ou somente as recebidas. Cada unidade preserva sua retirada original, sem duplicidade; movimentações, situação e auditoria da seleção são atômicas. |
| RF-06 | Consultar o histórico de movimentações. | Administrador e Operador consultam retiradas e devoluções, inclusive encerradas, com patrimônio, equipamento, data, hora, Operador, destinatário e tipo. Filtros por texto, tipo, período e reserva, paginação e vínculos entre reserva, retirada e devolução facilitam a consulta. A tela não permite editar ou excluir registros. |
| RF-07 | Gerenciar manutenção. | Equipamentos em manutenção permanecem indisponíveis e mantêm o histórico das intervenções. |
| RF-08 | Exibir painel resumido do inventário. | O Administrador visualiza os totais de equipamentos ativos, disponíveis, em uso, em manutenção e inativos, as dez movimentações mais recentes e um gráfico da distribuição dos equipamentos ativos por situação. Os valores são coerentes com os registros persistidos. |
| RF-09 | Consultar feriados nacionais durante a reserva. | O calendário destaca os feriados nacionais com legenda e mantém essas datas selecionáveis. Antes de efetivar a reserva, o diálogo de confirmação também informa quando o período selecionado coincide com feriado nacional por meio da BrasilAPI; a ocorrência do feriado e a indisponibilidade da API não impedem a conclusão da reserva. |
| RF-10 | Vincular a utilização ao contexto pedagógico. | O Professor associa a utilização do equipamento a turma, disciplina e atividade pedagógica, preservando essas informações no respectivo registro. |
| RF-11 | Exibir indicadores de utilização pedagógica. | O Administrador visualiza informações consolidadas sobre a utilização por turma, disciplina e atividade pedagógica. |

## Estado de RF-05 e RF-06

A retirada com ou sem reserva, a devolução básica total ou parcial e a consulta do histórico foram integradas à `main` pelo PR #19, no commit `4071580`. A retirada com reserva entrega integralmente as unidades alocadas ao Professor proprietário, a partir do início e antes dos 30 minutos de tolerância, com gravação e auditoria atômicas. A devolução com problema (RN-14) e o ciclo de manutenção (RF-07) foram implementados localmente em `feat/manutencao`, com testes automatizados em `manutencoes/tests.py`. Concorrência em PostgreSQL, integração desta branch, revisão cruzada e validação publicada continuam pendentes; a implementação local não declara os cards formalmente concluídos.

## Base cadastral para RF-10 e estado do RF-11

Em 06/10/2026 foram implementados os cadastros compartilhados de Turma, Disciplina e Atividade Pedagógica, geridos pelo Administrador com validações, permissões, auditoria e inativação/reativação. Os modelos seguem o DER atual e ainda não se vinculam às utilizações, reservas, movimentações ou Professores. As [evidências da entrega de 09/10](cadastros-pedagogicos.md) registram os cenários executados e as limitações. A associação pelo Professor prevista no RF-10 e os indicadores do RF-11 continuam pendentes; os requisitos não estão concluídos.

## Estado do RF-09

> **RF-09 implementado e testado no backend e na interface do Professor.**

O contrato externo, o fluxo informativo e a contingência estão definidos no [projeto lógico da consulta de feriados](projeto-logico-brasilapi.md). O cliente da BrasilAPI, a consulta anual usada pelo calendário, a consulta prévia integrada à disponibilidade, a apresentação do aviso no diálogo de confirmação e os testes automatizados estão implementados.

## Funcionalidade futura confirmada

A tela de **Configurações** do Professor permanece planejada para uma etapa futura. Enquanto seu comportamento e seus campos não forem definidos, ela não é exibida na sidebar para evitar uma opção de navegação sem funcionalidade. Termos de Uso e Política de Privacidade permanecem disponíveis no menu do usuário.
