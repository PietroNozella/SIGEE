# Evidências de autenticação e autorização

Este documento reúne evidências reproduzíveis do incremento de segurança associado ao `RF-01`, ao `RNF-01` e ao `RS-01`. A verificação foi executada em 10 de setembro de 2026 com dados sintéticos e banco de testes isolado do Django.

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
| CSRF | `CsrfViewMiddleware` e `{% csrf_token %}` nos formulários `POST` de login, logout, cadastro e exclusão. |
| Acesso direto | Resposta `403` para usuário autenticado sem permissão e redirecionamento ao login para anônimo. |

## Verificação do HTTPS publicado

Foi consultado `https://sigee-psi.vercel.app/login/` em 10 de setembro de 2026. O servidor respondeu por HTTPS e apresentou o cabeçalho:

```text
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Server: Vercel
```

O transporte HTTPS e a política HSTS foram confirmados. Entretanto, a rota retornou `HTTP 404` tanto em `HEAD` quanto em `GET`. Portanto, essa evidência confirma a camada HTTPS da hospedagem, mas ainda não comprova a disponibilidade da tela de login publicada. É necessário realizar ou corrigir o deploy antes de usar o ambiente publicado como evidência funcional na versão final do TCC.

## Limites da evidência

- Os testes automatizados usam banco isolado e dados sintéticos.
- MFA não foi implementado e permanece fora do recorte atual.
- Recuperação de senha não foi implementada.
- Bloqueio ou atraso progressivo por tentativas de login não foi implementado; o requisito permanece candidato e ainda depende de confirmação.
- A auditoria de ações foi integrada posteriormente em módulo próprio, com registro persistente e consulta restrita ao Administrador funcional, conforme as [evidências de auditoria](auditoria.md).
