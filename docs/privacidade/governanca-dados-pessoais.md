# Governança e inventário de dados pessoais

Este documento consolida o inventário das operações de tratamento do SIGEE, o fluxo dos dados e os fornecedores externos. Ele descreve os dados e acessos representados no código; as versões dos documentos apresentados ao usuário são definidas em `config/settings.py` e consultadas por `legal/services.py`.

As hipóteses legais e os prazos marcados como **proposta para validação** não estão aprovados para uma implantação real. A equipe e a instituição controladora devem validá-los antes de utilizar dados pessoais reais.

## Agentes e escopo

- **Controladora em uma implantação real:** instituição que adota o SIGEE e decide as finalidades e os meios essenciais do tratamento. Sua identidade jurídica precisa ser registrada antes do uso institucional.
- **Protótipo acadêmico:** deve utilizar dados sintéticos e contas autorizadas da equipe. A identificação do responsável pelo ambiente público ainda precisa ser validada pela dupla e pelo orientador.
- **Operadores e suboperadores:** dependem dos contratos e da atuação concreta de Vercel, Supabase, provedor de e-mail configurado e demais fornecedores. Gmail é o exemplo de SMTP apresentado em `.env.example`; o fornecedor efetivamente adotado precisa ser confirmado no ambiente.
- **Titulares no escopo atual:** Administradores, Operadores e Professores com conta funcional.
- **Fora do escopo atual:** contas ou dados pessoais de alunos, crianças e adolescentes; dados de saúde, biometria, documentos, dados financeiros e decisões automatizadas sobre pessoas.

## Inventário das operações

