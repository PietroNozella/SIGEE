import django.db.models.deletion
from django.db import migrations, models


def criar_tipos_e_vincular_equipamentos(apps, schema_editor):
    Equipamento = apps.get_model("inventario", "Equipamento")
    TipoEquipamento = apps.get_model("inventario", "TipoEquipamento")

    for equipamento in Equipamento.objects.all().iterator():
        tipo, _ = TipoEquipamento.objects.get_or_create(
            categoria_id=equipamento.categoria_id,
            nome=equipamento.nome,
        )
        equipamento.tipo_id = tipo.pk
        equipamento.save(update_fields=("tipo",))


def restaurar_nome_e_categoria(apps, schema_editor):
    Equipamento = apps.get_model("inventario", "Equipamento")

    for equipamento in Equipamento.objects.select_related("tipo").iterator():
        equipamento.nome = equipamento.tipo.nome
        equipamento.categoria_id = equipamento.tipo.categoria_id
        equipamento.save(update_fields=("nome", "categoria"))


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0004_alter_equipamento_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipamento",
            name="categoria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="inventario.categoria",
            ),
        ),
        migrations.AlterField(
            model_name="equipamento",
            name="nome",
            field=models.CharField(max_length=150, null=True),
        ),
        migrations.CreateModel(
            name="TipoEquipamento",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome", models.CharField(max_length=150, verbose_name="tipo/modelo")),
                ("ativo", models.BooleanField(default=True)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                (
                    "categoria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tipos_equipamento",
                        to="inventario.categoria",
                    ),
                ),
            ],
            options={
                "verbose_name": "tipo de equipamento",
                "verbose_name_plural": "tipos de equipamento",
                "ordering": ["categoria__nome", "nome"],
            },
        ),
        migrations.AddConstraint(
            model_name="tipoequipamento",
            constraint=models.UniqueConstraint(
                fields=("categoria", "nome"),
                name="tipo_equip_categoria_nome_unicos",
            ),
        ),
        migrations.AddField(
            model_name="equipamento",
            name="tipo",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="equipamentos",
                to="inventario.tipoequipamento",
            ),
        ),
        migrations.RunPython(
            criar_tipos_e_vincular_equipamentos,
            restaurar_nome_e_categoria,
        ),
        migrations.RemoveField(
            model_name="equipamento",
            name="categoria",
        ),
        migrations.RemoveField(
            model_name="equipamento",
            name="nome",
        ),
        migrations.AlterField(
            model_name="equipamento",
            name="tipo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="equipamentos",
                to="inventario.tipoequipamento",
            ),
        ),
    ]
