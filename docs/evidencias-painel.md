# Evidências do painel do inventário — 27/10/2026

Este recorte verifica RF-08 na visão geral do Administrador: indicadores do
acervo, distribuição por situação e categoria, retiradas diárias, manutenções
abertas e movimentações recentes. Não foi necessária correção funcional.

## Base de testes isolados

Os **20 testes de `inventario/test_painel.py`** estão incluídos nos 122 testes
de `inventario` e `usuarios` executados no recorte de cadastros em 27/10:
122 aprovados no PostgreSQL 17.6 isolado, sem erros, falhas ou casos ignorados,
em 33,223 segundos. Essa execução foi reaproveitada; não houve nova execução
da suíte nem medição de cobertura neste recorte.

A base cobre acesso por perfil e permissão, bloqueio de POST, inventário vazio,
separação de inativos, filtros, limites e desempates de listas, período no fuso
local, contagem por unidade física, reutilização de equipamentos, dados sem
JavaScript e quantidade constante de consultas de dados. Os cenários completos
de cadastros estão em [evidencias-cadastros.md](evidencias-cadastros.md).

Para executar somente esses testes em SQLite isolado:

```powershell
python manage.py test inventario.test_painel --settings=config.settings_testes
```

## Conferência na aplicação publicada

Em `https://sigee-psi.vercel.app`, uma conta funcional de Administrador de QA
consultou o acervo existente. Não foram criados equipamentos, movimentações,
reservas, manutenções ou contextos pedagógicos neste recorte. Uma consulta
independente ao banco calculou os valores esperados, para compará-los com os
elementos apresentados no navegador.

| Cenário | Resultado observado |
|---|---|
| Cinco indicadores globais | 5 ativos: 3 disponíveis, nenhum em uso e 2 em manutenção; 12 inativos contabilizados separadamente. |
| Distribuição por situação | Quantidades, percentuais e larguras renderizadas coincidiram com o banco: 60%, 0% e 40%. |
| Categorias | Quantidades e segmentos coincidiram com o inventário ativo, usando escala comum ao maior total de categoria. |
| Retiradas nos 30 dias | 14 unidades físicas no período de 28/09 a 27/10/2026; os 30 valores diários, dias zerados e escala coincidiram com o banco no fuso `America/Sao_Paulo`. |
| Movimentações recentes | As dez últimas retiradas/devoluções coincidiram em tipo, patrimônio e instante, incluindo equipamentos hoje inativos. |
| Manutenções abertas | A única intervenção aberta no acervo consultado coincidiu com o banco. O limite de cinco e os desempates estão cobertos pelos testes isolados. |
| Filtro de categoria com ativos | Atualizou indicadores, categorias, retiradas, manutenções e movimentações recentes de acordo com o mesmo recorte. |
| Categoria apenas com inativos | Exibiu dois inativos, zero ativos e estados vazios coerentes nos demais painéis. |
| Categoria sem equipamentos | Exibiu indicadores zerados e estados vazios, preservando os 30 dias com contagem zero. |
| Categoria inválida na URL | Ignorou o identificador inexistente e voltou ao conjunto completo, sem seleção de categoria. |
| POST autenticado com CSRF válido | Retornou 405; o painel aceita somente consulta por GET. |

Os três modos de ordenação por categoria foram acionados sem erro. Como havia
somente uma categoria com equipamentos ativos, esse ensaio publicado não
demonstrou a reordenação entre várias categorias.

No gráfico diário, Home, End e seta para a esquerda selecionaram os dias
esperados, com `aria-pressed` e informação textual visível. Isso constitui uma
verificação localizada de interação, sem afirmar conformidade global de
acessibilidade. Uma captura completa em viewport de 1440 × 1000 foi inspecionada
em `output/playwright/painel-inventario-desktop-20261027.png`.

## Preservação dos dados e encerramento

Foram comparados antes e depois os campos selecionados de equipamentos,
movimentações, manutenções, reservas e utilizações pedagógicas. Os resumos
criptográficos permaneceram iguais. Uma conexão nova, em transação somente
leitura, confirmou novamente essa igualdade e os cinco totais globais.

A conta temporária recebeu somente o grupo Administrador, sem privilégios
`is_staff`, `is_superuser` ou permissões individuais. Ao final, foi desativada,
recebeu senha inutilizável e teve a sessão conhecida removida. A conferência
independente não encontrou sessões vigentes dessa conta. Seu aceite foi uma
fixture sintética, sem representar consentimento humano. O navegador foi
encerrado; conta e auditorias técnicas foram preservadas.

Os nove passos do navegador e a conferência independente estão em
`.tmp/painel-publicado-20261027/resultado.json` e
`.tmp/painel-publicado-20261027/verificacao-independente.json`, fora do
versionamento e sem credenciais ou cookies nos relatórios.

Este recorte fecha a conferência funcional do painel sobre os dados
observados. Permanecem para os próximos incrementos a avaliação sistemática de
interface, dispositivos e navegadores, acessibilidade, desempenho e configurações
finais. O resultado não substitui a validação com o orientador.
