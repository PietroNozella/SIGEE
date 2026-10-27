# Evidências de retiradas e devoluções — 27/10/2026

Este recorte verifica RF-05/RF-06 e RN-04, RN-08, RN-09, RN-10 e RN-13:
retiradas com e sem reserva, conferência dos patrimônios, devolução parcial e
integral, autorização, duplicidade e preservação dos vínculos. A validação
publicada da devolução com problema e do ciclo de manutenção está no
[recorte separado de manutenção](evidencias-manutencoes.md).

## Testes isolados

Os módulos `movimentacoes` e `manutencoes` executaram **137 testes em SQLite em
memória: 128 aprovados e nove ignorados**, sem falhas ou erros, em 6,575 segundos.
Os ignorados dependem de bloqueio de linhas, indisponível nesse banco.

Em **PostgreSQL 17.6 isolado, os 137 testes passaram**, sem falhas, erros ou casos
ignorados, em 25,754 segundos. Isso inclui cenários de solicitações simultâneas,
rollback de lotes, cancelamento/expiração concorrentes com retirada, devoluções
concorrentes e transições de manutenção. O resultado cobre os cenários existentes,
sem afirmar que todas as combinações possíveis de concorrência foram testadas.

A instância temporária utilizou `127.0.0.1:5439` e o banco de testes
`test_sigee_qa_movimentacoes`, criado e removido pelo Django. O contêiner foi
encerrado ao final. Não foi utilizado o banco publicado pelo runner e não houve
nova medição de cobertura. Para os testes locais comuns:

```powershell
python manage.py test movimentacoes manutencoes --settings=config.settings_testes
```

Esse comando utiliza SQLite e ignora os nove cenários mencionados. Para
executá-los, configurar e conferir uma instância PostgreSQL isolada.

## Validação publicada

Em `https://sigee-psi.vercel.app`, foram utilizados dois Operadores e um Professor
temporários, dois equipamentos e categoria, tipo/modelo e local exclusivos de
QA. Os testes acessaram diretamente os formulários necessários, sem abrir a
lista que sincroniza expiração das reservas anteriores.

| Cenário | Resultado observado |
|---|---|
| Quantidade zero, quantidade divergente dos patrimônios e patrimônio repetido | Rejeitados pelo servidor, sem movimentação ou mudança de situação. |
| Retirada sem reserva pela interface | Duas unidades conferidas no diálogo foram entregues ao Professor de QA; registraram Operador, destinatário, lote comum e situação `EM_USO`. |
| Nova retirada das mesmas unidades em uso | Rejeitada sem duplicar movimentações. |
| Professor tentando gravar retirada ou devolução | Ambos os POST retornaram 403 e preservaram os registros. |
| Devolução parcial por outro Operador | Uma unidade voltou a `DISPONIVEL` e a outra permaneceu `EM_USO`, com o vínculo à retirada e ao destinatário preservado. |
| Devolução repetida ou seleção desatualizada contendo unidade já devolvida | Ambas rejeitadas; a unidade ainda pendente não foi devolvida parcialmente pela tentativa inválida. |
| Conclusão da devolução sem reserva | O Operador confirmou a unidade restante pela interface; ambas ficaram disponíveis. |
| Entrega de reserva antes do início | Rejeitada sem criar movimentação. |
| Entrega de reserva na janela permitida | As duas unidades alocadas foram entregues integralmente pela interface, com lote comum, Professor proprietário e Operador registrados. |
| Repetição da entrega da mesma reserva | Rejeitada sem duplicar registros ou alterar as unidades. |
| Devolução integral do lote reservado | Confirmada pela interface, com retorno das duas unidades à disponibilidade e vínculos à reserva e às retiradas preservados. |
| Histórico filtrado pelo identificador de QA | Exibiu as oito movimentações esperadas: quatro retiradas e quatro devoluções. |

A reserva usada para entrega foi preparada como fixture técnica futura. Após
verificar a rejeição antecipada, apenas seu horário foi ajustado para dois minutos
antes do relógio corrente, com término futuro, permitindo testar a janela de
retirada. Esse preparo não representa criação retroativa pelo fluxo do Professor,
que foi validado separadamente no [recorte de reservas](evidencias-reservas.md).

## Encerramento e limites

Uma conexão independente, em transação somente leitura, confirmou quatro
retiradas, quatro devoluções únicas e oito eventos de auditoria de sucesso.
Cada devolução preservou equipamento, destinatário, reserva, lote e retirada de
origem. As duas devoluções do lote sem reserva foram realizadas por outro
Operador, conforme a regra aprovada. Não houve manutenção criada neste ensaio.

Todas as unidades de QA foram devolvidas antes da inativação. As três contas
foram desativadas, com senhas inutilizáveis e remoção das sessões conhecidas;
os equipamentos, a categoria, o tipo/modelo e o local foram inativados. Os
registros históricos e a auditoria foram preservados. Os aceites dessas contas
foram fixtures sintéticas, sem representar consentimento humano.

A reserva com entrega permanece no estado `ATIVA` previsto pelo modelo atual,
com os vínculos à retirada e à devolução integral preservados. Não foi forçado
um cancelamento após a entrega, operação vedada pela RN-12. Não existe devolução
pendente de QA.

Os campos conferidos dos equipamentos, reservas, movimentações e manutenções
anteriores permaneceram iguais antes e depois da operação. Resultados por etapa,
verificação independente e dados dos testes isolados estão em
`.tmp/movimentacoes-publicadas-20261027/`, fora do versionamento, sem senhas ou
cookies nos relatórios. O navegador exclusivo de QA foi encerrado.

Não foi necessária alteração funcional de código neste recorte. Os testes
publicados não exercitaram solicitações simultâneas, devolução com problema,
acompanhamento de manutenção, desempenho ou acessibilidade.
