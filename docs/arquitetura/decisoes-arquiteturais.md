# Decisões Arquiteturais

Este documento reúne as decisões já registradas para o SIGEE. Nem todos os elementos previstos estão implementados no estado atual.

## Aplicação monolítica

O sistema será uma aplicação web monolítica com Django e renderização no servidor por Django Templates. Não haverá frontend SPA separado nem API própria desacoplada.

## Autenticação e autorização

A autenticação e as permissões permanecerão nos recursos nativos do Django, utilizando Django Authentication, Groups e Permissions. Supabase Auth e políticas RLS não fazem parte do escopo aprovado.

## Banco de dados

O Supabase será utilizado somente para hospedar o PostgreSQL. A persistência da aplicação utilizará Django ORM e migrations.

## Integração com feriados nacionais

A BrasilAPI será consultada durante a criação de reservas para identificar feriados nacionais. A integração será informativa e não bloqueará a reserva caso o serviço esteja indisponível ou exceda o tempo limite configurado.

## Implantação

A Vercel está prevista para a implantação da aplicação Django. Essa escolha depende de prova técnica de compatibilidade com a aplicação, a conexão segura com o PostgreSQL e a execução das migrations.

## Versionamento e organização

- O versionamento utilizará Git e GitHub, com revisão por Pull Request.
- O trabalho será organizado em Kanban, com acompanhamento no Notion e comunicação no Microsoft Teams.
- Requisitos, regras de negócio, decisões de arquitetura, diagramas, protótipos e evidências de testes deverão manter rastreabilidade com a implementação registrada no repositório durante o desenvolvimento.
