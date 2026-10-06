from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from usuarios.permissoes import pode_consultar_historico, pode_registrar_devolucao, pode_registrar_retirada
from reservas.models import Reserva
from reservas.services import expirar_reservas_vencidas

from .forms import ConsultaRetiradaForm, DevolucaoForm, HistoricoFiltroForm, RetiradaReservaForm, RetiradaSemReservaForm
from .models import Movimentacao
from .services import (
    equipamentos_disponiveis_para_retirada,
    grupos_devolucao,
    registrar_devolucoes,
    registrar_retirada_sem_reserva,
    retiradas_do_grupo,
    consultar_historico,
    registrar_retirada_reserva,
    reservas_para_retirada,
)


@login_required
@require_GET
def historico_lista(request):
    if not pode_consultar_historico(request.user):
        raise PermissionDenied
    form = HistoricoFiltroForm(request.GET)
    registros = consultar_historico(form.cleaned_data) if form.is_valid() else Movimentacao.objects.none()
    pagina = Paginator(registros, 25).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "movimentacoes/historico_lista.html", {
        "form": form, "pagina": pagina, "parametros_paginacao": parametros.urlencode(),
    })


@login_required
@require_GET
def retirada_reserva_lista(request):
    if not pode_registrar_retirada(request.user):
        raise PermissionDenied
    expirar_reservas_vencidas()
    busca = request.GET.get("busca", "").strip()
    status = request.GET.get("status", Reserva.Status.ATIVA)
    if status not in ["", *Reserva.Status.values]:
        status = Reserva.Status.ATIVA
    pagina = Paginator(reservas_para_retirada(busca=busca, status=status), 15).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "movimentacoes/retirada_reserva_lista.html", {
        "pagina": pagina, "busca": busca, "status": status, "status_choices": Reserva.Status.choices,
        "parametros_paginacao": parametros.urlencode(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def retirada_reserva_registrar(request, reserva_id):
    if not pode_registrar_retirada(request.user):
        raise PermissionDenied
    reserva = get_object_or_404(Reserva.objects.select_related("professor", "tipo_equipamento", "local"), pk=reserva_id)
    form = RetiradaReservaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            try:
                movimentacoes = registrar_retirada_reserva(
                    operador=request.user, reserva_id=reserva.pk, observacao=form.cleaned_data["observacao"],
                )
            except ValidationError as erro:
                form.add_error(None, erro)
            except IntegrityError:
                form.add_error(None, "Não foi possível registrar a retirada. Nenhuma alteração foi salva. Tente novamente.")
            else:
                messages.success(request, f"Retirada da reserva #{reserva.pk} registrada: {len(movimentacoes)} equipamento(s) em uso.")
                return redirect("movimentacoes:devolucao_lista")
        registrar_evento(
            usuario=request.user, acao=AcaoAuditoria.RETIRADA_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="reservas.Reserva", entidade_id=reserva.pk,
        )
        reserva.refresh_from_db()
    unidades = reserva.itens.select_related("equipamento__tipo", "equipamento__local").order_by("equipamento__numero_patrimonio")
    retirada = Movimentacao.objects.filter(reserva=reserva, tipo=Movimentacao.Tipo.RETIRADA).order_by("pk").first()
    return render(request, "movimentacoes/retirada_reserva_form.html", {
        "reserva": reserva, "unidades": unidades, "form": form, "retirada": retirada,
    })


def _dados_disponibilidade(consulta):
    tipo = consulta.cleaned_data["tipo_equipamento"]
    locais = list(consulta.fields["local"].queryset)
    local = consulta.cleaned_data["local"]
    if local is None and len(locais) == 1:
        local = locais[0]
    equipamentos = []
    if local is not None:
        equipamentos = list(equipamentos_disponiveis_para_retirada(
            tipo_equipamento=tipo, local=local,
        ).select_related("tipo", "local"))
    return {
        "locais": [{"id": item.pk, "nome": item.nome} for item in locais],
        "local": local.pk if local else None,
        "disponiveis": len(equipamentos),
        "equipamentos": [
            {"id": item.pk, "patrimonio": item.numero_patrimonio,
             "tipo": item.tipo.nome, "local": item.local.nome}
            for item in equipamentos
        ],
    }


@login_required
@require_GET
def retirada_disponibilidade(request):
    if not pode_registrar_retirada(request.user):
        raise PermissionDenied
    consulta = ConsultaRetiradaForm(request.GET)
    if not consulta.is_valid():
        return JsonResponse({"erros": consulta.errors.get_json_data()}, status=400)
    return JsonResponse(_dados_disponibilidade(consulta))


@login_required
@require_http_methods(["GET", "POST"])
def retirada_sem_reserva(request):
    if not pode_registrar_retirada(request.user):
        raise PermissionDenied

    consultando = request.method == "POST" and request.POST.get("acao") == "consultar"
    form = RetiradaSemReservaForm(request.POST if request.method == "POST" else None)
    disponibilidade = None
    erros_consulta = None
    selecionados = request.POST.getlist("equipamentos") if request.method == "POST" else []
    if consultando:
        consulta = ConsultaRetiradaForm(request.POST)
        if consulta.is_valid():
            disponibilidade = _dados_disponibilidade(consulta)
            initial = request.POST.dict()
            initial["local"] = disponibilidade["local"]
            form = RetiradaSemReservaForm(initial=initial)
            quantidade = consulta.cleaned_data["quantidade"] or 1
            form.initial["quantidade"] = quantidade
            selecionados = [
                str(item["id"]) for item in disponibilidade["equipamentos"][:quantidade]
            ]
        else:
            # Consulta não exige destinatário nem seleciona/grava movimentações.
            form = RetiradaSemReservaForm(initial=request.POST.dict())
            erros_consulta = consulta
    elif request.method == "POST":
        if form.is_valid():
            try:
                movimentacoes = registrar_retirada_sem_reserva(
                    operador=request.user,
                    tipo_equipamento=form.cleaned_data["tipo_equipamento"],
                    local=form.cleaned_data["local"],
                    quantidade=form.cleaned_data["quantidade"],
                    equipamentos=form.cleaned_data["equipamentos"],
                    destinatario=form.cleaned_data["destinatario"],
                    observacao=form.cleaned_data["observacao"],
                )
            except ValidationError as erro:
                if hasattr(erro, "message_dict"):
                    for campo, erros in erro.message_dict.items():
                        form.add_error(campo if campo in form.fields else None, erros)
                else:
                    form.add_error(None, erro)
            except IntegrityError:
                form.add_error(
                    None,
                    "Não foi possível registrar a retirada. Nenhuma alteração foi salva. "
                    "Tente novamente.",
                )
            else:
                messages.success(
                    request,
                    f"Retirada de {len(movimentacoes)} equipamento(s) registrada com sucesso. "
                    "Os equipamentos estão em uso.",
                )
                return redirect("movimentacoes:devolucao_lista")

        registrar_evento(
            usuario=request.user, acao=AcaoAuditoria.RETIRADA_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="movimentacoes.Movimentacao",
        )

    if disponibilidade is None and request.method == "POST":
        consulta = ConsultaRetiradaForm(request.POST)
        if consulta.is_valid():
            disponibilidade = _dados_disponibilidade(consulta)
    return render(request, "movimentacoes/retirada_form.html", {
        "form": form, "disponibilidade": disponibilidade,
        "selecionados": selecionados,
        "erros_consulta": erros_consulta,
    })


@login_required
@require_GET
def devolucao_lista(request):
    if not pode_registrar_devolucao(request.user):
        raise PermissionDenied
    busca = request.GET.get("busca", "").strip()
    pagina = Paginator(grupos_devolucao(busca), 15).get_page(request.GET.get("pagina"))
    grupos = list(pagina.object_list)
    referencias = Movimentacao.objects.select_related(
        "equipamento__tipo", "destinatario", "operador",
    ).in_bulk([grupo["retirada_id"] for grupo in grupos])
    for grupo in grupos:
        grupo["retirada"] = referencias[grupo["retirada_id"]]
        grupo["devolvidas"] = grupo["total"] - grupo["pendentes"]
    pagina.object_list = grupos
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "movimentacoes/devolucao_lista.html", {
        "pagina": pagina, "busca": busca, "parametros_paginacao": parametros.urlencode(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def devolucao_registrar(request, retirada_id):
    if not pode_registrar_devolucao(request.user):
        raise PermissionDenied
    retirada = get_object_or_404(
        Movimentacao.objects.select_related(
            "equipamento__tipo", "equipamento__local", "destinatario", "operador",
        ),
        pk=retirada_id, tipo=Movimentacao.Tipo.RETIRADA,
    )
    grupo = retiradas_do_grupo(retirada)
    form = DevolucaoForm(
        request.POST if request.method == "POST" else None,
        retiradas=grupo.filter(devolvida=False),
    )
    if request.method == "POST":
        if form.is_valid():
            try:
                devolucoes = registrar_devolucoes(
                    operador=request.user, retirada_id=retirada.pk,
                    retiradas_ids=[item.pk for item in form.cleaned_data["retiradas"]],
                    observacao=form.cleaned_data["observacao"],
                )
            except ValidationError as erro:
                form.add_error(None, erro)
            except IntegrityError:
                form.add_error(
                    None, "Não foi possível registrar a devolução. Nenhuma alteração foi salva. "
                    "Atualize o lote e tente novamente.",
                )
            else:
                impedidos = sum(
                    not item.equipamento.ativo or item.equipamento.situacao == Equipamento.Situacao.MANUTENCAO
                    for item in devolucoes
                )
                complemento = (
                    "Equipamentos inativos ou em manutenção mantiveram seu impedimento."
                    if impedidos else "Os equipamentos devolvidos estão disponíveis."
                )
                messages.success(
                    request, f"Devolução de {len(devolucoes)} equipamento(s) registrada com sucesso. {complemento}",
                )
                return redirect("movimentacoes:devolucao_lista")
        registrar_evento(
            usuario=request.user, acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="movimentacoes.Movimentacao", entidade_id=retirada.pk,
        )
    unidades = list(grupo.order_by("equipamento__numero_patrimonio", "pk"))
    abertas = [item for item in unidades if not item.devolvida]
    selecionados = (
        request.POST.getlist("retiradas") if request.method == "POST"
        else [str(item.pk) for item in abertas]
    )
    return render(request, "movimentacoes/devolucao_form.html", {
        "retirada": retirada, "form": form, "devolvida": not abertas,
        "unidades": unidades, "selecionados": selecionados,
        "total": len(unidades), "pendentes": len(abertas), "devolvidas": len(unidades) - len(abertas),
        "referencia_id": min(item.pk for item in unidades),
    })
