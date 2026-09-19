from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from usuarios.permissoes import e_professor_funcional

from .brasilapi import ConsultaFeriados, consultar_feriados_no_periodo
from .models import Reserva


@dataclass(frozen=True)
class ResultadoCriacaoReserva:
    reserva: Reserva
    consulta_feriados: ConsultaFeriados


def criar_reserva(*, professor, equipamento, inicio, fim):
    if not e_professor_funcional(professor):
        raise ValidationError(
            {
                "professor": (
                    "Somente um usuário com perfil Professor pode criar uma reserva."
                )
            }
        )
    if getattr(equipamento, "pk", None) is None:
        raise ValidationError(
            {"equipamento": "Selecione um equipamento cadastrado."}
        )

    # A primeira validação evita uma chamada externa quando os dados locais já
    # são inválidos. O período é validado novamente dentro da transação para
    # proteger contra alterações concorrentes enquanto a BrasilAPI é consultada.
    reserva = Reserva(
        professor=professor,
        equipamento=equipamento,
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
            equipamento_bloqueado = Equipamento.objects.select_for_update().get(
                pk=equipamento.pk
            )
        except Equipamento.DoesNotExist as erro:
            raise ValidationError(
                {"equipamento": "O equipamento selecionado não está disponível."}
            ) from erro

        reserva.equipamento = equipamento_bloqueado
        reserva.full_clean()
        reserva.save()

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
