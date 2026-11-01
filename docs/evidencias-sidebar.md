# Sidebar automática — 30/10/2026

A navegação compartilhada usa Django Templates, Bootstrap 5, CSS e JavaScript
nativo. Os itens, rotas e condições de permissão existentes foram preservados.
Este incremento implementa o comportamento solicitado para a sidebar, sem
adicionar dependências, alterar regras de negócio ou modificar o banco.

## Comportamento e adaptações

- Acima de 1200 px, a faixa ocupa 72 px e expande para 260 px em 160 ms,
  com `ease-out`. O conteúdo e o cabeçalho reservam sempre apenas 72 px.
- A expansão depende de ponteiro dentro ou foco visível de teclado dentro.
  Cliques comuns não mantêm a expansão por foco residual.
- Os textos permanecem no documento, com opacidade e recorte; os nomes
  acessíveis, títulos dos links e destaque da página atual continuam disponíveis.
- O símbolo SVG e o texto da marca já eram recursos separados. Foram mantidos,
  sem distorção: o símbolo permanece fixo e o texto é revelado na expansão.
- Conforme ajuste solicitado após a primeira implementação, a conta permanece
  no canto superior direito do cabeçalho, com nome e avatar no desktop e somente
  o avatar nas telas menores. Seu menu reúne os documentos legais e a saída por
  POST com CSRF e confirmação. O popover nativo abre abaixo da conta, alinhado à
  direita, e opera independentemente da sidebar. Isso requer um navegador com
  suporte à API Popover.
- Até 1200 px, a faixa dá lugar ao drawer com foco contido e fundo inerte.
  Abrir o drawer fecha o menu da conta e torna o cabeçalho inerte. Escape,
  botão de fechar, clique fora ou navegação interna devolvem o foco ao botão
  de abertura.
- A navegação tem rolagem independente. Em alturas inferiores ao espaço mínimo
  dos controles, a própria sidebar também permite rolagem vertical.
- A preferência por movimento reduzido remove as transições da sidebar.

## Verificação executada

Os 80 testes de `inventario.tests`, `legal.tests` e
`inventario.test_autorizacao` passaram com SQLite em memória na implementação
da sidebar. Após devolver a conta ao cabeçalho, os 30 testes de
`inventario.tests.AutenticacaoTests` e `legal.tests` também passaram:

```powershell
.\.venv\Scripts\python.exe manage.py test inventario.tests legal.tests inventario.test_autorizacao --settings=config.settings_testes --noinput
.\.venv\Scripts\python.exe manage.py test inventario.tests.AutenticacaoTests legal.tests --settings=config.settings_testes --noinput
```

A verificação no Chrome em modo headless usou prévias HTML renderizadas pelo
template Django atual, recursos estáticos reais e contexto sintético dos três
perfis. O conteúdo central era uma fixture de validação. Não foi um ensaio
completo de login e navegação entre páginas de uma sessão real.

Foram conferidos expansão e recolhimento por mouse; passagem para a área dos
textos sem oscilação; saída de foco por teclado;
recolhimento após encerrar todas as condições; drawer em 1200, 375 e 320 px;
retorno ao desktop em 1201 px; ciclo de foco do drawer; fechamento,
cancelamento da saída, movimento reduzido e rolagem em janelas de 320 e 200 px
de altura. Uma conferência com toque emulado validou abertura, conta, saída,
cancelamento e fechamento do drawer. Não houve erros JavaScript no roteiro
principal aprovado.

Após o ajuste da conta, prévias de 1440 e 375 px validaram avatar no cabeçalho,
alinhamento do dropdown, navegação por teclado, retorno do foco ao cancelar a
saída, submissão POST com CSRF interceptada no navegador e independência entre
o menu e a expansão da sidebar. Abrir o drawer fechou o popover e preservou o
ciclo de foco na navegação. Não houve erros JavaScript nesse roteiro.

Uma verificação posterior da página autenticada real identificou o template
antigo ainda em memória no servidor local iniciado sem recarga automática:
o HTML continha `sidebar-account` e referências estáticas `20261030.2`, enquanto
os arquivos em disco já continham a conta no cabeçalho e a versão `20261030.3`.
O servidor de testes foi reiniciado com recarga automática. Após isso, o login
real e o painel em `127.0.0.1:8000` foram validados em 1440 e 375 px: conta apenas
no cabeçalho, dropdown alinhado abaixo do avatar, cancelamento com retorno do
foco e comportamento da sidebar preservado.

Durante 25 quadros de animação, as coordenadas e larguras do conteúdo principal,
da área central, do primeiro ícone e do símbolo da marca permaneceram iguais.
O JavaScript passou em `node --check` e o diff passou em `git diff --check`.
O detector Impeccable não apontou ocorrências nos alvos; sua resolução automática
dos links CSS de Django Templates é limitada, e os estilos foram fornecidos
também como alvos explícitos.

As capturas e os scripts auxiliares estão em `.tmp/`, ignorada pelo Git.

## Como conferir manualmente

1. Em uma página autenticada, use uma janela acima de 1200 px. Passe o mouse
   da faixa de ícones para os textos e depois para o conteúdo; observe que o
   conteúdo permanece imóvel e que a sidebar só recolhe ao sair.
2. Use Tab e Shift+Tab para entrar e sair da navegação. Abra a conta no canto
   superior direito do cabeçalho; a sidebar deve continuar recolhida. Confira
   os documentos e a saída, fechando por Escape ou clique fora. Cancelar a
   confirmação de saída deve devolver o foco à conta no cabeçalho.
3. Reduza a largura para 1200 px ou menos. Abra o drawer; verifique o ciclo
   Tab/Shift+Tab, o botão de fechar, Escape, clique na máscara e seleção de link.
   Volte ao desktop e confira a liberação do fundo.
4. Reduza a altura e role a navegação. Ative movimento reduzido
   no sistema ou nas ferramentas do navegador e confira a ausência de animação.
