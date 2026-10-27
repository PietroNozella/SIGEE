# Desempenho das consultas — 27/10/2026

Recorte de RNF-05: verificar se as consultas principais respondem em até três
segundos na base de testes. Foi encontrado e corrigido um gargalo real na
expiração de reservas. O critério foi atendido nas consultas e na carga local
descritas abaixo; o resultado não estabelece capacidade ou latência em produção.

## Problema e correção

A rotina `expirar_reservas_vencidas()` percorria todas as reservas ativas com
início anterior à tolerância, inclusive as que já tinham retirada registrada.
Para cada uma, abria uma transação, buscava o registro com bloqueio e consultava
a existência da retirada, concluindo que a reserva deveria ser preservada.

Com cinco mil reservas históricas nesse estado, as páginas do Professor e do
Operador repetiam mais de dez mil consultas SQL por acesso. O modelo existente
mantém essas reservas como `ATIVA` após a retirada; a otimização não altera esse
ciclo de vida.

Em `reservas/services.py`, a seleção inicial agora exclui no próprio banco as
reservas com uma `RETIRADA` vinculada, usando `NOT EXISTS` pelo ORM. Para os
candidatos restantes, permanecem a transação, o bloqueio `select_for_update`
e a revalidação da regra antes da expiração. Não houve migration, índice novo,
dependência ou mudança das regras de tolerância, disponibilidade e auditoria.

O diagnóstico usou Django Client e instrumentação das chamadas SQL, incluindo
autenticação e renderização. É distinto da medição HTTP posterior:

| Consulta | SQL antes → depois | Tempo antes → depois |
|---|---:|---:|
| Minhas Reservas — Professor | 10.032 → 32 | 23.011,7 → 64,1 ms |
| Reservas para retirada — Operador | 10.029 → 29 | 22.729,7 → 50,2 ms |

## Ambiente e dados

- Windows 11, Intel Core i5-12400F, 12 processadores lógicos.
- Python 3.12.14, Django 5.2.17, PostgreSQL 17.6 em contêiner local.
- Docker com 12 CPUs e aproximadamente 15,53 GiB de memória disponíveis ao engine;
  isso não representa consumo ou reserva exclusiva desses recursos.
- Servidor Django local em `127.0.0.1:8767`, `DEBUG=False`, conexão com banco
  exclusivo em `127.0.0.1:5439/sigee_qa_desempenho` e `CONN_MAX_AGE=0`.
- Fixture sintética: 2.000 equipamentos, 52 contas funcionais, 5.900 reservas,
  11.800 itens de reserva, 20.080 movimentações, 1.000 contextos pedagógicos,
  50 manutenções abertas e 80 retiradas pendentes. Das reservas, cinco mil
  permaneciam ativas com retirada histórica, exercitando o gargalo identificado.

Os dados foram criados como fixtures técnicas para esta medição; não representam
volume real declarado pela instituição nem um ensaio de todos os fluxos de
cadastro. Os aceites eram sintéticos. Não foi utilizado o banco publicado.

## Medição HTTP sem concorrência

Cada consulta recebeu uma primeira requisição e dez repetições: **132 respostas
HTTP**, todas com status 200 e marcador de conteúdo esperado. Redirecionamentos
ao login não foram aceitos. Foi medido o intervalo entre enviar a requisição e
ler o HTML completo, sem instrumentação SQL. Login e carregamento de arquivos
estáticos não integram esses tempos.

A mediana considera as dez repetições; o máximo inclui também a primeira
requisição. Não se afirma que a primeira requisição tenha caches frios. Todas
as amostras ficaram abaixo de 3.000 ms:

