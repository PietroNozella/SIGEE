# SIGEE — Sistema Integrado de Gestão de Equipamentos Escolares

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-F59E0B?style=for-the-badge)

**Tecnologias atuais**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)
![Figma](https://img.shields.io/badge/Figma-F24E1E?style=for-the-badge&logo=figma&logoColor=white)

**Tecnologias previstas**

![Django Templates](https://img.shields.io/badge/Django%20Templates-092E20?style=for-the-badge&logo=django&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap%205-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![BrasilAPI](https://img.shields.io/badge/BrasilAPI-009C3B?style=for-the-badge)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

O SIGEE é uma aplicação web desenvolvida como Projeto Final de Curso (PFC) do Bacharelado em Engenharia de Software da Universidade de Mogi das Cruzes (UMC).

## Identificação acadêmica

- **Instituição:** Universidade de Mogi das Cruzes — UMC
- **Curso:** Bacharelado em Engenharia de Software
- **Turma:** 8ºA ES — Matutino
- **Projeto:** Projeto Final de Curso — PFC
- **Local e ano:** Mogi das Cruzes — SP, 2026
- **Autores:** Diego Alves da Silva Fagundes e Pietro Lopes Nozella Sousa
- **Orientador:** Pedro Henrique Miho de Souza
- **Coorientador:** Alessandro Aparecido da Silva Horas

## Problema e contexto

Em instituições de ensino, o registro descentralizado de reservas, localização, manutenção e utilização de equipamentos pode dificultar a consulta da disponibilidade, a rastreabilidade dos itens e a identificação de como esses recursos tecnológicos são empregados nas atividades de ensino. Esse cenário pode gerar conflitos de uso, atrasos nas atividades e dificuldade no acompanhamento da utilização pedagógica.

O SIGEE propõe centralizar o controle dos equipamentos, reservas, movimentações e manutenções, permitindo também relacionar sua utilização a turmas, disciplinas e atividades pedagógicas.

## Objetivos

### Objetivo geral

Desenvolver uma plataforma web para auxiliar instituições de ensino no gerenciamento de equipamentos tecnológicos, centralizando informações e processos de controle, disponibilidade, reserva, retirada, devolução e manutenção, além de permitir o acompanhamento de sua utilização no contexto educacional.

### Objetivos específicos

1. Organizar as informações dos equipamentos tecnológicos.
2. Permitir a consulta da situação e da disponibilidade dos equipamentos.
3. Implementar reserva, retirada e devolução com controle das movimentações.
4. Registrar e acompanhar manutenções.
5. Centralizar a gestão e a consulta em uma aplicação web.
6. Vincular a utilização dos equipamentos a turmas, disciplinas e atividades pedagógicas.

## Público e perfis de acesso

- **Administrador:** gerencia o sistema, o inventário, os usuários e o painel resumido com indicadores.
- **Operador:** registra retiradas, devoluções e demais movimentações autorizadas.
- **Professor:** consulta a disponibilidade, realiza reservas e associa a utilização dos equipamentos ao contexto pedagógico.

Não haverá cadastro público. A primeira conta administrativa funcional será configurada por meio de uma conta técnica de Django Superuser; depois disso, usuários autorizados com perfil Administrador poderão cadastrar as demais contas.

## Escopo planejado

O escopo final do PFC contempla:

- autenticação e autorização por perfil;
- gestão e consulta do inventário;
- categorias, locais, patrimônio único e situação dos equipamentos;
- reservas por período com bloqueio de conflitos e indisponibilidade;
- consulta informativa de feriados nacionais pela BrasilAPI durante a reserva;
- retirada, devolução e histórico de movimentações;
- manutenção e histórico de intervenções;
- vinculação da utilização a turma, disciplina e atividade pedagógica;
- painel resumido do inventário;
- indicadores de utilização pedagógica;
- auditoria básica de acessos e ações relevantes.

### Fora do escopo

- identificação por código de barras ou QR Code;
- integrações externas além da BrasilAPI e dos serviços de infraestrutura previstos;
- gerenciamento simultâneo de múltiplas unidades escolares;
- relatórios avançados;
- notificações automáticas.

## Funcionalidades planejadas

O baseline aprovado contém 11 requisitos funcionais:

- **RF-01:** autenticação e autorização por perfil;
- **RF-02:** cadastro e gerenciamento do inventário;
- **RF-03:** consulta e filtragem de equipamentos;
- **RF-04:** reserva de equipamentos;
- **RF-05:** retirada e devolução;
- **RF-06:** histórico de movimentações;
- **RF-07:** gerenciamento de manutenção;
- **RF-08:** painel resumido do inventário;
- **RF-09:** consulta de feriados nacionais durante a reserva;
- **RF-10:** vinculação da utilização ao contexto pedagógico;
- **RF-11:** indicadores de utilização pedagógica.

Os critérios de aceite estão em [Requisitos funcionais](docs/requisitos-funcionais.md).

## Arquitetura e tecnologias

O SIGEE adota uma arquitetura web monolítica com Django e renderização no servidor. As regras de negócio, autenticação, autorização, acesso aos dados e renderização das páginas permanecem integrados na mesma aplicação.

| Área | Tecnologias e decisões |
|---|---|
| Interface | Django Templates, HTML5, CSS3, Bootstrap 5 e JavaScript pontual |
| Aplicação | Python 3.12, Django 5.2 LTS, Django ORM, Authentication e Groups/Permissions |
| Banco de dados | PostgreSQL com hospedagem prevista no Supabase; SQLite para desenvolvimento local |
| Integração externa | BrasilAPI para consulta não bloqueante de feriados nacionais |
| Implantação | Vercel, condicionada à validação da aplicação, conexão com o banco e migrations |
| Versionamento | Git e GitHub, com integração das alterações por Pull Request |
| Prototipação | Figma |

## Organização do desenvolvimento

- **Método de trabalho:** Kanban.
- **Gestão e acompanhamento:** Notion e Microsoft Teams.
- **Requisitos:** levantamento incremental, com identificação, prioridade e critério de aceite verificável.
- **Modelagem:** UML para fluxos e arquitetura, DER para dados e Figma para validação da interface.
- **Validação:** execução dos requisitos e fluxos críticos de ponta a ponta, com registro do resultado esperado, resultado obtido e evidências.

O [protótipo do SIGEE no Figma](https://www.figma.com/design/cBCn1GfruefHTGZZqTTvDU/Sem-t%C3%ADtulo?node-id=0-1&t=Oi1tT0KLAXj8Yo2G-1) integra os materiais de apoio do projeto.

## Segurança e privacidade

O planejamento prevê autenticação por sessão, autorização aplicada no servidor, proteção CSRF, validação de entrada, segredos em variáveis de ambiente, comunicação HTTPS no ambiente publicado, minimização dos dados pessoais e auditoria das ações relevantes. Os requisitos completos e os itens ainda candidatos estão em [Requisitos não funcionais e de segurança](docs/requisitos-nao-funcionais.md).

## Estado atual do desenvolvimento

O código disponível atualmente possui:

- estrutura inicial em Django;
- apps `inventario` e `movimentacoes`;
- modelos e migrations de Categoria, Local, Equipamento e Movimentação;
- restrição de unicidade do número patrimonial dos equipamentos;
- registros desses modelos no Django Admin;
- configuração por variáveis de ambiente;
- SQLite para desenvolvimento local e suporte a PostgreSQL por `DATABASE_URL`.

Ainda não existem telas ou rotas da aplicação além de `/admin/`, nem testes automatizados implementados. Reservas, manutenção, perfis funcionais, contexto pedagógico, indicadores, BrasilAPI e deploy permanecem como escopo planejado, não como funcionalidades concluídas.

## Execução local

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No arquivo `.env`, substitua `DJANGO_SECRET_KEY` por uma chave local. Para utilizar SQLite, remova ou deixe vazia a variável `DATABASE_URL`. Para utilizar PostgreSQL, substitua o valor de exemplo por uma conexão válida.

Depois, prepare o banco, crie o usuário técnico do Django Admin e inicie a aplicação:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Documentação versionada

- [Requisitos funcionais](docs/requisitos-funcionais.md)
- [Requisitos não funcionais e de segurança](docs/requisitos-nao-funcionais.md)
- [Regras de negócio](docs/regras-de-negocio.md)
