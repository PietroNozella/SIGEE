# Autenticação, recuperação de senha e autorização

Este documento descreve os incrementos implementados do `RF-01` e do `RS-07`. O fluxo usa `contas.User`, derivado de `AbstractUser`, com chave primária UUID, mantendo os formulários, as views, os tokens, as sessões, os grupos e as permissões nativas do Django.

## Fluxo implementado

1. Um acesso anônimo a uma página do inventário redireciona para o login e informa a página original no parâmetro `next`.
2. O usuário informa nome de usuário e senha.
3. O Django valida as credenciais e, quando válidas, inicia a sessão.
4. O usuário retorna à página indicada por `next` ou, na ausência desse parâmetro, à listagem de equipamentos.
5. O logout aceita somente `POST`, encerra a sessão e redireciona para o login.
6. Após cinco tentativas inválidas para o mesmo nome de usuário, o acesso fica bloqueado por quinze minutos, inclusive se a senha correta for informada durante esse intervalo.

A mensagem para credenciais inválidas é neutra e não informa se o nome de usuário existe. Não há cadastro público.

## Recuperação de senha implementada

1. O usuário abre `Esqueceu a senha?` e informa o e-mail único cadastrado.
2. O sistema apresenta a mesma confirmação para e-mail existente, inexistente ou associado a uma conta inativa.
3. Uma conta ativa e com senha utilizável recebe um link individual por e-mail.
4. O token expira em uma hora, não contém a senha e é invalidado após a alteração.
5. A nova senha passa pelos mesmos validadores configurados para o cadastro.
6. Ao concluir, o usuário retorna ao login e acessa a conta com a nova credencial.

Em desenvolvimento, o backend de e-mail exibe a mensagem no console. No ambiente publicado, o envio usa Gmail SMTP na porta `587` com TLS. O endereço remetente e a senha de app ficam somente nas variáveis protegidas da hospedagem; nenhuma credencial é versionada. A solicitação e a conclusão são auditadas sem armazenar o endereço informado, a senha ou o token.

## Autorização implementada

- `Administrador`: consulta e administra o inventário, visualiza seu resumo e cadastra contas comuns.
- `Operador` e `Professor`: consultam a listagem e usam seus filtros.
- Usuários autenticados sem a permissão exigida recebem `403`; usuários anônimos são redirecionados ao login com `next`.
- Botões e links são exibidos conforme as permissões, mas a decisão final sempre ocorre na view.
- O cadastro de usuários exige uma conta não Superuser pertencente somente ao grupo `Administrador` e com `contas.add_user`.

O formulário de cadastro estende `UserCreationForm`. Portanto, a senha inicial passa pelos validadores configurados e é armazenada com o hash do Django. A conta criada pertence a exatamente um dos três grupos funcionais e nunca recebe `is_staff` ou `is_superuser`.

O e-mail é obrigatório para as contas funcionais e deve ser único sem diferenciação entre letras maiúsculas e minúsculas. O formulário rejeita a duplicidade com uma mensagem clara, e um índice único no banco preserva a regra mesmo quando a gravação não passa pelo formulário do SIGEE. Contas técnicas sem e-mail continuam permitidas pelo modelo derivado de `AbstractUser`.

## Desativação reversível de usuários

A tela `/usuarios/` permite ao Administrador funcional consultar contas comuns,
filtrar por nome, usuário, e-mail e situação, desativar e reativar. Consulta exige
`contas.view_user`; alteração de situação exige `contas.change_user`. Execute
`python manage.py configurar_perfis` para aplicar essas permissões a bancos existentes.

A desativação usa `is_active=False`, encerra as sessões da conta e preserva senha,
identificadores, grupos, permissões, aceites e referências históricas. Username e
e-mail continuam reservados. A reativação exige novo login; sessões anteriores
não são recuperadas. Não há exclusão definitiva na interface funcional.

