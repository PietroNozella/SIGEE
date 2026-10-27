# Evidências de devolução com problema e manutenção — 27/10/2026

Este recorte verifica RF-07, sua integração à devolução de RF-06 e as regras
RN-05, RN-06 e RN-14: identificação do problema por patrimônio, indisponibilidade,
abertura automática ou manual e conclusão com preservação do histórico.

## Base de testes automatizados

O [recorte anterior](evidencias-movimentacoes.md) já executou conjuntamente
`movimentacoes` e `manutencoes`: **137 testes aprovados em PostgreSQL 17.6
isolado**, sem falhas, erros ou casos ignorados. Essa execução incluiu abertura,
início, conclusão, resultados reparado/sem reparo, autorização, reversão de lotes,
restrições do banco e três cenários concorrentes de manutenção.

Como os módulos permaneceram sem alteração funcional, essa evidência foi
reaproveitada. Não houve nova execução dessa suíte nem medição de cobertura
neste recorte. A nova evidência abaixo corresponde à interface e ao servidor
publicados, com conferências independentes no banco do projeto.

## Cenários publicados

Em `https://sigee-psi.vercel.app`, foram usados Administrador, Operador e Professor
temporários, dois equipamentos e categoria, tipo/modelo e local exclusivos de QA.
O Operador retirou as duas unidades para o Professor e confirmou uma devolução
mista: uma unidade normal e outra com defeito.

| Cenário | Resultado observado |
|---|---|
| Problema sem descrição | Rejeitado, sem devolução ou manutenção gravada. |
| Problema informado para uma unidade não recebida | Rejeitado, sem gravação parcial. |
| Devolução mista pela interface | As duas unidades foram recebidas; somente a defeituosa gerou manutenção `PENDENTE` e ficou em `MANUTENCAO`. A outra voltou a `DISPONIVEL`. |
| Rastreabilidade automática | A intervenção registrou o Operador responsável e a devolução de origem, vinculada à retirada e ao equipamento corretos. |
| Operador e Professor tentando abrir, iniciar ou concluir manutenção | Os seis POST foram negados com 403, preservando as intervenções. |
| Abertura manual pelo Administrador | A segunda unidade, disponível, recebeu manutenção pendente sem vínculo de devolução, com o Administrador como responsável. |
| Abertura duplicada | Rejeitada nos dois equipamentos; permaneceram somente as duas intervenções esperadas. |
| Conclusão antes do início | Rejeitada; a intervenção permaneceu pendente. |
| Início por GET | Rejeitado com 405. |
| Início pela interface | O Administrador iniciou as duas intervenções, que passaram a `EM_ANDAMENTO`, preservando os responsáveis pela abertura. |
| Conclusão sem descrição da solução | Rejeitada, preservando estado e data de início. |
| Disponibilidade durante manutenção | A consulta publicada de retirada retornou zero unidades e a tentativa de retirar uma delas foi rejeitada, sem nova movimentação. |
| Conclusão como reparado | Confirmada pela interface; a unidade voltou a `DISPONIVEL` e permaneceu ativa antes da limpeza de QA. |
| Conclusão sem possibilidade de reparo | Confirmada pela interface; a unidade foi inativada, mantendo situação `MANUTENCAO` e histórico. |
| Tentativa de alterar conclusão encerrada | Rejeitada; o resultado anterior foi preservado. |
| Histórico e disponibilidade finais | A lista filtrada exibiu as duas intervenções concluídas, e somente a unidade reparada apareceu na disponibilidade de retirada. |

A consulta publicada de disponibilidade utilizada neste ensaio foi a de
retirada. O bloqueio de reserva durante manutenção integra a base automatizada
citada acima; não houve nova tentativa de reserva publicada neste recorte.

## Verificação independente e encerramento

Uma nova conexão, em transação somente leitura, confirmou:

- duas intervenções concluídas: a automática como `REPARADO`, a manual como
  `SEM_REPARO`, com origens distintas e responsáveis corretos;
- datas de abertura, início e conclusão presentes e ordenadas, com as descrições
  de conclusão preservadas;
- dois eventos de abertura, dois de início e dois de conclusão de manutenção,
  além dos quatro eventos de sucesso das duas retiradas e duas devoluções;
- ausência de devoluções ou manutenções pendentes de QA;
- preservação dos campos conferidos dos equipamentos, reservas, movimentações e
  manutenções anteriores.

As transições de manutenção foram concluídas pela interface. Não foi necessário
usar os procedimentos de contingência da limpeza para devolver unidades ou
encerrar intervenções. Ao final, as três contas receberam senhas inutilizáveis e
foram desativadas, com remoção das sessões conhecidas. Equipamentos, categoria,
tipo/modelo e local de QA foram inativados; os históricos e a auditoria foram
preservados. A inativação técnica final da unidade reparada ocorreu somente
depois de confirmar sua disponibilidade funcional.

Os aceites das contas foram fixtures sintéticas, sem representar consentimento
humano. O navegador exclusivo de QA foi encerrado. Resultados por etapa e a
verificação independente estão em `.tmp/manutencoes-publicadas-20261027/`, fora
do versionamento e sem senhas ou cookies nos relatórios.

Não foi necessária alteração funcional de código. O ensaio publicado não mediu
desempenho, acessibilidade ou concorrência e não representa validação acadêmica
pelo orientador.
