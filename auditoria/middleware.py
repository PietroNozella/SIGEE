from .eventos import AcaoAuditoria
from .models import RegistroAuditoria
from .services import registrar_evento


class AuditoriaAcessoNegadoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        usuario = getattr(request, "user", None)

        if response.status_code == 403 and getattr(
            usuario, "is_authenticated", False
        ):
            registrar_evento(
                usuario=usuario,
                acao=AcaoAuditoria.ACESSO_NEGADO,
                resultado=RegistroAuditoria.Resultado.ACESSO_NEGADO,
            )

        return response
