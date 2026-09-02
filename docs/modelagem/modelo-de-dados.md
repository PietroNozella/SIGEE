# Modelo de Dados

Este documento descreve somente os modelos presentes no estado atual da aplicação.

## Categoria

- `nome`: texto de até 100 caracteres e valor único.
- `descricao`: texto opcional de até 255 caracteres.
- `ativo`: indicador de registro ativo.
- `data_criacao`: data e hora de criação.

## Local

- `nome`: texto de até 100 caracteres e valor único.
- `descricao`: texto opcional de até 255 caracteres.
- `ativo`: indicador de registro ativo.
- `data_criacao`: data e hora de criação.

## Equipamento

- `numero_patrimonio`: texto de até 50 caracteres e valor único.
- `nome`: texto de até 150 caracteres.
- `descricao`: texto opcional.
- `categoria`: referência protegida para Categoria.
- `local`: referência protegida para Local.
- `situacao`: Disponível, Em uso ou Manutenção; o valor inicial é Disponível.
- `ativo`: indicador de registro ativo.
- `data_cadastro`: data e hora de cadastro.
- `data_atualizacao`: data e hora da última atualização.

## Movimentação

- `equipamento`: referência protegida para Equipamento.
- `operador`: referência protegida para o usuário que registra a movimentação.
- `destinatario`: referência protegida para o usuário que recebe o equipamento.
- `tipo`: texto de até 20 caracteres.
- `data_hora`: data e hora do registro.
- `retirada_origem`: referência opcional e protegida para outra Movimentação.
- `observacao`: texto opcional.

## Relacionamentos implementados

- Uma Categoria pode estar relacionada a vários Equipamentos.
- Um Local pode estar relacionado a vários Equipamentos.
- Um Equipamento pode possuir várias Movimentações.
- Um usuário pode atuar como operador ou destinatário em várias Movimentações.
- Uma Movimentação pode referenciar outra Movimentação como retirada de origem.

## Elementos ainda não modelados

Reservas, manutenções, turmas, disciplinas, atividades pedagógicas e indicadores fazem parte do escopo aprovado, mas ainda não possuem modelos implementados no repositório.
