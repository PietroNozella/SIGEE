from datetime import UTC, datetime
from math import ceil, isfinite
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone


INICIO_SESSAO = "_sigee_inicio_sessao"
ULTIMA_ATIVIDADE = "_sigee_ultima_atividade"


def agora_em_segundos():
    return timezone.now().timestamp()


def iniciar_controle_sessao(session):
    agora = agora_em_segundos()
    session[INICIO_SESSAO] = agora
    session[ULTIMA_ATIVIDADE] = agora
    # Uma data fixa impede que gravações posteriores estendam o limite absoluto.
    if settings.SESSION_EXPIRE_AT_BROWSER_CLOSE:
        session.set_expiry(0)
    else:
        session.set_expiry(datetime.fromtimestamp(
            agora + settings.SESSION_ABSOLUTE_TIMEOUT, tz=UTC,
        ))


def segundos_restantes(session, agora=None):
    inicio = session.get(INICIO_SESSAO)
    atividade = session.get(ULTIMA_ATIVIDADE)
    # Sessões anteriores à política exigem novo login: não há início confiável.
    if not all(type(valor) in (int, float) and isfinite(valor) for valor in (inicio, atividade)):
        return 0
    agora = agora_em_segundos() if agora is None else agora
    if not inicio <= atividade <= agora:
        return 0
    return max(0, ceil(min(
        inicio + settings.SESSION_ABSOLUTE_TIMEOUT,
        atividade + settings.SESSION_IDLE_TIMEOUT,
    ) - agora))


def url_sessao_expirada(request, *, retomar=False):
    parametros = {"sessao": "expirada"}
    # Nunca retomar automaticamente uma operação POST após autenticar novamente.
    if retomar and request.method == "GET":
        parametros["next"] = request.get_full_path()
    return f"{reverse('login')}?{urlencode(parametros)}"
