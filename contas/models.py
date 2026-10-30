import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_administrador_principal = models.BooleanField(
        "administrador principal", default=False, db_default=False, editable=False,
    )

    class Meta(AbstractUser.Meta):
        db_table = "auth_user"
        swappable = "AUTH_USER_MODEL"
        constraints = [
            models.UniqueConstraint(
                Lower("email"), condition=~models.Q(email=""),
                name="usuarios_user_email_ci_unique",
            ),
            models.UniqueConstraint(
                fields=("is_administrador_principal",),
                condition=models.Q(is_administrador_principal=True),
                name="usuario_principal_unico",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_administrador_principal=False)
                    | models.Q(is_active=True, is_staff=False, is_superuser=False)
                ),
                name="usuario_principal_ativo_funcional",
            ),
        ]
