from django.db import migrations


def vincular_permissao_consulta_reservas(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    alias = schema_editor.connection.alias

    content_type, _ = ContentType.objects.using(alias).get_or_create(
        app_label="reservas", model="reserva",
    )
    permission, _ = Permission.objects.using(alias).get_or_create(
        content_type_id=content_type.pk, codename="view_reserva",
        defaults={"name": "Can view reserva"},
    )
    administrador, _ = Group.objects.using(alias).get_or_create(name="Administrador")
    Group.permissions.through.objects.using(alias).get_or_create(
        group_id=administrador.pk, permission_id=permission.pk,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0002_permissao_indicadores_administrador"),
        ("reservas", "0004_alter_reserva_status"),
    ]

    operations = [
        migrations.RunPython(vincular_permissao_consulta_reservas, migrations.RunPython.noop),
    ]
