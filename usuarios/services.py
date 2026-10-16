from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from reservas.models import Reserva

from .permissoes import (
    GRUPOS_FUNCIONAIS, GRUPO_ADMINISTRADOR, pode_gerenciar_usuarios,
    usuarios_funcionais,
)


def invalidar_sessoes_usuario(usuario_id):
    sessoes = Session.objects.filter(expire_date__gte=timezone.now())
    ids = [
        sessao.pk for sessao in sessoes
        if sessao.get_decoded().get("_auth_user_id") == str(usuario_id)
    ]
    return Session.objects.filter(pk__in=ids).delete()[0]


@transaction.atomic
def alterar_situacao_usuario(*, administrador, usuario_id, ativo):
    if not administrador.is_authenticated:
        raise PermissionDenied

    # A ordem também serializa dois administradores tentando inativar um ao outro.
    usuarios = {
        usuario.pk: usuario
        for usuario in get_user_model().objects.select_for_update().filter(
            pk__in=(administrador.pk, usuario_id),
        ).order_by("pk")
    }
    administrador_atual = usuarios.get(administrador.pk)
    if administrador_atual is None or not pode_gerenciar_usuarios(administrador_atual, "change"):
        raise PermissionDenied
    usuario = usuarios.get(usuario_id)
    if usuario is None:
        raise Http404

    grupos = set(usuario.groups.values_list("name", flat=True))
    if usuario.is_staff or usuario.is_superuser:
        raise ValidationError("Contas técnicas não podem ser alteradas por este fluxo.")
    if len(grupos) != 1 or not grupos.issubset(GRUPOS_FUNCIONAIS):
        raise ValidationError("A conta precisa possuir um único perfil funcional. Contas anonimizadas não podem ser reativadas.")
    if not ativo:
        if grupos == {GRUPO_ADMINISTRADOR} and not usuarios_funcionais().filter(
            is_active=True, groups__name=GRUPO_ADMINISTRADOR,
        ).exclude(pk=usuario.pk).exists():
            raise ValidationError("O último Administrador ativo não pode ser desativado.")
        if usuario.pk == administrador_atual.pk:
            raise ValidationError("Você não pode desativar a própria conta.")
        if usuario.reservas.filter(
            status=Reserva.Status.ATIVA,
        ).exclude(movimentacoes__tipo="RETIRADA").exists():
            raise ValidationError("O usuário possui reservas ativas sem retirada. Cancele ou aguarde a expiração antes de desativar a conta.")

    if usuario.is_active == ativo:
        return usuario

    usuario.is_active = ativo
    usuario.save(update_fields=("is_active",))
    invalidar_sessoes_usuario(usuario.pk)
    registrar_evento(
        usuario=administrador_atual,
        acao=AcaoAuditoria.USUARIO_REATIVADO if ativo else AcaoAuditoria.USUARIO_DESATIVADO,
        resultado=RegistroAuditoria.Resultado.SUCESSO,
        entidade=usuario._meta.label,
        entidade_id=usuario.pk,
    )
    return usuario
