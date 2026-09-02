# Requisitos de Segurança

- Permissões serão aplicadas no servidor conforme os perfis Administrador, Operador e Professor.
- A autenticação e a autorização serão implementadas com Django Authentication, Groups e Permissions, seguindo controle de acesso baseado em papéis (RBAC).
- Sessões, cookies seguros, proteção CSRF e validação de entrada utilizarão os mecanismos consolidados do Django.
- Credenciais, `DJANGO_SECRET_KEY` e `DATABASE_URL` permanecerão em variáveis de ambiente, fora do código-fonte.
- O ambiente publicado deverá utilizar HTTPS, inclusive na conexão com o PostgreSQL.
- Serão tratados apenas os dados pessoais básicos necessários, como nome, e-mail e perfil de acesso.
- Testes e demonstrações utilizarão dados sintéticos.
- Ações relevantes deverão registrar usuário, ação, data/hora e entidade afetada.
- A auditoria básica de acessos e ações relevantes integra os requisitos transversais de segurança da entrega.

## Itens sujeitos à validação acadêmica

Os controles relacionados à proteção contra tentativas abusivas de login, recuperação segura de senha e publicação de Termo de Uso e Política de Privacidade permanecem candidatos sujeitos à validação acadêmica; não compõem o baseline obrigatório até essa confirmação.
