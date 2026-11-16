from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from usuarios.permissoes import pode_gerenciar_documentos_legais

from .conteudo import interpretar_conteudo, secoes_para_exibicao
from .forms import RascunhoDocumentoForm, RevisaoRascunhoForm
from .models import DocumentoLegal
from .services import copiar_versao_para_rascunho, publicar_rascunho, salvar_rascunho


def _autorizar_gestao(usuario):
    if not pode_gerenciar_documentos_legais(usuario):
        raise PermissionDenied


def _documento(usuario, tipo):
    _autorizar_gestao(usuario)
    return get_object_or_404(DocumentoLegal.objects.select_related("versao_vigente"), pk=tipo)


@login_required
@require_safe
def documentos_legais(request):
    _autorizar_gestao(request.user)
    documentos = DocumentoLegal.objects.select_related("versao_vigente").order_by("-tipo")
    return render(request, "legal/gestao_lista.html", {"documentos": documentos})


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def editar_documento(request, tipo):
    documento = _documento(request.user, tipo)
    form = RascunhoDocumentoForm(
        request.POST if request.method == "POST" else None,
        initial={
            "conteudo": documento.rascunho_conteudo,
            "contato": documento.rascunho_contato,
            "resumo": documento.rascunho_resumo,
            "revisao": documento.revisao_rascunho,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            salvar_rascunho(usuario=request.user, tipo=tipo, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, "Rascunho salvo.")
            return redirect("legal:previa_documento", tipo=tipo)
    historico = documento.versoes.select_related("publicado_por").defer("conteudo", "resumo", "contato")
    return render(request, "legal/gestao_editar.html", {
        "documento": documento, "form": form, "historico": historico,
    })


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def previa_documento(request, tipo):
    documento = _documento(request.user, tipo)
    if request.method == "POST":
        form = RevisaoRascunhoForm(request.POST)
        if form.is_valid():
            try:
                versao = publicar_rascunho(usuario=request.user, tipo=tipo, **form.cleaned_data)
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
            else:
                messages.success(request, f"Versão {versao.numero} publicada.")
                return redirect("legal:editar_documento", tipo=tipo)
        else:
            messages.error(request, "Abra a prévia atual antes de publicar.")
        return redirect("legal:previa_documento", tipo=tipo)

    return render(request, "legal/gestao_versao.html", {
        "documento": documento,
        "form": RevisaoRascunhoForm(initial={"revisao": documento.revisao_rascunho}),
        "contato_privacidade": documento.rascunho_contato,
        "secoes": secoes_para_exibicao(interpretar_conteudo(documento.rascunho_conteudo)),
        "resumo": documento.rascunho_resumo,
    })


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def historico_documento(request, tipo, numero):
    documento = _documento(request.user, tipo)
    versao = get_object_or_404(documento.versoes, numero=numero)
    if request.method == "POST":
        form = RevisaoRascunhoForm(request.POST)
        if form.is_valid():
            try:
                copiar_versao_para_rascunho(usuario=request.user, tipo=tipo, numero=numero, **form.cleaned_data)
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
            else:
                messages.success(request, f"Versão {numero} copiada para o rascunho.")
                return redirect("legal:editar_documento", tipo=tipo)
        else:
            messages.error(request, "Reabra a versão do histórico para copiar o conteúdo.")
        return redirect("legal:historico_documento", tipo=tipo, numero=numero)

    return render(request, "legal/gestao_versao.html", {
        "documento": documento,
        "versao": versao,
        "form": RevisaoRascunhoForm(initial={"revisao": documento.revisao_rascunho}),
        "contato_privacidade": versao.contato,
        "secoes": secoes_para_exibicao(versao.conteudo),
        "resumo": versao.resumo,
    })
