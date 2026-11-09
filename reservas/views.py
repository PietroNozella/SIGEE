from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, DateTimeField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from inventario.models import Categoria, Local, TipoEquipamento
from movimentacoes.models import Movimentacao
from movimentacoes.services import reservas_para_retirada
from usuarios.permissoes import (
    e_professor_funcional, pode_cancelar_reserva_operacional, pode_consultar_historico,
    pode_consultar_reservas_administrativas, pode_registrar_retirada,
)

from .brasilapi import consultar_feriados_no_periodo
from .forms import CancelamentoOperacionalForm, DisponibilidadeReservaForm, ReservaForm
from .models import Reserva
from .consultas import reservas_visiveis
from .services import (
    cancelar_reserva,
    cancelar_reserva_operacional,
    consultar_disponibilidade,
    criar_reserva,
    expirar_reservas_vencidas,
    permite_cancelamento_operacional,
)


def _exigir_professor_funcional(user):
    if not e_professor_funcional(user):
        raise PermissionDenied


@login_required
@require_GET
def reserva_detalhe(request, reserva_id):
    from .services import resumo_entrega
    reservas = reservas_visiveis(request.user)
    expirar_reservas_vencidas()
    reserva = get_object_or_404(reservas.com_etapa(), pk=reserva_id)
    registros = Movimentacao.objects.filter(reserva=reserva).select_related(
        "equipamento__tipo", "operador", "manutencao", "utilizacao_pedagogica__turma",
        "utilizacao_pedagogica__disciplina", "utilizacao_pedagogica__atividade",
    ).order_by("data_hora", "pk")
    if reserva.etapa == "AGUARDANDO":
        rota = "reservas:reserva_lista" if e_professor_funcional(request.user) else (
            "reservas:reserva_consulta" if pode_consultar_reservas_administrativas(request.user) else "movimentacoes:retirada_reserva_lista"
        )
        rotulo = "Reservas"
    else:
        rota = "movimentacoes:devolucao_lista" if reserva.etapa == "EM_USO" else "movimentacoes:historico_lista"
        rotulo = "Em uso" if reserva.etapa == "EM_USO" else "Histórico"
    return render(request, "reservas/reserva_detalhe.html", {
        "reserva": reserva, "registros": registros,
        "resumo": resumo_entrega(reserva),
        "pode_cancelar": (
            e_professor_funcional(request.user)
            and reserva.status == Reserva.Status.ATIVA
            and not reserva.tem_retirada
        ),
        "pode_cancelar_operacional": (
            pode_cancelar_reserva_operacional(request.user) and permite_cancelamento_operacional(reserva)
        ),
        "substituicoes": reserva.substituicoes.select_related("equipamento_anterior", "equipamento_substituto"),
        "unidades": reserva.itens.select_related("equipamento__tipo"),
        "url_voltar": reverse(rota), "rotulo_voltar": rotulo,
        "aba_fluxo": "reservas" if reserva.etapa == "AGUARDANDO" else ("em_uso" if reserva.etapa == "EM_USO" else "historico"),
    })


@login_required
@require_http_methods(["GET", "POST"])
def reserva_cancelamento_operacional(request, reserva_id):
    if not pode_cancelar_reserva_operacional(request.user):
        raise PermissionDenied
    reserva = get_object_or_404(Reserva.objects.select_related(
        "professor", "tipo_equipamento", "local", "turma", "cancelada_por",
    ), pk=reserva_id)
    form = CancelamentoOperacionalForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            cancelar_reserva_operacional(
                operador=request.user, reserva_id=reserva.pk, motivo=form.cleaned_data["motivo"],
                desistencia_confirmada=form.cleaned_data["desistencia_confirmada"],
            )
        except ValidationError as erro:
            _adicionar_erros_validacao(form, erro)
            reserva.refresh_from_db()
        else:
            messages.success(request, "Reserva cancelada. A desistência e o responsável foram registrados.")
            destino = "reservas:reserva_detalhe" if pode_consultar_historico(request.user) else "reservas:reserva_cancelamento_operacional"
            return redirect(destino, reserva_id=reserva.pk)
    return render(request, "reservas/reserva_cancelamento_operacional.html", {
        "reserva": reserva, "form": form,
        "pode_consultar_detalhe": pode_consultar_historico(request.user),
        "pode_consultar_lista": pode_registrar_retirada(request.user),
        "pode_confirmar": permite_cancelamento_operacional(reserva),
        "unidades": reserva.itens.select_related("equipamento__tipo"),
        "aba_fluxo": "reservas",
    })


@login_required
@require_GET
def reserva_consulta(request):
    if not pode_consultar_reservas_administrativas(request.user):
        raise PermissionDenied
    expirar_reservas_vencidas()
    busca = request.GET.get("busca", "").strip()[:200]
    categoria_id = request.GET.get("categoria", "")
    categoria = Categoria.objects.filter(pk=categoria_id).first() if categoria_id.isdecimal() and len(categoria_id) <= 19 else None
    status = request.GET.get("status", "").strip()
    if status not in Reserva.Status.values:
        status = ""
    reservas = (
        reservas_para_retirada(busca=busca, status=status)
        .prefetch_related("itens__equipamento")
        .order_by("-inicio", "-pk")
    )
    if categoria:
        reservas = reservas.filter(tipo_equipamento__categoria=categoria)
    pagina = Paginator(reservas, 15).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "reservas/reserva_consulta.html", {
        "pagina": pagina, "busca": busca, "status": status,
        "categorias": Categoria.objects.order_by("nome"), "categoria_selecionada": categoria,
        "status_choices": Reserva.Status.choices,
        "parametros_paginacao": parametros.urlencode(),
    })


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
        Reserva.objects.aguardando_retirada().filter(professor=request.user)
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
                turma=form.cleaned_data["turma"], disciplina=form.cleaned_data["disciplina"],
                atividade=form.cleaned_data["atividade"], observacao=form.cleaned_data["observacao"],
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
