# Evidências de utilização pedagógica e indicadores — 27/10/2026

Este recorte verifica RF-10/RF-11 e RN-15/RN-16/RN-17: contexto vinculado à
retirada própria, agrupamento por reserva ou lote, edição até a devolução integral
e consolidação por turma, disciplina e atividade pedagógica.

## Testes isolados

O app `pedagogico` executou **79 testes em SQLite em memória: 75 aprovados e
quatro ignorados**, sem falhas ou erros, em 6,519 segundos. Os ignorados dependem
de bloqueio de linhas e cobrem gravações concorrentes e disputa entre gravação
do contexto e devolução integral, nos fluxos com e sem reserva.

Em **PostgreSQL 17.6 isolado, os 79 testes passaram**, sem falhas, erros ou casos
ignorados, em 24,218 segundos. O ensaio incluiu cadastros, autorização, validações,
vínculos, reenvio, rollback, referências inativas e cálculos dos indicadores.
A instância utilizou `127.0.0.1:5439` e `test_sigee_qa_pedagogico`, criado e
removido pelo Django; o contêiner foi encerrado ao final. Não houve nova medição
de cobertura. Para os testes locais em SQLite:

```powershell
python manage.py test pedagogico --settings=config.settings_testes
```

Esse comando ignora os quatro cenários de concorrência. Eles exigem PostgreSQL
isolado, com conexão conferida antes da execução do runner.

## Cenário publicado

Em `https://sigee-psi.vercel.app`, foram usados Administrador, Operador e dois
Professores temporários, dois equipamentos e referências exclusivas de QA.
Duas turmas, uma disciplina e uma atividade foram cadastradas pela interface.

Os serviços existentes prepararam as retiradas e devoluções das fixtures: um
lote sem reserva e outro com reserva, reutilizando os mesmos dois equipamentos.
A reserva elegível foi criada como fixture técnica na janela de retirada; isso
não representa criação retroativa pelo fluxo do Professor. As interfaces físicas
foram verificadas nos [recortes anteriores](evidencias-movimentacoes.md).
Neste ensaio, cadastro, gravação/edição do contexto, consulta dos indicadores e
inativação das referências foram exercitados pela interface publicada.

| Cenário | Resultado observado |
|---|---|
| Cadastros e retiradas sem contexto | Os novos registros não aumentaram os totais pedagógicos. |
| Campo obrigatório vazio | Turma vazia foi recusada sem criar contexto parcial. |
| Contexto sem reserva | O Professor salvou turma, disciplina, atividade e observação para as duas unidades do lote. |
| Reenvio dos mesmos dados | Preservou IDs e datas; não duplicou registros nem auditorias de sucesso. |
| Edição após devolução parcial | A alteração da turma e da observação foi aplicada às duas unidades, incluindo a já devolvida. |
| Devolução integral | Os dois detalhes ficaram somente para consulta; POST de alteração foi recusado sem mudar o contexto. |
| Contexto com reserva | O Professor salvou o contexto das duas unidades reservadas, mantendo o proprietário e os vínculos físicos. |
| Minhas Utilizações | Reuniu os dois grupos próprios, com e sem reserva, incluindo o lote já encerrado. |
| Outro Professor | GET e POST retornaram 404 nos dois detalhes; sua lista permaneceu vazia. |
| Administrador e Operador tentando alterar contextos | POST negado com 403 nos dois fluxos. |
| Professor e Operador tentando consultar indicadores | GET negado com 403. |
| Inativação das referências | Os totais e os vínculos foram preservados, com indicação de cadastro inativo nas tabelas. |

## Conferência dos números

Os dados anteriores apresentavam **1 utilização, 3 retiradas e 3 equipamentos
distintos**. Depois dos dois lotes de QA, a tela exibiu **3 utilizações,
7 retiradas e 5 equipamentos distintos**. O acréscimo correto foi, portanto,
**2 utilizações, 4 retiradas e 2 equipamentos**, contando cada patrimônio novo
somente uma vez no total, apesar de sua reutilização nos dois lotes.

Cada lote ficou associado a uma turma diferente, usando a mesma disciplina e
atividade. As linhas de QA foram conferidas assim:

| Agrupamento | Utilizações | Retiradas | Equipamentos distintos |
|---|---:|---:|---:|
| Turma A — lote com reserva | 1 | 2 | 2 |
| Turma B — lote sem reserva, após edição | 1 | 2 | 2 |
| Disciplina compartilhada | 2 | 4 | 2 |
| Atividade compartilhada | 2 | 4 | 2 |

Os totais gerais e essas quatro linhas permaneceram iguais após a devolução
integral e a inativação dos cadastros. A conferência independente no banco também
confirmou a preservação dos totais após a inativação técnica dos equipamentos.
Essa persistência corresponde ao histórico de uso, não à disponibilidade atual.

## Encerramento e limites

Uma conexão independente, em transação somente leitura, confirmou quatro
contextos para quatro retiradas, agrupados em dois usos dos mesmos equipamentos,
quatro auditorias de criação e duas de edição. Foram preservados Professor,
referências e observações esperadas, sem alterações nos registros anteriores.

As quatro contas foram desativadas, com senhas inutilizáveis. Os equipamentos,
a categoria, o tipo/modelo, o local e os quatro
cadastros pedagógicos de QA ficaram inativos. Os históricos foram preservados;
não há devolução pendente nem manutenção criada neste recorte. A reserva entregue
mantém o estado previsto pelo modelo, com os vínculos à retirada e à devolução
integral; não foi forçado cancelamento após a entrega.

Os aceites das contas foram fixtures sintéticas, sem representar consentimento
humano. O navegador de QA foi encerrado. Resultados por etapa, dados dos testes
isolados e verificação independente estão em `.tmp/pedagogico-publicado-20261027/`,
fora do versionamento e sem senhas ou cookies nos relatórios.

Não foi necessária correção funcional. Este ensaio não mediu desempenho,
acessibilidade ou concorrência no ambiente publicado e não substitui validação
acadêmica pelo orientador.
