# Requisitos não funcionais e de segurança

Os requisitos não funcionais estabelecem condições para o funcionamento e a verificação do SIGEE. Eles abrangem controle de acesso, integridade dos dados, rastreabilidade, uso da interface, desempenho e testes. Os requisitos de segurança e privacidade complementam essas condições.

## Requisitos não funcionais

### RNF01 - Autenticação e autorização

O servidor deve impedir o acesso direto a operações não autorizadas para o perfil do usuário.

### RNF02 - Integridade e validação

O número de patrimônio deve ser único, e campos obrigatórios, formatos, limites e regras de domínio devem ser validados no servidor antes da gravação.

### RNF03 - Rastreabilidade

Os históricos de movimentação, manutenção e utilização pedagógica devem ser preservados. Equipamentos com registros relacionados devem ser inativados, em vez de excluídos.

### RNF04 - Usabilidade e acessibilidade básica

Os fluxos críticos definidos abaixo devem permitir o uso em telas de computador e celular, com navegação por teclado, foco visível e texto legível. A verificação usa Chrome e Edge nas versões estáveis instaladas no momento da validação, com larguras de 1366 e 390 pixels. O contraste do texto comum deve ser de pelo menos 4,5:1 em relação ao fundo, conforme o [critério de contraste da WCAG](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

### RNF05 - Desempenho e compatibilidade

As consultas de equipamentos, reservas, histórico, painel e indicadores pedagógicos devem responder em até três segundos no ambiente local de validação, com uma sessão em uso e base sintética de pelo menos 100 equipamentos, 20 reservas e 40 movimentações. Após a primeira abertura de cada página, devem ser feitas três medições da requisição HTML principal pela aba Network do navegador; todas devem atender ao limite. A compatibilidade dos fluxos críticos usa os mesmos navegadores e tamanhos de tela definidos no RNF04.

### RNF06 - Testes automatizados e cobertura

As principais regras de negócio, modelos e serviços devem possuir testes automatizados. Pelo menos quatro dos oito fluxos críticos definidos abaixo devem ter testes executados com sucesso, incluindo um caso válido e uma rejeição relevante por fluxo. Isso corresponde ao mínimo de 50% dos fluxos; não representa uma porcentagem de linhas de código.

## Verificação dos RNF04 a RNF06

Os oito fluxos críticos são:

1. autenticação, recuperação de senha e autorização;
2. cadastro, importação e remoção ou inativação de equipamentos;
3. cadastro de contas e desativação ou reativação conforme a autoridade do Administrador;
4. reserva, disponibilidade, prevenção de conflito, cancelamento e expiração;
5. entrega e devolução total ou parcial;
6. abertura, acompanhamento e conclusão de manutenção;
7. planejamento e correção do contexto pedagógico;
8. consulta de histórico, painel e indicadores pedagógicos.

Para RNF04, percorrer os fluxos com o perfil autorizado nos dois navegadores e nas duas larguras, usando também `Tab`, `Shift+Tab` e `Enter`; conferir foco, leitura, acionamento dos controles e contraste do texto. A largura de celular pode ser conferida pela emulação de dispositivo do navegador. As listas e tabelas precisam permitir acesso a todo o conteúdo, inclusive por rolagem quando aplicável.

Para RNF05, anotar o banco, a máquina utilizada, as versões dos navegadores, as quantidades de registros e os três tempos de cada consulta. As medições devem usar a mesma base sintética. O limite se refere à requisição HTML principal, sem somar o carregamento de imagens, fontes e demais arquivos estáticos.

Para RNF06, contar uma única vez cada fluxo com os dois cenários automatizados aprovados: `fluxos cobertos / 8 × 100`. Os testes existentes estão nos apps `inventario`, `usuarios`, `reservas`, `movimentacoes`, `manutencoes`, `pedagogico`, `auditoria` e `legal`. Os comandos locais e a execução de concorrência com PostgreSQL estão no [README](../../README.md#testes).

Esses critérios definem como verificar os requisitos. A execução da suíte automatizada não substitui a conferência manual de interface nem a medição dos tempos.

## Requisitos de segurança e privacidade

Os requisitos RS-01 a RS-12 integram o escopo confirmado do SIGEE. A confirmação do requisito não representa, por si só, comprovação de atendimento; os documentos técnicos descrevem os controles implementados e suas limitações.

### RS-01 - Autenticação e autorização

**Critério de aceite:** Áreas restritas exigem autenticação e cada perfil executa somente ações autorizadas pelo servidor.

### RS-02 - Dados e segredos

**Critério de aceite:** O sistema limita os dados pessoais às informações necessárias de conta, autenticação, perfil, sessão, proteção contra abuso, reserva e planejamento pedagógico, movimentação, manutenção, utilização pedagógica, auditoria e aceite; testes usam dados sintéticos; senhas em texto puro, credenciais de infraestrutura e segredos não são persistidos no repositório.

### RS-03 - Integridade e rastreabilidade

**Critério de aceite:** Validações no Django e no banco protegem os dados; históricos são preservados e equipamentos relacionados são inativados.

### RS-04 - Comunicação segura

**Critério de aceite:** O ambiente publicado utiliza HTTPS e não expõe segredos em templates, JavaScript ou versionamento.

### RS-05 - Gerenciamento seguro de sessões

**Critério de aceite:** Sessões expiram e são invalidadas no logout.

### RS-06 - Proteção contra tentativas abusivas de autenticação

**Critério de aceite:** Cinco falhas para o mesmo nome de usuário geram bloqueio por quinze minutos; o controle não persiste o IP e não expõe a existência da conta.

### RS-07 - Recuperação segura de senha

**Critério de aceite:** A recuperação utiliza resposta neutra e token seguro, com expiração em uma hora e invalidação após o uso.

### RS-08 - Validação segura das entradas

**Critério de aceite:** Dados são validados no servidor antes do processamento ou da persistência.

### RS-09 - Registro de eventos de segurança

**Critério de aceite:** Eventos relevantes de autenticação são registrados para verificação posterior.

### RS-10 - Proteção e minimização de dados pessoais

**Critério de aceite:** A coleta e o armazenamento são limitados às informações necessárias às finalidades do SIGEE.

### RS-11 - Auditoria de ações dos usuários

**Critério de aceite:** Ações relevantes registram usuário, ação, data/hora e entidade afetada.

### RS-12 - Transparência e informações de privacidade

**Critério de aceite:** Termo de Uso versão 2.0 e Política de Privacidade versão 2.1 são públicos e informam dados, finalidades, fornecedores, retenção, segurança e direitos; após o login, o usuário precisa aceitar os Termos e confirmar a leitura da Política; o sistema registra usuário, versões e data/hora e exige novo aceite quando uma versão muda.

A implementação e o inventário de dados relacionados ao RS-12 estão descritos em [Termos de Uso, privacidade e aceite](../privacidade/privacidade-e-termos.md).

## Limites e decisões institucionais

O produto possui comandos assistidos para acesso, anonimização e descarte, mas o atendimento depende de validação humana. Autenticação multifator, notificações automáticas de incidentes e análise automática de comportamento permanecem fora do escopo atual.

As hipóteses legais, os prazos de retenção, a identidade da controladora e as condições contratuais dos fornecedores são propostas, não decisões jurídicas aprovadas. Elas precisam ser validadas pela equipe e pela instituição antes do uso com dados pessoais reais.
