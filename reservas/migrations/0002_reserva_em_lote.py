import django.db.models.deletion
from django.db import migrations, models


def agrupar_reservas_existentes(apps, schema_editor):
    Reserva = apps.get_model("reservas", "Reserva")
    ReservaEquipamento = apps.get_model("reservas", "ReservaEquipamento")

    for reserva in Reserva.objects.select_related("equipamento__tipo").iterator():
        reserva.tipo_equipamento_id = reserva.equipamento.tipo_id
        reserva.quantidade = 1
        reserva.save(update_fields=("tipo_equipamento", "quantidade"))
        ReservaEquipamento.objects.create(
            reserva_id=reserva.pk,
            equipamento_id=reserva.equipamento_id,
        )


def restaurar_equipamento_da_reserva(apps, schema_editor):
    Reserva = apps.get_model("reservas", "Reserva")

    for reserva in Reserva.objects.prefetch_related("itens").iterator():
        item = reserva.itens.first()
        if item is not None:
            reserva.equipamento_id = item.equipamento_id
            reserva.save(update_fields=("equipamento",))


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0005_tipo_equipamento"),
        ("reservas", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reserva",
            name="equipamento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="inventario.equipamento",
            ),
        ),
        migrations.CreateModel(
            name="ReservaEquipamento",
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
                (
                    "equipamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="itens_reserva",
                        to="inventario.equipamento",
                    ),
                ),
                (
                    "reserva",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itens",
                        to="reservas.reserva",
                    ),
                ),
            ],
            options={
                "verbose_name": "equipamento reservado",
                "verbose_name_plural": "equipamentos reservados",
                "ordering": ["equipamento__numero_patrimonio"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("reserva", "equipamento"),
                        name="reserva_equipamento_unico",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="reserva",
            name="quantidade",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="reserva",
            name="tipo_equipamento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="inventario.tipoequipamento",
            ),
        ),
        migrations.RunPython(
            agrupar_reservas_existentes,
            restaurar_equipamento_da_reserva,
        ),
        migrations.RemoveIndex(
            model_name="reserva",
            name="reserva_equip_periodo_idx",
        ),
        migrations.RemoveField(
            model_name="reserva",
            name="equipamento",
        ),
        migrations.AlterField(
            model_name="reserva",
            name="tipo_equipamento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="inventario.tipoequipamento",
            ),
        ),
        migrations.AddConstraint(
            model_name="reserva",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantidade__gte", 1)),
                name="reserva_quantidade_positiva",
            ),
        ),
        migrations.AddIndex(
            model_name="reserva",
            index=models.Index(
                fields=["tipo_equipamento", "inicio", "fim"],
                name="reserva_tipo_periodo_idx",
            ),
        ),
    ]
