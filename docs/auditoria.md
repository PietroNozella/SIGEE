# Auditoria de acessos e ações

Este documento descreve a auditoria básica do SIGEE, implementada para atender ao `RS-09` e ao `RS-11`. O objetivo é permitir a verificação posterior de eventos relevantes de autenticação e das funcionalidades atuais sem armazenar senhas, credenciais, conteúdo integral de arquivos ou valores informados nos filtros.

## Escopo implementado

A auditoria cobre atualmente:

- login bem-sucedido e tentativa de login inválida;
- logout;
- respostas de acesso negado para usuários autenticados;
- consulta filtrada do inventário;
- download do modelo de importação CSV;
- cadastro individual de equipamento;
- importação de equipamentos por CSV;
- exclusão definitiva de equipamento sem histórico;
- inativação de equipamento com histórico preservado;
- cadastro controlado de contas funcionais;
- criação e cancelamento de reservas próprias pelo Professor.

As funcionalidades futuras devem registrar seus próprios eventos quando forem implementadas. A auditoria de manutenção e utilização pedagógica continua pendente enquanto esses fluxos não existirem no código.

## Registro persistente

Cada evento é representado por `RegistroAuditoria` e armazenado no banco de dados pelos recursos nativos do Django ORM.

| Campo | Finalidade |
|---|---|
| `usuario` | Identifica a conta autenticada associada ao evento, quando aplicável. |
| `acao` | Armazena um código técnico padronizado, sem texto livre ou dados submetidos pelo usuário. |
| `resultado` | Diferencia sucesso, falha e acesso negado. |
| `data_hora` | Registra automaticamente o momento do evento. |
| `entidade` | Identifica o tipo de entidade afetada, quando aplicável. |
| `entidade_id` | Mantém a referência textual ao registro afetado, sem copiar seu conteúdo. |

A relação com o usuário utiliza `PROTECT`. Assim, uma conta associada a registros de auditoria não pode ser excluída diretamente enquanto essas referências existirem. A ordenação padrão apresenta primeiro os eventos mais recentes.

## Eventos atuais

| Código | Situação registrada | Resultado esperado |
|---|---|---|
| `LOGIN_REALIZADO` | Credenciais válidas iniciam uma sessão. | Sucesso |
| `LOGIN_FALHOU` | A autenticação é recusada. | Falha |
| `LOGOUT_REALIZADO` | O usuário encerra a sessão. | Sucesso |
| `ACESSO_NEGADO` | Um usuário autenticado recebe resposta `403`. | Acesso negado |
| `INVENTARIO_CONSULTADO` | A listagem é consultada com ao menos um filtro. | Sucesso |
| `MODELO_CSV_BAIXADO` | O modelo de importação é baixado. | Sucesso |
| `EQUIPAMENTO_CADASTRADO` | O cadastro individual é aceito ou rejeitado. | Sucesso ou falha |
| `EQUIPAMENTOS_IMPORTADOS` | Um lote CSV é aceito ou rejeitado. | Sucesso ou falha |
| `EQUIPAMENTO_EXCLUIDO` | Um equipamento sem histórico é excluído. | Sucesso |
| `EQUIPAMENTO_INATIVADO` | Um equipamento com histórico é inativado. | Sucesso |
| `USUARIO_CADASTRADO` | O cadastro controlado de uma conta é aceito ou rejeitado. | Sucesso ou falha |
| `RESERVA_CRIADA` | O Professor cria uma reserva própria. | Sucesso |
| `RESERVA_CANCELADA` | O Professor cancela uma reserva própria. | Sucesso |

Uma tentativa de login inválida é registrada sem vincular o nome de usuário informado a uma conta. Consultas registram que houve uso de filtros, mas não armazenam os termos pesquisados. A importação registra um evento para o lote e não copia o conteúdo do arquivo. No cadastro de contas, a auditoria identifica o Administrador responsável e, em caso de sucesso, o identificador da conta criada, sem copiar nome, e-mail, perfil ou senha.

## Controle de acesso e consulta

A consulta funcional está disponível em `/auditoria/` e exige simultaneamente:

1. sessão autenticada;
2. associação exclusiva ao grupo funcional `Administrador`;
3. permissão `auditoria.view_registroauditoria`.

O comando `python manage.py configurar_perfis` atribui essa permissão ao grupo `Administrador`, mas não aos grupos `Operador` e `Professor`. Uma permissão individual sem o perfil funcional correto não libera a tela. O Superuser é uma conta técnica e não acessa essa página funcional, embora possa utilizar o Django Admin para manutenção técnica conforme suas permissões.

A tela é somente leitura e oferece filtros por usuário, ação, resultado e período, além de paginação em grupos de vinte registros. Não existem rotas funcionais para cadastrar, alterar ou excluir eventos. O Django Admin também bloqueia inclusão, alteração e exclusão por sua interface.

## Minimização e proteção dos dados

O serviço de auditoria aceita apenas códigos de ação em letras maiúsculas, números e sublinhados. Os limites dos campos e os resultados permitidos são validados no serviço e no banco quando aplicável.

Não são persistidos no registro de auditoria:

- senhas, hashes ou tokens;
- credenciais informadas em tentativas de login;
- parâmetros, termos de busca ou dados completos de formulários;
- conteúdo integral dos arquivos CSV;
- endereço IP ou identificação do navegador.

## Evidências automatizadas

Os testes dos arquivos `auditoria/tests.py` e `auditoria/test_consulta.py` verificam:

- criação e validação dos registros;
- proteção da referência ao usuário;
- bloqueio de inclusão, alteração e exclusão pelo Django Admin;
- eventos de autenticação, inventário e acesso negado;
- cadastro de conta bem-sucedido ou inválido;
- ausência de credenciais, termos pesquisados e conteúdo de arquivos nos registros;
- redirecionamento do usuário anônimo;
- rejeição de perfis não autorizados e do Superuser técnico;
- consulta, filtros, intervalo de datas e paginação para o Administrador.

Em 19 de setembro de 2026, a suíte integrada da branch de reservas foi executada com banco de testes isolado:

```powershell
$env:DATABASE_URL=''
.\.venv\Scripts\python.exe manage.py test
```

Resultado observado:

```text
Ran 152 tests
OK
System check identified no issues (0 silenced).
```

## Rastreabilidade

| Requisito ou decisão | Evidência no código |
|---|---|
| `RS-09` - registrar eventos relevantes de autenticação | `auditoria/signals.py` |
| `RS-11` - registrar usuário, ação, data/hora e entidade | `auditoria/models.py` e `auditoria/services.py` |
| Acessos negados devem ser auditados | `auditoria/middleware.py` |
| Operações atuais do inventário devem ser auditadas | `inventario/views.py` |
| Cadastro controlado de contas deve ser auditado | `usuarios/views.py` e `auditoria/tests.py` |
| Consulta restrita ao Administrador | `auditoria/views.py`, `usuarios/permissoes.py` e `templates/base.html` |
| Consulta somente leitura | `auditoria/admin.py` e `templates/auditoria/registro_lista.html` |
| Evidência automatizada | `auditoria/tests.py` e `auditoria/test_consulta.py` |

## Limitações e evolução

O módulo atual implementa auditoria básica. Permanecem fora do recorte atual:

- exportação dos registros;
- alertas e análise automática de comportamento;
- registro de IP, dispositivo ou localização;
- mecanismos criptográficos de encadeamento ou assinatura dos eventos;
- política automática de retenção e descarte;
- auditoria de módulos que ainda não foram implementados.

Esses itens não são necessários para considerar atendido o recorte atual e somente devem ser acrescentados mediante requisito aprovado.
