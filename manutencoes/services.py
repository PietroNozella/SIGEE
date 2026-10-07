from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from usuarios.permissoes import pode_gerenciar_manutencao

from .models import Manutencao


def _administrador_autorizado(usuario, acao):
    if not usuario.is_authenticated:
        raise PermissionDenied
    atual = get_user_model().objects.filter(pk=usuario.pk).first()
    if atual is None or not pode_gerenciar_manutencao(atual, acao):
        raise PermissionDenied
    return atual


def _registrar_sucesso(manutencao, usuario, acao):
    registrar_evento(
        usuario=usuario, acao=acao, resultado=RegistroAuditoria.Resultado.SUCESSO,
        entidade="manutencoes.Manutencao", entidade_id=manutencao.pk,
    )


def _abrir_manutencao_bloqueada(*, equipamento, usuario, descricao_problema, devolucao=None):
    # Chamado somente dentro da transação que já bloqueou o equipamento.
    if equipamento.manutencoes.exclude(estado=Manutencao.Estado.CONCLUIDA).exists():
        raise ValidationError("Este equipamento já possui uma manutenção aberta.")
    manutencao = Manutencao(
        equipamento=equipamento, aberto_por=usuario, descricao_problema=descricao_problema,
        devolucao_origem=devolucao,
    )
    manutencao.full_clean()
    manutencao.save()
    equipamento.situacao = Equipamento.Situacao.MANUTENCAO
    equipamento.save(update_fields=("situacao", "data_atualizacao"))
    _registrar_sucesso(manutencao, usuario, AcaoAuditoria.MANUTENCAO_ABERTA)
    return manutencao


@transaction.atomic
def abrir_manutencao(*, administrador, equipamento_id, descricao_problema):
    usuario = _administrador_autorizado(administrador, "add")
    try:
        equipamento = Equipamento.objects.select_for_update().get(pk=equipamento_id)
    except Equipamento.DoesNotExist as erro:
        raise ValidationError("O equipamento informado não existe.") from erro
    if not equipamento.ativo or equipamento.situacao != Equipamento.Situacao.DISPONIVEL:
        raise ValidationError("A abertura manual exige um equipamento ativo e disponível.")
    return _abrir_manutencao_bloqueada(
        equipamento=equipamento, usuario=usuario, descricao_problema=descricao_problema,
    )


def _bloquear_intervencao(manutencao_id):
    try:
        equipamento_id = Manutencao.objects.values_list("equipamento_id", flat=True).get(pk=manutencao_id)
        # Abertura e movimentações também bloqueiam o equipamento antes da intervenção.
        equipamento = Equipamento.objects.select_for_update().get(pk=equipamento_id)
        manutencao = Manutencao.objects.select_for_update().get(pk=manutencao_id)
    except Manutencao.DoesNotExist as erro:
        raise ValidationError("A manutenção informada não existe.") from erro
    return manutencao, equipamento


@transaction.atomic
def iniciar_manutencao(*, administrador, manutencao_id):
    usuario = _administrador_autorizado(administrador, "change")
    manutencao, equipamento = _bloquear_intervencao(manutencao_id)
    if manutencao.estado != Manutencao.Estado.PENDENTE:
        raise ValidationError("Somente uma manutenção pendente pode ser iniciada.")
    manutencao.estado = Manutencao.Estado.EM_ANDAMENTO
    manutencao.iniciado_por = usuario
    manutencao.data_inicio = timezone.now()
    manutencao.full_clean()
    manutencao.save(update_fields=("estado", "iniciado_por", "data_inicio"))
    equipamento.situacao = Equipamento.Situacao.MANUTENCAO
    equipamento.save(update_fields=("situacao", "data_atualizacao"))
    _registrar_sucesso(manutencao, usuario, AcaoAuditoria.MANUTENCAO_INICIADA)
    return manutencao


@transaction.atomic
def concluir_manutencao(*, administrador, manutencao_id, resultado, descricao_solucao):
    usuario = _administrador_autorizado(administrador, "change")
    manutencao, equipamento = _bloquear_intervencao(manutencao_id)
    if manutencao.estado != Manutencao.Estado.EM_ANDAMENTO:
        raise ValidationError("Somente uma manutenção em andamento pode ser concluída.")
    manutencao.estado = Manutencao.Estado.CONCLUIDA
    manutencao.resultado = resultado
    manutencao.descricao_solucao = descricao_solucao
    manutencao.concluido_por = usuario
    manutencao.data_conclusao = timezone.now()
    manutencao.full_clean()
    manutencao.save(update_fields=("estado", "resultado", "descricao_solucao", "concluido_por", "data_conclusao"))
    if resultado == Manutencao.Resultado.REPARADO:
        # Uma inativação independente (RN-06) não é desfeita pelo reparo.
        equipamento.situacao = Equipamento.Situacao.DISPONIVEL
    else:
        equipamento.ativo = False
        equipamento.situacao = Equipamento.Situacao.MANUTENCAO
    equipamento.save(update_fields=("ativo", "situacao", "data_atualizacao"))
    _registrar_sucesso(manutencao, usuario, AcaoAuditoria.MANUTENCAO_CONCLUIDA)
    return manutencao
