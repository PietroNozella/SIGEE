from django.db import migrations


def vincular_permissao_indicadores(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    alias = schema_editor.connection.alias

    # Em uma instalação nova, post_migrate ainda não criou essas permissões.
    content_type, _ = ContentType.objects.using(alias).get_or_create(
        app_label="pedagogico", model="utilizacaopedagogica",
    )
    permission, _ = Permission.objects.using(alias).get_or_create(
        content_type_id=content_type.pk,
        codename="view_utilizacaopedagogica",
        defaults={"name": "Can view utilização pedagógica"},
    )
    administrador, _ = Group.objects.using(alias).get_or_create(name="Administrador")
    Group.permissions.through.objects.using(alias).get_or_create(
        group_id=administrador.pk, permission_id=permission.pk,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_email_usuario_unico"),
        ("pedagogico", "0002_utilizacaopedagogica"),
    ]

    # Reverter não revoga uma permissão também prevista na matriz de perfis.
    operations = [
        migrations.RunPython(vincular_permissao_indicadores, migrations.RunPython.noop),
    ]
