from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower


NOME_INDICE = "usuarios_user_email_ci_unique"


def criar_indice_email_unico(apps, schema_editor):
    User = apps.get_model("auth", "User")
    alias = schema_editor.connection.alias
    possui_duplicidade = (
        User.objects.using(alias)
        .exclude(email="")
        .annotate(email_normalizado=Lower("email"))
        .values("email_normalizado")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
        .exists()
    )

    if possui_duplicidade:
        raise RuntimeError(
            "Existem e-mails duplicados entre os usuários. "
            "Corrija as contas antes de aplicar esta migration."
        )

    tabela = schema_editor.quote_name(User._meta.db_table)
    indice = schema_editor.quote_name(NOME_INDICE)
    schema_editor.execute(
        f"CREATE UNIQUE INDEX {indice} "
        f"ON {tabela} (LOWER(email)) WHERE email <> ''"
    )


def remover_indice_email_unico(apps, schema_editor):
    indice = schema_editor.quote_name(NOME_INDICE)
    schema_editor.execute(f"DROP INDEX IF EXISTS {indice}")


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            criar_indice_email_unico,
            remover_indice_email_unico,
        ),
    ]
