# Contraste e compatibilidade — 27/10/2026

Complemento de RNF-04 e da amostra de compatibilidade de RNF-05. Este recorte
mediu contraste, corrigiu falhas visuais e conferiu layouts e teclado em Chrome
e Edge. Não houve alteração de regras de negócio, banco ou dependências.

## Correções realizadas

| Elemento | Antes | Depois |
|---|---|---|
| Texto explicativo no painel azul do login | 4,487:1, abaixo do limiar de 4,5:1 | Branco, 6,045:1 sobre a cor base. |
| Descrições de recursos no login | 3,819:1 | 6,045:1 sobre a cor base. |
| Rodapé do painel azul | 2,696:1 | 6,045:1 sobre a cor base. |
| Placeholders de usuário e senha | 4,481:1 | 6,040:1. |
| Dia selecionado no calendário | 2,084:1; a variável de texto sobre a cor primária não estava definida | Texto branco, 8,245:1. |
| Foco global na navegação | Contorno semitransparente, 1,867:1 sobre branco | Contorno azul sólido; 8,245:1 sobre branco. |
| Foco em controles customizados | Alguns removiam o contorno e dependiam de sombras claras | Contorno explícito de 3 px, preservando os estilos existentes. |
| Borda dos campos do login | Borda clara | Cores já existentes para borda de controles e estado de hover. |

As mudanças deste recorte estão em `static/inventario/css/sigee.css` e na versão
da referência ao CSS em `templates/base.html`. Não houve redesenho das telas.

## Método e limites da medição

Foram utilizadas cores calculadas pelo navegador, composição de transparências
sobre os fundos e luminância relativa sRGB. A comparação usa valores sem
arredondamento; a tabela apresenta valores resumidos. Os critérios de referência
são [contraste de texto do W3C](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
e [contraste de controles e estados](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).

Texto decorativo, controles desabilitados, elementos ocultos e conteúdo marcado
como `aria-hidden` não integram a aprovação final da amostra. A análise não
abrange todos os ícones, gráficos, imagens, estados possíveis ou tecnologias
assistivas do sistema.

No painel azul do login, 6,045:1 é o valor sobre `#3556d8`. Há uma sobreposição
decorativa de gradientes: uma composição conservadora de até 7% de branco sobre
essa base resulta em 5,249:1 com o novo texto branco. Portanto, não se afirma
que cada pixel do fundo tenha exatamente a razão nominal.

## Resultado nos navegadores

Ambiente: Windows, Chrome instalado 156.0.8078.48 e Edge instalado 156.0.4314.42,
executados sem janela visível. Os relatórios registram os respectivos user
agents, incluindo `Edg` no Edge. Ambos usam Chromium; não representam dois
motores independentes. A base foi SQLite local exclusiva, com dados sintéticos.

Em **cada navegador**, foram aprovados:

- 382 amostras de texto em sete estados/telas, além dos dois placeholders do login.
- Sete indicadores de foco: campo de login, mostrar senha, entrar, navegação,
  campo de equipamento, abrir calendário e dia selecionado.
- 40 estados de layout: 13 telas em três larguras e o calendário aberto em 320 px.
- Seis interações: abertura do menu, ciclo reverso de foco, Escape, foco dos
  erros do cadastro, navegação de dias por teclado e retorno ao botão do calendário.

As 13 telas foram login, recuperação de senha, painel, lista e cadastro de
equipamentos, indicadores pedagógicos, usuários, manutenções, histórico, nova
reserva, lista do Operador, retirada e lista de devoluções. As páginas esperadas
retornaram 200 nas 39 consultas por navegador, sem redirecionamento inesperado.
Não foram submetidas reservas, retiradas ou devoluções neste recorte.

Nas larguras verificadas, não houve overflow horizontal global ou controles
fora do documento, excetuando as colunas acessíveis pela rolagem interna das
tabelas. Os testes e a revisão das capturas não identificaram bloqueador visual.
A inspeção de dimensões não substitui a avaliação humana de todo o conteúdo.

## Ampliação e evidências

Os viewports foram 1280 × 800, 640 × 400 e 320 × 200 CSS px: os dois últimos
equivalem ao espaço de layout de uma janela de 1280 × 800 ampliada a 200% e
400%. A verificação de 320 CSS px segue a referência de
[reorganização de conteúdo do W3C](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).

**Não houve aplicação comprovada de zoom nativo.** O atalho automatizado não
alterou o viewport nem a escala. O ensaio verificou a reorganização nas larguras
equivalentes; a ampliação nativa e o uso em dispositivos reais continuam sujeitos
à conferência manual, sem alegação de conformidade WCAG completa.

Relatórios finais: `.tmp/contraste-20261027/`, arquivos `sumario.json`,
`chrome-contrast_after.json`, `edge-contrast_after.json`,
`chrome-compat_after.json` e `edge-compat_after.json`. As capturas locais estão
em `output/playwright/contraste-20261027/`, fora do versionamento.

A captura local `chrome-03-calendario-depois.png` registra a data selecionada
e o foco corrigidos. Ela não integra o pacote do GitHub.

As capturas de contraste do calendário mostram a consulta de feriados em curso;
as capturas posteriores de compatibilidade mostram seu aviso de indisponibilidade.
Isso demonstra a apresentação do estado de contingência, sem estabelecer causa,
validar a resposta normal do provedor ou indicar falha no ambiente publicado.

## Encerramento e pendências

O check do Django e `git diff --check` passaram. Como a mudança foi de CSS e
referência de arquivo estático, a verificação principal foi no navegador; não
houve nova execução de testes de domínio nem medição de cobertura.

As contas locais de QA foram desativadas, suas senhas inutilizadas e sessões
removidas ao final. Servidor e navegadores de QA foram encerrados. A limpeza
está registrada em `encerramento.json` na pasta deste recorte. Não houve deploy
ou acesso ao banco publicado.

Permanecem fora desta amostra Firefox, Safari, leitores de tela, zoom nativo e
dispositivos reais. O WebKit não iniciou por falta da revisão compatível com a
ferramenta; não foram instalados novos navegadores. As medições posteriores de
desempenho estão em [Desempenho das consultas](evidencias-desempenho.md).
A revisão posterior das configurações e da consulta de feriados está em
[Configurações e consulta de feriados](evidencias-configuracoes-feriados.md).
RNF-04 e RNF-05 não são declarados integralmente atendidos por este ensaio de interface.
