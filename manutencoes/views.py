from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from usuarios.permissoes import pode_gerenciar_manutencao

from .forms import AberturaManutencaoForm, ConclusaoManutencaoForm
from .models import Manutencao
from .services import abrir_manutencao, concluir_manutencao, iniciar_manutencao


def _exigir_permissao(usuario, acao="view"):
    if not pode_gerenciar_manutencao(usuario, acao):
        raise PermissionDenied


def _registrar_falha(usuario, acao, manutencao_id=""):
    registrar_evento(
        usuario=usuario, acao=acao, resultado=RegistroAuditoria.Resultado.FALHA,
        entidade="manutencoes.Manutencao", entidade_id=manutencao_id,
    )


@login_required
@require_GET
def manutencao_lista(request):
    _exigir_permissao(request.user)
    busca = request.GET.get("busca", "").strip()
    estado = request.GET.get("estado", "")
    registros = Manutencao.objects.select_related("equipamento__tipo", "aberto_por")
    if busca:
        registros = registros.filter(
            Q(equipamento__numero_patrimonio__icontains=busca)
            | Q(equipamento__tipo__nome__icontains=busca)
        )
    if estado in Manutencao.Estado.values:
        registros = registros.filter(estado=estado)
    else:
        estado = ""
    pagina = Paginator(registros, 15).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "manutencoes/manutencao_lista.html", {
        "pagina": pagina, "busca": busca, "estado": estado, "estados": Manutencao.Estado.choices,
        "parametros_paginacao": parametros.urlencode(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def manutencao_abrir(request):
    _exigir_permissao(request.user, "add")
    form = AberturaManutencaoForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            try:
                manutencao = abrir_manutencao(
                    administrador=request.user, equipamento_id=form.cleaned_data["equipamento"].pk,
                    descricao_problema=form.cleaned_data["descricao_problema"],
                )
            except ValidationError as erro:
                form.add_error(None, erro.messages)
            except IntegrityError:
                form.add_error(None, "Não foi possível abrir a manutenção. Nenhuma alteração foi salva. Atualize a lista e tente novamente.")
            else:
                messages.success(request, "Manutenção aberta. O equipamento está indisponível para uso e reserva.")
                return redirect("manutencoes:manutencao_detalhe", manutencao_id=manutencao.pk)
        _registrar_falha(request.user, AcaoAuditoria.MANUTENCAO_ABERTA)
    return render(request, "manutencoes/manutencao_form.html", {"form": form})


@login_required
@require_GET
def manutencao_detalhe(request, manutencao_id):
    _exigir_permissao(request.user)
    manutencao = get_object_or_404(Manutencao.objects.select_related(
        "equipamento__tipo", "equipamento__local", "aberto_por", "iniciado_por", "concluido_por", "devolucao_origem",
    ), pk=manutencao_id)
    return render(request, "manutencoes/manutencao_detalhe.html", {"manutencao": manutencao})


@login_required
@require_POST
def manutencao_iniciar(request, manutencao_id):
    _exigir_permissao(request.user, "change")
    get_object_or_404(Manutencao, pk=manutencao_id)
    try:
        iniciar_manutencao(administrador=request.user, manutencao_id=manutencao_id)
    except (ValidationError, IntegrityError) as erro:
        mensagem = " ".join(erro.messages) if isinstance(erro, ValidationError) else "Não foi possível iniciar a manutenção. Nenhuma alteração foi salva."
        messages.error(request, mensagem)
        _registrar_falha(request.user, AcaoAuditoria.MANUTENCAO_INICIADA, manutencao_id)
    else:
        messages.success(request, "Manutenção em andamento. O equipamento continua indisponível.")
    return redirect("manutencoes:manutencao_detalhe", manutencao_id=manutencao_id)


@login_required
@require_http_methods(["GET", "POST"])
def manutencao_concluir(request, manutencao_id):
    _exigir_permissao(request.user, "change")
    manutencao = get_object_or_404(Manutencao.objects.select_related("equipamento__tipo"), pk=manutencao_id)
    form = ConclusaoManutencaoForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            try:
                concluida = concluir_manutencao(
                    administrador=request.user, manutencao_id=manutencao_id,
                    resultado=form.cleaned_data["resultado"], descricao_solucao=form.cleaned_data["descricao_solucao"],
                )
            except ValidationError as erro:
                form.add_error(None, erro.messages)
            except IntegrityError:
                form.add_error(None, "Não foi possível concluir a manutenção. Nenhuma alteração foi salva. Atualize a página e tente novamente.")
            else:
                if concluida.resultado == Manutencao.Resultado.SEM_REPARO:
                    mensagem = "Manutenção concluída sem reparo. O equipamento foi inativado e o histórico preservado."
                else:
                    mensagem = "Manutenção concluída com reparo. O equipamento está disponível." if concluida.equipamento.ativo else "Manutenção concluída com reparo. A inativação anterior do equipamento foi preservada."
                messages.success(request, mensagem)
                return redirect("manutencoes:manutencao_detalhe", manutencao_id=manutencao_id)
        _registrar_falha(request.user, AcaoAuditoria.MANUTENCAO_CONCLUIDA, manutencao_id)
    return render(request, "manutencoes/manutencao_form.html", {"form": form, "manutencao": manutencao})
