from django.db import migrations


def permitir_cancelamento_operacional(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    tipo, _ = ContentType.objects.using(alias).get_or_create(app_label="reservas", model="reserva")
    permissao, _ = Permission.objects.using(alias).get_or_create(
        content_type_id=tipo.pk, codename="cancelar_reserva_operacional",
        defaults={"name": "Pode registrar cancelamento operacional de reserva"},
    )
    grupo, _ = Group.objects.using(alias).get_or_create(name="Operador")
    Group.permissions.through.objects.using(alias).get_or_create(group_id=grupo.pk, permission_id=permissao.pk)


def revogar_cancelamento_operacional(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupos = Group.objects.using(alias).filter(name="Operador").values("pk")
    permissoes = Permission.objects.using(alias).filter(
        content_type__app_label="reservas", content_type__model="reserva", codename="cancelar_reserva_operacional",
    ).values("pk")
    Group.permissions.through.objects.using(alias).filter(group_id__in=grupos, permission_id__in=permissoes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0004_manutencao_operador"),
        ("reservas", "0008_cancelamento_operacional"),
    ]
    operations = [migrations.RunPython(permitir_cancelamento_operacional, revogar_cancelamento_operacional)]
