from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .services import usuario_possui_aceite_vigente


ROTAS_ISENTAS = {
    "login",
    "logout",
    "legal:aceite_documentos",
    "legal:termos_de_uso",
    "legal:politica_privacidade",
}


class ExigirAceiteDocumentosLegaisMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            getattr(usuario, "is_authenticated", False)
            and not self._rota_isenta(request.path_info)
            and not usuario_possui_aceite_vigente(usuario)
        ):
            parametros = ""
            if request.method in {"GET", "HEAD"}:
                parametros = f"?{urlencode({'next': request.get_full_path()})}"
            return redirect(f"{reverse('legal:aceite_documentos')}{parametros}")

        return self.get_response(request)

    @staticmethod
    def _rota_isenta(caminho):
        if caminho.startswith(settings.STATIC_URL) or caminho.startswith("/admin/"):
            return True

        try:
            correspondencia = resolve(caminho)
        except Resolver404:
            return False
        return correspondencia.view_name in ROTAS_ISENTAS
