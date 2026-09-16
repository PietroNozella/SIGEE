# Autenticação e autorização

Este documento descreve os incrementos implementados do `RF-01`. O fluxo usa o `User`, o `AuthenticationForm`, as views de autenticação, as sessões, os grupos e as permissões nativas do Django.

## Fluxo implementado

1. Um acesso anônimo a uma página do inventário redireciona para o login e informa a página original no parâmetro `next`.
2. O usuário informa nome de usuário e senha.
3. O Django valida as credenciais e, quando válidas, inicia a sessão.
4. O usuário retorna à página indicada por `next` ou, na ausência desse parâmetro, à listagem de equipamentos.
5. O logout aceita somente `POST`, encerra a sessão e redireciona para o login.

A mensagem para credenciais inválidas é neutra e não informa se o nome de usuário existe. Não há cadastro público nem recuperação de senha.

## Autorização implementada

- `Administrador`: consulta e administra o inventário, visualiza seu resumo e cadastra contas comuns.
- `Operador` e `Professor`: consultam a listagem e usam seus filtros.
- Usuários autenticados sem a permissão exigida recebem `403`; usuários anônimos são redirecionados ao login com `next`.
- Botões e links são exibidos conforme as permissões, mas a decisão final sempre ocorre na view.
- O cadastro de usuários exige uma conta não Superuser pertencente somente ao grupo `Administrador` e com `auth.add_user`.

O formulário de cadastro estende `UserCreationForm`. Portanto, a senha inicial passa pelos validadores configurados e é armazenada com o hash do Django. A conta criada pertence a exatamente um dos três grupos funcionais e nunca recebe `is_staff` ou `is_superuser`.

O e-mail é obrigatório para as contas funcionais e deve ser único sem diferenciação entre letras maiúsculas e minúsculas. O formulário rejeita a duplicidade com uma mensagem clara, e um índice único no banco preserva a regra mesmo quando a gravação não passa pelo formulário do SIGEE. Contas técnicas sem e-mail continuam permitidas pelo `User` nativo do Django.

## Bootstrap dos perfis

Após aplicar as migrations, execute:

```powershell
python manage.py configurar_perfis
```

O comando cria os grupos ausentes e substitui suas permissões pela matriz oficial. Ele é idempotente e falha com uma mensagem clara quando alguma permissão esperada ainda não existe. Em seguida, um Superuser técnico deve criar pelo Django Admin a primeira conta comum e atribuir somente o grupo `Administrador`.

## Mecanismos de segurança

| Mecanismo | O que protege | O que não substitui |
|---|---|---|
| Hash de senha | O Django armazena uma representação derivada e não reversível da senha, com salt, e compara a credencial informada usando os hashers configurados. A senha em texto puro não é salva. | Não protege sozinho o tráfego entre navegador e servidor. |
| Proteção CSRF | O token CSRF permite ao Django rejeitar requisições `POST` forjadas por outro site, incluindo login e logout. | Não armazena senha nem identifica a sessão do usuário. |
| Cookie de sessão | O navegador mantém um identificador de sessão; os dados da sessão permanecem no servidor. O cookie permite associar requisições posteriores ao usuário autenticado. | Não criptografa o tráfego e não substitui a verificação de permissões. |
| HTTPS | Criptografa a comunicação entre navegador e servidor no ambiente publicado, protegendo credenciais e cookies durante o transporte. | Não substitui hash de senha, CSRF ou autorização no servidor. |

## Limite dos incrementos

Os incrementos de autenticação cobrem as rotas atuais do inventário e a criação de contas. A auditoria foi implementada em um incremento separado e usa a mesma matriz de grupos e permissões. Listagem, edição ou inativação de usuários, reservas, movimentações funcionais, manutenção e BrasilAPI permanecem fora deste trabalho.

Também não foram implementados autenticação multifator (MFA), recuperação de senha e bloqueio ou atraso progressivo após tentativas inválidas. MFA está fora do recorte atual; recuperação e proteção contra tentativas abusivas permanecem não implementadas e ainda dependem da priorização ou confirmação dos respectivos requisitos.

## Síntese para o TCC

O incremento de segurança do SIGEE utiliza o sistema nativo de autenticação do Django. O usuário informa nome de usuário e senha; credenciais válidas iniciam uma sessão e credenciais inválidas produzem uma mensagem neutra. O acesso anônimo às páginas do inventário é redirecionado ao login, preservando a URL original, enquanto usuários autenticados sem a permissão exigida recebem resposta `403`.

A autorização é representada pelos grupos `Administrador`, `Operador` e `Professor`, associados às permissões do Django conforme a [matriz de acesso](matriz-de-acesso.md). As verificações permanecem no servidor, inclusive para acessos diretos e requisições `POST`. A interface oculta ações não autorizadas apenas como orientação visual.

As senhas são processadas pelo `UserCreationForm` e pelos hashers configurados no Django; não há criptografia própria nem armazenamento da senha em texto puro. A proteção CSRF é aplicada aos formulários `POST`, e o cookie de sessão associa as requisições posteriores ao usuário autenticado. No ambiente publicado, a comunicação é oferecida sobre HTTPS e a hospedagem apresenta HSTS; a disponibilidade atual das rotas precisa ser confirmada após novo deploy.

## Evidência automatizada

Os testes verificam o formulário nativo, o hash da senha, a sessão, a mensagem neutra, `next`, a configuração idempotente dos grupos, a matriz de acesso, as URLs diretas e o cadastro controlado. Os comandos, cenários e resultados observados estão registrados em [Evidências de autenticação e autorização](evidencias-seguranca.md).
