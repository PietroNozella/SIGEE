# Melhorias do perfil Operador

Escopo acordado: ampliar a informação operacional, mantendo o design system, Django Templates e as responsabilidades administrativas. Desenvolvimento na branch local `melhoria/perfil-operador`, em etapas com commits próprios.

## Etapas

1. Corrigir a apresentação de equipamentos inativos e restringir o contexto pedagógico do Operador à turma, inclusive no histórico.
2. Permitir consulta e abertura de manutenção pelo Operador; manter início e conclusão com o Administrador. Tentar substituir automaticamente patrimônios afetados nas reservas ativas, respeitando tipo, local e conflitos do período, com histórico da troca.
3. Permitir entrega parcial por indisponibilidade, comunicação ao Professor e entrega complementar. Separar unidades solicitadas, entregues, pendentes de entrega e pendentes de devolução; preservar a reserva quando faltar substituto. O saldo de entrega pode ser atendido até o fim do período reservado, sem encerrar devoluções físicas pendentes.
4. Criar início operacional com situação dos equipamentos, entregas, devoluções e pendências; adicionar Meus dados ao menu da conta, somente para consulta, com orientação de atendimento pelo Administrador.
5. Revisar organização, estados e responsividade das telas afetadas, validar os fluxos e atualizar somente os trechos correspondentes da documentação e da monografia no Notion.

## Critérios transversais

- Equipamento inativo nunca deve ser apresentado como disponível para uso nem escolhido para reserva, entrega ou substituição.
- A substituição altera a unidade vinculada à reserva; não renumera o patrimônio do equipamento.
- Uma troca não modifica registros de entregas já realizadas.
- O Operador consulta informações operacionais e turma, sem disciplina, atividade ou observações pedagógicas.
- Nenhuma etapa publica mudanças ou envia notificações externas. A comunicação da entrega parcial ocorre na interface e pelo atendimento do Operador.
- Evidências locais não comprovam concorrência em PostgreSQL nem resultados de uso institucional.

## Situação e verificação — 5 de novembro de 2026

As cinco etapas foram concluídas na branch local. O início usa o design system existente e concentra atendimento, pendências e devoluções. No celular, a conferência mantém patrimônio e condição de entrega visíveis, e as unidades do inventário apresentam local, situação e ação sem rolagem horizontal.

- Suíte inicial: 475 testes, com 16 ignorados no SQLite.
- Suíte ao concluir as cinco etapas: 506 testes, com 16 ignorados no SQLite por exigirem funcionalidades do PostgreSQL; nenhum erro ou falha.
- Após o último refinamento visual: 17 testes do inventário aprovados.
- `manage.py check` sem novos problemas e `makemigrations --check --dry-run` sem alterações pendentes.
- Revisão visual em 1440 × 1000 e 390 × 844, com prévia e dados fictícios em SQLite separado. Foi confirmado no navegador o fluxo de entrega parcial, com uma unidade entregue e outra pendente.
- O detector do Impeccable não retornou achados nos arquivos analisados. A resolução automática de links CSS dos templates Django é limitada; a conferência no navegador complementou essa análise.
- A monografia no Notion recebeu alterações pontuais nos capítulos 3 e 4 e no Apêndice A, somente nas descrições, regras e instruções afetadas. Os registros históricos de resultados não foram reescritos.

## Atualização do ambiente

As migrations `reservas.0007`, `movimentacoes.0005` e `usuarios.0004` criam o histórico das substituições, protegem a unicidade das entregas e concedem consulta/abertura de manutenção ao Operador. Foram verificadas no banco isolado. O PostgreSQL configurado no ambiente não foi alterado; as migrations precisam ser aplicadas antes de executar a versão atualizada nesse banco. O comando `configurar_perfis` continua idempotente.

## Refinamento do início

O resumo foi padronizado em três cards com o estilo do Administrador, seguido do gráfico de situação por categoria. A consulta e o template do gráfico são compartilhados entre os perfis, com inativos excluídos, escala comum e ordenação. A seleção de categoria no Operador abre os equipamentos correspondentes. Foram aprovados 34 testes direcionados ao início e ao painel administrativo, incluindo comparação dos dados entre os perfis.

O início foi reorganizado em leitura em Z, com três indicadores no topo e duas linhas na grade do Administrador: gráfico por categoria ao lado das entregas de hoje; pendências de entrega ao lado das devoluções. O gráfico passa a ocupar somente a coluna esquerda em desktop, mantendo o empilhamento responsivo.

O refinamento de densidade substituiu as duas linhas do layout em Z por duas colunas independentes. Gráfico e faltas de entrega ficam à esquerda, entregas do dia e devoluções à direita. Isso permite que o próximo bloco de cada coluna comece imediatamente após o anterior, evitando a lacuna ao lado do gráfico. As linhas de devolução mantêm informação e ação lado a lado em desktop e se empilham no celular.

## Revisão dos testes — 6 de novembro de 2026

Os testes novos de tela foram reduzidos de 11 para 5 cenários, concentrando a cobertura em acesso, dados pessoais, contexto do Operador e disponibilidade. Foram retiradas verificações de textos da interface e cenários de consulta dispensáveis; as restrições de perfil em Meus dados foram reunidas ao teste da própria conta. Os 21 cenários de manutenção e entrega foram preservados, incluindo substituição, conflitos, entrega parcial, complementação e integridade transacional. Nenhum comportamento da aplicação foi alterado nesta revisão.

A suíte completa executou 501 testes sem erros ou falhas, com 16 ignorados por dependerem de funcionalidades do PostgreSQL. O histórico local foi consolidado em três commits: fluxos operacionais; início e telas do Operador; documentação. A branch `backup/perfil-operador-antes-organizacao` preserva os oito commits anteriores.
