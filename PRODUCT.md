# SIGEE

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Administrador: mantém cadastros e acompanha o acervo. Professor: reserva equipamentos e informa o contexto pedagógico. Operador: atende entregas e devoluções, identifica problemas, abre e consulta manutenção e acompanha faltas de entrega.

## Product Purpose

Organizar o inventário e o empréstimo de equipamentos escolares, preservando a identificação de cada patrimônio e a rastreabilidade das operações.

## Operating Context

O atendimento do Operador se organiza em Reservas, Em uso, Manutenções e Histórico. O início deve ajudar a identificar o que atender agora. As decisões funcionais desta melhoria estão em `docs/tecnica/melhorias-operador.md`; o estado implementado deve ser conferido no código e nos testes.

## Capabilities and Constraints

Django Templates, HTML, CSS, Bootstrap local e JavaScript pontual. Sem mudança de stack, publicação ou notificações externas nesta melhoria. O Professor consulta somente seus registros. O Operador visualiza apenas a turma do contexto pedagógico. Entregas parciais por manutenção preservam a reserva e o saldo. Dados de demonstração não representam resultados de uso institucional.

## Brand Commitments

Preservar o design system SIGEE, seus componentes, ícones, navegação e linguagem. A implementação visual vigente em `static/inventario/css/sigee.css` é a referência dos tokens e componentes. Melhorar hierarquia, legibilidade, estados e responsividade sem substituir a identidade.

## Product Principles

- Apresentar primeiro informações que orientam uma ação operacional.
- Separar disponibilidade atual, alocação futura, saldo de entrega e devolução física.
- Exibir somente informações necessárias ao perfil.
- Preservar histórico, autoria e coerência das situações.
- Usar rótulos claros, foco visível, estados vazios úteis e acesso por teclado.
