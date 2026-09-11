from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento

from .forms import AceiteDocumentosLegaisForm
from .services import (
    contexto_documentos,
    registrar_aceite_vigente,
    usuario_possui_aceite_vigente,
)


def termos_de_uso(request):
    return render(request, "legal/termos_de_uso.html", contexto_documentos())


def politica_privacidade(request):
    return render(
        request,
        "legal/politica_privacidade.html",
        contexto_documentos(),
    )


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
def aceite_documentos(request):
    destino = _destino_seguro(request)
    if usuario_possui_aceite_vigente(request.user):
        return redirect(destino)

    form = AceiteDocumentosLegaisForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            aceite, criado = registrar_aceite_vigente(request.user)
            if criado:
                registrar_evento(
                    usuario=request.user,
                    acao=AcaoAuditoria.DOCUMENTOS_LEGAIS_ACEITOS,
                    resultado=RegistroAuditoria.Resultado.SUCESSO,
                    entidade="AceiteDocumentosLegais",
                    entidade_id=aceite.pk,
                )
        messages.success(request, "Termos e Política registrados com sucesso.")
        return redirect(destino)

    contexto = {**contexto_documentos(), "form": form, "next": destino}
    return render(request, "legal/aceite_documentos.html", contexto)
