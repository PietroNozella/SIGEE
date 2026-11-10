<div align="center">

# SIGEE

### Sistema Integrado de Gestão de Equipamentos Escolares

Inventário, reservas e utilização de equipamentos escolares em um único ambiente.

**[Acessar a aplicação](https://sigee-psi.vercel.app/login/)**

**Aplicação**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)

**Interface**

![Django Templates](https://img.shields.io/badge/Django%20Templates-092E20?style=for-the-badge&logo=django&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Bootstrap](https://img.shields.io/badge/Bootstrap%205-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)

**Dados e infraestrutura**

![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

**Desenvolvimento e design**

![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)
![Figma](https://img.shields.io/badge/Figma-F24E1E?style=for-the-badge&logo=figma&logoColor=white)

</div>

[Visão geral](#visão-geral) · [Funcionalidades](#funcionalidades) · [Perfis](#perfis-de-acesso) · [Arquitetura](#tecnologias-e-arquitetura) · [Execução local](#execução-local) · [Testes](#testes) · [Documentação](#documentação)

## Visão geral

O SIGEE é uma aplicação web para gerenciar equipamentos tecnológicos de instituições de ensino, desde o cadastro patrimonial até a reserva, entrega, devolução e manutenção. O sistema relaciona o uso dos equipamentos a turmas, disciplinas e atividades pedagógicas e reúne consultas operacionais, indicadores e auditoria.

O início do Operador reúne entregas do dia, pendências de entrega e devoluções previstas ou vencidas, com resumo da situação atual dos equipamentos. Equipamentos inativos são apresentados como indisponíveis para uso.

O fluxo de empréstimo é organizado em **Reservas**, **Em uso** e **Histórico**. O Professor agenda os equipamentos e informa o contexto pedagógico; o Operador confirma a entrega e recebe as devoluções; o Administrador mantém os cadastros e acompanha o acervo. Toda nova retirada exige uma reserva válida.

## Funcionalidades

| Área | Recursos |
|---|---|
| **Inventário** | Cadastro por unidade física, patrimônio único, tipo/modelo, categoria e local; importação CSV com gravação integral do lote; filtros, edição e exclusão ou inativação conforme o histórico. |
| **Reservas** | Agendamento próprio em lote por tipo/modelo e local, alocação de patrimônios, contexto pedagógico obrigatório, disponibilidade, prevenção de conflitos, cancelamento e expiração por tolerância de retirada. |
| **Entrega e devolução** | Entrega integral, parcial por manutenção ou complementar, substituição automática com histórico, atualização de situação, devolução total ou parcial e registro de problemas por patrimônio, com transações e rastreabilidade por unidade. |
| **Manutenção** | Abertura automática na devolução com problema ou manual pelo Administrador ou Operador; acompanhamento e conclusão como reparado ou sem possibilidade de reparo, com preservação do histórico. |
| **Contexto pedagógico** | Cadastros de turmas, disciplinas e atividades; planejamento na reserva, criação das utilizações na entrega e correção pelo Professor até a devolução integral. |
| **Consultas e indicadores** | Itens em uso, histórico de reservas e movimentações, painel do inventário e indicadores por turma, disciplina e atividade, com acesso conforme o perfil. |
| **Identidade e auditoria** | Cadastro controlado de contas, recuperação de senha, desativação reversível, Administrador principal, autorização no servidor e registro das ações relevantes. |
| **Privacidade e integração** | Termos e Política de Privacidade com aceite versionado; comandos assistidos de exportação, anonimização e descarte; consulta informativa de feriados pela BrasilAPI. |

Feriados nacionais são informativos e não impedem uma reserva. A indisponibilidade da BrasilAPI também permite continuar o fluxo; as validações locais de período, quantidade e disponibilidade permanecem aplicáveis.

Os registros antigos de retirada sem reserva permanecem disponíveis para devolução e consulta. As regras de compatibilidade estão no [fluxo de reservas, uso e histórico](docs/tecnica/fluxo-reservas-uso-historico.md).

## Perfis de acesso

O sistema não possui cadastro público. As contas funcionais pertencem a um único perfil, e as permissões são verificadas no servidor.

| Perfil | Responsabilidades |
|---|---|
| **Administrador** | Gerencia equipamentos, usuários e cadastros pedagógicos; acompanha reservas, itens em uso, histórico e manutenção; consulta painel, indicadores e auditoria. |
| **Operador** | Acessa início operacional e Meus dados; confere entregas integrais, parciais e complementares; registra devoluções e problemas; abre e consulta manutenção; acompanha pendências e histórico com contexto limitado à turma. |
| **Professor** | Consulta disponibilidade, cria e cancela reservas próprias quando permitido, informa e corrige o contexto pedagógico e acompanha seus itens em uso e registros históricos. |

O **Administrador principal** pertence ao mesmo perfil Administrador e possui autoridade exclusiva para desativar ou reativar administradores comuns. O Superuser do Django é uma conta técnica de configuração e manutenção, separada dos perfis funcionais.

A [matriz de acesso](docs/tecnica/matriz-de-acesso.md) detalha as ações, permissões e restrições de propriedade.

## Tecnologias e arquitetura

O SIGEE utiliza um monólito Django com páginas renderizadas no servidor. Os apps separam as responsabilidades do domínio, enquanto o ORM, os serviços transacionais e os controles de acesso mantêm as regras na aplicação.

O envio por SMTP depende da configuração do ambiente; em desenvolvimento, o backend padrão de e-mail exibe as mensagens no console.

| Camada | Implementação |
|---|---|
| **Aplicação** | Python 3.12, Django 5.2, Django ORM e autenticação nativa por sessões, grupos e permissões. |
| **Interface** | Django Templates, HTML, CSS, Bootstrap 5 e JavaScript. Bootstrap, fontes e ícones são servidos pelo projeto. |
| **Dados** | SQLite para desenvolvimento local; PostgreSQL configurado por `DATABASE_URL`, com Supabase como infraestrutura do banco na implantação. |
| **Integrações** | BrasilAPI para feriados nacionais e SMTP configurável para recuperação de senha. |
| **Implantação** | Vercel, com região `gru1` definida em `vercel.json`. Migrations e variáveis de ambiente integram a preparação do ambiente. |
| **Segurança** | Validação no servidor, CSRF, hash de senhas, bloqueio temporário de tentativas com django-axes, cookies seguros com `DEBUG=False` e auditoria. |

Os apps `inventario`, `reservas`, `movimentacoes`, `manutencoes` e `pedagogico` concentram os fluxos de equipamentos. `contas`, `usuarios`, `auditoria` e `legal` oferecem os controles de identidade, acesso, registro e aceite.

Consulte a [arquitetura do sistema](docs/tecnica/arquitetura-do-sistema.md) para conhecer as decisões técnicas e os relacionamentos entre os módulos.

## Execução local

O Administrador configura a semana habitual e as exceções por data em **Administração → Calendário da escola**. Uso dos equipamentos e atendimento do Operador têm horários separados. Inicialmente, segunda a sexta permanecem liberadas durante todo o dia. Novas reservas seguem as faixas; compromissos já confirmados são preservados e sinalizados quando uma mudança exigir decisão. O seletor de datas de exceção também destaca os feriados nacionais consultados na BrasilAPI.

Nessa mesma tela, **Configurar intervalo** define a margem após o uso das mesmas unidades, inicialmente 5 minutos, com opção zero para desativá-la. Cada reserva guarda o intervalo vigente; alterações posteriores não reescrevem compromissos e registros anteriores preservam margem zero. A regra é aplicada na consulta, na confirmação e na substituição por manutenção. O horário não libera um equipamento ainda sob custódia. A mudança do parâmetro exige motivo e fica no histórico do calendário.

Os comandos abaixo utilizam **PowerShell no Windows** e preparam uma instalação nova.

### Pré-requisitos

- Python 3.12;
- Git;
- PostgreSQL, caso opte por esse banco; a execução local também utiliza SQLite.

### Instalação

Clone o repositório e prepare o ambiente:

```powershell
git clone https://github.com/PietroNozella/SIGEE.git
Set-Location SIGEE
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### Configuração do ambiente

Gere uma chave local e copie o resultado para `DJANGO_SECRET_KEY` no arquivo `.env`:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Para iniciar com SQLite, ajuste os valores abaixo. O arquivo `.env.example` contém uma URL ilustrativa de PostgreSQL; deixe `DATABASE_URL` vazia para utilizar o banco local.

```dotenv
DJANGO_SECRET_KEY=substitua-pela-chave-gerada
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=
```

Para usar PostgreSQL, preencha `DATABASE_URL` com uma conexão válida. Na configuração orientada para Supabase, inclua `sslmode=require`. O arquivo `.env` é ignorado pelo Git.

<details>
<summary><strong>Configurações adicionais</strong></summary>

| Variável | Finalidade | Padrão |
|---|---|---|
| `SIGEE_CONTATO_PRIVACIDADE` | Canal exibido nos documentos de privacidade. | `suporte.sigee@gmail.com` |
| `DJANGO_SESSION_COOKIE_AGE` | Duração máxima da sessão, em segundos. | `1209600` (14 dias) |
| `DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE` | Expiração da sessão ao fechar o navegador. | `False` |
| `DJANGO_AXES_FAILURE_LIMIT` | Falhas de autenticação antes do bloqueio. | `5` |
| `DJANGO_AXES_COOLOFF_MINUTES` | Duração do bloqueio, em minutos. | `15` |
| `DJANGO_PASSWORD_RESET_TIMEOUT` | Validade do token de recuperação, em segundos. | `3600` (1 hora) |

Com `DEBUG=True`, o backend padrão de e-mail exibe as mensagens no console. Para configurar envio SMTP, consulte as variáveis `DJANGO_EMAIL_*` e `DJANGO_DEFAULT_FROM_EMAIL` em [.env.example](.env.example); o modelo apresenta Gmail como exemplo de provedor. Host, remetente e credenciais dependem do ambiente.

</details>

### Preparação e inicialização

Aplique as migrations, configure os perfis e crie a conta técnica inicial:

```powershell
python manage.py migrate
python manage.py configurar_perfis
python manage.py createsuperuser
python manage.py runserver
```

`configurar_perfis` é idempotente e aplica as permissões definidas no código. Execute-o depois das migrations.

### Páginas de erro

Os erros 400, 403, 404 e 500 usam telas em português compartilhadas por todo o sistema. Falhas na verificação de segurança de formulários (CSRF) também possuem orientação própria, preservando o bloqueio do envio. A página 500 não depende de banco de dados, processadores de contexto ou arquivos estáticos.

As páginas personalizadas de 400, 404 e 500 são exibidas com `DJANGO_DEBUG=False`, conforme o comportamento nativo do Django. Em desenvolvimento, `DEBUG=True` mantém as páginas de diagnóstico. O teste `config.test_erros` verifica as respostas com depuração desativada, sem alterar a configuração do ambiente local.

### Primeiro acesso

1. Acesse o [Django Admin local](http://127.0.0.1:8000/admin/) com a conta técnica criada por `createsuperuser`.
2. Crie uma conta funcional ativa, com senha e e-mail de recuperação, pertencente somente ao grupo `Administrador`, sem `is_staff` e sem `is_superuser`.
3. Acesse o [SIGEE local](http://127.0.0.1:8000/login/) com essa conta. Após o aceite dos documentos vigentes, o Administrador acessa o painel e cadastra as demais contas.
4. Prepare uma conta Administrador destinada à reserva de acesso e designe-a como principal. Em outro terminal, com o ambiente virtual ativado, execute:

```powershell
python manage.py configurar_administrador_principal nome_da_conta_reserva
```

A conta principal é protegida contra desativação pelo fluxo funcional. Sua configuração, substituição e recuperação estão descritas em [Autenticação e contas](docs/tecnica/autenticacao.md#administrador-principal-de-reserva).

Para atualizar uma instalação existente, siga o [procedimento de atualização de bancos](docs/implantacao/seguranca-banco-supabase.md#atualização-de-bancos-existentes), que inclui a transição para UUID e o planejamento pedagógico na reserva.

## Testes

A suíte inclui cenários de regras de negócio, autenticação, autorização, importação, reservas, movimentações, manutenção, contexto pedagógico, indicadores, auditoria, privacidade e contingência da BrasilAPI.

Execute as verificações locais com a configuração de testes:

```powershell
python manage.py check --settings=config.settings_testes
python manage.py test --settings=config.settings_testes
```

Essa configuração fixa **SQLite em memória** e **e-mail em memória**, independentemente de `DATABASE_URL` no `.env`. Ela mantém o runner isolado do banco publicado e não envia e-mails.

Para executar somente um módulo:

```powershell
python manage.py test reservas --settings=config.settings_testes
```

Os cenários que exigem bloqueio de linha são ignorados no SQLite. A preparação da conexão local e os comandos para executá-los estão em [Testes com PostgreSQL isolado](docs/implantacao/seguranca-banco-supabase.md#testes-com-postgresql-isolado). As instruções acima não representam medição de cobertura, desempenho ou validação do ambiente publicado. Os [critérios dos RNFs](docs/requisitos/requisitos-nao-funcionais.md#verificação-dos-rnf04-a-rnf06) definem a conferência de interface, os tempos de consulta e a cobertura por fluxo.

## Documentação

Consulte as referências por assunto para aprofundar as regras, decisões técnicas e procedimentos do sistema.

| Assunto | Referências |
|---|---|
| Requisitos | [Funcionais](docs/requisitos/requisitos-funcionais.md), [não funcionais e segurança](docs/requisitos/requisitos-nao-funcionais.md), [regras de negócio](docs/requisitos/regras-de-negocio.md) |
| Arquitetura e acesso | [Arquitetura](docs/tecnica/arquitetura-do-sistema.md), [matriz de acesso](docs/tecnica/matriz-de-acesso.md) |
| Fluxos e integrações | [Reservas, uso e histórico](docs/tecnica/fluxo-reservas-uso-historico.md), [BrasilAPI](docs/tecnica/integracao-brasilapi.md) |
| Autenticação e auditoria | [Autenticação e contas](docs/tecnica/autenticacao.md), [auditoria](docs/tecnica/auditoria.md) |
| Implantação | [Proteção do Supabase e atualização de bancos existentes](docs/implantacao/seguranca-banco-supabase.md) |
| Privacidade | [Termos e aceite](docs/privacidade/privacidade-e-termos.md), [governança](docs/privacidade/governanca-dados-pessoais.md), [retenção e descarte](docs/privacidade/plano-retencao-descarte.md), [direitos dos titulares](docs/privacidade/procedimento-direitos-titulares.md), [incidentes](docs/privacidade/plano-resposta-incidentes.md) |

Os [diagramas](docs/diagramas/) complementam a documentação da arquitetura, dos dados e dos processos do sistema.
