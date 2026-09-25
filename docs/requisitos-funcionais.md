# Requisitos funcionais

Este documento registra o baseline aprovado de requisitos funcionais do SIGEE. A presença de um requisito não significa que ele já esteja implementado; o estado real da aplicação deve ser comprovado pelo código, pelos testes e pelas evidências do repositório.

| ID | Requisito | Critério de aceite |
|---|---|---|
| RF-01 | Autenticar usuários, recuperar o acesso e aplicar autorização por perfil. | Usuários válidos acessam o sistema, podem redefinir a senha pelo e-mail único cadastrado e cada perfil executa somente as ações permitidas. |
| RF-02 | Cadastrar e gerenciar o inventário. | Equipamentos físicos possuem patrimônio único, tipo/modelo, categoria, local e situação válidos. Categoria representa a classificação ampla; tipo/modelo identifica o conjunto de unidades selecionável para reserva. O cadastro pode ser unitário ou por CSV; na importação, o lote só é salvo se todas as linhas forem válidas. |
| RF-03 | Consultar e filtrar equipamentos. | Filtros por texto, categoria, local e situação retornam resultados coerentes. |
| RF-04 | Reservar equipamentos. | Professor autenticado seleciona um tipo/modelo, local de retirada, data, horários e quantidade. O sistema informa as unidades disponíveis naquele local e aloca equipamentos físicos do mesmo tipo e local automaticamente em uma única reserva vinculada à própria conta. Conflitos, indisponibilidade, início no passado e períodos que incluam sábado ou domingo são bloqueados. No calendário, datas passadas e fins de semana aparecem como indisponíveis e não podem ser selecionados. A data atual é aceita quando o horário inicial ainda não passou. |
| RF-05 | Registrar retirada e devolução. | Operador autorizado registra as movimentações e a situação do equipamento é atualizada corretamente. |
| RF-06 | Consultar o histórico de movimentações. | Retiradas e devoluções preservam data, hora, responsável, destinatário e tipo. |
| RF-07 | Gerenciar manutenção. | Equipamentos em manutenção permanecem indisponíveis e mantêm o histórico das intervenções. |
| RF-08 | Exibir painel resumido do inventário. | O Administrador visualiza os totais de equipamentos ativos, disponíveis, em uso, em manutenção e inativos, as dez movimentações mais recentes e um gráfico da distribuição dos equipamentos ativos por situação. Os valores são coerentes com os registros persistidos. |
| RF-09 | Consultar feriados nacionais durante a reserva. | O calendário destaca os feriados nacionais com legenda e mantém essas datas selecionáveis. Antes de efetivar a reserva, o diálogo de confirmação também informa quando o período selecionado coincide com feriado nacional por meio da BrasilAPI; a ocorrência do feriado e a indisponibilidade da API não impedem a conclusão da reserva. |
| RF-10 | Vincular a utilização ao contexto pedagógico. | O Professor associa a utilização do equipamento a turma, disciplina e atividade pedagógica, preservando essas informações no respectivo registro. |
| RF-11 | Exibir indicadores de utilização pedagógica. | O Administrador visualiza informações consolidadas sobre a utilização por turma, disciplina e atividade pedagógica. |

## Estado do RF-09

> **RF-09 implementado e testado no backend e na interface do Professor.**

O contrato externo, o fluxo informativo e a contingência estão definidos no [projeto lógico da consulta de feriados](projeto-logico-brasilapi.md). O cliente da BrasilAPI, a consulta anual usada pelo calendário, a consulta prévia integrada à disponibilidade, a apresentação do aviso no diálogo de confirmação e os testes automatizados estão implementados.

## Funcionalidade futura confirmada

A tela de **Configurações** do Professor permanece planejada para uma etapa futura. Enquanto seu comportamento e seus campos não forem definidos, ela não é exibida na sidebar para evitar uma opção de navegação sem funcionalidade. Termos de Uso e Política de Privacidade permanecem disponíveis no menu do usuário.
