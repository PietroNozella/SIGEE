"""Configuração explícita para testes locais isolados do banco publicado."""

from .settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
