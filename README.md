# SIGEE

**Sistema Integrado de Gestão de Equipamentos Escolares**

Projeto Final de Curso (PFC) do Bacharelado em Engenharia de Software da Universidade de Mogi das Cruzes (UMC).

## Sobre o projeto

O SIGEE é uma aplicação web em desenvolvimento para apoiar a gestão de equipamentos tecnológicos em instituições de ensino. O escopo planejado contempla inventário, disponibilidade, reservas, movimentações, manutenção e rastreabilidade de utilização.

## Estado atual

Atualmente, o projeto possui:

- estrutura inicial em Django;
- modelos e migrations de Categoria, Local, Equipamento e Movimentação;
- restrição de unicidade do número patrimonial dos equipamentos;
- registros desses modelos no Django Admin;
- configuração por variáveis de ambiente, com SQLite local e suporte a PostgreSQL.

Ainda não há telas ou rotas da aplicação além de `/admin/`, nem testes automatizados implementados.

## Tecnologias atuais

- Python 3.12
- Django 5.2
- Django ORM e migrations
- SQLite para desenvolvimento local
- PostgreSQL por `DATABASE_URL`

## Execução local

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No arquivo `.env`, substitua `DJANGO_SECRET_KEY` por uma chave local. Para utilizar SQLite, remova ou deixe vazia a variável `DATABASE_URL`. Para utilizar PostgreSQL, substitua o valor de exemplo por uma conexão válida.

Depois, prepare o banco, crie o usuário do Django Admin e inicie a aplicação:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Autores

- Diego Alves da Silva Fagundes
- Pietro Lopes Nozella Sousa
