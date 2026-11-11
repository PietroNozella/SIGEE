from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from usuarios.permissoes import pode_configurar_calendario
from inventario.models import TipoEquipamento
from reservas.brasilapi import feriados_para_calendario
from reservas.models import Reserva

from .fechamentos import (
    configurar_excecao_fechamento, decidir_reserva_afetada, pendencias_de_fechamento,
    reabrir_fechamento, registrar_fechamento,
)
from .forms import (
    AlteracaoFechamentoForm, CotaProfessorForm, DecisaoFechamentoForm, FaixaHorarioFormSet, FechamentoEscolarForm,
    IntervaloReservasForm, PoliticaFechamentoForm, RegraCalendarioForm, RemoverExcecaoForm,
)
from .models import AlteracaoCalendario, CalendarioEscolar, FechamentoEscolar, RegraCalendario, ReservaAfetadaFechamento
from .services import descrever_regra, intervalo_vigente, regras_vigentes, reservas_afetadas, salvar_cota, salvar_intervalo, salvar_regra


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
    secao = request.GET.get("secao", "calendario")
    if secao not in ("calendario", "reservas", "historico"):
        secao = "calendario"
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
    reservas_que_exigem_decisao = Reserva.objects.com_etapa().filter(status=Reserva.Status.ATIVA).filter(
        Q(tem_retirada=False) | Q(tem_entrega_pendente=True),
    )
    pendencias = pendencias_de_fechamento().filter(
        fechamento_id=OuterRef("pk"), reserva_id__in=reservas_que_exigem_decisao.values("pk"),
    )
    fechamentos = FechamentoEscolar.objects.filter(reabertura__isnull=True).alias(
        tem_pendencias=Exists(pendencias),
    ).filter(Q(data__gte=timezone.localdate()) | Q(tem_pendencias=True)).select_related("abertura")
    return render(request, "calendario/calendario.html", {
        "dias": dias, "excecoes": excecoes, "versao": _versao(), "secao": secao,
        "intervalo_minutos": int(intervalo_vigente().total_seconds() // 60),
        "total_cotas": TipoEquipamento.objects.filter(ativo=True, cota_por_professor__isnull=False).count(),
        "afetadas": Paginator(afetadas, 10).get_page(request.GET.get("pagina")),
        "total_afetadas": len(afetadas),
        "alteracoes": AlteracaoCalendario.objects.select_related("usuario", "fechamento_registrado")[:15],
        "fechamentos": fechamentos,
    })


@login_required
@require_http_methods(["GET", "POST"])
def fechamento_form(request):
    _exigir_administrador(request.user)
    voltar = reverse("calendario:calendario_escola")
    form = FechamentoEscolarForm(
        request.POST if request.method == "POST" else None, initial={"versao": _versao(), "data": timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        try:
            fechamento = registrar_fechamento(usuario=request.user, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, "Fechamento registrado. Confira as reservas afetadas.")
            return redirect("calendario:fechamento_detalhe", fechamento_id=fechamento.pk)
    return render(request, "calendario/fechamento_form.html", {
        "form": form, "voltar": voltar, "titulo": "Registrar fechamento", "acao": "Registrar fechamento",
        "descricao": "A data ficará fechada para novos agendamentos e as entregas afetadas serão suspensas. Devoluções físicas continuam disponíveis.",
    })


@login_required
@require_GET
def fechamento_detalhe(request, fechamento_id):
    _exigir_administrador(request.user)
    fechamento = get_object_or_404(
        FechamentoEscolar.objects.select_related("abertura__usuario", "reabertura__usuario"), pk=fechamento_id,
    )
    reservas = Reserva.objects.com_etapa().select_related("professor", "tipo_equipamento")
    impactos = fechamento.reservas_afetadas.select_related("decidido_por").prefetch_related(
        Prefetch("reserva", queryset=reservas),
    ).order_by("reserva__inicio", "reserva_id")
    return render(request, "calendario/fechamento_detalhe.html", {
        "fechamento": fechamento, "impactos": Paginator(impactos, 15).get_page(request.GET.get("pagina")),
        "pode_reabrir": not fechamento.reabertura_id and fechamento.data >= timezone.localdate(),
        "agora": timezone.now(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def reabertura_form(request, fechamento_id):
    _exigir_administrador(request.user)
    fechamento = get_object_or_404(FechamentoEscolar, pk=fechamento_id)
    voltar = reverse("calendario:fechamento_detalhe", args=[fechamento.pk])
    form = AlteracaoFechamentoForm(
        request.POST if request.method == "POST" else None, initial={"versao": _versao()},
    )
    if request.method == "POST" and form.is_valid():
        try:
            reabrir_fechamento(usuario=request.user, fechamento_id=fechamento.pk, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, "Fechamento retirado. A data volta a seguir o calendário.")
            return redirect(voltar)
    return render(request, "calendario/fechamento_form.html", {
        "form": form, "voltar": voltar, "titulo": f"Reabrir {fechamento.data:%d/%m/%Y}", "acao": "Confirmar reabertura",
        "descricao": "A data volta a seguir o calendário. As decisões já registradas ficam no histórico.",
    })


@login_required
@require_http_methods(["GET", "POST"])
def politica_fechamento(request):
    _exigir_administrador(request.user)
    calendario = CalendarioEscolar.objects.filter(pk=1).first() or CalendarioEscolar()
    voltar = reverse("calendario:calendario_escola") + "?secao=reservas"
    form = PoliticaFechamentoForm(request.POST if request.method == "POST" else None, initial={
        "versao": calendario.versao, "permite_manter": calendario.permite_manter_em_fechamento,
    })
    if request.method == "POST" and form.is_valid():
        try:
            configurar_excecao_fechamento(usuario=request.user, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, "Política de fechamento atualizada.")
            return redirect(voltar)
    return render(request, "calendario/fechamento_form.html", {
        "form": form, "voltar": voltar, "titulo": "Política de fechamento", "acao": "Salvar política",
        "descricao": "A política vale para novas decisões. As autorizações já registradas continuam vinculadas à reserva.",
    })


@login_required
@require_http_methods(["GET", "POST"])
def decisao_fechamento(request, impacto_id):
    _exigir_administrador(request.user)
    impacto = get_object_or_404(
        ReservaAfetadaFechamento.objects.select_related("fechamento", "reserva__professor", "reserva__tipo_equipamento"),
        pk=impacto_id,
    )
    reserva = impacto.reserva
    tem_retirada = reserva.movimentacoes.filter(tipo="RETIRADA").exists()
    pode_decidir = (
        impacto.decisao == ReservaAfetadaFechamento.Decisao.PENDENTE
        and not impacto.fechamento.reabertura_id and reserva.status == Reserva.Status.ATIVA
    )
    limite = reserva.fim if tem_retirada else min(reserva.fim, reserva.inicio + Reserva.TOLERANCIA_RETIRADA)
    pode_manter = pode_decidir and timezone.now() < limite and CalendarioEscolar.objects.filter(
        pk=1, permite_manter_em_fechamento=True,
    ).exists()
    pode_cancelar = pode_decidir and not tem_retirada
    voltar = reverse("calendario:fechamento_detalhe", args=[impacto.fechamento_id])
    form = DecisaoFechamentoForm(
        request.POST if request.method == "POST" else None, pode_cancelar=pode_cancelar, pode_manter=pode_manter,
    )
    if request.method == "POST" and form.is_valid():
        try:
            decidir_reserva_afetada(usuario=request.user, impacto_id=impacto.pk, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, "Decisão registrada na reserva.")
            return redirect(voltar)
    return render(request, "calendario/fechamento_form.html", {
        "form": form, "voltar": voltar, "reserva": reserva,
        "titulo": f"Decidir sobre a reserva #{reserva.pk}", "acao": "Registrar decisão",
        "descricao": "A decisão e o motivo aparecem no histórico da reserva.",
        "acao_indisponivel": not (pode_cancelar or pode_manter),
    })


@login_required
@require_GET
def cotas(request):
    _exigir_administrador(request.user)
    busca = request.GET.get("busca", "").strip()[:200]
    tipos = TipoEquipamento.objects.select_related("categoria")
    if busca:
        from django.db.models import Q
        tipos = tipos.filter(Q(nome__icontains=busca) | Q(categoria__nome__icontains=busca))
    return render(request, "calendario/cotas.html", {"tipos": Paginator(tipos, 20).get_page(request.GET.get("pagina")), "busca": busca})


@login_required
@require_http_methods(["GET", "POST"])
def cota_form(request, tipo_id):
    _exigir_administrador(request.user)
    tipo = get_object_or_404(TipoEquipamento.objects.select_related("categoria"), pk=tipo_id)
    form = CotaProfessorForm(request.POST if request.method == "POST" else None, instance=tipo, initial={"versao": _versao()})
    if request.method == "POST" and form.is_valid():
        try:
            salvar_cota(usuario=request.user, tipo_id=tipo.pk, limite=form.cleaned_data["cota_por_professor"],
                motivo=form.cleaned_data["motivo"], versao=form.cleaned_data["versao"])
        except ValidationError as erro:
            form.add_error(None, " ".join(erro.messages))
        else:
            messages.success(request, "Cota atualizada. Reservas já confirmadas foram preservadas.")
            return redirect("calendario:cotas")
    return render(request, "calendario/cota_form.html", {"form": form, "tipo": tipo})


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
            return redirect(reverse("calendario:calendario_escola") + "?secao=reservas")
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
