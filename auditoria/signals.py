from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .eventos import AcaoAuditoria
from .models import RegistroAuditoria
from .services import registrar_evento


@receiver(user_logged_in, dispatch_uid="auditoria_login_realizado")
def registrar_login_realizado(sender, request, user, **kwargs):
    registrar_evento(
        usuario=user,
        acao=AcaoAuditoria.LOGIN_REALIZADO,
        resultado=RegistroAuditoria.Resultado.SUCESSO,
    )


@receiver(user_login_failed, dispatch_uid="auditoria_login_falhou")
def registrar_login_falhou(sender, credentials, request, **kwargs):
    registrar_evento(
        acao=AcaoAuditoria.LOGIN_FALHOU,
        resultado=RegistroAuditoria.Resultado.FALHA,
    )


@receiver(user_logged_out, dispatch_uid="auditoria_logout_realizado")
def registrar_logout_realizado(sender, request, user, **kwargs):
    registrar_evento(
        usuario=user,
        acao=AcaoAuditoria.LOGOUT_REALIZADO,
        resultado=RegistroAuditoria.Resultado.SUCESSO,
    )
