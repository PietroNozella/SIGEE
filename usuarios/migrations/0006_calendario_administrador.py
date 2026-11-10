from django.db import migrations


def conceder_permissao(apps, schema_editor):
    alias = schema_editor.connection.alias
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    tipo, _ = ContentType.objects.using(alias).get_or_create(app_label="calendario", model="calendarioescolar")
    permissao, _ = Permission.objects.using(alias).get_or_create(content_type_id=tipo.pk,
        codename="configurar_calendario", defaults={"name": "Pode configurar o calendário da escola"})
    grupo, _ = Group.objects.using(alias).get_or_create(name="Administrador")
    Group.permissions.through.objects.using(alias).get_or_create(group_id=grupo.pk, permission_id=permissao.pk)


def revogar_permissao(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupos = Group.objects.using(alias).filter(name="Administrador").values("pk")
    permissoes = Permission.objects.using(alias).filter(content_type__app_label="calendario", codename="configurar_calendario").values("pk")
    Group.permissions.through.objects.using(alias).filter(group_id__in=grupos, permission_id__in=permissoes).delete()


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0005_cancelamento_operacional"), ("calendario", "0001_initial")]
    operations = [migrations.RunPython(conceder_permissao, revogar_permissao)]
