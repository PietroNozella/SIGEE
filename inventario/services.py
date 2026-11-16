from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from manutencoes.models import Manutencao
from usuarios.permissoes import pode_reativar_equipamento

from .models import Equipamento


@transaction.atomic
def reativar_equipamento(*, administrador, equipamento_id):
    atual = get_user_model().objects.filter(pk=administrador.pk).first()
    if atual is None or not pode_reativar_equipamento(atual):
        raise PermissionDenied

    equipamento = get_object_or_404(Equipamento.objects.select_for_update(), pk=equipamento_id)
    if equipamento.ativo:
        return equipamento
    ultima_manutencao = equipamento.manutencoes.filter(
        estado=Manutencao.Estado.CONCLUIDA,
    ).order_by("-data_conclusao", "-pk").first()
    if ultima_manutencao and ultima_manutencao.resultado == Manutencao.Resultado.SEM_REPARO:
        raise ValidationError("Equipamento sem possibilidade de reparo não pode ser reativado por este fluxo.")
    if equipamento.manutencoes.exclude(estado=Manutencao.Estado.CONCLUIDA).exists():
        raise ValidationError("Conclua a manutenção antes de reativar o equipamento.")
    if not Equipamento.objects.filter(pk=equipamento.pk).sem_retirada_aberta().exists():
        raise ValidationError("Registre a devolução física antes de reativar o equipamento.")
    if equipamento.situacao != Equipamento.Situacao.DISPONIVEL:
        raise ValidationError("Confira a situação do equipamento antes de reativá-lo. A reativação não altera sua situação.")
    if not (equipamento.tipo.ativo and equipamento.tipo.categoria.ativo and equipamento.local.ativo):
        raise ValidationError("Reative o tipo/modelo, a categoria e o local antes de reativar o equipamento.")

    equipamento.ativo = True
    equipamento.save(update_fields=("ativo", "data_atualizacao"))
    registrar_evento(
        usuario=atual, acao=AcaoAuditoria.EQUIPAMENTO_REATIVADO,
        resultado=RegistroAuditoria.Resultado.SUCESSO,
        entidade="inventario.Equipamento", entidade_id=equipamento.pk,
    )
    return equipamento
