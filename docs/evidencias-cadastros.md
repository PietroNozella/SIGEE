# Evidências de equipamentos e usuários — 27/10/2026

Este recorte verifica os cadastros de RF-01/RF-02, a consulta de equipamentos
de RF-03 e as regras RN-01, RN-06 e RN-18: patrimônio único, importação atômica,
perfis funcionais, inativação e preservação de histórico.

## Testes isolados

Os apps `inventario` e `usuarios` executaram **122 testes em SQLite em memória:
120 aprovados e dois ignorados**, sem falhas ou erros, em 22,307 segundos.
Os ignorados verificam concorrência entre administradores e entre criação de
reserva e desativação de Professor.

Em **PostgreSQL 17.6 isolado, os 122 testes passaram**, sem falhas, erros ou casos
ignorados, em 33,223 segundos. A base incluiu formulários, CSV, autorização,
unicidade, inativação, sessões, auditoria e proteções de contas. A instância usou
`127.0.0.1:5439` e `test_sigee_qa_cadastros`, criado e removido pelo Django;
o contêiner foi encerrado ao final. Não houve nova medição de cobertura.

Para os testes locais em SQLite:

```powershell
python manage.py test inventario usuarios --settings=config.settings_testes
```

Esse comando ignora os dois cenários concorrentes, que exigem PostgreSQL isolado
e conexão explicitamente conferida antes de executar o runner.

## Validação publicada de equipamentos

Em `https://sigee-psi.vercel.app`, foram utilizados Administrador e Operador
temporários, categoria/local exclusivos e um Professor criado pela interface.
Os CSV enviados continham somente dados sintéticos desse namespace de QA.

| Cenário | Resultado observado |
|---|---|
| Cadastro pela interface | Gravou um patrimônio novo, com tipo/modelo, categoria, local e situação esperados. |
| Patrimônio duplicado, patrimônio ausente e categoria ausente | Rejeitados pelo servidor sem novo equipamento. |
| Edição pela interface | Atualizou a descrição e preservou identidade, patrimônio e situação. |
| Patrimônio duplicado na edição | Rejeitado sem alterar a descrição ou o patrimônio anteriores. |
| CSV com uma linha válida e outra com patrimônio já cadastrado | Lote rejeitado integralmente; a linha válida não foi gravada. |
| CSV válido com duas linhas | Gravou exatamente duas unidades, no mesmo tipo/modelo e local da fixture. |
| Inativação de equipamento com histórico | A interface identificou o histórico e confirmou inativação; preservou o equipamento e suas duas movimentações. |
| Professor e Operador tentando gravar | Cadastro, edição, importação e exclusão/inativação por POST retornaram 403 para ambos. |

Para conferir RN-06, os serviços existentes prepararam uma retirada e uma
devolução do primeiro equipamento, destinadas ao Professor de QA. A interface
foi utilizada somente após confirmar que o item possuía histórico e que o diálogo
oferecia inativação. Não houve exclusão definitiva de equipamentos ou contas
no ensaio publicado. A exclusão de equipamento sem histórico permaneceu coberta
pelos testes isolados.

## Validação publicada de usuários e sessões

Foram mantidos dois navegadores de QA: um para o Administrador e outro para o
Professor, posteriormente reutilizado pelo Operador. Isso permitiu testar o
acesso do Professor enquanto o Administrador alterava sua situação.

| Cenário | Resultado observado |
|---|---|
| Professor cadastrado pela interface | Conta ativa, senha verificada pelo hasher do Django, exatamente um grupo `Professor`, sem `is_staff`, `is_superuser` ou permissões individuais. |
| Usuário duplicado, e-mail duplicado, perfil inválido e senha fraca | Rejeitados sem criar contas adicionais. |
| Autodesativação do Administrador | A tentativa não desativou sua conta. |
| Professor e Operador tentando cadastrar/desativar contas | POST negado com 403. |
| Professor com reserva ativa sem retirada | A desativação foi bloqueada, preservando conta ativa e sessão existente. |
| Cancelamento da reserva de QA | Liberou a desativação; o registro da reserva foi preservado como `CANCELADA`. |
| Desativação pela interface | Desativou o Professor e removeu a sessão anterior conferida, preservando movimentações e reserva. |
| Reativação pela interface | Preservou conta, perfil e credencial; não restaurou a sessão antiga. |
| Reuso do cookie anterior | Negado antes e depois da reativação, com redirecionamento ao login. O identificador não foi persistido nos relatórios. |
| Novo login após reativação | Acesso permitido com a credencial original. |
| Lista filtrada por usuários ativos e namespace de QA | Exibiu exatamente as três contas funcionais esperadas. |

A reserva pendente foi fixture técnica futura de uma unidade importada, sem
movimentação. O cancelamento utilizou o serviço existente e ocorreu antes da
desativação válida. Não foram alteradas reservas de outros usuários. As
proteções de último Administrador e contas técnicas foram verificadas no banco
isolado; não houve tentativa de desativar contas reais para reproduzi-las.

## Conferência independente e encerramento

Uma conexão nova, em transação somente leitura, confirmou três equipamentos,
as duas unidades importadas, descrição editada, ausência de gravação parcial,
três contas funcionais sem privilégios técnicos e os vínculos históricos. Foram
conferidas as auditorias do Administrador para cadastro de usuário, desativação,
reativação, cadastro/edição/inativação de equipamento e importação do lote.

Os relatórios registram a remoção da sessão antiga, a exigência de novo login
após reativação e zero sessões conhecidas de QA restantes na limpeza. Nenhum
cookie ou senha foi incluído nos relatórios. A conferência preservou os campos
verificados dos equipamentos, usuários e demais registros anteriores.

Ao final, as três contas foram desativadas e receberam senhas inutilizáveis.
O equipamento com histórico permaneceu inativo; os outros dois foram inativados
tecnicamente, preservando seus registros. Categoria, tipo/modelo e local de QA
também ficaram inativos, sem devoluções pendentes. Não foi necessário encerrar
retiradas pela contingência de limpeza.

Os aceites das contas foram fixtures sintéticas, sem representar consentimento
humano. Os dois navegadores foram encerrados. As evidências por etapa, testes
isolados e conferência independente estão em `.tmp/cadastros-publicados-20261027/`,
fora do versionamento e sem credenciais nos relatórios.

Não foi necessária correção funcional neste recorte. O ensaio publicado não
mediu desempenho, acessibilidade nem envio real de recuperação de senha por
e-mail, e não substitui validação pelo orientador.
