from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0003_dados_iniciais_categoria_local"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="equipamento",
            options={
                "ordering": ["numero_patrimonio"],
                "permissions": [
                    (
                        "view_resumo_inventario",
                        "Pode visualizar o resumo do inventário",
                    ),
                ],
                "verbose_name": "equipamento",
                "verbose_name_plural": "equipamentos",
            },
        ),
    ]