| Categoria | Dados | Origem e obrigatoriedade | Finalidade | Acesso | Armazenamento ou compartilhamento | Hipótese legal proposta para validação | Retenção |
|---|---|---|---|---|---|---|---|
| Conta funcional | nome, sobrenome, e-mail, nome de usuário, perfil, estado, datas técnicas e hash da senha | cadastro controlado; obrigatório para criar a conta | identificar, autenticar, recuperar acesso e aplicar permissões | Administrador funcional no cadastro; Superuser técnico na manutenção | PostgreSQL/Supabase | execução da relação institucional ou legítimo interesse, conforme a controladora | enquanto ativa; critério posterior depende de validação |
| Sessão e CSRF | identificador de sessão, horários de início e última atividade e token CSRF | autenticação e cookies técnicos automáticos | autenticação contínua, expiração por tempo e proteção contra requisições forjadas | aplicação Django | cookie identificador no navegador e dados de sessão no servidor | legítimo interesse em segurança ou execução do serviço | sessão: 30 minutos de inatividade e até 8 horas desde o login, configuráveis; CSRF: até um ano |
| Proteção contra abuso | nome de usuário, horário, caminho, navegador, cabeçalhos técnicos e quantidade de falhas | tentativa de login | limitar tentativas abusivas | aplicação e Superuser técnico | banco pelo django-axes; senha é mascarada, IP não é armazenado e o log duplicado de acessos válidos está desativado | legítimo interesse em segurança | janela padrão configurável de 15 minutos; a expiração deixa de bloquear o acesso, mas a remoção dos registros vencidos é acionada por eventos de autenticação, sem exclusão agendada no instante do vencimento |
| Recuperação de senha | e-mail, nome exibido e link temporário | solicitação do usuário | recuperar o acesso | sistema de e-mail e titular | serviço SMTP configurado e caixa do destinatário; por padrão, em desenvolvimento a mensagem é exibida no console | execução do serviço e segurança | token válido por uma hora no padrão configurável; retenção da mensagem depende do backend, do provedor e da caixa do destinatário |
| Reserva | Professor, tipo/modelo, local, período, quantidade, estado, equipamentos alocados, turma, disciplina, atividade e observação pedagógica | formulário do Professor; contexto obrigatório, observação opcional | planejar o uso, reservar unidades e impedir conflitos | próprio Professor; Operador para entrega; Administrador para consulta; acesso técnico conforme permissões | PostgreSQL/Supabase | execução da atividade institucional | proposta pendente de validação |
| Movimentação | Operador, destinatário, equipamento, tipo, data, hora, retirada de origem e observação | confirmação de entrega de reserva e devolução pelo Operador; registros legados preservados | preservar rastreabilidade física | Operador e Administrador; Professor somente dos próprios registros | PostgreSQL/Supabase | execução da atividade e legítimo interesse em rastreabilidade | proposta pendente de validação |
| Manutenção | equipamento, origem na devolução quando aplicável, responsáveis, datas, estado, resultado e descrições | devolução com problema ou abertura manual pelo Administrador ou Operador | acompanhar intervenção e preservar rastreabilidade | Administrador inicia e conclui; Administrador e Operador abrem e consultam | PostgreSQL/Supabase | mesma hipótese institucional aplicável ao histórico, a validar | proposta pendente de validação |
| Configurações e fechamentos | Administrador responsável, motivo, data/hora, versão, valores anterior/novo, reservas afetadas e decisões | configuração de calendário, intervalo, cota, fechamento, reabertura e decisão administrativa | preservar condições acordadas e rastrear alterações e exceções | Administrador autorizado; Professor e Operador consultam os efeitos nas reservas permitidas | PostgreSQL/Supabase | mesma hipótese institucional aplicável à operação e à rastreabilidade, a validar | proposta pendente de validação |
| Utilização pedagógica | Professor, retirada, turma, disciplina, atividade, observação e data | criação por unidade na entrega; edição própria e tratamento de legados | registrar uso realizado e consolidar indicadores | Professor proprietário/destinatário; Administrador/Operador no histórico; Administrador nos indicadores | PostgreSQL/Supabase | mesma hipótese da atividade institucional, a validar | proposta pendente de validação |
| Auditoria | conta, ação, resultado, data, hora, entidade e identificador | eventos automáticos | segurança, responsabilização e investigação | Administrador funcional e Superuser técnico | PostgreSQL/Supabase | legítimo interesse, exercício regular de direitos ou obrigação aplicável | proposta pendente de validação |
| Aceite | conta, versões dos documentos e data/hora | confirmação do usuário | comprovar apresentação e aceite dos documentos | Superuser técnico em consulta somente leitura | PostgreSQL/Supabase | exercício regular de direitos | proposta pendente de validação |
| Campos livres | descrições e observações de equipamento, local, movimentação, reserva, utilização e atividade pedagógica, além de problema e solução da manutenção | entrada de usuário; obrigatoriedade depende da funcionalidade | registrar contexto estritamente necessário | conforme a funcionalidade | PostgreSQL/Supabase | mesma hipótese da funcionalidade correspondente | mesma retenção do registro principal |
| Metadados de infraestrutura | endereço IP, navegador e dados técnicos que o provedor possa registrar | requisição HTTP | entrega, segurança e diagnóstico da aplicação | fornecedor e equipe autorizada | Vercel | deve ser confirmada com o contrato do fornecedor | deve ser confirmada com o fornecedor |
| Feriados | ano derivado da data da reserva e `User-Agent` técnico `SIGEE/1.0` | chamada do backend | informar feriados nacionais | BrasilAPI | BrasilAPI; nenhum identificador do Professor é enviado intencionalmente | não envolve dado pessoal enviado intencionalmente | não persistido pelo SIGEE |

## Fluxo dos dados

A manutenção vincula os responsáveis pela abertura, início e conclusão à intervenção. A exportação inclui as responsabilidades estruturadas da conta, sem identificar os demais responsáveis. Campos livres contêm somente informações necessárias ao equipamento e à intervenção; sua revisão é assistida. A auditoria não copia esses textos.

