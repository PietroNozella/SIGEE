from django.db import migrations


def permitir_manutencao_operador(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    grupo, _ = Group.objects.using(alias).get_or_create(name="Operador")
    tipo, _ = ContentType.objects.using(alias).get_or_create(app_label="manutencoes", model="manutencao")
    for acao in ("view", "add"):
        permissao, _ = Permission.objects.using(alias).get_or_create(
            content_type=tipo, codename=f"{acao}_manutencao", defaults={"name": f"Can {acao} manutenção"},
        )
        Group.permissions.through.objects.using(alias).get_or_create(group_id=grupo.pk, permission_id=permissao.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0003_permissao_consulta_reservas_administrador"),
        ("manutencoes", "0001_initial"),
    ]
    operations = [migrations.RunPython(permitir_manutencao_operador, migrations.RunPython.noop)]
