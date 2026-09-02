# Diagrama Entidade-Relacionamento

O diagrama abaixo representa exclusivamente os modelos implementados no estado atual do SIGEE. O usuário corresponde ao modelo de autenticação configurado pelo Django.

```mermaid
erDiagram
    CATEGORIA ||--o{ EQUIPAMENTO : classifica
    LOCAL ||--o{ EQUIPAMENTO : localiza
    EQUIPAMENTO ||--o{ MOVIMENTACAO : possui
    USUARIO ||--o{ MOVIMENTACAO : opera
    USUARIO ||--o{ MOVIMENTACAO : recebe
    MOVIMENTACAO o|--o{ MOVIMENTACAO : referencia_retirada

    CATEGORIA {
        bigint id PK
        string nome UK
        string descricao
        boolean ativo
        datetime data_criacao
    }

    LOCAL {
        bigint id PK
        string nome UK
        string descricao
        boolean ativo
        datetime data_criacao
    }

    EQUIPAMENTO {
        bigint id PK
        string numero_patrimonio UK
        string nome
        text descricao
        bigint categoria_id FK
        bigint local_id FK
        string situacao
        boolean ativo
        datetime data_cadastro
        datetime data_atualizacao
    }

    USUARIO {
        bigint id PK
    }

    MOVIMENTACAO {
        bigint id PK
        bigint equipamento_id FK
        bigint operador_id FK
        bigint destinatario_id FK
        string tipo
        datetime data_hora
        bigint retirada_origem_id FK
        text observacao
    }
```

Reservas, manutenções, turmas, disciplinas, atividades pedagógicas e indicadores ainda não aparecem no DER porque não possuem modelos implementados.
