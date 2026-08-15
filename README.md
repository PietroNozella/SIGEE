<div align="center">

  # SIGEE

  **Sistema Integrado de Gestão de Equipamentos Escolares**

  Aplicação web desenvolvida como Projeto de Conclusão de Curso (PFC) em Engenharia de Software na Universidade de Mogi das Cruzes (UMC).

  [![Python 3.12](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![Django 5.2](https://img.shields.io/badge/Django_5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
  [![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
  [![Bootstrap 5.3](https://img.shields.io/badge/Bootstrap_5.3-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

</div>

## Sobre o projeto

O SIGEE centraliza o controle de equipamentos escolares, sua disponibilidade, reservas, retiradas, devoluções e manutenções. A proposta busca melhorar a rastreabilidade dos ativos e apoiar a organização do uso de recursos tecnológicos em instituições de ensino.

## Escopo da entrega final

Ao final do projeto, o sistema deverá entregar:

- Autenticação e autorização por perfis: **Administrador**, **Operador** e **Professor**.
- Cadastro e consulta do inventário, com número patrimonial único, categoria, localização e situação do equipamento.
- Pesquisa e filtros para localizar equipamentos.
- Reserva por período, com validação de conflitos de disponibilidade.
- Registro de retirada e devolução de equipamentos.
- Histórico de movimentações, com data e hora, responsável, destinatário e tipo de movimentação.
- Registro e consulta do histórico de manutenção, com indisponibilidade temporária quando necessário.
- Painel resumido com totais por situação do inventário e movimentações recentes.

Equipamentos que possuírem histórico relacionado serão inativados, em vez de excluídos definitivamente, preservando a rastreabilidade das informações.

### Fora do escopo

Não fazem parte da entrega final: leitura por código de barras ou QR Code, integrações externas, suporte a múltiplas unidades escolares, relatórios avançados e notificações automáticas.

## Tecnologias e arquitetura

O SIGEE será uma aplicação monolítica web, com renderização no servidor.

- **Back-end:** Python 3.12, Django 5.2, Django ORM, Django Authentication, Groups e Permissions.
- **Banco de dados:** PostgreSQL hospedado no Supabase.
- **Front-end:** Django Templates, HTML, CSS, JavaScript e Bootstrap 5.3.
- **Implantação:** Vercel.
- **Ferramentas de apoio:** Git, GitHub, Figma, Notion e Microsoft Teams.

O Supabase será utilizado como serviço de banco de dados. A autenticação, os perfis e as permissões serão controlados pelos recursos nativos do Django; não será utilizado Supabase Auth nem políticas RLS.

## Qualidade, segurança e validação

- O acesso às funcionalidades será restrito conforme o perfil do usuário.
- Serão mantidos apenas dados básicos de identificação, como nome, e-mail e perfil; não haverá tratamento de dados sensíveis.
- Testes e demonstrações utilizarão dados sintéticos.
- Os requisitos funcionais, as regras de negócio e os critérios de aceite serão validados, priorizando os fluxos críticos de reserva, retirada, devolução, manutenção e controle de acesso.
- A interface deverá ser responsiva, oferecer navegação por teclado e contraste adequado. As consultas deverão responder em até três segundos na base de testes.

## Processo de desenvolvimento

O trabalho será organizado em Kanban, com acompanhamento no Notion e comunicação no Microsoft Teams. A documentação do projeto incluirá requisitos, diagramas UML, diagrama entidade-relacionamento, protótipos no Figma e evidências de testes, garantindo rastreabilidade entre o que foi definido, implementado e validado.

## Autores

Projeto desenvolvido em dupla para o PFC de Engenharia de Software da UMC:

- **Diego Alves da Silva Fagundes** — [GitHub](https://github.com/Diego251Fagundes)
- **Pietro Lopes Nozella Sousa** — [GitHub](https://github.com/PietroNozella)

## Orientadores

- **Orientador(a):** a ser definido
- **Coorientador(a):** Alessandro Aparecido da Silva Horas
