<div align="center">

# SIGEE

### Sistema Integrado de Gestão de Equipamentos Escolares

Centralize o inventário tecnológico da instituição com controle de acesso, rastreabilidade e segurança.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-F59E0B?style=for-the-badge)
[![Deploy](https://img.shields.io/badge/deploy-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://sigee-psi.vercel.app/login/)

**[Acessar o SIGEE →](https://sigee-psi.vercel.app/login/)**

#### Aplicação

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![Django Templates](https://img.shields.io/badge/Django%20Templates-092E20?style=for-the-badge&logo=django&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)

#### Interface

![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap%205-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)

#### Dados e infraestrutura

![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

#### Desenvolvimento e design

![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)
![Figma](https://img.shields.io/badge/Figma-F24E1E?style=for-the-badge&logo=figma&logoColor=white)

</div>

## Sobre o SIGEE

O SIGEE é uma plataforma web para organizar e acompanhar equipamentos tecnológicos de instituições de ensino. A aplicação reúne inventário, usuários, permissões e registros de auditoria em um único ambiente, reduzindo controles dispersos e facilitando a consulta das informações.

## Problema e contexto

Em instituições de ensino, o registro descentralizado de reservas, localização, manutenção e utilização de equipamentos dificulta a consulta da disponibilidade e a rastreabilidade dos itens.

O SIGEE centraliza o inventário, as reservas e os registros relacionados, reduzindo conflitos de uso e facilitando o acompanhamento dos equipamentos.

## Perfis de acesso

O SIGEE não possui cadastro público. As contas são criadas por usuários autorizados e recebem um perfil compatível com suas responsabilidades.

| Perfil | Acesso disponível atualmente |
|---|---|
| **Administrador** | Gerencia o inventário, importa equipamentos, cadastra usuários, consulta o resumo e acessa a auditoria. |
| **Operador** | Consulta o inventário e a disponibilidade registrada dos equipamentos. |
| **Professor** | Consulta os equipamentos e a disponibilidade, cria reservas próprias em lote e cancela as próprias reservas. |

Consulte os detalhes de autorização na [matriz de acesso](docs/matriz-de-acesso.md).

## Arquitetura

O SIGEE utiliza uma arquitetura web monolítica com Django e renderização no servidor. Autenticação, autorização, regras de negócio, persistência e interface permanecem integradas na mesma aplicação, reduzindo a complexidade operacional e mantendo o código simples de evoluir.

| Camada | Tecnologias e decisões |
|---|---|
| **Interface** | Django Templates, HTML5, CSS3, Bootstrap 5 e JavaScript pontual. |
| **Aplicação** | Python 3.12, Django 5.2 LTS, Django ORM, Authentication e Groups/Permissions. |
| **Persistência** | SQLite no desenvolvimento local e PostgreSQL configurado por `DATABASE_URL`, com Supabase na infraestrutura do projeto. |
| **Implantação** | Aplicação publicada na Vercel com HTTPS. |
| **Segurança** | Sessões, proteção CSRF, validação no servidor, hash de senhas, cookies seguros em produção e auditoria. |
| **Integração externa** | BrasilAPI para consulta informativa e não bloqueante de feriados nacionais durante a reserva. |

## Execução local

### Pré-requisitos

- Python 3.12;
- Git;
- PostgreSQL opcional — sem `DATABASE_URL`, o projeto utiliza SQLite.

### Instalação

Na raiz do repositório, crie e ative o ambiente virtual, instale as dependências e prepare o arquivo de configuração:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite o arquivo `.env`, defina uma chave local em `DJANGO_SECRET_KEY` e escolha o banco de dados:

- para usar SQLite, deixe `DATABASE_URL=` sem valor;
- para usar PostgreSQL, informe uma URL de conexão válida.

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|:---:|---|
| `DJANGO_SECRET_KEY` | Sim | Chave usada pelos mecanismos criptográficos do Django. |
| `DJANGO_DEBUG` | Não | Ativa o modo de depuração; use `False` em produção. |
| `DJANGO_ALLOWED_HOSTS` | Não | Lista de hosts permitidos, separados por vírgula. |
| `DATABASE_URL` | Não | Conexão PostgreSQL; sem valor, utiliza SQLite local. |
| `SIGEE_CONTATO_PRIVACIDADE` | Não | E-mail exibido nos documentos de privacidade. |

### Preparação e inicialização

Prepare o banco, configure os perfis funcionais e crie a primeira conta técnica:

```powershell
python manage.py migrate
python manage.py configurar_perfis
python manage.py createsuperuser
python manage.py runserver
```

O superusuário deve criar uma conta comum pelo Django Admin e atribuir somente o grupo `Administrador`. Essa conta funcional poderá cadastrar os demais usuários pela rota `/usuarios/novo/`.

Execute `configurar_perfis` depois das migrations. O comando é idempotente e mantém as permissões dos perfis alinhadas à configuração do projeto.

## Testes

A suíte automatizada cobre autenticação, autorização, inventário, importação CSV, usuários, documentos legais, auditoria, reservas, disponibilidade, conflitos, cancelamento e contingência da BrasilAPI.

Para validar o projeto com SQLite:

```powershell
$env:DATABASE_URL=''
python manage.py check
python manage.py test
```

## Funcionalidades disponíveis nesta entrega

- [x] cadastro, importação, consulta, edição e inativação de equipamentos;
- [x] reservas próprias por Professor, com quantidade e controle de disponibilidade;
- [x] prevenção de conflitos e bloqueio de períodos inválidos;
- [x] cancelamento das próprias reservas;
- [x] consulta informativa de feriados nacionais pela BrasilAPI.

## Roadmap

- [ ] retirada e devolução de equipamentos;
- [ ] registro e acompanhamento de manutenções;
- [ ] vinculação da utilização ao contexto pedagógico;
- [ ] indicadores de utilização pedagógica.

![BrasilAPI](https://img.shields.io/badge/integração%20ativa-BrasilAPI-009C3B?style=for-the-badge)

## Documentação técnica

- [Arquitetura do sistema](docs/arquitetura-do-sistema.md)
- [Matriz de acesso](docs/matriz-de-acesso.md)
- [Autenticação e autorização](docs/autenticacao.md)
- [Auditoria de acessos e ações](docs/auditoria.md)
- [Segurança](docs/evidencias-seguranca.md)
- [Privacidade e termos](docs/privacidade-e-termos.md)
