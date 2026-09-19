from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento, Local, TipoEquipamento
from usuarios.permissoes import e_professor_funcional

from .brasilapi import ConsultaFeriados, consultar_feriados_no_periodo
from .models import Reserva, ReservaEquipamento


@dataclass(frozen=True)
class ResultadoCriacaoReserva:
    reserva: Reserva
    consulta_feriados: ConsultaFeriados


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


def consultar_disponibilidade(*, professor, tipo_equipamento, local, inicio, fim):
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

    # A primeira validação evita uma chamada externa quando os dados locais já
    # são inválidos. O período é validado novamente dentro da transação para
    # proteger contra alterações concorrentes enquanto a BrasilAPI é consultada.
    reserva = Reserva(
        professor=professor,
        tipo_equipamento=tipo_equipamento,
        local=local,
        quantidade=quantidade,
        inicio=inicio,
        fim=fim,
    )
    reserva.full_clean()

    inicio_local = timezone.localtime(inicio)
    fim_local = timezone.localtime(fim)
    consulta_feriados = consultar_feriados_no_periodo(
        inicio_local.date(),
        fim_local.date(),
    )

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

    return ResultadoCriacaoReserva(
        reserva=reserva,
        consulta_feriados=consulta_feriados,
    )


def cancelar_reserva(*, professor, reserva):
    if not e_professor_funcional(professor):
        raise ValidationError(
            "Somente um usuário com perfil Professor pode cancelar uma reserva."
        )
    if reserva.professor_id != professor.pk:
        raise ValidationError("A reserva só pode ser cancelada pelo próprio Professor.")

    with transaction.atomic():
        reserva_bloqueada = Reserva.objects.select_for_update().get(
            pk=reserva.pk,
            professor=professor,
        )
        if reserva_bloqueada.status != Reserva.Status.ATIVA:
            raise ValidationError("Esta reserva já está cancelada.")

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

    return reserva_bloqueada
