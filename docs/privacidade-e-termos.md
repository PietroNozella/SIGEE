# Termos de Uso, privacidade e aceite

Este documento descreve a implementação do `RS-12` no SIGEE e relaciona os dados tratados, as finalidades, os controles adotados e as evidências verificáveis no repositório. O Termo de Uso e a Política de Privacidade são apresentados como documentos do produto. A identificação definitiva da controladora e dos demais agentes depende da implantação concreta.

## Responsabilidades

A definição de controlador e operador depende da atuação concreta de cada agente, e não apenas do nome do software. No modelo previsto para o SIGEE, a instituição que adota o sistema, define as finalidades e decide como os dados serão utilizados exerce o papel de controladora. Fornecedores que tratem dados em seu nome devem ter suas responsabilidades definidas antes da implantação institucional.

O SIGEE não presume uma base legal única para todos os tratamentos. A instituição controladora deve identificar e documentar a hipótese aplicável a cada finalidade antes de utilizar dados reais.

## Dados e finalidades representados no sistema

O inventário completo, incluindo conta, sessão, proteção contra abuso, recuperação de senha, reservas, movimentações, auditoria, aceite, campos livres, infraestrutura e fornecedores, está em [Governança e inventário de dados pessoais](governanca-dados-pessoais.md). Campos livres não devem ser usados para registrar dados pessoais excessivos ou sensíveis sem necessidade e autorização institucional.

## Fluxo implementado

1. O Termo de Uso e a Política de Privacidade podem ser consultados sem autenticação.
2. A tela de login contém links para os dois documentos.
3. Depois da autenticação, uma conta sem aceite vigente é encaminhada para `/aceite/` antes de acessar as áreas internas.
4. O usuário precisa aceitar os Termos e confirmar a leitura da Política.
5. Antes de registrar o aceite, o servidor compara as versões enviadas pelo formulário com as versões vigentes. Se houver mudança, exige nova leitura e confirmação; caso contrário, armazena a conta, as duas versões e a data e hora em um registro protegido contra alteração e exclusão pela interface administrativa.
6. O aceite gera o evento `DOCUMENTOS_LEGAIS_ACEITOS` na auditoria.
7. Uma alteração da versão configurada exige nova confirmação.
8. As áreas autenticadas mantêm links permanentes para os documentos.

## Aceite dos documentos e consentimento

O registro implementado comprova o aceite dos Termos de Uso e a ciência da Política de Privacidade. Ele não deve ser descrito como uma autorização genérica para qualquer tratamento de dados pessoais.

Quando a instituição adotar o consentimento como hipótese legal para uma finalidade específica, deverá obter uma manifestação livre, informada, inequívoca e vinculada àquela finalidade, além de oferecer mecanismo de revogação. Esse eventual consentimento específico não é substituído pela confirmação geral implementada no SIGEE.

## Medidas implementadas

- autenticação e hash de senha pelos recursos nativos do Django;
- bloqueio temporário após tentativas repetidas de login, por nome de usuário e sem persistência do endereço IP pelo SIGEE;
- autorização no servidor com grupos e permissões;
- proteção CSRF nos formulários `POST`;
- cookies de sessão e CSRF com `SameSite=Lax`, sessão inacessível a JavaScript e marcação `Secure` quando `DEBUG=False`;
- redirecionamento para HTTPS quando `DEBUG=False`;
- validação de entradas no servidor;
- minimização dos registros de auditoria, sem senha, hash, token, conteúdo de formulário ou termos pesquisados;
- proteção das referências de auditoria e aceite com `PROTECT`;
- bloqueio de inclusão, edição e exclusão de aceites pelo Django Admin;
- controle de versão dos documentos e nova confirmação após atualização;
- Bootstrap e fontes servidos localmente, sem requisições do navegador a Google Fonts ou jsDelivr;
- comandos controlados para exportação, anonimização e descarte, com simulação antes das ações destrutivas.

Essas medidas reduzem riscos, mas não substituem a configuração segura da infraestrutura e as decisões institucionais. As rotinas propostas estão em [Retenção e descarte](plano-retencao-descarte.md), [Direitos dos titulares](procedimento-direitos-titulares.md) e [Resposta a incidentes](plano-resposta-incidentes.md).

## Evidências automatizadas

Os testes de `legal/tests.py` e `usuarios/test_privacidade.py` verificam:

- acesso público ao Termo e à Política;
- links na tela de login;
- bloqueio das áreas internas antes do aceite;
- obrigatoriedade das duas confirmações;
- persistência da conta, versões e data e hora;
- rejeição de redirecionamento externo;
- exigência de novo aceite após mudança de versão;
- rejeição de um formulário exibido antes de uma mudança de versão;
- ausência de duplicidade para a mesma combinação de versões;
- registro do evento de auditoria;
- proteção do aceite e bloqueio de alterações no Django Admin;
- transparência sobre fornecedores, retenção e direitos;
- ausência de Google Fonts e jsDelivr nas páginas públicas;
- bloqueio de tentativas repetidas sem persistir IP ou senha;
- exportação, anonimização, invalidação de sessões e descarte controlado.

Para reproduzir a suíte integrada com SQLite isolado:

```powershell
$env:DATABASE_URL=''
.\.venv\Scripts\python.exe manage.py test
```

O resultado mais recente é mantido em [Evidências de autenticação e autorização](evidencias-seguranca.md).
