# Integração com a BrasilAPI

O cliente HTTP, a validação da resposta externa, a consulta anual usada pelo calendário, a consulta prévia integrada à disponibilidade e a apresentação dos avisos no diálogo de confirmação estão implementados e cobertos por testes automatizados.

## Objetivo

Antes de efetivar a reserva, informar ao Professor no diálogo de confirmação quando o período escolhido coincidir com um feriado nacional. O aviso é informativo: a ocorrência do feriado e a indisponibilidade da API não bloqueiam a reserva.

## Relação com as validações da reserva

A consulta de feriados não substitui as validações locais previstas para a reserva. Conforme a `RN-19`, o SIGEE aplica antecedência, período e calendário institucional de uso e atendimento, sem depender da BrasilAPI. A data atual permanece permitida quando o horário inicial ainda não passou. Sábados e domingos são fechados por padrão e podem ser liberados pelo Administrador no calendário da escola.

O formulário de exceções do Administrador reutiliza o seletor de datas e a consulta anual de feriados. As datas anteriores a hoje ficam bloqueadas; sábados, domingos e feriados futuros permanecem selecionáveis, pois cabe ao Administrador definir a exceção institucional. O endpoint `/calendario/feriados/?ano=AAAA` exige a permissão de configuração do calendário. A consulta envia à BrasilAPI apenas o ano e sua falha não impede salvar a configuração.

O feriado retornado pela BrasilAPI gera somente aviso informativo. A abertura ou o fechamento da data depende da configuração institucional; uma exceção por data prevalece sobre a semana habitual.

## Fluxo implementado

```text
Professor abre o calendário da reserva
        ↓
SIGEE consulta os feriados do ano exibido
        ↓
Calendário destaca feriados e desativa datas fora do prazo ou fechadas pela escola
        ↓
Professor informa o período da reserva
        ↓
SIGEE valida o período e consulta a disponibilidade e o feriado selecionado
        ↓
Exibe o aviso no diálogo de confirmação, quando necessário
        ↓
Professor decide se confirma a reserva
        ↓
SIGEE revalida os dados locais e efetiva a reserva
```

Se a API falhar, o diálogo informa que a consulta não foi concluída e permite continuar normalmente.

## Contrato externo implementado

| Item | Definição de projeto |
|---|---|
| Método e endpoint | `GET https://brasilapi.com.br/api/feriados/v1/{ano}` |
| Entrada enviada | Apenas o ano com quatro dígitos, derivado da data da reserva. O cliente interno também aceita períodos entre anos e, nesse caso, faz uma consulta para cada ano envolvido, embora a interface atual trabalhe com uma única data. |
| Resposta esperada | HTTP `200` com uma lista JSON de feriados. |
| Campos utilizados | `date`, no formato `AAAA-MM-DD`; `name`, para o texto do aviso; e `type`, para confirmar o caráter nacional. O campo `weekday` não é necessário para o requisito. |
| Timeout | 3 segundos por requisição anual. O valor pode ser calibrado com evidências de operação sem alterar a regra de contingência. |
| Autenticação | A API pública não exige chave no endpoint utilizado. |

Exemplo reduzido do formato observado:

```json
[
  {
    "date": "2026-09-07",
    "name": "Independência do Brasil",
    "type": "national",
    "weekday": "segunda-feira"
  }
]
```

## Processamento lógico

1. Ao abrir ou trocar o ano do calendário, receber o ano solicitado e consultar o endpoint com tempo limite explícito.
2. Devolver ao calendário somente a data e o nome dos feriados. A interface os destaca com legenda e permite selecionar datas que atendam às regras temporais e ao calendário da escola. Um feriado não modifica as regras de abertura, fechamento ou atendimento.
3. Durante a consulta prévia de disponibilidade, receber o tipo/modelo, o local, a data e os horários inicial e final validados. A quantidade é resolvida pelas unidades físicas do tipo e local escolhidos, independentemente da consulta de feriados.
4. Identificar todos os anos abrangidos pelo período, sem repetir anos, e consultar o endpoint para cada ano necessário.
5. Validar cada resposta, converter `date` e selecionar os feriados compreendidos entre o início e o fim, inclusive.
6. Devolver a disponibilidade e o resultado da consulta de feriados para o formulário.
7. Exibir os nomes e as datas encontradas no diálogo antes da confirmação final.
8. Ao confirmar, revalidar período, disponibilidade e permissões no servidor antes de persistir a reserva.

## Resposta inválida e contingência

A consulta é considerada inválida quando ocorre timeout, erro de rede ou TLS, status diferente de `200`, JSON malformado, resposta que não seja uma lista ou item sem `date`, `name` e `type` válidos.

Nessas situações, o comportamento implementado é:

- descartar a resposta inválida do ano afetado;
- registrar uma mensagem técnica em nível de aviso, sem senha, cookie de sessão ou dados pessoais;
- informar na interface que não foi possível consultar os feriados naquele momento;
- permitir que o Professor continue a reserva normalmente.

Esse registro técnico de falha não representa a implementação da auditoria funcional do SIGEE.

## Saída interna implementada

O endpoint de consulta prévia devolve:

- lista de feriados encontrados, contendo somente data e nome necessários para o aviso;
- indicação de consulta completa ou indisponível;
- quantidade de unidades disponíveis para o período.

Nenhuma resposta da BrasilAPI é usada para decidir disponibilidade do equipamento, detectar conflito de reservas ou impedir a persistência.

## Cenários de teste implementados

- período sem feriado;
- período contendo um ou mais feriados;
- feriado em dia útil com aviso, sem bloqueio da reserva;
- resposta prévia com feriado e estrutura do aviso no diálogo de confirmação;
- período abrangendo dois anos;
- timeout e erro de rede;
- status HTTP inesperado;
- JSON ou item inválido;
- falha da API sem bloqueio da reserva.

## Referências

O cliente está em `reservas/brasilapi.py`; as views de consulta estão em `reservas/views.py`. `reservas/tests.py` contém os cenários de resposta válida, falhas e contingência. A execução isolada segue o [README](../../README.md#testes). O contrato externo é descrito na [documentação da BrasilAPI](https://brasilapi.com.br/docs).
