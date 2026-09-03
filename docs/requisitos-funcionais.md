# Requisitos funcionais

Este documento registra o baseline aprovado de requisitos funcionais do SIGEE. A presença de um requisito não significa que ele já esteja implementado; o estado real da aplicação deve ser comprovado pelo código, pelos testes e pelas evidências do repositório.

| ID | Requisito | Critério de aceite |
|---|---|---|
| RF-01 | Autenticar usuários e aplicar autorização por perfil. | Usuários válidos acessam o sistema e cada perfil executa somente as ações permitidas. |
| RF-02 | Cadastrar e gerenciar o inventário. | Equipamentos possuem patrimônio único, categoria, local e situação válidos. O cadastro pode ser unitário ou por CSV; na importação, o lote só é salvo se todas as linhas forem válidas. |
| RF-03 | Consultar e filtrar equipamentos. | Filtros por texto, categoria, local e situação retornam resultados coerentes. |
| RF-04 | Reservar equipamentos. | Professor autenticado reserva equipamento disponível para um período definido; conflitos e indisponibilidade são bloqueados. |
| RF-05 | Registrar retirada e devolução. | Operador autorizado registra as movimentações e a situação do equipamento é atualizada corretamente. |
| RF-06 | Consultar o histórico de movimentações. | Retiradas e devoluções preservam data, hora, responsável, destinatário e tipo. |
| RF-07 | Gerenciar manutenção. | Equipamentos em manutenção permanecem indisponíveis e mantêm o histórico das intervenções. |
| RF-08 | Exibir painel resumido do inventário. | O Administrador visualiza indicadores numéricos, totais por situação, movimentações recentes e representações gráficas coerentes com os dados. |
| RF-09 | Consultar feriados nacionais durante a reserva. | O sistema informa quando o período selecionado coincide com feriado nacional por meio da BrasilAPI; a indisponibilidade da API não impede a conclusão da reserva. |
| RF-10 | Vincular a utilização ao contexto pedagógico. | O Professor associa a utilização do equipamento a turma, disciplina e atividade pedagógica, preservando essas informações no respectivo registro. |
| RF-11 | Exibir indicadores de utilização pedagógica. | O Administrador visualiza informações consolidadas sobre a utilização por turma, disciplina e atividade pedagógica. |
