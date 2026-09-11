# Projeto lógico da consulta de feriados — BrasilAPI

> **Status: RF-09 projetado e ainda não implementado.**

Este documento define somente o comportamento esperado da integração. Não existem cliente HTTP, chamada externa, tela de reserva ou testes da BrasilAPI implementados neste incremento.

## Objetivo

Durante a reserva, informar ao Professor quando o período escolhido coincidir com um feriado nacional. O aviso é informativo: a ocorrência do feriado e a indisponibilidade da API não bloqueiam a reserva.

## Fluxo previsto

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

## Contrato externo previsto

| Item | Definição de projeto |
|---|---|
| Método e endpoint | `GET https://brasilapi.com.br/api/feriados/v1/{ano}` |
| Entrada enviada | Apenas o ano com quatro dígitos, derivado das datas inicial e final da reserva. Para um período entre anos, será feita uma consulta para cada ano envolvido. |
| Resposta esperada | HTTP `200` com uma lista JSON de feriados. |
| Campos utilizados | `date`, no formato `AAAA-MM-DD`; `name`, para o texto do aviso; e `type`, para confirmar o caráter nacional. O campo `weekday` não é necessário para o requisito. |
| Timeout proposto | 3 segundos por requisição anual. Esse valor é uma decisão inicial de projeto e poderá ser calibrado quando o fluxo de reserva existir. |
| Autenticação | A API pública não exige chave no endpoint previsto. |

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

1. Receber as datas inicial e final já validadas pelo futuro formulário de reserva.
2. Identificar todos os anos abrangidos pelo período, sem repetir anos.
3. Consultar o endpoint uma vez para cada ano.
4. Validar cada resposta antes de utilizar seus dados.
5. Converter `date` para data e selecionar os feriados compreendidos entre o início e o fim, inclusive.
6. Exibir os nomes e as datas encontradas como aviso informativo.
7. Manter a reserva disponível, com ou sem feriados e mesmo quando a consulta externa falhar.

## Resposta inválida e contingência

A consulta será considerada inválida quando ocorrer timeout, erro de rede ou TLS, status diferente de `200`, JSON malformado, resposta que não seja uma lista ou item sem `date`, `name` e `type` válidos.

Nessas situações, o comportamento previsto é:

- descartar a resposta inválida do ano afetado;
- registrar uma mensagem técnica em nível de aviso, sem senha, cookie de sessão ou dados pessoais;
- informar na interface que não foi possível consultar os feriados naquele momento;
- permitir que o Professor continue a reserva normalmente.

Esse registro técnico de falha não representa a implementação da auditoria funcional do SIGEE.

## Saída interna prevista

A futura camada de reserva receberá:

- lista de feriados encontrados, contendo somente data e nome necessários para o aviso;
- indicação de consulta completa ou indisponível;
- mensagem informativa apropriada para a interface.

Nenhuma resposta da BrasilAPI será usada para decidir disponibilidade do equipamento, detectar conflito de reservas ou impedir a persistência.

## Cenários de teste futuros

- período sem feriado;
- período contendo um ou mais feriados;
- período abrangendo dois anos;
- timeout e erro de rede;
- status HTTP inesperado;
- JSON ou item inválido;
- falha da API sem bloqueio da reserva.

Fonte técnica consultada: [documentação da BrasilAPI](https://brasilapi.com.br/docs) e endpoint público de feriados nacionais para o ano de 2026, verificado em 10 de setembro de 2026.