O servidor impede desativar a própria conta, o último Administrador ativo ou
contas técnicas. Somente o Administrador principal pode desativar e reativar
outros administradores comuns. O principal não pode ter sua situação alterada
pelo fluxo funcional. Administradores comuns continuam gerenciando Professores e
Operadores. Contas sem um único perfil funcional, incluindo as anonimizadas,
não podem ser alteradas por esse fluxo. Reservas ativas sem retirada bloqueiam a
desativação até serem canceladas pelo Professor ou expiradas pelo fluxo de reservas.
Reservas com retirada e equipamentos em uso permanecem no histórico e podem ser
devolvidos pelo Operador mesmo após a desativação do destinatário.

Mudanças geram `USUARIO_DESATIVADO` ou `USUARIO_REATIVADO`, identificando o
Administrador responsável e a conta afetada. Repetir a mesma situação não duplica
eventos de sucesso. A anonimização continua sendo um procedimento separado.
As regras ampliam o controle de contas da RN-18 e a autorização do RF-01;
os cenários estão em `usuarios/test_soft_delete.py`.

## Bootstrap dos perfis

Após aplicar as migrations, execute:

```powershell
python manage.py configurar_perfis
```

O comando cria os grupos ausentes e substitui suas permissões pela matriz oficial. Ele é idempotente e falha com uma mensagem clara quando alguma permissão esperada ainda não existe. Em seguida, um Superuser técnico deve criar pelo Django Admin a primeira conta comum e atribuir somente o grupo `Administrador`.

### Administrador principal de reserva

Depois de aplicar as migrations, crie uma conta comum exclusiva para a reserva de
acesso, com senha utilizável, e-mail de recuperação e somente o grupo
`Administrador`. Designe essa conta pelo terminal do ambiente correspondente:

```powershell
python manage.py configurar_administrador_principal nome_da_conta_reserva
```

O comando exige conta ativa, sem `is_staff` ou `is_superuser`, exclusivamente no
grupo `Administrador` e com senha utilizável. Não cria usuários nem modifica
credenciais ou permissões. Repetir a designação da mesma conta não duplica eventos.
As migrations mantêm todos os usuários existentes como administradores comuns;
nenhum é promovido automaticamente. Até designar o principal, os administradores
continuam gerenciando Professores e Operadores, mas não alteram a situação de
outros administradores.

Para transferir a função a outra conta Administrador previamente preparada:

```powershell
python manage.py configurar_administrador_principal nome_do_substituto --substituir
```

A transferência é atômica: o anterior permanece ativo como administrador comum e
o substituto passa a principal. Falhas desfazem a transferência e sua auditoria.
O banco permite no máximo um principal e exige que a conta principal permaneça
ativa e sem privilégios técnicos. A presença de um principal é uma etapa de
configuração, não uma conta criada automaticamente pela migration.

O campo mantém `FALSE` como padrão também no banco, permitindo que a versão
anterior cadastre contas comuns durante a transição para o código atualizado.

A conta reserva permanece ativa, embora não seja usada no cotidiano. Sua senha e
o acesso ao e-mail de recuperação devem ficar sob a responsabilidade institucional.
Se houver perda de acesso, a manutenção técnica pode redefinir a senha pelos
mecanismos do Django ou preparar outra conta e transferir a função pelo comando.

O campo de designação não faz parte do cadastro funcional e é somente leitura no
Django Admin. No Admin, os campos de situação, privilégios técnicos e grupos do
principal também são somente leitura, e sua exclusão é bloqueada. O comando de
anonimização recusa a conta principal, inclusive com `--confirmar`; designe um
substituto antes de seguir esse procedimento.

Os testes estão em `usuarios/test_administrador_principal.py`, além dos cenários
de desativação em `usuarios/test_soft_delete.py`. A aplicação e a reversão da
migration são verificadas em `contas/test_administrador_principal.py`, preservando
contas, grupos, auditoria e o índice de e-mail único.

### Verificação local em 30/10/2026

