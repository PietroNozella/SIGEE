# Interface e acessibilidade básica — 27/10/2026

Primeiro recorte de RNF-04: navegação comum aos três perfis, login, consulta de
equipamentos e formulários de equipamento e reserva. Foram corrigidos problemas
comprovados na interface, sem alterar regras de reserva, permissões ou banco.

## Problemas e correções

| Problema observado | Correção aplicada | Evidência |
|---|---|---|
| No celular, Tab alcançava links da barra lateral escondidos fora da tela. Abrir o menu mantinha o foco atrás dele. | Menu fechado fica oculto e inerte. Ao abrir, recebe identificação de diálogo, foco no botão interno de fechamento e mantém Tab/Shift+Tab dentro da navegação; o fundo fica inerte. | Três perfis, navegação por teclado, foco e estado dos elementos conferidos no navegador. |
| Fechamento do menu precisava devolver o usuário a um controle visível. | Escape, botão de fechar e clique no fundo devolvem o foco ao botão de abertura. Mudar para desktop libera conteúdo e navegação lateral. | Fechamento, navegação entre páginas e transições de largura verificados. |
| Cancelar a saída após mudar de desktop para celular deixava o foco sem destino visível. | Ao fechar a confirmação, o foco volta ao botão de abrir menu quando a barra lateral está inerte. | Caso reproduzido antes e aprovado após a correção. |
| Quantidade bloqueada na reserva não tinha explicação visual. | A mensagem de disponibilidade existente passou a aparecer abaixo do campo, preservando o anúncio por tecnologia assistiva. | Estados inicial, três unidades disponíveis e período incompleto conferidos. |
| A tabela de equipamentos exigia rolagem horizontal sem orientação visível. | Instrução discreta em telas menores informa como acessar colunas e ações. | Instrução visível e rolagem pelo teclado confirmadas. |

Arquivos funcionais alterados: `templates/base.html`,
`static/inventario/js/sigee.js`, `static/inventario/css/sigee.css`,
`templates/inventario/equipamento_lista.html` e
`templates/reservas/reserva_form.html`. Foram atualizadas as versões dos arquivos
estáticos referenciadas no template base. Não foram adicionadas dependências.

## Passos observados e capturas

As capturas são desta execução, com dados fictícios. Os caminhos abaixo são
locais, fora do versionamento; a pasta base é
`output/playwright/interface-20261027/`.

1. **Login — adequado no recorte observado.** Em 320, 390 e 1440 px, os controles
   permaneceram no documento sem rolagem horizontal global ou ausência de
   rótulos detectada pela inspeção de DOM. Capturas aceitas:
   `01-login-320-antes.png` e `01-login-1440-antes.png`.
2. **Menu dos três perfis — corrigido.** O atalho para conteúdo, abertura,
   fechamento, ciclo de foco, confirmação de saída e retorno ao desktop foram
   verificados. Capturas: `08-menu-390-depois.png` e `10-menu-320-depois.png`.
3. **Lista de equipamentos — orientação melhorada.** A tabela mantém rolagem
   interna para preservar suas colunas. Não houve overflow global do documento
   nas larguras medidas. Captura: `11-equipamentos-320-depois.png`.
4. **Cadastro de equipamento — adequado no recorte observado.** Enviar o
   formulário vazio levou o foco ao resumo de erros e identificou campos
   inválidos, sem criar equipamento. Captura: `12-formulario-erros-320-depois.png`.
5. **Reserva — orientação melhorada.** Quantidade bloqueada explica o próximo
   passo; após selecionar equipamento, local e período válido, informa três
   unidades disponíveis e libera o campo. Limpar o período volta a bloquear e
   orientar. Capturas: `13-reserva-320-depois.png` e
   `14-reserva-disponivel-320-depois.png`.
6. **Lista do Operador — adequada no recorte visual observado.** Não foram
   identificados cortes evidentes dos controles na captura de 390 px. As
   interações do menu desse perfil também passaram na rodada final.
   Captura: `07-operador-390-antes.png`.

As capturas citadas são artefatos locais de QA e não integram o pacote do GitHub.
Os resultados e limites permanecem descritos neste documento, sem imagens
incorporadas que dependeriam de arquivos ignorados pelo Git.

## Verificação executada

Ambiente local: servidor Django em `127.0.0.1:8766`, SQLite exclusivo em
`.tmp/interface-20261027.sqlite3` e navegador automatizado HeadlessChrome 156
no Windows. Não foi utilizado o banco publicado. A fixture continha três contas
funcionais, três equipamentos e nomes longos de categoria, tipo/modelo e local
para exercitar o layout. Os aceites eram fixtures técnicas, sem consentimento
humano.

Resultados finais no navegador:

- **78 verificações de navegação aprovadas**, com Administrador, Professor e
  Operador em 390 e 1440 px, mais estados de transição em 320, 991 e 992 px.
- **Seis verificações dos formulários aprovadas**, incluindo foco dos erros e
  explicação visual da disponibilidade em 320 px.
- **Um caso adicional de redimensionamento com diálogo aberto aprovado**.

Nos ensaios iniciais, o roteiro precisou ser ajustado para aguardar eventos de
mudança de largura; os templates do servidor de QA e os arquivos estáticos
também precisaram ser atualizados antes da repetição. Os números acima se
referem somente aos relatórios finais aprovados.

A suíte `inventario usuarios reservas` executou **190 testes em SQLite em
memória: 187 aprovados, três ignorados, sem falhas ou erros**, em 27,794 segundos.
Os ignorados dependem de concorrência em PostgreSQL; não foram reexecutados
nesse banco neste recorte. A última correção no retorno de foco do diálogo foi
verificada no navegador. Não houve nova medição de cobertura.

```powershell
python manage.py test inventario usuarios reservas --settings=config.settings_testes
```

Os relatórios locais estão em `.tmp/interface-20261027/`: `shell_after.json`,
`forms_after.json` e `resize_dialog_after.json`. Os roteiros temporários e a
configuração de QA também permanecem em `.tmp/`, sem integrar o sistema.

Ao encerrar, as três contas locais foram desativadas e receberam senhas
inutilizáveis; suas sessões foram removidas. A base manteve os três equipamentos
sintéticos, sem reservas ou movimentações. O servidor e o navegador de QA foram
encerrados. Esse resultado está em `encerramento.json` na mesma pasta.

## Limites e próximos recortes

Este incremento corrige a navegação móvel e melhora instruções existentes;
**RNF-04 não está integralmente validado**. A inspeção de rótulos foi uma
conferência de DOM, e não uma avaliação completa por leitor de tela.

As medições posteriores de contraste e a amostra de layouts e teclado em Chrome
e Edge estão em [Contraste e compatibilidade](evidencias-contraste-compatibilidade.md).
Permanecem as limitações de zoom nativo, outros navegadores e dispositivos reais
descritas nesse complemento. Não foram medidos tempos de resposta neste recorte.
Não houve deploy; a conferência da versão publicada corrigida dependerá da
publicação autorizada.
