from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from usuarios.permissoes import pode_configurar_calendario
from reservas.brasilapi import feriados_para_calendario

from .forms import FaixaHorarioFormSet, IntervaloReservasForm, RegraCalendarioForm, RemoverExcecaoForm
from .models import AlteracaoCalendario, CalendarioEscolar, RegraCalendario
from .services import descrever_regra, intervalo_vigente, regras_vigentes, reservas_afetadas, salvar_intervalo, salvar_regra


def _exigir_administrador(usuario):
    if not pode_configurar_calendario(usuario):
        raise PermissionDenied


def _versao():
    return CalendarioEscolar.objects.filter(pk=1).values_list("versao", flat=True).first() or 1


@login_required
@require_GET
def feriados(request):
    _exigir_administrador(request.user)
    try:
        resultado = feriados_para_calendario(request.GET.get("ano", ""))
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse(resultado)


@login_required
@require_GET
def calendario_escola(request):
    _exigir_administrador(request.user)
    regras = regras_vigentes()
    dias = []
    for dia, nome in RegraCalendario.DIAS:
        faixas = []
        for finalidade, titulo in RegraCalendario.Finalidade.choices:
            regra = regras.get((finalidade, dia))
            resumo = descrever_regra(regra)["resumo"] if regra else ("Dia inteiro" if dia < 5 else "Fechado")
            faixas.append({"finalidade": finalidade, "titulo": titulo,
                           "resumo": resumo, "periodos": resumo.split("; "),
                           "padrao": regra is None})
        dias.append({"numero": dia, "nome": nome, "faixas": faixas})
    excecoes = []
    for regra in regras.values():
        if regra.data and regra.data >= timezone.localdate():
            descricao = descrever_regra(regra)
            excecoes.append(descricao | {"pk": regra.pk, "data_excecao": regra.data,
                "finalidade_nome": regra.get_finalidade_display(), "periodos": descricao["resumo"].split("; ")})
    excecoes.sort(key=lambda e: (e["data"], e["finalidade"]))
    afetadas = reservas_afetadas(regras=regras)
    return render(request, "calendario/calendario.html", {
        "dias": dias, "excecoes": excecoes, "versao": _versao(),
        "intervalo_minutos": int(intervalo_vigente().total_seconds() // 60),
        "afetadas": Paginator(afetadas, 10).get_page(request.GET.get("pagina")),
        "total_afetadas": len(afetadas),
        "alteracoes": AlteracaoCalendario.objects.select_related("usuario")[:15],
    })


@login_required
@require_http_methods(["GET", "POST"])
def intervalo_form(request):
    _exigir_administrador(request.user)
    calendario = CalendarioEscolar.objects.filter(pk=1).first() or CalendarioEscolar()
    form = IntervaloReservasForm(request.POST if request.method == "POST" else None,
        instance=calendario, initial={"versao": calendario.versao})
    if request.method == "POST" and form.is_valid():
        try:
            salvar_intervalo(usuario=request.user, minutos=form.cleaned_data["intervalo_minutos"],
                motivo=form.cleaned_data["motivo"], versao=form.cleaned_data["versao"])
        except ValidationError as erro:
            form.add_error(None, " ".join(erro.messages))
        else:
            messages.success(request, "Intervalo atualizado. O novo valor vale somente para novas reservas.")
            return redirect("calendario:calendario_escola")
    return render(request, "calendario/intervalo_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def regra_form(request, finalidade=None, dia=None, regra_id=None):
    _exigir_administrador(request.user)
    semanal = dia is not None
    if semanal:
        if finalidade not in RegraCalendario.Finalidade.values or dia not in range(7):
            raise Http404
        regra = RegraCalendario.objects.filter(finalidade=finalidade, dia_semana=dia, data__isnull=True).first()
        regra = regra or RegraCalendario(finalidade=finalidade, dia_semana=dia, dia_inteiro=dia < 5)
    else:
        regra = get_object_or_404(RegraCalendario, pk=regra_id, data__isnull=False) if regra_id else RegraCalendario()
    modo = "INTEIRO" if regra.dia_inteiro else "FAIXAS" if regra.pk and regra.faixas.exists() else "FECHADO"
    form = RegraCalendarioForm(request.POST if request.method == "POST" else None,
        instance=regra, semanal=semanal, initial={"funcionamento": modo, "versao": _versao()})
    formset = FaixaHorarioFormSet(request.POST if request.method == "POST" else None, instance=regra, prefix="faixas")
    if request.method == "POST":
        valido = form.is_valid()
        modo = form.cleaned_data.get("funcionamento")
        if modo == "FAIXAS":
            valido = formset.is_valid() and valido
        if valido:
            faixas = [f.instance for f in formset.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")] if modo == "FAIXAS" else []
            if modo == "FAIXAS" and not faixas:
                form.add_error(None, "Adicione pelo menos uma faixa ou escolha Fechado ou Dia inteiro.")
            else:
                try:
                    salvar_regra(usuario=request.user, regra=form.save(commit=False), faixas=faixas,
                        motivo=form.cleaned_data["motivo"], versao=form.cleaned_data["versao"])
                except (ValidationError, IntegrityError) as erro:
                    form.add_error(None, "Não foi possível salvar a configuração. Nenhuma alteração foi gravada." if isinstance(erro, IntegrityError) else " ".join(erro.messages))
                else:
                    messages.success(request, "Calendário atualizado. Confira as reservas que precisam de decisão.")
                    return redirect("calendario:calendario_escola")
    return render(request, "calendario/regra_form.html", {"form": form, "formset": formset, "regra": regra, "semanal": semanal})


@login_required
@require_http_methods(["GET", "POST"])
def remover_excecao(request, regra_id):
    _exigir_administrador(request.user)
    regra = get_object_or_404(RegraCalendario, pk=regra_id, data__isnull=False)
    form = RemoverExcecaoForm(request.POST if request.method == "POST" else None, initial={"versao": _versao()})
    if request.method == "POST" and form.is_valid():
        try:
            salvar_regra(usuario=request.user, regra=regra, faixas=[], motivo=form.cleaned_data["motivo"], versao=form.cleaned_data["versao"], remover=True)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, "Exceção removida. A data voltou a seguir a regra habitual.")
            return redirect("calendario:calendario_escola")
    return render(request, "calendario/remover_excecao.html", {"form": form, "regra": regra})
