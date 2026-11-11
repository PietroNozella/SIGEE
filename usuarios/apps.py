from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "usuarios"
    verbose_name = "Usuários"

    def ready(self):
        from . import signals  # noqa: F401
