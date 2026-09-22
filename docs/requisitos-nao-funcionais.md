# Requisitos não funcionais e de segurança

Este documento reúne os requisitos não funcionais prioritários e os requisitos de segurança e privacidade do SIGEE. Todos representam planejamento até que existam implementação, teste e evidência verificável no repositório.

## Requisitos não funcionais

| ID | Requisito | Critério verificável |
|---|---|---|
| RNF-01 | Autenticação e autorização | O servidor nega acesso direto não autorizado de acordo com o perfil do usuário. |
| RNF-02 | Integridade e validação | Patrimônio é único; campos obrigatórios, formatos, limites e regras de domínio são validados no servidor; entradas inválidas são rejeitadas com mensagem adequada. |
| RNF-03 | Rastreabilidade | Históricos de movimentação, manutenção e utilização pedagógica são preservados; itens com registros relacionados são inativados, não excluídos. |
| RNF-04 | Usabilidade e acessibilidade básica | Fluxos críticos funcionam em desktop e dispositivos móveis, com navegação por teclado e contraste adequado. |
| RNF-05 | Desempenho e compatibilidade | Consultas principais respondem em até três segundos na base de testes e os fluxos críticos são validados em navegadores atuais. |
| RNF-06 | Testes automatizados e cobertura | Regras de negócio, modelos e serviços principais possuem testes automatizados, e a suíte apresenta cobertura mínima de 50% dos fluxos críticos. |

## Requisitos de segurança e privacidade

O baseline confirmado contempla `RS-01` a `RS-12`.

| ID | Situação | Requisito | Critério de aceite |
|---|---|---|---|
| RS-01 | Confirmado | Autenticação e autorização | Áreas restritas exigem autenticação e cada perfil executa somente ações autorizadas pelo servidor. |
| RS-02 | Confirmado | Dados e segredos | O sistema limita os dados pessoais às informações necessárias de conta, autenticação, perfil, sessão, proteção contra abuso, reserva, movimentação, auditoria e aceite; testes usam dados sintéticos; senhas em texto puro, credenciais de infraestrutura e segredos não são persistidos no repositório. |
| RS-03 | Confirmado | Integridade e rastreabilidade | Validações no Django e no banco protegem os dados; históricos são preservados e equipamentos relacionados são inativados. |
| RS-04 | Confirmado | Comunicação segura | O ambiente publicado utiliza HTTPS e não expõe segredos em templates, JavaScript ou versionamento. |
| RS-05 | Confirmado | Gerenciamento seguro de sessões | Sessões expiram e são invalidadas no logout. |
| RS-06 | Confirmado | Proteção contra tentativas abusivas de autenticação | Cinco falhas para o mesmo nome de usuário geram bloqueio por quinze minutos; o controle não persiste o IP e não expõe a existência da conta. |
| RS-07 | Confirmado | Recuperação segura de senha | A recuperação utiliza resposta neutra e token seguro, com expiração em uma hora e invalidação após o uso. |
| RS-08 | Confirmado | Validação segura das entradas | Dados são validados no servidor antes do processamento ou da persistência. |
| RS-09 | Confirmado | Registro de eventos de segurança | Eventos relevantes de autenticação são registrados para verificação posterior. |
| RS-10 | Confirmado | Proteção e minimização de dados pessoais | A coleta e o armazenamento são limitados às informações necessárias às finalidades do SIGEE. |
| RS-11 | Confirmado | Auditoria de ações dos usuários | Ações relevantes registram usuário, ação, data/hora e entidade afetada. |
| RS-12 | Confirmado | Transparência e informações de privacidade | Termo de Uso e Política de Privacidade versão 2.0 são públicos e informam dados, finalidades, fornecedores, retenção, segurança e direitos; após o login, o usuário precisa aceitar os Termos e confirmar a leitura da Política; o sistema registra usuário, versões e data/hora e exige novo aceite quando uma versão muda. |

A implementação, o inventário de dados e as evidências relacionadas ao `RS-12` estão registrados em [Termos de Uso, privacidade e aceite](privacidade-e-termos.md).

## Limites e decisões pendentes

O produto possui comandos assistidos para acesso, anonimização e descarte, mas o atendimento continua dependendo de validação humana. Autenticação multifator, notificações automáticas de incidentes e análise automática de comportamento permanecem fora do escopo atual.

As hipóteses legais, os prazos de retenção, a identidade da controladora e as condições contratuais dos fornecedores são propostas, não decisões jurídicas aprovadas. Elas precisam ser validadas pela dupla, pelo orientador e pela instituição antes do uso com dados pessoais reais.
