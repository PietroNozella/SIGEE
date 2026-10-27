# Evidências de reservas — 27/10/2026

Este recorte verifica RF-04 e as regras RN-02, RN-03, RN-07, RN-12 e RN-19:
criação de reservas próprias, disponibilidade, conflitos e cancelamento.
Não inclui retirada, devolução ou o ciclo de manutenção.

## Testes em bancos isolados

A execução inicial em SQLite em memória aprovou os 67 testes existentes do app
`reservas`, sem falhas ou erros, em 6,156 segundos.

Foi acrescentado `reservas/test_concorrencia.py`: dois Professores, em conexões
distintas sincronizadas por uma barreira, solicitam simultaneamente as duas
unidades do mesmo tipo/local e período. O resultado exigido e observado foi uma
solicitação aprovada e outra recusada por quantidade indisponível, com uma única
reserva de duas unidades, dois vínculos físicos distintos e um evento de criação.
Não houve alocação duplicada nem reserva parcial.

Com esse teste, os **68 testes de reservas passaram em PostgreSQL 17.6 isolado**,
sem falhas, erros ou casos ignorados, em 10,284 segundos. A instância temporária
usou `127.0.0.1:5439` e o banco de testes `test_sigee_qa_reservas`; o Django criou
e removeu esse banco. O contêiner foi encerrado ao final. Esse ensaio não executou
solicitações simultâneas no ambiente publicado e não mediu cobertura.

Para os testes locais em SQLite:

```powershell
python manage.py test reservas --settings=config.settings_testes
```

O teste de concorrência exige suporte a `select_for_update` e é ignorado no
SQLite. Para exercitá-lo, utilizar PostgreSQL isolado com conexão explicitamente
conferida; não usar o banco publicado como destino do runner de testes.

## Validação no ambiente publicado

Em `https://sigee-psi.vercel.app`, foram utilizados dois Professores temporários
e duas unidades físicas de QA, em categoria, tipo/modelo e local exclusivos.
A pré-verificação e as verificações entre etapas confirmaram a ausência de
reservas sem retirada que exigissem expiração nos 30 minutos seguintes, evitando
a sincronização das reservas anteriores durante o ensaio.

| Cenário | Resultado observado |
|---|---|
| Quantidade acima do estoque, quantidade zero, data passada, fim de semana e término igual ao início | Cinco submissões diretas autenticadas foram rejeitadas com erros de validação; nenhuma reserva foi criada. |
| Criação pela interface | O Professor A consultou duas unidades disponíveis e confirmou uma reserva de duas unidades no diálogo; o banco confirmou o proprietário e os dois vínculos. |
| Conflito no mesmo período | Para o Professor B, a disponibilidade passou a zero e a tentativa de gravação foi recusada, sem reserva parcial. |
| Período adjacente | O intervalo que começava exatamente no término da reserva manteve duas unidades disponíveis. |
| Proteção da reserva alheia | O cancelamento por outro Professor retornou 404 e preservou a reserva; ela não apareceu na lista própria desse Professor. |
| Cancelamento por GET | A requisição foi recusada com HTTP 405. |
| Cancelamento pelo proprietário | O Professor A cancelou pela interface, com confirmação e mensagem de sucesso; o banco confirmou a situação `CANCELADA`. |
| Reutilização após cancelamento | O Professor B encontrou novamente duas unidades disponíveis e confirmou uma nova reserva, pela interface, para o mesmo período. |

O calendário e os diálogos de confirmação foram utilizados nas duas criações.
Um aviso informativo de feriados ficou visível, sem impedir as confirmações.
Essa observação, isoladamente, não comprova sucesso da consulta externa: o
diálogo também apresenta aviso quando a consulta está indisponível.

## Encerramento e limites

As duas reservas sintéticas permaneceram canceladas: a primeira pela interface,
a segunda pelo serviço de cancelamento durante a limpeza técnica. As duas contas
foram desativadas, com senhas inutilizáveis e remoção das sessões conhecidas.
Os equipamentos, o tipo/modelo, a categoria e o local de QA foram inativados.
Os registros e a auditoria foram preservados. Os aceites dessas contas foram
preparados como fixtures sintéticas; não representam consentimento humano.

Uma conexão independente, em transação somente leitura, confirmou o encerramento,
os dois eventos de criação e os dois de cancelamento, a ausência de movimentações
ou manutenções dos equipamentos de QA e a preservação dos estados e campos
conferidos dos equipamentos e reservas anteriores. Os resultados por etapa estão
em `.tmp/reservas-publicadas-20261027/`, fora do versionamento e sem senhas ou
cookies nos relatórios.

Não foi necessária alteração funcional nas regras ou na interface neste recorte.
Os resultados não substituem as validações dos demais módulos, desempenho,
acessibilidade ou aprovação do orientador.
