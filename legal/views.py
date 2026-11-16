from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .conteudo import secoes_para_exibicao
from .forms import AceiteDocumentosLegaisForm
from .services import (
    PRIVACIDADE,
    TERMOS,
    alteracoes_desde_ultimo_aceite,
    documentos_vigentes,
    par_de_versoes,
    registrar_aceite_vigente,
    usuario_possui_aceite_vigente,
)


def _documento_publico(request, tipo, rota):
    documento = documentos_vigentes()[tipo]
    vigente = documento.versao_vigente
    numero_solicitado = request.GET.get("versao")
    desatualizado = numero_solicitado is not None and numero_solicitado != vigente.numero
    return render(request, "legal/documento_publico.html", {
        "titulo": documento.get_tipo_display(),
        "tipo": tipo,
        "versao": vigente,
        "secoes": secoes_para_exibicao(vigente.conteudo),
        "contato_privacidade": vigente.contato,
        "url_vigente": reverse(rota),
        "desatualizado": desatualizado,
    }, status=409 if desatualizado else 200)


@require_safe
@never_cache
def termos_de_uso(request):
    return _documento_publico(request, TERMOS, "legal:termos_de_uso")


@require_safe
@never_cache
def politica_privacidade(request):
    return _documento_publico(request, PRIVACIDADE, "legal:politica_privacidade")


def _destino_seguro(request):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return reverse(settings.LOGIN_REDIRECT_URL)


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def aceite_documentos(request):
    destino = _destino_seguro(request)
    if usuario_possui_aceite_vigente(request.user):
        return redirect(destino)

    form = None
    par_recusado = False
    if request.method == "POST":
        form = AceiteDocumentosLegaisForm(request.POST)
        if form.is_valid():
            versoes_enviadas = (form.cleaned_data["versao_termos"], form.cleaned_data["versao_privacidade"])
            aceite, _ = registrar_aceite_vigente(request.user, versoes_enviadas=versoes_enviadas)
            if aceite:
                messages.success(request, "Termos e Política registrados com sucesso.")
                return redirect(destino)
            par_recusado = True

    documentos = documentos_vigentes()
    versao_termos, versao_privacidade = par_de_versoes(documentos)
    par_postado = request.POST.get("versao_termos"), request.POST.get("versao_privacidade")
    desatualizado = par_recusado or (all(par_postado) and par_postado != (versao_termos, versao_privacidade))
    if form is None or desatualizado:
        form = AceiteDocumentosLegaisForm(initial={
            "versao_termos": versao_termos, "versao_privacidade": versao_privacidade,
        })
    return render(request, "legal/aceite_documentos.html", {
        "form": form,
        "next": destino,
        "versao_termos": versao_termos,
        "versao_privacidade": versao_privacidade,
        "contato_privacidade": documentos[PRIVACIDADE].versao_vigente.contato,
        "desatualizado": desatualizado,
        "alteracoes": alteracoes_desde_ultimo_aceite(request.user, documentos),
    })
