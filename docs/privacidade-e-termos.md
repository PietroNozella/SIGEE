# Termos de Uso, privacidade e aceite

Este documento descreve a implementação do `RS-12` no SIGEE e relaciona os dados tratados, as finalidades, os controles adotados e as evidências verificáveis no repositório. O Termo de Uso e a Política de Privacidade são apresentados como documentos do produto e não identificam integrantes do projeto como agentes de tratamento.

## Responsabilidades

A definição de controlador e operador depende da atuação concreta de cada agente, e não apenas do nome do software. No modelo previsto para o SIGEE, a instituição que adota o sistema, define as finalidades e decide como os dados serão utilizados exerce o papel de controladora. Fornecedores que tratem dados em seu nome devem ter suas responsabilidades definidas antes da implantação institucional.

O SIGEE não presume uma base legal única para todos os tratamentos. A instituição controladora deve identificar e documentar a hipótese aplicável a cada finalidade antes de utilizar dados reais.

## Dados e finalidades representados no sistema

| Categoria | Dados representados | Finalidade no SIGEE | Evidência atual |
|---|---|---|---|
| Conta e perfil | Nome, sobrenome, e-mail, nome de usuário, situação da conta, grupo funcional, datas técnicas e senha protegida por hash | Identificar e autenticar o usuário, administrar contas e aplicar permissões | `usuarios/forms.py`, Django `User`, `Group` e `Permission` |
| Sessão e proteção de formulários | Identificador de sessão e token CSRF em cookies técnicos | Manter a sessão autenticada e impedir requisições forjadas | `config/settings.py` e middlewares do Django |
| Auditoria | Conta responsável, código da ação, resultado, data e hora, entidade e identificador do registro afetado | Segurança, rastreabilidade e apuração de ações relevantes | `auditoria/models.py`, `auditoria/services.py` e `auditoria/eventos.py` |
| Movimentação | Equipamento, operador, destinatário, tipo, data e hora, vínculo com retirada e observação | Preservar o histórico de retirada e devolução | `movimentacoes/models.py` |
| Aceite dos documentos | Conta, versão dos Termos, versão da Política e data e hora | Comprovar quais documentos foram apresentados e confirmados | `legal/models.py` e `legal/services.py` |

Campos livres de inventário e movimentação não devem ser utilizados para registrar dados pessoais excessivos ou dados pessoais sensíveis sem necessidade e autorização institucional.

## Fluxo implementado

1. O Termo de Uso e a Política de Privacidade podem ser consultados sem autenticação.
2. A tela de login contém links para os dois documentos.
3. Depois da autenticação, uma conta sem aceite vigente é encaminhada para `/aceite/` antes de acessar as áreas internas.
4. O usuário precisa aceitar os Termos e confirmar a leitura da Política.
5. O sistema armazena a conta, as duas versões e a data e hora em um registro protegido contra alteração e exclusão pela interface administrativa.
6. O aceite gera o evento `DOCUMENTOS_LEGAIS_ACEITOS` na auditoria.
7. Uma alteração da versão configurada exige nova confirmação.
8. As áreas autenticadas mantêm links permanentes para os documentos.

## Aceite dos documentos e consentimento

O registro implementado comprova o aceite dos Termos de Uso e a ciência da Política de Privacidade. Ele não deve ser descrito como uma autorização genérica para qualquer tratamento de dados pessoais.

Quando a instituição adotar o consentimento como hipótese legal para uma finalidade específica, deverá obter uma manifestação livre, informada, inequívoca e vinculada àquela finalidade, além de oferecer mecanismo de revogação. Esse eventual consentimento específico não é substituído pela confirmação geral implementada no SIGEE.

## Medidas implementadas

- autenticação e hash de senha pelos recursos nativos do Django;
- autorização no servidor com grupos e permissões;
- proteção CSRF nos formulários `POST`;
- cookies de sessão e CSRF marcados como seguros quando `DEBUG=False`;
- redirecionamento para HTTPS quando `DEBUG=False`;
- validação de entradas no servidor;
- minimização dos registros de auditoria, sem senha, hash, token, conteúdo de formulário ou termos pesquisados;
- proteção das referências de auditoria e aceite com `PROTECT`;
- bloqueio de inclusão, edição e exclusão de aceites pelo Django Admin;
- controle de versão dos documentos e nova confirmação após atualização.

Essas medidas reduzem riscos, mas não substituem a configuração segura da infraestrutura, o controle institucional de acessos, a definição de prazos de retenção, o atendimento aos titulares e a resposta a incidentes.

## Evidências automatizadas

Os testes de `legal/tests.py` verificam:

- acesso público ao Termo e à Política;
- links na tela de login;
- bloqueio das áreas internas antes do aceite;
- obrigatoriedade das duas confirmações;
- persistência da conta, versões e data e hora;
- rejeição de redirecionamento externo;
- exigência de novo aceite após mudança de versão;
- ausência de duplicidade para a mesma combinação de versões;
- registro do evento de auditoria;
- proteção do aceite e bloqueio de alterações no Django Admin.

Em 11 de setembro de 2026, a suíte integrada foi executada com SQLite isolado para testes:

```powershell
$env:DATABASE_URL=''
.\.venv\Scripts\python.exe manage.py test
```

Resultado observado:

```text
Ran 102 tests
OK
System check identified no issues (0 silenced).
```
