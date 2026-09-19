# Projeto lógico da consulta de feriados — BrasilAPI

> **Status: integração, interface do Professor e testes automatizados implementados.**

O cliente HTTP, a validação da resposta externa, o serviço de criação da reserva e a apresentação dos avisos na interface do Professor estão implementados e cobertos por testes automatizados.

## Objetivo

Durante a reserva, informar ao Professor quando o período escolhido coincidir com um feriado nacional. O aviso é informativo: a ocorrência do feriado e a indisponibilidade da API não bloqueiam a reserva.

## Relação com as validações da reserva

A consulta de feriados não substitui as validações locais previstas para a reserva. Conforme a `RN-19`, períodos que incluam sábado ou domingo e reservas cuja data e hora inicial já tenham passado são bloqueados pelo próprio SIGEE, sem depender da BrasilAPI. A data atual permanece permitida quando o horário inicial ainda não passou.

Assim, feriado e fim de semana possuem efeitos diferentes: o feriado retornado pela BrasilAPI gera somente aviso informativo, enquanto sábado ou domingo impedem a conclusão da reserva.

## Fluxo implementado

```text
Professor informa período da reserva
        ↓
SIGEE identifica os anos envolvidos
        ↓
Consulta feriados nacionais na BrasilAPI
        ↓
Compara datas com o período
        ↓
Exibe aviso informativo
        ↓
Se a API falhar, registra a falha e permite continuar a reserva
```

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

1. Receber o tipo/modelo, o local, a quantidade, a data e os horários inicial e final validados pelo formulário de reserva. A quantidade é resolvida pela disponibilidade das unidades físicas do tipo e local escolhidos, independentemente da consulta de feriados.
2. Identificar todos os anos abrangidos pelo período, sem repetir anos.
3. Consultar o endpoint uma vez para cada ano, uma única vez por solicitação de reserva em lote.
4. Validar cada resposta antes de utilizar seus dados.
5. Converter `date` para data e selecionar os feriados compreendidos entre o início e o fim, inclusive.
6. Exibir os nomes e as datas encontradas como aviso informativo.
7. Manter a reserva disponível, com ou sem feriados e mesmo quando a consulta externa falhar.

## Resposta inválida e contingência

A consulta é considerada inválida quando ocorre timeout, erro de rede ou TLS, status diferente de `200`, JSON malformado, resposta que não seja uma lista ou item sem `date`, `name` e `type` válidos.

Nessas situações, o comportamento implementado é:

- descartar a resposta inválida do ano afetado;
- registrar uma mensagem técnica em nível de aviso, sem senha, cookie de sessão ou dados pessoais;
- informar na interface que não foi possível consultar os feriados naquele momento;
- permitir que o Professor continue a reserva normalmente.

Esse registro técnico de falha não representa a implementação da auditoria funcional do SIGEE.

## Saída interna implementada

A camada de reserva recebe:

- lista de feriados encontrados, contendo somente data e nome necessários para o aviso;
- indicação de consulta completa ou indisponível;
- mensagem informativa apropriada para a interface.

Nenhuma resposta da BrasilAPI será usada para decidir disponibilidade do equipamento, detectar conflito de reservas ou impedir a persistência.

## Cenários de teste implementados

- período sem feriado;
- período contendo um ou mais feriados;
- feriado em dia útil com aviso, sem bloqueio da reserva;
- período abrangendo dois anos;
- timeout e erro de rede;
- status HTTP inesperado;
- JSON ou item inválido;
- falha da API sem bloqueio da reserva.

Fonte técnica consultada: [documentação da BrasilAPI](https://brasilapi.com.br/docs) e endpoint público de feriados nacionais para o ano de 2026, verificado em 10 de setembro de 2026.
