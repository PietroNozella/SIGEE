# Plano de resposta a incidentes com dados pessoais

Este plano orienta o protótipo acadêmico. A instituição controladora deve indicar nomes, contatos e substitutos antes de utilizar dados reais e deve validar as obrigações regulatórias aplicáveis.

## Papéis

| Papel | Responsabilidade | Definição atual |
|---|---|---|
| coordenador do incidente | decidir prioridade, contenção e encerramento | validar entre equipe e instituição |
| responsável técnico | investigar, conter, preservar evidências e corrigir | equipe técnica do SIGEE |
| responsável por privacidade | avaliar titulares, risco e comunicações | validar pela controladora |
| comunicação institucional | comunicar titulares, ANPD e fornecedores quando necessário | validar pela controladora |

## Fluxo

1. **Detectar e confirmar:** registrar horário, fonte do alerta, sistemas e comportamento observado.
2. **Conter e preservar evidências:** revogar credenciais, bloquear acessos ou isolar o componente sem destruir logs relevantes.
3. **Identificar o impacto:** determinar categorias de dados, quantidade aproximada de titulares, perfis afetados, fornecedores e período.
4. **Avaliar risco ou dano relevante:** considerar autenticação, possibilidade de fraude, dados de crianças, sensíveis, financeiros, escala e facilidade de identificação.
5. **Comunicar:** acionar controladora e fornecedores; quando aplicável, comunicar ANPD e titulares com informações claras e medidas de mitigação.
6. **Corrigir e acompanhar:** tratar a causa, monitorar efeitos, recuperar o serviço e confirmar a eficácia da correção.
7. **Encerrar e aprender:** registrar decisões, responsáveis, evidências, comunicações, prazos e melhorias.

## Registro mínimo

- identificador, datas de detecção, confirmação e encerramento;
- origem e descrição do incidente;
- dados e titulares afetados ou potencialmente afetados;
- medidas de contenção e recuperação;
- avaliação de risco e decisão sobre comunicação;
- comunicações realizadas;
- causa raiz e correções;
- responsáveis e fornecedores envolvidos.

Os registros de incidentes com dados pessoais devem observar o prazo regulatório vigente. A [Resolução CD/ANPD nº 15/2024](https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/documentos/rcis___anonimizado_final_ocultado_2_parte3.pdf) prevê conservação mínima de cinco anos, mesmo quando o evento não for comunicado à ANPD ou aos titulares.

## Contatos e fornecedores

- canal de privacidade: valor configurado em `SIGEE_CONTATO_PRIVACIDADE`;
- Vercel: suporte e painel do projeto;
- Supabase: suporte, logs e painel do banco;
- Google/Gmail: segurança da conta SMTP;
- GitHub: segurança do repositório e revogação de credenciais.

Os contatos específicos, responsáveis e caminhos de escalonamento não devem ficar vazios na versão usada em produção.

## Exercício acadêmico

Antes da entrega final, realizar uma simulação de comprometimento de credencial administrativa:

1. detectar login ou alteração suspeita;
2. invalidar a conta e as sessões;
3. identificar ações consultando a auditoria;
4. levantar dados acessíveis ao perfil;
5. decidir se existe risco relevante e justificar;
6. preparar uma comunicação fictícia, sem enviá-la;
7. registrar tempo, falhas observadas e correções propostas.
