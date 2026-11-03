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
| Conta funcional | desativação reversível pela interface autorizada; dados e vínculos permanecem até procedimento técnico de anonimização ou descarte cabível | enquanto houver vínculo e durante período posterior aprovado | desativar pela interface ou anonimizar por comando, conforme a finalidade e as restrições da conta | validar prazo; sem descarte automático |
| Sessão Django | cookie por até 14 dias no padrão configurável; sessões expiradas dependem de limpeza | limpar sessões expiradas periodicamente | exclusão | comandos disponíveis; sem agendamento automático |
| Tentativas de login | janela padrão configurável de 15 minutos; tentativas vencidas deixam de bloquear o acesso; limpeza acionada por eventos de autenticação; logs duplicados de acessos válidos desativados | remover registros vencidos nos eventos de autenticação; definir rotina adicional se for necessário garantir periodicidade | exclusão pelo django-axes | sem agendador próprio; o vencimento não garante remoção física naquele instante |
| Recuperação de senha | token válido por uma hora no padrão configurável e não persistido separadamente | manter a mensagem somente pelo prazo operacional aprovado no backend e no provedor adotados | expiração do token; descarte da mensagem conforme o ambiente e o provedor | validar fornecedor e retenção das mensagens |
| Reservas e planejamento pedagógico | conservação indefinida, incluindo turma, disciplina, atividade e observação da reserva; expiração ou cancelamento não excluem o registro | período necessário à operação e à rastreabilidade aprovada | preservar vínculos necessários; anonimizar a conta quando cabível e revisar campos livres; eventual exclusão exige procedimento específico | validar prazo; sem rotina de descarte do histórico |
| Movimentações | conservação indefinida | período de rastreabilidade patrimonial aprovado | anonimizar referência pessoal, preservando o histórico necessário | validar prazo |
| Manutenções | conservação indefinida de responsáveis, datas, problema, solução, resultado e origem; concluir a intervenção não exclui o registro | acompanhar a finalidade e a retenção do histórico patrimonial e dos responsáveis | preservar vínculos necessários; anonimizar a conta quando cabível e revisar descrições; eventual descarte exige procedimento específico | validar prazo; sem rotina de descarte do histórico |
| Utilizações pedagógicas | conservação indefinida de Professor, retirada, turma, disciplina, atividade e observação; devolução integral encerra a edição, sem excluir os dados | período necessário aos indicadores e à rastreabilidade aprovados | preservar o vínculo à retirada; anonimizar a conta quando cabível e revisar observações; eventual descarte exige procedimento específico | validar prazo; sem rotina de descarte do histórico |
| Auditoria | conservação indefinida | prazo baseado em risco, incidentes e exercício de direitos | exclusão por data de corte aprovada | validar prazo |
| Aceites | conservação indefinida e protegida pela interface | período necessário para comprovar a versão apresentada | excluir somente de conta inativa e após data de corte aprovada | validar prazo |
| Campos livres | permanecem no registro principal; a anonimização da conta não remove nomes ou outros identificadores eventualmente digitados nesses campos | seguir a retenção da funcionalidade e revisar dados pessoais excessivos no atendimento assistido | corrigir ou remover conteúdo quando cabível, preservando o histórico necessário | revisão humana; sem identificação ou anonimização automática dos textos |
| Arquivo CSV importado | processado em memória; conteúdo não é persistido como arquivo | duração da requisição | descarte automático | atendido |
| Dados de demonstração | podem existir no ambiente acadêmico | somente durante o projeto e demonstrações autorizadas | exclusão ou recriação do banco sintético | definir responsável |
| Backups | controlados pelo provedor | acompanhar o ciclo do dado principal e limitações técnicas | expiração segura no provedor | validar Supabase/Vercel |

## Procedimentos executáveis

- `python manage.py clearsessions`: remove sessões Django expiradas diretamente; esse comando nativo não oferece simulação.
- `python manage.py limpar_dados_expirados`: exige ao menos um critério. Aceita `--auditoria-antes-de AAAA-MM-DD`, `--aceites-antes-de AAAA-MM-DD` e `--sessoes-expiradas`, que podem ser combinados. Sem `--confirmar`, apenas simula; com a opção, exclui os registros selecionados e registra a operação na auditoria. As datas são exclusivas: o comando seleciona registros anteriores ao corte. Aceites são selecionados somente de contas inativas.
- `python manage.py anonimizar_usuario nome_da_conta`: apresenta uma simulação; substitua `nome_da_conta` pelo nome de usuário exato. A anonimização exige `--confirmar` e recusa contas técnicas e o Administrador principal. Antes de anonimizar o principal, designe um substituto conforme [Autenticação](../tecnica/autenticacao.md#administrador-principal-de-reserva).

Para conferir a limpeza de sessões expiradas antes de executá-la:

```powershell
python manage.py limpar_dados_expirados --sessoes-expiradas
```

Depois da aprovação dos totais, execute o mesmo critério com confirmação:

```powershell
python manage.py limpar_dados_expirados --sessoes-expiradas --confirmar
```

Para auditoria e aceites, informe as datas de corte aprovadas no formato `AAAA-MM-DD`; este plano não define um prazo institucional. Os comandos de limpeza não removem reservas, movimentações, manutenções ou utilizações pedagógicas. A desativação reversível de contas também não equivale a descarte e segue as restrições descritas em [Autenticação](../tecnica/autenticacao.md#desativação-reversível-de-usuários).

## Regras de segurança do descarte

1. Confirmar identidade do titular e autoridade de quem aprovou a operação.
2. Exportar os dados antes da ação quando houver solicitação de acesso associada.
3. Verificar impedimentos de retenção e registros relacionados.
4. Usar os comandos assistidos sem `--confirmar` e revisar o resumo; para sessões, preferir a simulação por `limpar_dados_expirados` antes da exclusão.
5. Fazer backup controlado somente quando a política exigir e registrar sua expiração.
6. Executar com confirmação e conferir a auditoria e os registros afetados. Em caso de anonimização, validar também que a conta não autentica.
7. Comunicar o resultado e registrar eventuais dados preservados e seu fundamento.

## Limitações

A exclusão imediata de uma conta pode ser bloqueada por auditorias, aceites, reservas, movimentações, responsabilidades de manutenção e utilizações pedagógicas protegidas por `PROTECT`. A anonimização substitui os identificadores diretos da conta, desativa o acesso e preserva os vínculos históricos; não anonimiza automaticamente descrições e observações. A instituição deve decidir por quanto tempo os registros históricos pseudonimizados permanecem necessários e aprovar o tratamento dos campos livres e dos backups.
