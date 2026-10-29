from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Q, Value
from django.db.models.functions import Concat

from usuarios.permissoes import e_professor_funcional, pode_consultar_historico

from .models import Reserva


def reservas_visiveis(usuario):
    if not pode_consultar_historico(usuario):
        raise PermissionDenied
    reservas = Reserva.objects.select_related("professor", "tipo_equipamento", "local", "turma", "disciplina", "atividade")
    return reservas.filter(professor=usuario) if e_professor_funcional(usuario) else reservas


def historico_reservas(usuario, filtros):
    reservas = reservas_visiveis(usuario).encerradas()
    if filtros.get("busca"):
        busca = filtros["busca"]
        reservas = reservas.annotate(
            nome_professor=Concat("professor__first_name", Value(" "), "professor__last_name"),
            nome_operador=Concat("movimentacoes__operador__first_name", Value(" "), "movimentacoes__operador__last_name"),
        ).filter(
            Q(professor__username__icontains=busca) | Q(nome_professor__icontains=busca)
            | Q(movimentacoes__operador__username__icontains=busca) | Q(nome_operador__icontains=busca)
            | Q(tipo_equipamento__nome__icontains=busca)
            | Q(itens__equipamento__numero_patrimonio__icontains=busca)
        ).values_list("pk", flat=True)
        # A consulta externa preserva uma linha por reserva, mesmo com operadores distintos.
        reservas = reservas_visiveis(usuario).encerradas().filter(pk__in=reservas)
    if filtros.get("reserva"):
        reservas = reservas.filter(pk=filtros["reserva"])
    if filtros.get("tipo"):
        reservas = reservas.filter(movimentacoes__tipo=filtros["tipo"]).distinct()
    if filtros.get("inicio") or filtros.get("fim"):
        from movimentacoes.models import Movimentacao
        movimentos = Movimentacao.objects.filter(reserva_id=OuterRef("pk"))
        sem_retirada = Q(tem_retirada=False)
        if filtros.get("tipo"):
            movimentos = movimentos.filter(tipo=filtros["tipo"])
        if filtros.get("inicio"):
            movimentos = movimentos.filter(data_hora__date__gte=filtros["inicio"])
            sem_retirada &= Q(inicio__date__gte=filtros["inicio"])
        if filtros.get("fim"):
            movimentos = movimentos.filter(data_hora__date__lte=filtros["fim"])
            sem_retirada &= Q(inicio__date__lte=filtros["fim"])
        reservas = reservas.alias(movimento_no_periodo=Exists(movimentos)).filter(
            Q(tem_retirada=True, movimento_no_periodo=True) | sem_retirada,
        )
    return reservas.order_by("-inicio", "-pk")
