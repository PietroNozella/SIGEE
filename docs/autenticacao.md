# Autenticação, recuperação de senha e autorização

Este documento descreve os incrementos implementados do `RF-01` e do `RS-07`. O fluxo usa o `User`, os formulários, as views, os tokens, as sessões, os grupos e as permissões nativas do Django.

## Fluxo implementado

1. Um acesso anônimo a uma página do inventário redireciona para o login e informa a página original no parâmetro `next`.
2. O usuário informa nome de usuário e senha.
3. O Django valida as credenciais e, quando válidas, inicia a sessão.
4. O usuário retorna à página indicada por `next` ou, na ausência desse parâmetro, à listagem de equipamentos.
5. O logout aceita somente `POST`, encerra a sessão e redireciona para o login.

A mensagem para credenciais inválidas é neutra e não informa se o nome de usuário existe. Não há cadastro público.

## Recuperação de senha implementada

1. O usuário abre `Esqueceu a senha?` e informa o e-mail único cadastrado.
2. O sistema apresenta a mesma confirmação para e-mail existente, inexistente ou associado a uma conta inativa.
3. Uma conta ativa e com senha utilizável recebe um link individual por e-mail.
4. O token expira em uma hora, não contém a senha e é invalidado após a alteração.
5. A nova senha passa pelos mesmos validadores configurados para o cadastro.
6. Ao concluir, o usuário retorna ao login e acessa a conta com a nova credencial.

Em desenvolvimento, o backend de e-mail exibe a mensagem no console. No ambiente publicado, o backend SMTP, o remetente e as credenciais devem ser configurados por variáveis de ambiente. A solicitação e a conclusão são auditadas sem armazenar o endereço informado, a senha ou o token.

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
| Token de recuperação | O gerador nativo do Django vincula o token ao usuário, ao estado da senha, ao último login, ao e-mail e ao prazo configurado. | Não substitui o controle do usuário sobre sua caixa de e-mail nem a proteção contra solicitações abusivas. |
| Proteção CSRF | O token CSRF permite ao Django rejeitar requisições `POST` forjadas por outro site, incluindo login, recuperação e logout. | Não armazena senha nem identifica a sessão do usuário. |
| Cookie de sessão | O navegador mantém um identificador de sessão; os dados da sessão permanecem no servidor. O cookie permite associar requisições posteriores ao usuário autenticado. | Não criptografa o tráfego e não substitui a verificação de permissões. |
| HTTPS | Criptografa a comunicação entre navegador e servidor no ambiente publicado, protegendo credenciais e cookies durante o transporte. | Não substitui hash de senha, CSRF ou autorização no servidor. |

## Limite dos incrementos

Os incrementos de autenticação cobrem as rotas atuais do inventário e a criação de contas. A auditoria foi implementada em um incremento separado e usa a mesma matriz de grupos e permissões. Listagem, edição ou inativação de usuários, reservas, movimentações funcionais, manutenção e BrasilAPI permanecem fora deste trabalho.

Também não foram implementados autenticação multifator (MFA) e bloqueio ou atraso progressivo após tentativas inválidas ou solicitações repetidas de recuperação. MFA está fora do recorte atual; a proteção contra tentativas abusivas permanece candidata no `RS-06`.

## Síntese para o TCC

O incremento de segurança do SIGEE utiliza o sistema nativo de autenticação do Django. O usuário informa nome de usuário e senha; credenciais válidas iniciam uma sessão e credenciais inválidas produzem uma mensagem neutra. O acesso anônimo às páginas do inventário é redirecionado ao login, preservando a URL original, enquanto usuários autenticados sem a permissão exigida recebem resposta `403`.

A autorização é representada pelos grupos `Administrador`, `Operador` e `Professor`, associados às permissões do Django conforme a [matriz de acesso](matriz-de-acesso.md). As verificações permanecem no servidor, inclusive para acessos diretos e requisições `POST`. A interface oculta ações não autorizadas apenas como orientação visual.

As senhas são processadas pelos formulários e hashers do Django; não há criptografia própria nem armazenamento da senha em texto puro. A recuperação usa o gerador de tokens do framework, resposta pública neutra, prazo de uma hora e invalidação após a troca. A proteção CSRF é aplicada aos formulários `POST`, e o cookie de sessão associa as requisições posteriores ao usuário autenticado. No ambiente publicado, a comunicação é oferecida sobre HTTPS e a hospedagem apresenta HSTS; a disponibilidade atual das rotas precisa ser confirmada após novo deploy.

## Evidência automatizada

Os testes verificam o formulário nativo, o hash da senha, a sessão, a mensagem neutra, `next`, a configuração idempotente dos grupos, a matriz de acesso, o cadastro controlado e o fluxo de recuperação com token válido, expirado e já utilizado. Os comandos, cenários e resultados observados estão registrados em [Evidências de autenticação e autorização](evidencias-seguranca.md).
