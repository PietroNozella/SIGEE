# Arquitetura

## Visão geral

O SIGEE adota uma arquitetura web monolítica com Django e renderização no servidor. Não haverá frontend SPA separado nem API própria desacoplada.

## Estrutura atual da aplicação

- `config`: configurações gerais, URLs e pontos de entrada ASGI e WSGI.
- `inventario`: modelos e administração de categorias, locais e equipamentos.
- `movimentacoes`: modelo e administração de movimentações.
- `templates`: diretório preparado para os templates do Django.
- `static`: diretório preparado para arquivos estáticos.

No estado atual, a única rota configurada é o Django Admin em `/admin/`.

## Tecnologias previstas

- **Aplicação:** Python 3.12 e Django 5.2 LTS.
- **Autenticação e autorização:** Django Authentication, Groups e Permissions.
- **Persistência:** Django ORM e migrations.
- **Banco de dados:** PostgreSQL hospedado no Supabase.
- **Interface:** Django Templates, HTML5, CSS3, JavaScript pontual e Bootstrap 5.
- **Integração externa:** BrasilAPI — API de Feriados Nacionais.
- **Implantação prevista:** Vercel para a aplicação Django e Supabase para o PostgreSQL.

## Persistência e configuração

A aplicação lê `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` e `DATABASE_URL` de variáveis de ambiente carregadas a partir do arquivo `.env`. Quando `DATABASE_URL` não está definida, a configuração atual utiliza SQLite para desenvolvimento local.

## Integração externa

Durante a criação de uma reserva, o backend consultará a BrasilAPI por HTTPS para identificar feriados nacionais. A consulta terá caráter informativo e não será bloqueante.

## Implantação

A implantação na Vercel depende de prova técnica de compatibilidade com a aplicação Django, a conexão segura com o banco e a execução das migrations.
