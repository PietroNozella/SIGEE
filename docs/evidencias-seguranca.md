# Evidências de autenticação, autorização e privacidade

Este documento reúne evidências reproduzíveis dos incrementos de segurança e privacidade associados ao `RF-01`, ao `RNF-01` e ao baseline `RS-01` a `RS-12`. As verificações usam dados sintéticos e banco de testes isolado do Django.

## Resultado dos cenários de segurança

| Evidência | Comportamento verificado | Teste automatizado | Resultado |
|---|---|---|---|
| Login válido | Credenciais corretas criam a sessão e redirecionam para a listagem. | `AutenticacaoTests.test_login_correto_inicia_sessao_e_redireciona_para_listagem` | Passou |
| Login inválido | Senha incorreta e usuário inexistente recebem a mesma mensagem neutra, sem iniciar sessão. | `AutenticacaoTests.test_credenciais_invalidas_exibem_a_mesma_mensagem_neutra` | Passou |
| Acesso anônimo bloqueado | As páginas protegidas redirecionam para o login e preservam a URL original em `next`. | `AutenticacaoTests.test_todas_as_paginas_do_inventario_exigem_autenticacao` | Passou |
| Administrador criando conta | O Administrador funcional acessa o formulário; a conta criada recebe hash de senha, um único grupo e não recebe `is_staff` ou `is_superuser`. | `CadastroUsuarioTests.test_cadastro_salva_hash_grupo_unico_e_conta_comum` | Passou |
| Operador e Professor consultando | Os dois perfis recebem resposta `200` na listagem de equipamentos. | `AutorizacaoInventarioTests.test_tres_perfis_podem_consultar_a_listagem` | Passou |
| Operador e Professor impedidos de alterar | Cadastro, importação, download do modelo e exclusão direta retornam `403`; a tentativa de exclusão não altera o equipamento. | `AutorizacaoInventarioTests.test_operador_e_professor_recebem_403_nas_rotas_de_alteracao` | Passou |
| Logout invalidando a sessão | `GET` no logout retorna `405`; `POST` encerra a sessão e uma nova tentativa de abrir a listagem volta ao login. | `AutenticacaoTests.test_logout_aceita_somente_post_e_impede_retorno_direto` | Passou |
| Solicitação de recuperação | Conta ativa recebe e-mail em texto e HTML; e-mail inexistente ou conta inativa recebe a mesma confirmação pública sem mensagem enviada. | `RecuperacaoSenhaTests.test_email_existente_recebe_link_em_texto_e_html` e `test_email_inexistente_ou_conta_inativa_recebe_resposta_neutra` | Passou |
| Redefinição segura | Link válido altera a senha, gera auditoria e não pode ser reutilizado; link expirado é rejeitado. | `RecuperacaoSenhaTests.test_link_valido_redefine_senha_e_nao_pode_ser_reutilizado` e `test_link_expirado_e_rejeitado` | Passou |
| Tentativas repetidas | O terceiro erro no cenário reduzido bloqueia novas tentativas, não persiste IP e não mantém a senha informada. | `ProtecaoTentativasLoginTests.test_bloqueia_temporariamente_sem_persistir_ip_ou_senha` | Passou |
| Transparência pública | Termos e Política informam versão, fornecedores, retenção e direitos, sem Google Fonts ou jsDelivr. | `TransparenciaPublicaTests` | Passou |
| Direitos dos titulares | Exportação omite senha, anonimização exige confirmação e preserva histórico, e descarte atua somente após datas de corte explícitas. | `DireitosTitularesCommandsTests` | Passou |

As verificações de autorização são realizadas nas views. A ausência de botões no template é somente uma orientação de interface e não substitui o bloqueio da URL ou do `POST`.

## Execução focada

Comando executado:

```powershell
python manage.py test inventario.tests.AutenticacaoTests inventario.test_autorizacao.AutorizacaoInventarioTests usuarios.tests.CadastroUsuarioTests --verbosity 2 --keepdb
```

Resultado observado:

```text
Ran 23 tests in 12.850s
OK
System check identified no issues (0 silenced).
```

### Recuperação de senha

Comando executado em 15 de setembro de 2026:

```powershell
python manage.py test usuarios.tests.RecuperacaoSenhaTests --verbosity 2
```

Resultado observado:

```text
Ran 7 tests in 6.372s
OK
System check identified no issues (0 silenced).
```

A suíte completa foi executada em 21 de setembro de 2026 com SQLite, isolada do banco publicado:

```powershell
$env:DATABASE_URL=''
python manage.py test --verbosity 1
```

```text
Ran 173 tests in 26.955s
OK
System check identified no issues (1 silenced).
```

O check silenciado é `axes.W006`. A configuração por nome de usuário sem IP é intencional para minimizar dados; o bloqueio continua abrangendo origens diferentes para a mesma conta.

## Regressão do inventário

Para confirmar que a autorização não quebrou os comportamentos anteriores do inventário, foi executada separadamente a suíte histórica do módulo:

```powershell
python manage.py test inventario.tests --verbosity 1 --keepdb
```

Resultado observado:

```text
Ran 39 tests in 51.198s
OK
System check identified no issues (0 silenced).
```

Essa regressão cobre patrimônio único, formulário e listagem, filtros, indicadores, exclusão ou inativação, importação CSV e o fluxo inicial de autenticação.

## Evidências no código

| Controle | Evidência |
|---|---|
| Autenticação e sessão | `LoginView`, `LogoutView`, `AuthenticationForm`, `login_required` e middleware de sessão/autenticação do Django. |
| Autorização | `permission_required(..., raise_exception=True)`, grupos e permissões configurados pelo comando `configurar_perfis`. |
| Senha | `UserCreationForm` e `check_password`; a senha em texto puro não é persistida. |
| Recuperação de senha | `PasswordResetView`, `PasswordResetConfirmView`, `PasswordResetForm`, `SetPasswordForm` e gerador de token nativo do Django. |
| CSRF | `CsrfViewMiddleware` e `{% csrf_token %}` nos formulários `POST` de login, logout, cadastro e exclusão. |
| Acesso direto | Resposta `403` para usuário autenticado sem permissão e redirecionamento ao login para anônimo. |
| Proteção contra abuso | `django-axes`, limite configurável, bloqueio temporário e identificação somente pelo nome de usuário. |
| Direitos e retenção | Comandos `exportar_dados_usuario`, `anonimizar_usuario` e `limpar_dados_expirados`, com testes de simulação e confirmação. |
| Minimização no navegador | Bootstrap e fontes servidos pelo próprio projeto, sem Google Fonts ou jsDelivr nas páginas públicas. |

## Verificação do HTTPS publicado

O ambiente publicado usa HTTPS e apresentou o cabeçalho:

```text
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Server: Vercel
```

O transporte HTTPS e a política HSTS foram confirmados. Como esta branch ainda não foi implantada, os controles novos precisam de nova verificação funcional após o deploy.

## Limites da evidência

- Os testes automatizados usam banco isolado e dados sintéticos.
- MFA não foi implementado e permanece fora do recorte atual.
- O envio real depende da configuração de um provedor SMTP no ambiente publicado; os testes usam o backend de e-mail em memória.
- O bloqueio é por nome de usuário e não substitui MFA ou proteção de infraestrutura contra ataques distribuídos.
- A auditoria de ações foi integrada posteriormente em módulo próprio, com registro persistente e consulta restrita ao Administrador funcional, conforme as [evidências de auditoria](auditoria.md).
- Hipóteses legais, prazos de retenção e identidade dos agentes continuam sujeitos à validação institucional e não são comprovados por testes técnicos.
