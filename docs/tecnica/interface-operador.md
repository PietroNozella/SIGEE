# Interface do Operador

Modo: **Operate**. A identidade é a do SIGEE existente, com tokens de `sigee.css`, componentes nativos dos templates e ícones locais. As decisões de propósito e limites derivam da conversa de definição do perfil e do escopo em `melhorias-operador.md`.

O início apresenta situação dos equipamentos, reservas para atender hoje, faltas de entrega e devoluções previstas ou vencidas. As listas usam horários e quantidades reais e levam à conferência correspondente. A situação atual do acervo é explicitamente distinta da disponibilidade para reservas futuras. O topo utiliza três cards no padrão do painel administrativo: disponíveis, em uso e em manutenção. O gráfico de barras empilhadas por categoria reutiliza a mesma consulta, template, cores, escala comum e ordenação do Administrador; no Operador, selecionar uma categoria leva à consulta dos equipamentos.

As telas de conferência priorizam Professor, período, local, turma, patrimônios e quantidades. O resumo separa solicitado, entregue, saldo de entrega e devolução. Substituições e entregas complementares ficam ligadas à mesma reserva. O aviso de entrega parcial exige comunicação ao Professor antes da confirmação.

Meus dados é uma consulta da própria conta, acessível no menu do usuário. Não permite alteração ou exclusão direta. Documentos legais permanecem em um grupo próprio.

Em desktop, os três indicadores ficam no topo. A composição abaixo usa duas colunas independentes: gráfico por categoria e pendências de entrega à esquerda; entregas de hoje e devoluções à direita. Os blocos seguem a altura de seu conteúdo, sem aguardar o término de uma linha compartilhada com a outra coluna. A proporção 1,35 para 1 e o intervalo de 24 px preservam a grade visual do Administrador. Abaixo de 1200 px, as colunas se empilham na ordem do documento: gráfico, pendências, entregas e devoluções, com a mesma sequência para teclado e leitura assistiva. Em celular, as seções se empilham; tabelas possuem região de rolagem, botões mantêm texto e filtros recebem rótulos. Estados vazios, falta de unidades, prazo encerrado, manutenção e conta inativa possuem mensagens específicas.
