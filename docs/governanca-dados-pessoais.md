# Governança e inventário de dados pessoais

Este documento consolida o inventário das operações de tratamento do SIGEE, o fluxo dos dados e os fornecedores externos. Ele descreve o estado técnico verificado na versão 2.0 dos documentos legais.

As hipóteses legais e os prazos marcados como **proposta para validação** não estão aprovados para uma implantação real. A equipe e a instituição controladora devem validá-los antes de utilizar dados pessoais reais.

## Agentes e escopo

- **Controladora em uma implantação real:** instituição que adota o SIGEE e decide as finalidades e os meios essenciais do tratamento. Sua identidade jurídica precisa ser registrada antes do uso institucional.
- **Protótipo acadêmico:** deve utilizar dados sintéticos e contas autorizadas da equipe. A identificação do responsável pelo ambiente público ainda precisa ser validada pela dupla e pelo orientador.
- **Operadores e suboperadores:** dependem dos contratos e da atuação concreta de Vercel, Supabase, Google/Gmail e demais fornecedores.
- **Titulares no escopo atual:** Administradores, Operadores e Professores com conta funcional.
- **Fora do escopo atual:** contas ou dados pessoais de alunos, crianças e adolescentes; dados de saúde, biometria, documentos, dados financeiros e decisões automatizadas sobre pessoas.

## Inventário das operações

| Categoria | Dados | Origem e obrigatoriedade | Finalidade | Acesso | Armazenamento ou compartilhamento | Hipótese legal proposta para validação | Retenção |
|---|---|---|---|---|---|---|---|
| Conta funcional | nome, sobrenome, e-mail, nome de usuário, perfil, estado, datas técnicas e hash da senha | cadastro controlado; obrigatório para criar a conta | identificar, autenticar, recuperar acesso e aplicar permissões | Administrador funcional no cadastro; Superuser técnico na manutenção | PostgreSQL/Supabase | execução da relação institucional ou legítimo interesse, conforme a controladora | enquanto ativa; critério posterior depende de validação |
| Sessão e CSRF | identificador de sessão e token CSRF | cookies técnicos automáticos | autenticação contínua e proteção contra requisições forjadas | aplicação Django | navegador e tabela de sessões | legítimo interesse em segurança ou execução do serviço | sessão: até 14 dias na configuração atual; CSRF: até um ano |
| Proteção contra abuso | nome de usuário, horário, caminho, navegador, cabeçalhos técnicos e quantidade de falhas | tentativa de login | limitar tentativas abusivas | aplicação e Superuser técnico | banco pelo django-axes; senha é mascarada, IP não é armazenado e o log duplicado de acessos válidos está desativado | legítimo interesse em segurança | janela de 15 minutos; tentativas deixam de contar e são limpas após o período de bloqueio |
| Recuperação de senha | e-mail, nome exibido e link temporário | solicitação do usuário | recuperar o acesso | sistema de e-mail e titular | Gmail SMTP e caixa do destinatário | execução do serviço e segurança | token válido por uma hora; retenção do e-mail depende do provedor e da caixa do destinatário |
| Reserva | Professor, tipo/modelo, local, período, quantidade, estado e equipamentos alocados | formulário do Professor | reservar unidades e impedir conflitos | próprio Professor; acesso técnico conforme permissões | PostgreSQL/Supabase | execução da atividade institucional | proposta pendente de validação |
| Movimentação | Operador, destinatário, equipamento, tipo, data, hora, retirada de origem e observação | fluxo futuro de retirada/devolução | preservar rastreabilidade física | Operador e Administrador conforme matriz planejada | PostgreSQL/Supabase | execução da atividade e legítimo interesse em rastreabilidade | proposta pendente de validação |
| Auditoria | conta, ação, resultado, data, hora, entidade e identificador | eventos automáticos | segurança, responsabilização e investigação | Administrador funcional e Superuser técnico | PostgreSQL/Supabase | legítimo interesse, exercício regular de direitos ou obrigação aplicável | proposta pendente de validação |
| Aceite | conta, versões dos documentos e data/hora | confirmação do usuário | comprovar apresentação e aceite dos documentos | Superuser técnico em consulta somente leitura | PostgreSQL/Supabase | exercício regular de direitos | proposta pendente de validação |
| Campos livres | descrições de equipamento, local e movimentação | entrada de usuário; em geral opcional | registrar contexto estritamente necessário | conforme a funcionalidade | PostgreSQL/Supabase | mesma hipótese da funcionalidade correspondente | mesma retenção do registro principal |
| Metadados de infraestrutura | endereço IP, navegador e dados técnicos que o provedor possa registrar | requisição HTTP | entrega, segurança e diagnóstico da aplicação | fornecedor e equipe autorizada | Vercel | deve ser confirmada com o contrato do fornecedor | deve ser confirmada com o fornecedor |
| Feriados | ano derivado da data da reserva e `User-Agent` técnico `SIGEE/1.0` | chamada do backend | informar feriados nacionais | BrasilAPI | BrasilAPI; nenhum identificador do Professor é enviado intencionalmente | não envolve dado pessoal enviado intencionalmente | não persistido pelo SIGEE |

## Fluxo dos dados

```text
Usuário
  -> navegador (cookies técnicos e formulários)
  -> Vercel / aplicação Django
     -> Supabase PostgreSQL (contas, reservas, auditoria e aceite)
     -> Gmail SMTP (somente recuperação de senha)
     -> BrasilAPI (somente ano da consulta de feriados)
  <- páginas HTML e respostas do SIGEE
```

Bootstrap e fontes são servidos como arquivos estáticos do próprio projeto. O navegador não precisa consultar Google Fonts ou jsDelivr para renderizar as páginas.

## Fornecedores e APIs

| Fornecedor | Serviço | Dados envolvidos | Decisão atual | Validação pendente |
|---|---|---|---|---|
| Vercel | hospedagem da aplicação | requisições e metadados técnicos; dados processados pelo backend | necessário ao deploy atual | contrato, região, retenção de logs e suboperadores |
| Supabase | PostgreSQL gerenciado | todos os dados persistidos | necessário ao banco publicado | região, backups, descarte, acesso e suboperadores |
| Google/Gmail | SMTP | destinatário, nome exibido e link de recuperação | necessário para recuperação publicada | retenção, região, conta institucional e contrato |
| BrasilAPI | feriados nacionais | ano e identificador técnico do cliente | chamada não bloqueante sem dado pessoal intencional | revisar periodicamente o contrato público |
| GitHub | código-fonte | código e documentação, sem banco ou segredos | necessário ao versionamento | manter proteção de segredos e revisão de histórico |

## Educação e crianças

O contexto do produto é educacional, mas os titulares atuais são profissionais com perfis Administrador, Operador e Professor. O sistema não cadastra alunos, responsáveis, notas, frequência, necessidades especiais ou outros dados de crianças e adolescentes.

Antes de ampliar o domínio pedagógico, a equipe deve repetir este inventário. Se a mudança introduzir dados de alunos, será necessária avaliação específica de melhor interesse, minimização, vínculo com responsáveis, permissões, transparência adequada à idade e retenção.

## Decisões que exigem validação

1. identidade do controlador do protótipo e da implantação;
2. hipótese legal por finalidade;
3. prazo de conta, reserva, movimentação, auditoria e aceite;
4. região, suboperadores, backups e transferência internacional dos fornecedores;
5. canal institucional e responsáveis pelo atendimento a titulares e incidentes.
