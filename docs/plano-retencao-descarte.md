# Plano de retenção e descarte

Este plano diferencia comportamento técnico existente, proposta e decisão institucional. Nenhum prazo marcado como pendente deve ser apresentado como aprovado antes da validação da dupla, do orientador e da instituição controladora.

## Princípios

- conservar somente enquanto houver finalidade e fundamento válidos;
- não excluir históricos necessários de forma silenciosa;
- preferir inativação e anonimização quando a referência histórica precisar permanecer;
- aplicar o descarte também a sessões, arquivos temporários, logs e backups;
- registrar quem autorizou e executou uma operação de descarte;
- executar primeiro em modo de simulação e verificar os totais antes da confirmação.

## Critérios por categoria

| Categoria | Comportamento atual | Critério proposto | Destino | Situação |
|---|---|---|---|---|
| Conta funcional | permanece até intervenção técnica | enquanto houver vínculo e durante período posterior aprovado | inativar e anonimizar quando cabível | validar prazo |
| Sessão Django | cookie por até 14 dias; sessões expiradas dependem de limpeza | limpar sessões expiradas periodicamente | exclusão | implementável sem prazo adicional |
| Tentativas de login | janela de bloqueio de 15 minutos; logs duplicados de acessos válidos estão desativados | deixar de considerar e limpar tentativas após a janela | exclusão | implementado pelo django-axes |
| Recuperação de senha | token válido por uma hora e não persistido separadamente | manter apenas nos provedores pelo prazo operacional | expiração automática; descarte do e-mail conforme provedor | validar fornecedor |
| Reservas | conservação indefinida | período necessário à operação e à rastreabilidade aprovada | anonimizar referência pessoal ou excluir quando permitido | validar prazo |
| Movimentações | conservação indefinida | período de rastreabilidade patrimonial aprovado | anonimizar referência pessoal, preservando o histórico necessário | validar prazo |
| Auditoria | conservação indefinida | prazo baseado em risco, incidentes e exercício de direitos | exclusão por data de corte aprovada | validar prazo |
| Aceites | conservação indefinida e protegida pela interface | período necessário para comprovar a versão apresentada | excluir somente de conta inativa e após data de corte aprovada | validar prazo |
| Arquivo CSV importado | processado em memória; conteúdo não é persistido como arquivo | duração da requisição | descarte automático | atendido |
| Dados de demonstração | podem existir no ambiente acadêmico | somente durante o projeto e demonstrações autorizadas | exclusão ou recriação do banco sintético | definir responsável |
| Backups | controlados pelo provedor | acompanhar o ciclo do dado principal e limitações técnicas | expiração segura no provedor | validar Supabase/Vercel |

## Procedimentos executáveis

- `python manage.py clearsessions`: remove sessões Django expiradas.
- `python manage.py limpar_dados_expirados`: simula a limpeza de auditoria, aceites de contas inativas e sessões expiradas; a exclusão exige `--confirmar` e datas de corte explícitas.
- `python manage.py anonimizar_usuario <username>`: apresenta uma simulação; a anonimização exige `--confirmar`.

## Regras de segurança do descarte

1. Confirmar identidade do titular e autoridade de quem aprovou a operação.
2. Exportar os dados antes da ação quando houver solicitação de acesso associada.
3. Verificar impedimentos de retenção e registros relacionados.
4. Executar o comando sem `--confirmar` e revisar o resumo.
5. Fazer backup controlado somente quando a política exigir e registrar sua expiração.
6. Executar com confirmação, conferir auditoria e validar que a conta não autentica.
7. Comunicar o resultado e registrar eventuais dados preservados e seu fundamento.

## Limitações

A exclusão imediata de uma conta pode ser bloqueada por auditorias, aceites, reservas e movimentações protegidas por `PROTECT`. A anonimização remove identificadores diretos e desativa o acesso, mas a instituição deve decidir por quanto tempo os registros históricos pseudonimizados permanecem necessários.
