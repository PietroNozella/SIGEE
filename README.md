<div align="center">

# SIGEE

**Sistema Integrado de Gestão de Equipamentos Escolares**

Aplicação web acadêmica desenvolvida como Projeto de Conclusão de Curso (PFC) em Engenharia de Software na Universidade de Mogi das Cruzes (UMC).

[![Status](https://img.shields.io/badge/status-planejamento_e_modelagem-F0AD4E?style=for-the-badge)](#estado-atual)
[![Python 3.12](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django 5.2 LTS](https://img.shields.io/badge/Django_5.2_LTS-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap_5-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

</div>

## Estado atual

O projeto está na etapa de **planejamento e modelagem**. No estado atual deste repositório, ainda não existem aplicação Django, modelos, migrations ou testes implementados.

As funcionalidades e tecnologias descritas abaixo representam o **escopo aprovado para a entrega final**, e não funcionalidades já concluídas. O código, os testes e as evidências de execução serão registrados no repositório conforme o desenvolvimento avançar.

## Preparação do ambiente local

O projeto utiliza Python 3.12, Django 5.2 e PostgreSQL. Para preparar o ambiente:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Preencha `DATABASE_URL` no arquivo `.env` com a conexão do PostgreSQL no Supabase. Enquanto a variável não estiver disponível, o projeto utiliza SQLite somente para desenvolvimento local. O arquivo `.env` não deve ser versionado.

## Sobre o projeto

O SIGEE tem como objetivo centralizar a gestão de equipamentos tecnológicos de uma instituição de ensino. A solução deverá controlar inventário, disponibilidade, reservas, movimentações, manutenções e utilização pedagógica, preservando a rastreabilidade das operações.

## Perfis de acesso

- **Administrador:** gerencia o sistema e o inventário e consulta o painel com indicadores.
- **Operador:** registra retiradas, devoluções, movimentações e operações autorizadas de manutenção.
- **Professor:** consulta a disponibilidade, realiza reservas e associa a utilização dos equipamentos a turmas, disciplinas e atividades pedagógicas.

A autenticação e a autorização serão implementadas no servidor com Django Authentication, Groups e Permissions, seguindo controle de acesso baseado em papéis (RBAC).

## Escopo aprovado

A entrega final deverá contemplar os 11 requisitos funcionais aprovados:

- **RF-01 — Autenticação e autorização:** autenticar usuários e limitar as ações conforme o perfil.
- **RF-02 — Inventário:** cadastrar e gerenciar equipamentos com patrimônio único, categoria, local e situação.
- **RF-03 — Consulta:** pesquisar e filtrar equipamentos por texto, categoria, local e situação.
- **RF-04 — Reservas:** reservar equipamentos por período, bloqueando conflitos e indisponibilidade.
- **RF-05 — Retirada e devolução:** registrar as movimentações físicas, com ou sem reserva prévia quando permitido.
- **RF-06 — Histórico:** consultar movimentações com data, hora, responsável, destinatário e tipo.
- **RF-07 — Manutenção:** registrar e acompanhar intervenções, mantendo o equipamento indisponível durante a manutenção.
- **RF-08 — Painel do inventário:** apresentar indicadores numéricos, totais por situação, movimentações recentes e representações gráficas.
- **RF-09 — Feriados nacionais:** consultar a BrasilAPI durante o processo de reserva sem tornar a integração bloqueante.
- **RF-10 — Contexto pedagógico:** vincular a utilização a turma, disciplina e atividade pedagógica.
- **RF-11 — Indicadores pedagógicos:** apresentar ao administrador informações consolidadas sobre a utilização dos equipamentos.

A auditoria básica de acessos e ações relevantes integra os requisitos transversais de segurança da entrega.

Equipamentos com registros relacionados deverão ser **inativados**, em vez de excluídos definitivamente, para preservar os históricos de movimentação, manutenção e utilização pedagógica.

### Fora do escopo

- leitura por código de barras ou QR Code;
- APIs ou integrações externas adicionais além da BrasilAPI e dos serviços de infraestrutura previstos;
- suporte a múltiplas unidades escolares;
- relatórios avançados;
- notificações automáticas.

## Arquitetura e tecnologias previstas

O SIGEE adotará uma arquitetura web **monolítica com Django** e renderização no servidor. Não haverá frontend SPA separado nem API própria desacoplada.

- **Aplicação:** Python 3.12 e Django 5.2 LTS.
- **Autenticação e autorização:** Django Authentication, Groups e Permissions.
- **Persistência:** Django ORM e migrations.
- **Banco de dados:** PostgreSQL hospedado no Supabase.
- **Interface:** Django Templates, HTML5, CSS3, JavaScript pontual e Bootstrap 5.
- **Integração externa:** BrasilAPI — API de Feriados Nacionais.
- **Implantação prevista:** Vercel para a aplicação Django e Supabase para o PostgreSQL.
- **Versionamento:** Git e GitHub, com revisão por Pull Request.
- **Organização e documentação:** Notion, Figma e Microsoft Teams.

O Supabase será utilizado somente para hospedar o PostgreSQL. A autenticação e as permissões permanecerão nos recursos nativos do Django; Supabase Auth e políticas RLS não fazem parte do escopo aprovado.

A implantação na Vercel depende de prova técnica de compatibilidade com a aplicação Django, a conexão segura com o banco e a execução das migrations.

## Integração com a BrasilAPI

Durante a criação de uma reserva, o backend consultará a BrasilAPI por HTTPS para identificar feriados nacionais no período selecionado. Essa integração terá caráter informativo e **não bloqueará a reserva** caso o serviço esteja indisponível ou exceda o tempo limite configurado.

## Qualidade, segurança e validação

- Permissões serão aplicadas no servidor conforme os perfis Administrador, Operador e Professor.
- Sessões, cookies seguros, proteção CSRF e validação de entrada utilizarão os mecanismos consolidados do Django.
- Credenciais, `DJANGO_SECRET_KEY` e `DATABASE_URL` permanecerão em variáveis de ambiente, fora do código-fonte.
- O ambiente publicado deverá utilizar HTTPS, inclusive na conexão com o PostgreSQL.
- Serão tratados apenas os dados pessoais básicos necessários, como nome, e-mail e perfil de acesso.
- Testes e demonstrações utilizarão dados sintéticos.
- Ações relevantes deverão registrar usuário, ação, data/hora e entidade afetada.
- Os fluxos críticos deverão funcionar em desktop e dispositivos móveis, com navegação por teclado e contraste adequado.
- As consultas principais deverão responder em até três segundos na base de testes.
- As principais regras, modelos e serviços deverão possuir testes automatizados, com cobertura mínima de 50% e validação dos fluxos críticos.

Os controles relacionados à proteção contra tentativas abusivas de login, recuperação segura de senha e publicação de Termo de Uso e Política de Privacidade permanecem candidatos sujeitos à validação acadêmica; não compõem o baseline obrigatório até essa confirmação.

## Critérios de conclusão

O escopo será considerado concluído quando:

- os requisitos funcionais aprovados estiverem implementados, testados e demonstrados;
- conflitos de reserva e ações sem permissão forem bloqueados no servidor;
- a indisponibilidade da BrasilAPI não impedir a conclusão de uma reserva;
- movimentações, manutenções, utilizações pedagógicas e ações auditáveis preservarem a rastreabilidade;
- o painel apresentar indicadores numéricos e gráficos coerentes com os dados cadastrados;
- os testes automatizados atingirem a cobertura mínima definida para a entrega.

## Processo de desenvolvimento

O trabalho será organizado em Kanban, com acompanhamento no Notion e comunicação no Microsoft Teams. Requisitos, regras de negócio, decisões de arquitetura, diagramas, protótipos e evidências de testes deverão manter rastreabilidade com a implementação registrada no repositório durante o desenvolvimento.

## Autores

Projeto desenvolvido em dupla para o PFC de Engenharia de Software da UMC:

- **Diego Alves da Silva Fagundes** — [GitHub](https://github.com/Diego251Fagundes)
- **Pietro Lopes Nozella Sousa** — [GitHub](https://github.com/PietroNozella)

## Orientação acadêmica

- **Orientador(a):** a confirmar
- **Coorientador(a):** a confirmar
