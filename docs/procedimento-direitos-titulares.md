# Procedimento para direitos dos titulares

O canal inicial do SIGEE é o endereço configurado em `SIGEE_CONTATO_PRIVACIDADE`. A instituição controladora deve confirmar que o canal é monitorado e indicar responsáveis e substitutos antes do uso de dados reais.

## Fluxo de atendimento

1. **Receber e protocolar:** registrar data, solicitante, direito invocado e canal de resposta, sem copiar dados desnecessários.
2. **Verificar identidade:** usar informação suficiente para evitar entrega ou alteração indevida; nunca solicitar senha.
3. **Localizar dados:** consultar conta, grupos, reservas, movimentações, auditoria e aceites.
4. **Analisar cabimento:** identificar dados corrigíveis, exportáveis, elimináveis, sujeitos a anonimização ou que precisem ser preservados.
5. **Executar com dupla verificação:** um responsável prepara e outro valida ações destrutivas ou irreversíveis.
6. **Responder:** informar o resultado, dados preservados, motivo e canal de contestação.
7. **Registrar encerramento:** guardar protocolo, decisão, responsáveis e evidência mínima pelo prazo aprovado.

## Direitos e resposta do SIGEE

| Solicitação | Procedimento |
|---|---|
| confirmação e acesso | executar `exportar_dados_usuario` e revisar o JSON antes da entrega segura |
| correção | corrigir a conta pelo Django Admin ou fluxo institucional autorizado e registrar a ação |
| informação sobre compartilhamentos | consultar a matriz em `governanca-dados-pessoais.md` e os contratos vigentes |
| bloqueio ou restrição | marcar a conta como inativa, remover grupos e invalidar sessões |
| eliminação ou anonimização | verificar retenções e executar `anonimizar_usuario` quando cabível |
| portabilidade | fornecer JSON estruturado quando tecnicamente aplicável |
| revogação de consentimento | identificar a finalidade específica; o aceite geral dos documentos não é consentimento |
| oposição | encaminhar à controladora para avaliar a hipótese legal e o impacto da interrupção |
| revisão automatizada | informar que o SIGEE não toma decisões com efeito sobre pessoas unicamente por tratamento automatizado |

## Comandos de apoio

```powershell
python manage.py exportar_dados_usuario <username>
python manage.py anonimizar_usuario <username>
python manage.py anonimizar_usuario <username> --confirmar
```

O resultado da exportação contém dados pessoais. Ele deve ser encaminhado por canal seguro, não deve ser versionado e precisa ser descartado após a entrega e o prazo de protocolo aplicável.

## Registro mínimo do atendimento

- número de protocolo;
- data de recebimento e conclusão;
- identidade verificada e representante, quando houver;
- escopo do pedido;
- decisão e fundamento;
- ações executadas;
- dados preservados e critério de retenção;
- responsáveis pela execução e validação;
- data e canal da resposta.
