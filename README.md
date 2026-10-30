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
| **Administrador** | Gerencia o inventário, importa equipamentos, cadastra usuários, mantém turmas, disciplinas e atividades pedagógicas, acompanha manutenções, consulta o resumo, a auditoria e o histórico de movimentações. |
| **Operador** | Consulta equipamentos e reservas, registra retirada em lote com ou sem reserva, confirma devolução integral ou parcial, encaminha unidades com problema para manutenção e consulta o histórico de movimentações. |
| **Professor** | Consulta equipamentos e disponibilidade, cria e cancela reservas próprias em lote e consulta Minhas Utilizações para associar contexto pedagógico às retiradas com ou sem reserva, até a devolução integral. |

Consulte os detalhes de autorização na [matriz de acesso](docs/matriz-de-acesso.md).

A navegação do Operador reúne **Equipamentos**, **Reservas**, **Em uso** e **Histórico**. Em Reservas, o botão Registrar retirada abre a entrega sem reserva; em Em uso, são conferidos os lotes pendentes de devolução.

## Arquitetura

O SIGEE utiliza uma arquitetura web monolítica com Django e renderização no servidor. Autenticação, autorização, regras de negócio, persistência e interface permanecem integradas na mesma aplicação, reduzindo a complexidade operacional e mantendo o código simples de evoluir.

| Camada | Tecnologias e decisões |
|---|---|
| **Interface** | Django Templates, HTML5, CSS3, Bootstrap 5 e JavaScript pontual. |
| **Aplicação** | Python 3.12, Django 5.2 LTS, Django ORM, Authentication e Groups/Permissions. |
| **Persistência** | SQLite no desenvolvimento local e PostgreSQL configurado por `DATABASE_URL`, com Supabase na infraestrutura do projeto. |
| **Implantação** | Aplicação publicada na Vercel com HTTPS. |
| **Segurança** | Sessões, proteção CSRF, bloqueio temporário de tentativas, validação no servidor, hash de senhas, cookies seguros em produção e auditoria. |
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
| `DATABASE_URL` | Não | Conexão PostgreSQL; no Supabase, inclua `sslmode=require`. Sem valor, utiliza SQLite local. |
| `SIGEE_CONTATO_PRIVACIDADE` | Não | E-mail exibido nos documentos de privacidade. |
| `DJANGO_SESSION_COOKIE_AGE` | Não | Duração máxima da sessão em segundos; padrão de 14 dias. |
| `DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE` | Não | Encerra a sessão ao fechar o navegador quando definido como `True`. |
| `DJANGO_AXES_FAILURE_LIMIT` | Não | Quantidade de falhas antes do bloqueio; padrão `5`. |
| `DJANGO_AXES_COOLOFF_MINUTES` | Não | Duração do bloqueio temporário; padrão `15` minutos. |

### Preparação e inicialização

Prepare o banco, configure os perfis funcionais e crie a primeira conta técnica:

```powershell
python manage.py migrate
python manage.py configurar_perfis
python manage.py createsuperuser
python manage.py runserver
```

O superusuário deve criar uma conta comum pelo Django Admin e atribuir somente o grupo `Administrador`. Essa conta funcional poderá cadastrar os demais usuários pela rota `/usuarios/novo/`.

Prepare também uma conta Administrador para reserva de acesso, com senha e e-mail
de recuperação, e designe-a como principal:

```powershell
python manage.py configurar_administrador_principal nome_da_conta_reserva
```

