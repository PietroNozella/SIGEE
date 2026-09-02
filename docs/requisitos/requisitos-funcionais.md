# Requisitos Funcionais

A entrega final do SIGEE deverá contemplar os 11 requisitos funcionais aprovados. A presença de um requisito neste documento não indica que ele já esteja implementado.

- **RF-01 — Autenticação e autorização:** autenticar usuários e limitar as ações conforme o perfil.
- **RF-02 — Inventário:** cadastrar e gerenciar equipamentos com patrimônio único, categoria, local e situação.
- **RF-03 — Consulta:** pesquisar e filtrar equipamentos por texto, categoria, local e situação.
- **RF-04 — Reservas:** reservar equipamentos por período, bloqueando conflitos e indisponibilidade.
- **RF-05 — Retirada e devolução:** registrar as movimentações físicas, com ou sem reserva prévia quando permitido.
- **RF-06 — Histórico:** consultar movimentações com data, hora, responsável, destinatário e tipo.
- **RF-07 — Manutenção:** registrar e acompanhar intervenções, mantendo o equipamento indisponível durante a manutenção.
- **RF-08 — Painel do inventário:** apresentar indicadores numéricos, totais por situação, movimentações recentes e representações gráficas.
- **RF-09 — Feriados nacionais:** consultar a BrasilAPI durante o processo de reserva sem tornar a integração bloqueante.
- **RF-10 — Contexto pedagógico:** vincular a utilização a turma, disciplina e atividade pedagógica.
- **RF-11 — Indicadores pedagógicos:** apresentar ao administrador informações consolidadas sobre a utilização dos equipamentos.

## Fora do escopo

- Leitura por código de barras ou QR Code.
- APIs ou integrações externas adicionais além da BrasilAPI e dos serviços de infraestrutura previstos.
- Suporte a múltiplas unidades escolares.
- Relatórios avançados.
- Notificações automáticas.
