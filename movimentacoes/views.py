from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from usuarios.permissoes import pode_registrar_retirada

from .forms import ConsultaRetiradaForm, RetiradaSemReservaForm
from .services import equipamentos_disponiveis_para_retirada, registrar_retirada_sem_reserva


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
                return redirect("movimentacoes:retirada_sem_reserva")

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
