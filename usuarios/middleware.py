from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import Resolver404, resolve
from django.utils.cache import add_never_cache_headers

from . import sessoes


ROTAS_PUBLICAS = {
    "login", "password_reset", "password_reset_done", "password_reset_confirm",
    "password_reset_complete", "legal:termos_de_uso", "legal:politica_privacidade",
    "admin:login",
}
ROTAS_PASSIVAS = {
    "usuarios:sessao_status", "calendario:feriados", "reservas:reserva_feriados",
    "reservas:reserva_disponibilidade", "movimentacoes:retirada_disponibilidade",
}


class LimiteSessaoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(settings.STATIC_URL):
            return self.get_response(request)
        try:
            rota = resolve(request.path_info).view_name
        except Resolver404:
            return self.get_response(request)

        agora = sessoes.agora_em_segundos()
        inicio = request.session.get(sessoes.INICIO_SESSAO)
        publica = rota in ROTAS_PUBLICAS or request.path_info == "/"
        consulta_json = (
            rota in ROTAS_PASSIVAS
            or "application/json" in request.headers.get("Accept", "")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        consulta_automatica = consulta_json or request.headers.get("Sec-Fetch-Mode", "navigate") != "navigate"

        if request.user.is_authenticated and not sessoes.segundos_restantes(request.session, agora):
            request.sessao_expirada = True
            logout(request)

        if not request.user.is_authenticated and not publica:
            if consulta_json:
                response = JsonResponse({
                    "codigo": "sessao_expirada",
                    "erro": "Sua sessão terminou. Entre novamente para continuar.",
                    "login_url": sessoes.url_sessao_expirada(request),
                }, status=401)
            elif getattr(request, "sessao_expirada", False) or request.COOKIES.get(settings.SESSION_COOKIE_NAME):
                response = HttpResponseRedirect(sessoes.url_sessao_expirada(request, retomar=True))
            else:
                return self.get_response(request)
            add_never_cache_headers(response)
            return response

        response = self.get_response(request)
        # Somente navegação e formulários aceitos contam como atividade.
        # Feriados, disponibilidade e verificação de sessão nunca renovam o prazo.
        if (
            request.user.is_authenticated
            and not publica and not consulta_automatica
            and request.method in {"GET", "POST"}
            and response.status_code < 400
            and request.session.get(sessoes.INICIO_SESSAO) == inicio
            and request.session.get(sessoes.ULTIMA_ATIVIDADE) != agora
        ):
            request.session[sessoes.ULTIMA_ATIVIDADE] = agora
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response
