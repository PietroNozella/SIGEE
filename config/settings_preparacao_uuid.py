"""Uso único: registrar contas.0001 em bancos que ainda usam auth.User.

Execute somente `migrate contas 0001 --settings=config.settings_preparacao_uuid`.
A conversão é executada depois com as configurações normais, em manutenção.
"""

from .settings import *

AUTH_USER_MODEL = "auth.User"
