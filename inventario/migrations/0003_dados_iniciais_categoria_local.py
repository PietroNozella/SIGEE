from django.db import migrations


DESCRICAO_PROVISORIA = "Dado inicial provisório para demonstração da RN-01."


def criar_dados_iniciais(apps, schema_editor):
    Categoria = apps.get_model("inventario", "Categoria")
    Local = apps.get_model("inventario", "Local")

    for nome in ("Notebook", "Projetor"):
        Categoria.objects.get_or_create(
            nome=nome,
            defaults={"descricao": DESCRICAO_PROVISORIA},
        )

    for nome in ("Sala-01", "Laboratório de informática", "Sala multimídia"):
        Local.objects.get_or_create(
            nome=nome,
            defaults={"descricao": DESCRICAO_PROVISORIA},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0002_alter_equipamento_numero_patrimonio"),
    ]

    operations = [
        migrations.RunPython(criar_dados_iniciais, migrations.RunPython.noop),
    ]