O histórico específico do calendário contém motivos e valores anterior/novo, embora o evento genérico de auditoria guarde apenas sua referência. A exportação assistida inclui decisões sobre reservas afetadas por fechamento e cancelamentos conforme a conta, mas não exporta integralmente o histórico de alterações do calendário. O atendimento ao titular deve revisar esses registros adicionais e os campos livres quando pertinentes ao pedido; a anonimização da conta não remove seus vínculos históricos protegidos.

```text
Usuário
  -> navegador (cookies técnicos e formulários)
  -> Vercel / aplicação Django
     -> Supabase PostgreSQL (contas, reservas, movimentações, manutenção, contexto, auditoria e aceite)
     -> serviço SMTP configurado (somente recuperação de senha, quando habilitado)
     -> BrasilAPI (somente ano da consulta de feriados)
  <- páginas HTML e respostas do SIGEE
```

Bootstrap e fontes são servidos como arquivos estáticos do próprio projeto. O navegador não precisa consultar Google Fonts ou jsDelivr para renderizar as páginas.

## Fornecedores e APIs

| Fornecedor | Serviço | Dados envolvidos | Decisão atual | Validação pendente |
|---|---|---|---|---|
| Vercel | hospedagem da aplicação | requisições e metadados técnicos; dados processados pelo backend | necessário ao deploy atual | contrato, região, retenção de logs e suboperadores |
| Supabase | PostgreSQL gerenciado | todos os dados persistidos | necessário ao banco publicado | região, backups, descarte, acesso e suboperadores |
| Provedor de e-mail configurado | SMTP | destinatário, nome exibido e link de recuperação | Gmail é exemplo em `.env.example`; envio e fornecedor dependem da configuração do ambiente | confirmar fornecedor, retenção, região, conta institucional e contrato |
| BrasilAPI | feriados nacionais | ano e identificador técnico do cliente | chamada não bloqueante sem dado pessoal intencional | revisar periodicamente o contrato público |
| GitHub | código-fonte | código e documentação, sem banco ou segredos | necessário ao versionamento | manter proteção de segredos e revisão de histórico |

## Educação e crianças

O contexto do produto é educacional, mas os titulares atuais são profissionais com perfis Administrador, Operador e Professor. O sistema não cadastra alunos, responsáveis, notas, frequência, necessidades especiais ou outros dados de crianças e adolescentes.

Os cadastros pedagógicos armazenam nome de Turma, Disciplina e Atividade Pedagógica, descrição opcional da atividade, situação e data de criação. Os cadastros não possuem identificadores de alunos nem vínculo direto ao Professor. O Administrador mantém os cadastros; a auditoria registra a conta responsável e o identificador da entidade, sem copiar nome ou descrição. Os campos livres devem conter somente o contexto necessário da atividade.

Toda nova reserva contém turma, disciplina e atividade, com observação opcional. A entrega cria o vínculo pedagógico por unidade retirada. O Professor consulta somente seus registros e corrige o contexto até a devolução integral; Administrador e Operador consultam pelo histórico autorizado. Registros antigos sem reserva preservam os vínculos e permitem edição pelo Professor destinatário enquanto há pendências. A exportação inclui planejamento e utilizações; a anonimização preserva a referência histórica à conta desativada. Não há identificadores de alunos nem descarte automático dos históricos; a retenção institucional exige aprovação específica.

Antes de ampliar o domínio pedagógico, a equipe deve repetir este inventário. Se a mudança introduzir dados de alunos, será necessária avaliação específica de melhor interesse, minimização, vínculo com responsáveis, permissões, transparência adequada à idade e retenção.

## Decisões que exigem validação

1. identidade do controlador do protótipo e da implantação;
2. hipótese legal por finalidade;
3. prazo de conta, reserva e planejamento, movimentação, manutenção, utilização pedagógica, auditoria e aceite;
4. região, suboperadores, backups e transferência internacional dos fornecedores;
5. canal institucional e responsáveis pelo atendimento a titulares e incidentes.
