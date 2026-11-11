from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .sessoes import iniciar_controle_sessao


@receiver(user_logged_in, dispatch_uid="usuarios_iniciar_controle_sessao")
def iniciar_sessao(sender, request, user, **kwargs):
    if request is not None:
        iniciar_controle_sessao(request.session)