Somente o principal pode desativar e reativar administradores comuns. Ambos mantêm
a gestão de Professores e Operadores. A conta principal permanece ativa e protegida;
para transferir a função, use o mesmo comando com outra conta e `--substituir`.
As migrations não promovem usuários existentes automaticamente. Consulte o
[procedimento de configuração e recuperação](docs/autenticacao.md#administrador-principal-de-reserva).

Execute `configurar_perfis` depois das migrations. O comando é idempotente e mantém as permissões dos perfis alinhadas à configuração do projeto.

As contas usam UUID como chave primária na tabela `auth_user`. Para atualizar um
banco que ainda usa IDs numéricos, guarde um backup e mantenha a aplicação em
manutenção até publicar a versão nova. Execute, nessa ordem:

```powershell
python manage.py migrate contas 0001 --settings=config.settings_preparacao_uuid
python manage.py migrate
python manage.py configurar_perfis
```

A configuração de preparação é exclusiva para o primeiro comando. A conversão
preserva as contas e seus vínculos, encerra as sessões e invalida links antigos
de recuperação de senha. A reversão exige restaurar o backup e o código anterior.

## Testes

A suíte automatizada cobre autenticação, bloqueio de tentativas, autorização, inventário, importação CSV, usuários, documentos legais, auditoria, reservas, disponibilidade, conflitos, cancelamento, manutenção, devolução com problema, direitos dos titulares e contingência da BrasilAPI.

Para validar o projeto com SQLite:

```powershell
python manage.py check --settings=config.settings_testes
python manage.py test --settings=config.settings_testes
```

Essa configuração usa SQLite em memória, independentemente do `DATABASE_URL`
presente no `.env`. No PowerShell, atribuir uma string vazia à variável de
ambiente pode removê-la e permitir que a conexão remota do `.env` seja carregada
novamente. Para testar concorrência em PostgreSQL, use uma instância isolada e
uma configuração específica; `settings_testes` destina-se aos testes locais em
SQLite.

## Funcionalidades disponíveis nesta entrega

A versão atual inclui manutenção, utilização pedagógica com e sem reserva,
painel e indicadores pedagógicos. As evidências de cada recorte distinguem testes
isolados e verificações dos fluxos no ambiente publicado.

- [x] cadastro, importação, consulta, edição e inativação de equipamentos;
- [x] reservas próprias por Professor, com quantidade e controle de disponibilidade;
- [x] prevenção de conflitos e bloqueio de períodos inválidos;
- [x] cancelamento das próprias reservas;
- [x] retirada sem reserva em lote por Operador, com quantidade, conferência dos patrimônios e atualização atômica para em uso;
- [x] retirada integral das unidades alocadas à reserva, do início até antes dos 30 minutos de tolerância;
- [x] devolução básica em lote ou parcial por qualquer Operador autorizado, com seleção dos patrimônios, vínculo individual à retirada, auditoria e proteção contra duplicidade;
- [x] histórico de retiradas e devoluções para Administrador e Operador, com filtros, paginação e vínculos de origem;
- [x] devolução com problema por patrimônio, com abertura automática de manutenção e gravação atômica do lote;
- [x] abertura manual, acompanhamento e conclusão de manutenção pelo Administrador, com resultado reparado ou sem reparo, indisponibilidade, auditoria e histórico;
- [x] criação, consulta, edição, inativação e reativação de turmas, disciplinas e atividades pedagógicas pelo Administrador, com permissões e auditoria;
- [x] associação pedagógica das utilizações com e sem reserva pelo Professor, aplicada ao lote após a retirada, com edição até a devolução integral e preservação no histórico;
- [x] Minhas Utilizações reúne as retiradas próprias com e sem reserva, inclusive encerradas;
- [x] indicadores pedagógicos por turma, disciplina e atividade, com utilizações, retiradas e equipamentos distintos;
- [x] painel do Administrador com totais, gráfico por situação e dez movimentações recentes;
- [x] consulta informativa de feriados nacionais pela BrasilAPI.
- [x] transparência de privacidade, inventário de dados e aceite versionado;
- [x] comandos assistidos para exportação, anonimização e descarte controlado.

## Roadmap

- [ ] conclusão da validação dos fluxos no ambiente publicado;
- [ ] revisão cruzada do incremento pedagógico sem reserva;
- [x] indicadores de utilização pedagógica.

![BrasilAPI](https://img.shields.io/badge/integração%20ativa-BrasilAPI-009C3B?style=for-the-badge)

## Documentação técnica

- [Arquitetura do sistema](docs/arquitetura-do-sistema.md)
- [Matriz de acesso](docs/matriz-de-acesso.md)
- [Evidências de criação, conflitos e cancelamento de reservas](docs/evidencias-reservas.md)
- [Evidências de retiradas e devoluções](docs/evidencias-movimentacoes.md)
- [Evidências de devolução com problema e manutenção](docs/evidencias-manutencoes.md)
- [Evidências de utilização pedagógica e indicadores](docs/evidencias-pedagogico-indicadores.md)
- [Evidências de cadastros de equipamentos e usuários](docs/evidencias-cadastros.md)
- [Evidências do painel do inventário](docs/evidencias-painel.md)
- [Interface e acessibilidade básica: primeiro recorte](docs/evidencias-interface.md)
- [Medições de contraste e compatibilidade em Chrome e Edge](docs/evidencias-contraste-compatibilidade.md)
- [Desempenho das consultas e correção da expiração de reservas](docs/evidencias-desempenho.md)
- [Configurações, TLS e consulta real de feriados](docs/evidencias-configuracoes-feriados.md)
- [Cadastros pedagógicos e evidências da entrega](docs/cadastros-pedagogicos.md)
- [Utilização pedagógica com reserva e evidências](docs/utilizacao-pedagogica-reserva.md)
- [Utilização pedagógica sem reserva e evidências](docs/utilizacao-pedagogica-sem-reserva.md)
- [Autenticação e autorização](docs/autenticacao.md)
- [Auditoria de acessos e ações](docs/auditoria.md)
- [Segurança](docs/evidencias-seguranca.md)
- [Proteção das tabelas Django no Supabase](docs/seguranca-banco-supabase.md)
- [Privacidade e termos](docs/privacidade-e-termos.md)
- [Governança e inventário de dados pessoais](docs/governanca-dados-pessoais.md)
- [Plano de retenção e descarte](docs/plano-retencao-descarte.md)
- [Procedimento para direitos dos titulares](docs/procedimento-direitos-titulares.md)
- [Plano de resposta a incidentes](docs/plano-resposta-incidentes.md)
