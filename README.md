<div align="center">
  
  # SIGEE
  
  **Sistema Integrado de Gestão de Equipamentos Escolares**
  
  Uma plataforma web para controle, reserva e manutenção de equipamentos tecnológicos em instituições de ensino — desenvolvido como Projeto de Conclusão de Curso (PFC) em Engenharia de Software.
  
  [![Python 3.12.0](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![Django](https://img.shields.io/badge/Django_5.2_LTS-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
  [![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
  [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
  [![Bootstrap](https://img.shields.io/badge/Bootstrap_5.3-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
  
</div>

<br/>

## 📖 Índice
- [Sobre o Projeto](#-sobre-o-projeto)
- [Objetivos](#-objetivos)
- [Tecnologias](#-tecnologias)
- [Funcionalidades Principais](#-funcionalidades-principais)
- [Autores](#-autores)
- [Orientadores](#-orientadores)
 
## 🏫 Sobre o Projeto

**Problema abordado:** Instituições de ensino frequentemente apresentam baixo nível de controle sobre os equipamentos tecnológico (computadores, notebooks, tablets), gerando indisponibilidade, manutenção reativa e desperdício de recursos, o que afeta diretamente a qualidade do ensino.

**Motivação:** Como PFC em Engenharia de Software, o SIGEE propõe uma solução prática e replicável para aumentar a disponibilidade e rastreabilidade de ativos, aplicando princípios de usabilidade, engenharia de software e métricas de qualidade.

## 🎯 Objetivos

**Objetivo Geral**
Projetar e implementar um sistema web para controle, reserva e manutenção de equipamentos escolares com foco em rastreabilidade e facilidade de uso.

**Objetivos Específicos**
- Implementar fluxo de reservas por período e local.
- Registrar histórico de manutenção e estado operacional por equipamento.
- Fornecer um *dashboard* com indicadores essenciais (disponibilidade, uso, pendências).
- Definir papéis e permissões seguras (Administrador, Técnico, Professor).

## 🛠️ Tecnologias

A base tecnológica definida para o desenvolvimento do projeto é composta por:

**Back-end & Banco de Dados**
- Python 3.12 / 3.13
- Django 5.2 LTS
- PostgreSQL (via Supabase)

**Front-end**
- Django Templates
- JavaScript puro
- Bootstrap 5.3

**Ferramentas de Apoio**
- Git e GitHub
- Figma
- Notion

## 🚀 Funcionalidades Principais

- **Reserva de Equipamentos:** Calendário de disponibilidade por item e por local, com bloqueio e verificação de conflitos de período.
- **Gestão de Inventário:** Cadastro completo (CRUD) de equipamentos (modelo, número de série, localização, estado atual).
- **Controle de Manutenção:** Geração de ordens de serviço, registro de intervenções e histórico por equipamento.
- **Dashboard e Relatórios:** Indicadores de taxa de utilização, lista de itens indisponíveis e pendências de manutenção.
- **Autenticação e Perfis:** Acesso restrito baseado em papéis de usuário com registro de auditoria simples.

## 👨‍💻 Autores

Projeto desenvolvido em dupla para o Projeto de Conclusão de Curso (PFC) de Engenharia de Software da Universidade de Mogi das Cruzes (UMC):

- **Diego Alves da Silva Fagundes** — [GitHub](https://github.com/Diego251Fagundes)
- **Pietro Lopes Nozella Sousa** — [GitHub](https://github.com/PietroNozella) 

## 🎓 Orientadores

- **Orientador(a):** a ser definido 
- **Coorientador(a):** Alessandro Aparecido da Silva Horas