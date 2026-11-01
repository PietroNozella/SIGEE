# Autenticação, recuperação de senha e autorização

Este documento descreve os controles do `RF01` e do `RS-07`. O fluxo usa `contas.User`, derivado de `AbstractUser`, com chave primária UUID, mantendo os formulários, as views, os tokens, as sessões, os grupos e as permissões nativas do Django.

## Fluxo implementado

1. Um acesso anônimo a uma página do inventário redireciona para o login e informa a página original no parâmetro `next`.
2. O usuário informa nome de usuário e senha.
3. O Django valida as credenciais e, quando válidas, inicia a sessão.
4. O usuário retorna à página interna válida indicada por `next`. Sem esse parâmetro, o Administrador autorizado acessa o painel; os demais seguem para a listagem de equipamentos. O aceite vigente dos documentos legais é exigido antes das áreas internas.
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

Por padrão, o backend de e-mail exibe a mensagem no console com `DEBUG=True` e utiliza SMTP com `DEBUG=False`. Host, porta, TLS, remetente e credenciais são configuráveis por variáveis de ambiente; os padrões de porta e TLS são `587` e `True`. O host padrão é `localhost`, e `.env.example` apresenta a configuração para Gmail SMTP. As credenciais reais ficam somente no ambiente, sem versionamento. A solicitação e a conclusão são auditadas sem armazenar o endereço informado, a senha ou o token.

## Autorização implementada

- `Administrador`: consulta e administra o inventário, visualiza seu resumo e cadastra contas comuns.
- `Operador` e `Professor`: consultam equipamentos e executam os fluxos autorizados na [matriz de acesso](matriz-de-acesso.md).
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
As regras ampliam o controle de contas da RN-18 e a autorização do RF01;
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

## Mecanismos de segurança

| Mecanismo | O que protege | O que não substitui |
|---|---|---|
| Hash de senha | O Django armazena uma representação derivada e não reversível da senha, com salt, e compara a credencial informada usando os hashers configurados. A senha em texto puro não é salva. | Não protege sozinho o tráfego entre navegador e servidor. |
| Token de recuperação | O gerador nativo do Django vincula o token ao usuário, ao estado da senha, ao último login, ao e-mail e ao prazo configurado. | Não substitui o controle do usuário sobre sua caixa de e-mail nem a proteção contra solicitações abusivas. |
| Proteção CSRF | O token CSRF permite ao Django rejeitar requisições `POST` forjadas por outro site, incluindo login, recuperação e logout. | Não armazena senha nem identifica a sessão do usuário. |
| Cookie de sessão | O navegador mantém um identificador de sessão; os dados da sessão permanecem no servidor. O cookie permite associar requisições posteriores ao usuário autenticado. | Não criptografa o tráfego e não substitui a verificação de permissões. |
| HTTPS | Criptografa a comunicação entre navegador e servidor no ambiente publicado, protegendo credenciais e cookies durante o transporte. | Não substitui hash de senha, CSRF ou autorização no servidor. |
| Bloqueio de tentativas | O `django-axes` limita tentativas repetidas por nome de usuário. O SIGEE não persiste o endereço IP nesse controle e mascara a senha registrada pelo middleware. | Não substitui MFA, senha forte, monitoramento ou proteção do provedor contra ataques distribuídos. |

## Limites

Os controles de autenticação abrangem as rotas restritas e a criação de contas. A auditoria usa a mesma matriz de grupos e permissões. A aplicação não possui MFA nem limitação específica para solicitações repetidas de recuperação de senha; esses controles permanecem fora do recorte atual.

## Referências de implementação e testes

As views de autenticação e recuperação estão em `usuarios/views.py`; a autorização funcional e a autoridade sobre contas estão em `usuarios/permissoes.py` e `usuarios/services.py`. `contas/models.py` define UUID e restrições do Administrador principal.

Os testes de autenticação e recuperação ficam em `inventario/tests.py` e `usuarios/tests.py`; a autorização do inventário está em `inventario/test_autorizacao.py`. Desativação, conta principal e migrations possuem cenários em `usuarios/test_soft_delete.py`, `usuarios/test_administrador_principal.py`, `contas/test_administrador_principal.py` e `contas/test_migracao_uuid.py`. O [README](../../README.md#testes) descreve a execução isolada.
