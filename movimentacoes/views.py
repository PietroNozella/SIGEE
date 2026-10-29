from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from usuarios.permissoes import pode_consultar_historico, pode_registrar_devolucao, pode_registrar_retirada
from reservas.models import Reserva
from reservas.services import expirar_reservas_vencidas
from reservas.consultas import historico_reservas

from .forms import DevolucaoForm, HistoricoFiltroForm, RetiradaReservaForm
from .models import Movimentacao
from .services import (
    grupos_devolucao,
    grupos_legados_encerrados,
    registrar_devolucoes,
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
    expirar_reservas_vencidas()
    valido = form.is_valid()
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    if valido and form.cleaned_data.get("retirada"):
        registros = consultar_historico(form.cleaned_data, usuario=request.user)
        return render(request, "movimentacoes/historico_lista.html", {
            "form": form, "pagina": Paginator(registros, 25).get_page(request.GET.get("pagina")),
            "parametros_paginacao": parametros.urlencode(),
        })
    reservas = historico_reservas(request.user, form.cleaned_data) if valido else Reserva.objects.none()
    pagina = Paginator(reservas, 15).get_page(request.GET.get("pagina"))
    legados = grupos_legados_encerrados(request.user) if valido else []
    if valido:
        filtros = form.cleaned_data
        if filtros.get("reserva"):
            legados = []
        elif any(filtros.get(campo) for campo in ("busca", "tipo", "inicio", "fim")):
            correspondencias = consultar_historico(filtros, usuario=request.user).values("pk")
            # A busca localiza o lote sem reduzir sua contagem de unidades.
            from .services import _chave_grupo
            chaves = Movimentacao.objects.filter(pk__in=correspondencias).annotate(chave_grupo=_chave_grupo()).values("chave_grupo")
            legados = legados.filter(chave_grupo__in=chaves)
    parametros_legados = request.GET.copy()
    parametros_legados.pop("pagina_legados", None)
    return render(request, "movimentacoes/historico_reservas.html", {
        "form": form, "pagina": pagina, "parametros_paginacao": parametros.urlencode(),
        "pagina_legados": Paginator(legados, 10).get_page(request.GET.get("pagina_legados")),
        "parametros_legados": parametros_legados.urlencode(),
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


@login_required
@require_http_methods(["GET", "POST"])
def retirada_sem_reserva(request):
    raise PermissionDenied("Toda retirada exige uma reserva.")


@login_required
@require_GET
def retirada_disponibilidade(request):
    raise PermissionDenied("Toda retirada exige uma reserva.")


@login_required
@require_GET
def devolucao_lista(request):
    if not pode_consultar_historico(request.user):
        raise PermissionDenied
    busca = request.GET.get("busca", "").strip()
    pagina = Paginator(grupos_devolucao(busca, usuario=request.user), 15).get_page(request.GET.get("pagina"))
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
                    problemas=form.cleaned_data["problemas"],
                )
            except ValidationError as erro:
                form.add_error(None, erro.messages)
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
                if form.cleaned_data["problemas"]:
                    messages.info(request, f"{len(form.cleaned_data['problemas'])} manutenção(ões) aberta(s), aguardando acompanhamento do Administrador.")
                return redirect("movimentacoes:devolucao_lista")
        registrar_evento(
            usuario=request.user, acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="movimentacoes.Movimentacao", entidade_id=retirada.pk,
        )
    unidades = list(grupo.order_by("equipamento__numero_patrimonio", "pk"))
    abertas = [item for item in unidades if not item.devolvida]
    for item in abertas:
        item.campo_problema = form[f"problema_{item.pk}"]
        item.campo_descricao_problema = form[f"descricao_problema_{item.pk}"]
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
