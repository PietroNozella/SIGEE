from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento, Local, TipoEquipamento
from usuarios.permissoes import e_professor_funcional

from .models import Reserva, ReservaEquipamento


def _equipamentos_disponiveis(
    tipo_equipamento,
    local,
    inicio,
    fim,
    *,
    bloquear=False,
):
    conflitos = ReservaEquipamento.objects.filter(
        equipamento_id=OuterRef("pk"),
        reserva__status=Reserva.Status.ATIVA,
        reserva__inicio__lt=fim,
        reserva__fim__gt=inicio,
    )
    equipamentos = (
        Equipamento.objects.filter(
            tipo=tipo_equipamento,
            local=local,
            ativo=True,
            situacao=Equipamento.Situacao.DISPONIVEL,
        )
        .annotate(possui_conflito=Exists(conflitos))
        .filter(possui_conflito=False)
        .order_by("numero_patrimonio")
    )
    if bloquear:
        equipamentos = equipamentos.select_for_update()
    return equipamentos


def _possui_retirada_vinculada(reserva):
    from movimentacoes.models import Movimentacao

    return Movimentacao.objects.filter(
        reserva=reserva,
        tipo=Movimentacao.Tipo.RETIRADA,
    ).exists()


def _expirar_reserva_bloqueada(reserva, agora):
    if reserva.status != Reserva.Status.ATIVA:
        return False
    if reserva.inicio + Reserva.TOLERANCIA_RETIRADA > agora:
        return False
    if _possui_retirada_vinculada(reserva):
        return False

    reserva.status = Reserva.Status.EXPIRADA
    reserva.save(update_fields=("status", "data_atualizacao"))

    if not RegistroAuditoria.objects.filter(
        acao=AcaoAuditoria.RESERVA_EXPIRADA,
        entidade="reservas.Reserva",
        entidade_id=str(reserva.pk),
    ).exists():
        registrar_evento(
            usuario=None,
            acao=AcaoAuditoria.RESERVA_EXPIRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="reservas.Reserva",
            entidade_id=reserva.pk,
        )

    return True


def expirar_reservas_vencidas(agora=None):
    agora = agora or timezone.now()
    limite = agora - Reserva.TOLERANCIA_RETIRADA
    candidatos = list(
        Reserva.objects.filter(
            status=Reserva.Status.ATIVA,
            inicio__lte=limite,
        ).values_list("pk", flat=True)
    )

    expiradas = 0
    for reserva_id in candidatos:
        with transaction.atomic():
            try:
                reserva = Reserva.objects.select_for_update().get(
                    pk=reserva_id,
                    status=Reserva.Status.ATIVA,
                )
            except Reserva.DoesNotExist:
                continue
            if _expirar_reserva_bloqueada(reserva, agora):
                expiradas += 1

    return expiradas


def consultar_disponibilidade(*, professor, tipo_equipamento, local, inicio, fim):
    expirar_reservas_vencidas()
    reserva = Reserva(
        professor=professor,
        tipo_equipamento=tipo_equipamento,
        local=local,
        quantidade=1,
        inicio=inicio,
        fim=fim,
    )
    reserva.full_clean()
    return _equipamentos_disponiveis(
        tipo_equipamento,
        local,
        inicio,
        fim,
    ).count()


def criar_reserva(
    *,
    professor,
    tipo_equipamento,
    local,
    quantidade,
    inicio,
    fim,
):
    if not e_professor_funcional(professor):
        raise ValidationError(
            {
                "professor": (
                    "Somente um usuário com perfil Professor pode criar uma reserva."
                )
            }
        )
    if getattr(tipo_equipamento, "pk", None) is None:
        raise ValidationError(
            {"tipo_equipamento": "Selecione um tipo de equipamento cadastrado."}
        )
    if getattr(local, "pk", None) is None:
        raise ValidationError({"local": "Selecione um local cadastrado."})

    expirar_reservas_vencidas()

    reserva = Reserva(
        professor=professor,
        tipo_equipamento=tipo_equipamento,
        local=local,
        quantidade=quantidade,
        inicio=inicio,
        fim=fim,
    )
    reserva.full_clean()

    with transaction.atomic():
        try:
            tipo_bloqueado = TipoEquipamento.objects.select_for_update().get(
                pk=tipo_equipamento.pk,
                ativo=True,
            )
        except TipoEquipamento.DoesNotExist as erro:
            raise ValidationError(
                {
                    "tipo_equipamento": (
                        "O tipo de equipamento selecionado não está disponível."
                    )
                }
            ) from erro

        try:
            local_bloqueado = Local.objects.select_for_update().get(
                pk=local.pk,
                ativo=True,
            )
        except Local.DoesNotExist as erro:
            raise ValidationError(
                {"local": "O local selecionado não está disponível."}
            ) from erro

        reserva.tipo_equipamento = tipo_bloqueado
        reserva.local = local_bloqueado
        reserva.full_clean()
        equipamentos = list(
            _equipamentos_disponiveis(
                tipo_bloqueado,
                local_bloqueado,
                inicio,
                fim,
                bloquear=True,
            )[:quantidade]
        )
        if len(equipamentos) < quantidade:
            raise ValidationError(
                {
                    "quantidade": (
                        f"Há somente {len(equipamentos)} unidade(s) disponível(is) "
                        "para o período informado."
                    )
                }
            )

        reserva.save()
        ReservaEquipamento.objects.bulk_create(
            ReservaEquipamento(reserva=reserva, equipamento=equipamento)
            for equipamento in equipamentos
        )

        registrar_evento(
            usuario=professor,
            acao=AcaoAuditoria.RESERVA_CRIADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="reservas.Reserva",
            entidade_id=reserva.pk,
        )

    return reserva


def cancelar_reserva(*, professor, reserva):
    if not e_professor_funcional(professor):
        raise ValidationError(
            "Somente um usuário com perfil Professor pode cancelar uma reserva."
        )
    if reserva.professor_id != professor.pk:
        raise ValidationError("A reserva só pode ser cancelada pelo próprio Professor.")

    expirou_durante_cancelamento = False
    with transaction.atomic():
        reserva_bloqueada = Reserva.objects.select_for_update().get(
            pk=reserva.pk,
            professor=professor,
        )
        if reserva_bloqueada.status == Reserva.Status.CANCELADA:
            raise ValidationError("Esta reserva já está cancelada.")
        if reserva_bloqueada.status == Reserva.Status.EXPIRADA:
            raise ValidationError("Esta reserva já expirou e não pode ser cancelada.")
        if reserva_bloqueada.status != Reserva.Status.ATIVA:
            raise ValidationError("Esta reserva não está ativa.")
        if _expirar_reserva_bloqueada(reserva_bloqueada, timezone.now()):
            expirou_durante_cancelamento = True
        elif _possui_retirada_vinculada(reserva_bloqueada):
            raise ValidationError(
                "Esta reserva já possui retirada registrada e não pode ser cancelada."
            )
        else:
            reserva_bloqueada.status = Reserva.Status.CANCELADA
            reserva_bloqueada.full_clean()
            reserva_bloqueada.save(update_fields=("status", "data_atualizacao"))

            registrar_evento(
                usuario=professor,
                acao=AcaoAuditoria.RESERVA_CANCELADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="reservas.Reserva",
                entidade_id=reserva_bloqueada.pk,
            )

    if expirou_durante_cancelamento:
        raise ValidationError("Esta reserva já expirou e não pode ser cancelada.")

    return reserva_bloqueada
