# Configurações e consulta de feriados — 27/10/2026

Este recorte esclareceu a indisponibilidade da BrasilAPI observada no QA,
conferiu configurações locais e sinais públicos da implantação e alinhou a
exigência de TLS na conexão local com o banco. Não foi necessário alterar o
cliente da BrasilAPI ou as regras de reserva.

## Causa verificada da indisponibilidade no QA

O mesmo cliente `reservas/brasilapi.py`, consultando o mesmo ano, apresentou:

| Ambiente de execução | Resultado |
|---|---|
| Sandbox restrito | `URLError`, causado por conexão recusada (`WinError 10061`), em aproximadamente 2.066 ms. |
| Execução com rede autorizada | 14 feriados de 2026, com esquema aceito pelo cliente e Natal presente, em aproximadamente 100 ms. |

A execução restrita utilizava configurações de proxy do ambiente; a execução
autorizada não apresentava esses proxies. O contraste entre as duas execuções
identificou a restrição de rede do QA como causa da falha reproduzida. Não houve
desativação de verificação TLS, troca de endpoint, instalação de certificados
ou alteração de timeout para obter a resposta.

Essa observação não garante disponibilidade permanente do provedor nem prova o
resultado da integração a partir da Vercel. As respostas foram obtidas do
[endpoint público de feriados da BrasilAPI](https://brasilapi.com.br/docs#tag/Feriados-Nacionais)
na execução descrita.

## Fluxo real na interface local

O servidor de QA foi executado com rede autorizada e SQLite exclusivo, usando
as três contas e os três equipamentos fictícios do recorte de interface.

1. A consulta anual retornou HTTP 200, `completa=true` e 14 feriados.
2. O calendário destacou Finados, em 02/11/2026. A data permaneceu selecionável,
   respeitando a regra existente de feriado informativo.
3. A consulta de disponibilidade retornou HTTP 200, três unidades disponíveis
   e a informação de Finados para o período escolhido.
4. O diálogo de confirmação exibiu o aviso informativo. Foi acionado **Voltar**;
   nenhuma reserva ou movimentação foi gravada.

As capturas locais `calendario-feriados-reais.png` e
`confirmacao-feriado-real.png` estão em
`output/playwright/configuracoes-20261027/`. São artefatos de QA fora do
versionamento, sem incorporação de imagens indisponíveis no GitHub.

As duas capturas foram inspecionadas. Os **28 testes existentes de BrasilAPI e
frontend de reservas passaram**, sem falhas ou casos ignorados, em 1,934 s:

```powershell
python manage.py test reservas.tests.BrasilAPITests reservas.tests.ReservaFrontendTests --settings=config.settings_testes
```

Os testes automatizados usam respostas controladas e cobrem, entre outros
casos, resposta válida, erro HTTP, timeout, resposta inválida e contingência.
Eles são complementados pelo ensaio real acima; não representam disponibilidade
do provedor. A suíte completa de 458 testes já executada no recorte de desempenho
não foi repetida, pois não houve alteração de código funcional nesta etapa.

## Configuração local e TLS do banco

A `DATABASE_URL` local não declarava `sslmode`. Foi acrescentado
`sslmode=require`, como já orientava `.env.example`. Antes de salvar o ajuste,
uma conexão com a URL proposta executou somente `SELECT 1`, em transação
somente leitura, e confirmou `ssl_in_use=true`.

Isso passa a exigir cifragem; não significa que as conexões anteriores fossem
necessariamente sem TLS. `require` também não equivale à verificação completa
de identidade do servidor com `verify-full`, conforme a
[documentação de conexão do Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres#ssl-connections).

Somente o `.env` local foi alterado. Ele permanece ignorado pelo Git, sem
credenciais nos relatórios. Não foram alterados dados, tabelas, RLS, senhas do
banco ou variáveis da Vercel. O modo de desenvolvimento local continua explícito;
a ausência de SMTP nesse arquivo não descreve a configuração da hospedagem.

## Implantação e configurações conferidas

| Evidência | Resultado e alcance |
|---|---|
| Login público | HTTP 200 por HTTPS, com HSTS, `X-Frame-Options: DENY` e `nosniff`. |
| Quatro estáticos referenciados pelo login | Bootstrap, CSS do SIGEE, JavaScript do login e ícone da marca responderam 200 por HTTPS. |
| Caminho inexistente | HTTP 404, sem os indicadores de página técnica de debug procurados. Isso não é leitura direta do valor de `DEBUG`. |
| Metadados da Vercel | Implantação `READY`, destino `production`, commit `f812603fe5de221586e4b769ede8b8d51ca32d76`. As alterações locais ainda não estão nesse commit. |
| Variáveis de produção | Presença confirmada de `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` e das nove variáveis de SMTP/recuperação listadas no relatório. Valores não foram descriptografados nem validados. |
| Settings em produção simulada | Com `DEBUG=False` e segredo sintético: redirecionamento HTTPS, cookies seguros, sessão HttpOnly, leitura de `sslmode=require` e fontes estáticas encontrados. Nenhuma conexão ao banco foi aberta nessa simulação. |

A presença das variáveis não comprova valores corretos, entrega de e-mail ou
uso de TLS pelo processo da Vercel. O envio SMTP real não foi testado e nenhum
e-mail foi enviado. Não foi solicitado ao usuário real aceitar documentos ou
alterar credenciais.

A inspeção pelo CLI atingiu o tempo limite; os metadados foram obtidos por GET
na API oficial, com a sessão existente e sem registrar valores de variáveis.
Não houve vínculo novo de projeto ou alteração remota. A ausência de
`vercel.json` no repositório não foi tratada como defeito: a
[integração Django da Vercel](https://vercel.com/docs/frameworks/backend/django#configure-the-django-entrypoint)
documenta detecção por `manage.py` e pelo entrypoint configurado.

O check de produção simulada retornou `security.W004`, porque HSTS não é
definido na aplicação; o ambiente publicado enviou essa política na camada
Vercel. Também retornou `axes.W006`, já silenciado conscientemente pelo projeto
para o controle por nome de usuário sem persistência de IP. Não houve erro de
configuração nessa checagem; ela não substitui a conferência dos valores reais
da hospedagem, conforme o
[checklist de implantação do Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Encerramento e limites restantes

Relatórios e roteiros locais: `.tmp/configuracoes-20261027/`. Os principais
arquivos são `brasilapi-sandbox.json`, `brasilapi-sem_restricao.json`,
`interface-feriados-reais.json`, `tls-local.json`, `publicacao.json`,
`vercel-metadados.json`, `settings.json` e `encerramento.json`.

As contas de QA foram desativadas, receberam senhas inutilizáveis e tiveram
suas sessões removidas. A base manteve três equipamentos, zero reservas e zero
movimentações. Servidor, navegador e inspeção de CLI não permaneceram em
execução. `git diff --check` passou. Não houve commit, push ou deploy.

Antes da validação final na versão publicada, permanecem: conferir os valores
protegidos relevantes na hospedagem sem expor segredos; testar entrega real de
recuperação de senha somente quando autorizada; publicar as alterações após a
revisão do conjunto e repetir a conferência dos fluxos afetados. Não se declara
o sistema integralmente validado em produção por este recorte.
