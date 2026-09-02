# Regras de Negócio

Este documento reúne as regras já registradas no escopo atual do SIGEE.

## Inventário e histórico

- Cada equipamento deverá possuir patrimônio único, categoria, local e situação.
- Equipamentos com registros relacionados deverão ser inativados, em vez de excluídos definitivamente, para preservar os históricos de movimentação, manutenção e utilização pedagógica.
- Movimentações deverão preservar data, hora, responsável, destinatário e tipo.

## Reservas e movimentações

- Reservas deverão bloquear conflitos de período e a reserva de equipamentos indisponíveis.
- Retiradas e devoluções deverão ser registradas, com ou sem reserva prévia quando permitido.
- A indisponibilidade da BrasilAPI não deverá impedir a conclusão de uma reserva.

## Manutenção

- O equipamento deverá permanecer indisponível durante a manutenção.

## Perfis e permissões

- O Administrador gerencia o sistema e o inventário e consulta o painel com indicadores.
- O Operador registra retiradas, devoluções, movimentações e operações autorizadas de manutenção.
- O Professor consulta a disponibilidade, realiza reservas e associa a utilização dos equipamentos a turmas, disciplinas e atividades pedagógicas.
- Ações sem permissão deverão ser bloqueadas no servidor.

## Integração com a BrasilAPI

Durante a criação de uma reserva, o backend consultará a BrasilAPI por HTTPS para identificar feriados nacionais no período selecionado. Essa integração terá caráter informativo e não bloqueará a reserva caso o serviço esteja indisponível ou exceda o tempo limite configurado.
