from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from usuarios.permissoes import pode_registrar_retirada, usuarios_funcionais_ativos

from .models import Movimentacao


def equipamentos_disponiveis_para_retirada(*, tipo_equipamento, local=None):
    equipamentos = Equipamento.objects.filter(
        tipo=tipo_equipamento, ativo=True,
        situacao=Equipamento.Situacao.DISPONIVEL,
    )
    if local is not None:
        equipamentos = equipamentos.filter(local=local)
    return equipamentos.order_by("numero_patrimonio")


def registrar_retirada_sem_reserva(
    *, operador, tipo_equipamento, local, quantidade, equipamentos,
    destinatario, observacao="",
):
    if not operador.is_authenticated:
        raise PermissionDenied
    operador_atual = get_user_model().objects.filter(pk=operador.pk).first()
    if operador_atual is None or not pode_registrar_retirada(operador_atual):
        raise PermissionDenied

    ids = [equipamento.pk for equipamento in equipamentos]
    if quantidade < 1 or len(ids) != quantidade or len(set(ids)) != quantidade:
        raise ValidationError({
            "equipamentos": "Selecione exatamente a quantidade informada, sem repetir patrimônios.",
        })

    with transaction.atomic():
        # Ordem estável evita bloqueios cruzados entre lotes que compartilham unidades.
        # Revalidar os mesmos IDs conferidos evita substituições silenciosas.
        bloqueados = list(
            Equipamento.objects.select_for_update()
            .filter(pk__in=ids).order_by("pk")
        )
        if len(bloqueados) != quantidade:
            raise ValidationError({
                "equipamentos": "Um dos equipamentos não está mais cadastrado. Revise o lote.",
            })
        for equipamento in bloqueados:
            if equipamento.tipo_id != tipo_equipamento.pk or equipamento.local_id != local.pk:
                raise ValidationError({
                    "equipamentos": "Todos os patrimônios devem pertencer ao tipo/modelo e local selecionados.",
                })
            if not equipamento.ativo or equipamento.situacao != Equipamento.Situacao.DISPONIVEL:
                raise ValidationError({
                    "equipamentos": (
                        f"O equipamento {equipamento.numero_patrimonio} está inativo ou "
                        "não está disponível para retirada. Revise o lote."
                    ),
                })

        try:
            destinatario_atual = usuarios_funcionais_ativos().get(pk=destinatario.pk)
        except get_user_model().DoesNotExist as erro:
            raise ValidationError({
                "destinatario": "Selecione um destinatário ativo com um único perfil funcional.",
            }) from erro

        movimentacoes = []
        for equipamento in bloqueados:
            movimentacao = Movimentacao(
                equipamento=equipamento, operador=operador_atual,
                destinatario=destinatario_atual, tipo=Movimentacao.Tipo.RETIRADA,
                observacao=observacao,
            )
            movimentacao.full_clean()
            movimentacao.save()
            equipamento.situacao = Equipamento.Situacao.EM_USO
            equipamento.save(update_fields=("situacao", "data_atualizacao"))
            registrar_evento(
                usuario=operador_atual, acao=AcaoAuditoria.RETIRADA_REGISTRADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="movimentacoes.Movimentacao", entidade_id=movimentacao.pk,
            )
            movimentacoes.append(movimentacao)

    return movimentacoes
