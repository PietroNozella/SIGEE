# SIGEE — Sistema Integrado de Gestão de Equipamentos Escolares

Aplicação web acadêmica desenvolvida como Projeto de Conclusão de Curso (PFC) em Engenharia de Software na Universidade de Mogi das Cruzes (UMC).

## Sobre o projeto

O SIGEE é uma aplicação web para a gestão de equipamentos tecnológicos de uma instituição de ensino.

## Problema e objetivo

O projeto parte da necessidade de centralizar a gestão desses equipamentos. Seu objetivo é controlar inventário, disponibilidade, reservas, movimentações, manutenções e utilização pedagógica, preservando a rastreabilidade das operações.

## Principais funcionalidades

O escopo aprovado prevê:

- Gestão e consulta do inventário.
- Reservas de equipamentos.
- Registro de retirada, devolução e demais movimentações.
- Acompanhamento de manutenções.
- Associação da utilização a turma, disciplina e atividade pedagógica.
- Indicadores administrativos e pedagógicos.

## Perfis

- **Administrador:** gerencia o sistema e o inventário e consulta o painel com indicadores.
- **Operador:** registra retiradas, devoluções, movimentações e operações autorizadas de manutenção.
- **Professor:** consulta a disponibilidade, realiza reservas e associa a utilização dos equipamentos a turmas, disciplinas e atividades pedagógicas.

## Arquitetura resumida

O SIGEE adota uma arquitetura web monolítica com Django e renderização no servidor por meio de Django Templates. A autenticação e a autorização utilizarão Django Authentication, Groups e Permissions. O PostgreSQL será hospedado no Supabase, e a implantação da aplicação na Vercel está prevista e depende de prova técnica de compatibilidade.

## Tecnologias principais

- Python 3.12 e Django 5.2 LTS.
- Django Templates, HTML5, CSS3, JavaScript pontual e Bootstrap 5.
- PostgreSQL hospedado no Supabase.
- BrasilAPI para consulta informativa de feriados nacionais.

## Estado atual do desenvolvimento

O projeto possui a estrutura inicial em Django, com configuração por variáveis de ambiente, suporte a PostgreSQL ou SQLite local, apps `inventario` e `movimentacoes`, modelos e migrations iniciais e registros no Django Admin. Ainda não existem telas ou rotas da aplicação além da administração, nem casos de teste automatizados implementados.

## Como executar localmente

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Após copiar o arquivo, substitua `DATABASE_URL` no `.env` por uma conexão válida do Supabase. Para utilizar SQLite localmente, deixe a variável vazia ou remova a linha. O arquivo `.env` não deve ser versionado.

## Documentação

A documentação técnica e funcional está disponível no [índice da documentação](docs/README.md).

## Autores

- **Diego Alves da Silva Fagundes** — [GitHub](https://github.com/Diego251Fagundes)
- **Pietro Lopes Nozella Sousa** — [GitHub](https://github.com/PietroNozella)
