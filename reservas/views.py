from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, DateTimeField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from inventario.models import Local, TipoEquipamento
from usuarios.permissoes import e_professor_funcional

from .brasilapi import consultar_feriados_no_periodo
from .forms import DisponibilidadeReservaForm, ReservaForm
from .models import Reserva
from .services import (
    cancelar_reserva,
    consultar_disponibilidade,
    criar_reserva,
    expirar_reservas_vencidas,
)


def _exigir_professor_funcional(user):
    if not e_professor_funcional(user):
        raise PermissionDenied


def _adicionar_erros_validacao(form, erro):
    campos_periodo = {
        "inicio": "data_reserva",
        "fim": "hora_fim",
    }
    if hasattr(erro, "message_dict"):
        for campo, mensagens in erro.message_dict.items():
            destino = campos_periodo.get(campo, campo)
            if destino not in form.fields:
                destino = None
            for mensagem in mensagens:
                form.add_error(destino, mensagem)
        return

    for mensagem in erro.messages:
        form.add_error(None, mensagem)


@login_required
@permission_required("reservas.view_reserva", raise_exception=True)
def reserva_lista(request):
    _exigir_professor_funcional(request.user)

    expirar_reservas_vencidas()
    agora = timezone.now()
    reservas = (
        Reserva.objects.filter(professor=request.user)
        .select_related("tipo_equipamento", "tipo_equipamento__categoria", "local")
        .prefetch_related("itens__equipamento", "itens__equipamento__local")
        .annotate(
            grupo_temporal=Case(
                When(inicio__gte=agora, then=Value(0)),
                default=Value(1),
            ),
            inicio_futuro=Case(
                When(inicio__gte=agora, then="inicio"),
                default=Value(None),
                output_field=DateTimeField(),
            ),
            inicio_passado=Case(
                When(inicio__lt=agora, then="inicio"),
                default=Value(None),
                output_field=DateTimeField(),
            ),
        )
        .order_by("grupo_temporal", "inicio_futuro", "-inicio_passado", "-pk")
    )
    status = request.GET.get("status", "").strip()
    if status in Reserva.Status.values:
        reservas = reservas.filter(status=status)
    else:
        status = ""

    paginator = Paginator(reservas, 8)
    pagina = paginator.get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)

    return render(
        request,
        "reservas/reserva_lista.html",
        {
            "pagina": pagina,
            "status_atual": status,
            "status_reserva": Reserva.Status,
            "parametros_paginacao": parametros.urlencode(),
        },
    )


@login_required
@permission_required("reservas.add_reserva", raise_exception=True)
def reserva_nova(request):
    _exigir_professor_funcional(request.user)

    tipo_inicial = None
    local_inicial = None
    tipo_id = request.GET.get("tipo", "")
    if tipo_id.isdigit():
        tipo_inicial = TipoEquipamento.objects.filter(
            pk=tipo_id,
            ativo=True,
        ).first()

    local_id = request.GET.get("local", "")
    if local_id.isdigit():
        local_inicial = Local.objects.filter(
            pk=local_id,
            ativo=True,
        ).first()

    form = ReservaForm(
        request.POST or None,
        initial={"tipo_equipamento": tipo_inicial, "local": local_inicial},
    )

    if request.method == "POST" and form.is_valid():
        try:
            criar_reserva(
                professor=request.user,
                tipo_equipamento=form.cleaned_data["tipo_equipamento"],
                local=form.cleaned_data["local"],
                quantidade=form.cleaned_data["quantidade"],
                inicio=form.cleaned_data["inicio"],
                fim=form.cleaned_data["fim"],
            )
        except ValidationError as erro:
            _adicionar_erros_validacao(form, erro)
        else:
            messages.success(request, "Reserva criada com sucesso.", extra_tags="reserva")
            return redirect("reservas:reserva_lista")

    return render(request, "reservas/reserva_form.html", {"form": form})


@login_required
@permission_required("reservas.add_reserva", raise_exception=True)
@require_GET
def reserva_disponibilidade(request):
    _exigir_professor_funcional(request.user)
    form = DisponibilidadeReservaForm(request.GET)
    if not form.is_valid():
        primeiro_erro = next(
            (
                erro
                for mensagens in form.errors.values()
                for erro in mensagens
            ),
            "Informe o tipo/modelo e um período válido.",
        )
        return JsonResponse({"erro": primeiro_erro}, status=400)

    try:
        disponiveis = consultar_disponibilidade(
            professor=request.user,
            tipo_equipamento=form.cleaned_data["tipo_equipamento"],
            local=form.cleaned_data["local"],
            inicio=form.cleaned_data["inicio"],
            fim=form.cleaned_data["fim"],
        )
    except ValidationError as erro:
        mensagens = (
            [mensagem for valores in erro.message_dict.values() for mensagem in valores]
            if hasattr(erro, "message_dict")
            else erro.messages
        )
        return JsonResponse({"erro": mensagens[0]}, status=400)

    inicio_local = timezone.localtime(form.cleaned_data["inicio"])
    fim_local = timezone.localtime(form.cleaned_data["fim"])
    consulta_feriados = consultar_feriados_no_periodo(
        inicio_local.date(),
        fim_local.date(),
    )

    return JsonResponse(
        {
            "disponiveis": disponiveis,
            "consulta_feriados": {
                "completa": consulta_feriados.completa,
                "feriados": [
                    {
                        "data": feriado.data.isoformat(),
                        "nome": feriado.nome,
                    }
                    for feriado in consulta_feriados.feriados
                ],
            },
        }
    )


@login_required
@permission_required("reservas.add_reserva", raise_exception=True)
@require_GET
def reserva_feriados(request):
    _exigir_professor_funcional(request.user)

    try:
        ano = int(request.GET.get("ano", ""))
        inicio_ano = date(ano, 1, 1)
        fim_ano = date(ano, 12, 31)
    except (OverflowError, TypeError, ValueError):
        return JsonResponse({"erro": "Informe um ano válido."}, status=400)

    consulta = consultar_feriados_no_periodo(inicio_ano, fim_ano)
    return JsonResponse(
        {
            "completa": consulta.completa,
            "feriados": [
                {
                    "data": feriado.data.isoformat(),
                    "nome": feriado.nome,
                }
                for feriado in consulta.feriados
            ],
        }
    )


@login_required
@permission_required("reservas.change_reserva", raise_exception=True)
@require_POST
def reserva_cancelar(request, reserva_id):
    _exigir_professor_funcional(request.user)
    reserva = get_object_or_404(
        Reserva,
        pk=reserva_id,
        professor=request.user,
    )

    try:
        cancelar_reserva(professor=request.user, reserva=reserva)
    except ValidationError as erro:
        messages.error(request, erro.messages[0], extra_tags="reserva")
    else:
        messages.success(request, "Reserva cancelada com sucesso.", extra_tags="reserva")

    return redirect("reservas:reserva_lista")
