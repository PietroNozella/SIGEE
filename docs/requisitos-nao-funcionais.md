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

O baseline confirmado contempla `RS-01` a `RS-05` e `RS-08` a `RS-11`. `RS-06`, `RS-07` e `RS-12` permanecem candidatos sujeitos à validação acadêmica.

| ID | Situação | Requisito | Critério de aceite |
|---|---|---|---|
| RS-01 | Confirmado | Autenticação e autorização | Áreas restritas exigem autenticação e cada perfil executa somente ações autorizadas pelo servidor. |
| RS-02 | Confirmado | Dados e segredos | O sistema limita os dados pessoais a nome, e-mail e perfil; testes usam dados sintéticos; credenciais e segredos ficam fora do repositório. |
| RS-03 | Confirmado | Integridade e rastreabilidade | Validações no Django e no banco protegem os dados; históricos são preservados e equipamentos relacionados são inativados. |
| RS-04 | Confirmado | Comunicação segura | O ambiente publicado utiliza HTTPS e não expõe segredos em templates, JavaScript ou versionamento. |
| RS-05 | Confirmado | Gerenciamento seguro de sessões | Sessões expiram e são invalidadas no logout. |
| RS-06 | Candidato | Proteção contra tentativas abusivas de autenticação | Tentativas repetidas são limitadas por bloqueio temporário, atraso progressivo ou mecanismo equivalente. |
| RS-07 | Candidato | Recuperação segura de senha | A recuperação utiliza token seguro, com expiração e invalidação após o uso. |
| RS-08 | Confirmado | Validação segura das entradas | Dados são validados no servidor antes do processamento ou da persistência. |
| RS-09 | Confirmado | Registro de eventos de segurança | Eventos relevantes de autenticação são registrados para verificação posterior. |
| RS-10 | Confirmado | Proteção e minimização de dados pessoais | A coleta e o armazenamento são limitados às informações necessárias às finalidades do SIGEE. |
| RS-11 | Confirmado | Auditoria de ações dos usuários | Ações relevantes registram usuário, ação, data/hora e entidade afetada. |
| RS-12 | Candidato | Transparência e informações de privacidade | Termo de Uso e Política de Privacidade informam os dados tratados e suas finalidades. |

## Limites da entrega

Autenticação multifator, notificações de segurança, auditoria avançada e automação de direitos do titular permanecem fora do escopo final do PFC.