Na branch `feat/administrador-principal`, a suíte completa executou **467 testes:
451 aprovados e 16 ignorados no SQLite**, sem falhas, em 111,010 segundos. Os casos
ignorados exigem recursos de concorrência do PostgreSQL. Os 19 testes novos cobrem
a autoridade sobre a conta alvo, sessões e auditoria, proteção no Django Admin,
cadastro sem promoção, configuração e substituição do principal, restrições do
banco e preservação dos dados na aplicação e reversão da migration.

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.settings_testes --noinput
.\.venv\Scripts\python.exe manage.py check --settings=config.settings_testes
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings_testes
git diff --check
```

As verificações passaram. A migration foi exercitada somente em bancos isolados
de testes; nenhuma conta real foi promovida. Concorrência em PostgreSQL e
validação no ambiente publicado não foram executadas neste incremento.

Após manter o padrão persistente `FALSE` para compatibilidade com a versão
anterior, a suíte de contas e usuários executou 61 testes: 59 aprovados e dois
ignorados no SQLite. O teste de migration também confere o cadastro pela versão
anterior depois de adicionar a nova coluna.

## Mecanismos de segurança

| Mecanismo | O que protege | O que não substitui |
|---|---|---|
| Hash de senha | O Django armazena uma representação derivada e não reversível da senha, com salt, e compara a credencial informada usando os hashers configurados. A senha em texto puro não é salva. | Não protege sozinho o tráfego entre navegador e servidor. |
| Token de recuperação | O gerador nativo do Django vincula o token ao usuário, ao estado da senha, ao último login, ao e-mail e ao prazo configurado. | Não substitui o controle do usuário sobre sua caixa de e-mail nem a proteção contra solicitações abusivas. |
| Proteção CSRF | O token CSRF permite ao Django rejeitar requisições `POST` forjadas por outro site, incluindo login, recuperação e logout. | Não armazena senha nem identifica a sessão do usuário. |
| Cookie de sessão | O navegador mantém um identificador de sessão; os dados da sessão permanecem no servidor. O cookie permite associar requisições posteriores ao usuário autenticado. | Não criptografa o tráfego e não substitui a verificação de permissões. |
| HTTPS | Criptografa a comunicação entre navegador e servidor no ambiente publicado, protegendo credenciais e cookies durante o transporte. | Não substitui hash de senha, CSRF ou autorização no servidor. |
| Bloqueio de tentativas | O `django-axes` limita tentativas repetidas por nome de usuário. O SIGEE não persiste o endereço IP nesse controle e mascara a senha registrada pelo middleware. | Não substitui MFA, senha forte, monitoramento ou proteção do provedor contra ataques distribuídos. |

## Limite dos incrementos

Os incrementos de autenticação cobrem as rotas atuais e a criação de contas. A auditoria usa a mesma matriz de grupos e permissões. A aplicação não possui MFA nem limitação específica para solicitações repetidas de recuperação de senha; esses controles permanecem fora do recorte atual.

## Síntese para o TCC

O incremento de segurança do SIGEE utiliza o sistema nativo de autenticação do Django. O usuário informa nome de usuário e senha; credenciais válidas iniciam uma sessão e credenciais inválidas produzem uma mensagem neutra. O acesso anônimo às páginas do inventário é redirecionado ao login, preservando a URL original, enquanto usuários autenticados sem a permissão exigida recebem resposta `403`.

A autorização é representada pelos grupos `Administrador`, `Operador` e `Professor`, associados às permissões do Django conforme a [matriz de acesso](matriz-de-acesso.md). As verificações permanecem no servidor, inclusive para acessos diretos e requisições `POST`. A interface oculta ações não autorizadas apenas como orientação visual.

As senhas são processadas pelos formulários e hashers do Django; não há criptografia própria nem armazenamento da senha em texto puro. A recuperação usa o gerador de tokens do framework, resposta pública neutra, prazo de uma hora e invalidação após a troca. A proteção CSRF é aplicada aos formulários `POST`, o cookie de sessão associa as requisições posteriores ao usuário autenticado e tentativas repetidas são bloqueadas temporariamente. No ambiente publicado, a comunicação é oferecida sobre HTTPS e a hospedagem apresenta HSTS.

## Evidência automatizada

Os testes verificam o formulário nativo, o hash da senha, a sessão, a mensagem neutra, `next`, o bloqueio temporário sem IP, a configuração idempotente dos grupos, a matriz de acesso, o cadastro controlado e o fluxo de recuperação com token válido, expirado e já utilizado. Os comandos, cenários e resultados observados estão registrados em [Evidências de autenticação e autorização](evidencias-seguranca.md).