| Perfil / consulta | Mediana (ms) | Máximo (ms) |
|---|---:|---:|
| Administrador — painel | 121,8 | 251,2 |
| Administrador — equipamentos | 83,5 | 107,6 |
| Administrador — consulta de reservas | 83,0 | 100,6 |
| Administrador — manutenções | 67,7 | 97,2 |
| Administrador — histórico | 158,6 | 164,3 |
| Administrador — indicadores pedagógicos | 82,8 | 94,6 |
| Professor — equipamentos | 69,8 | 103,3 |
| Professor — Minhas Reservas | 83,3 | 115,2 |
| Professor — utilizações pedagógicas | 75,6 | 93,9 |
| Operador — equipamentos | 97,7 | 141,1 |
| Operador — reservas para retirada | 79,4 | 97,4 |
| Operador — devoluções pendentes | 110,8 | 126,4 |

## Carga local com Postman

Postman CLI 1.76.0, runner local, perfil fixo com **três usuários virtuais por
um minuto solicitado**. O relatório observou 64 segundos no total. A sequência
continha quatro GETs autenticados: painel, Minhas Reservas, reservas para
retirada e indicadores pedagógicos. Cada requisição verificava status 200 e
conteúdo esperado. Não houve escrita de reservas, retiradas ou devoluções.

| Métrica | Resultado |
|---|---:|
| Requisições | 1.225 |
| Taxa observada | 19,14 requisições/s |
| Média | 95 ms |
| p95 | 134 ms |
| Máximo | 217 ms |
| Erros de transporte/scripts e falhas de asserção | 0 |

Os gates `p95 < 3000 ms` e `error_rate < 1%` passaram, com saída 0. O resultado
também apresentou zero erros e máximo inferior a três segundos. O relatório
indica `recorded=false`: o ensaio não foi registrado em workspace remoto.
Não houve carga contra Vercel, Supabase ou provedor de feriados.

## Regressão e conferência

O teste novo em `reservas/tests.py` compara a quantidade de consultas ao
processar uma e vinte reservas históricas com retirada/devolução. Falhou antes
da correção, com cinco versus 81 consultas, e passou depois. Também verifica
preservação do estado e ausência de auditorias de expiração indevidas. Os cinco
testes específicos de expiração passaram em SQLite.

A suíte completa executou **458 testes em PostgreSQL isolado, todos aprovados,
sem falhas, erros ou casos ignorados**, em 99,728 segundos. O Django criou e
removeu `test_sigee_qa_desempenho`, separado do banco do benchmark. A execução
incluiu os testes concorrentes existentes. Não houve nova medição de cobertura.

Uma conferência independente confirmou as contagens da fixture, as cinco mil
reservas históricas preservadas, zero reservas expiradas indevidamente, as 80
retiradas pendentes e a remoção do banco de testes. A revisão técnica não
identificou bloqueador no diff de serviço e teste.

Os relatórios locais estão em `.tmp/desempenho-20261027/`: `ambiente.json`,
`diagnostico_antes.json`, `diagnostico_depois.json`, `http_depois.json`,
`postman-depois.ndjson` e `verificacao-final.json`. Os roteiros de preparação,
medição e carga também ficam em `.tmp/`, fora do versionamento. Sessões de QA
foram removidas dos relatórios; a coleção com cookies e o arquivo privado de
sessões foram descartados no encerramento.

## Limites e encerramento

O servidor e o gerador de carga rodaram na mesma máquina. Foi utilizado
`runserver` com threads, não a infraestrutura de produção. Os números não
definem limite de usuários, SLA, comportamento pela internet, tempo de pintura
no navegador ou capacidade de Vercel/Supabase.

Endpoints com consulta externa de disponibilidade/feriados não integraram a
carga. A investigação posterior da indisponibilidade e das configurações está
em [Configurações e consulta de feriados](evidencias-configuracoes-feriados.md).
Esse complemento não transforma a medição local em garantia de desempenho publicado.

O servidor foi encerrado e o contêiner PostgreSQL temporário foi parado e
removido com sua base sintética. Não houve alteração do banco publicado,
commit, push ou deploy neste recorte.
