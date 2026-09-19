import django.db.models.deletion
from django.db import migrations, models


def preencher_local_das_reservas(apps, schema_editor):
    Reserva = apps.get_model("reservas", "Reserva")
    ReservaEquipamento = apps.get_model("reservas", "ReservaEquipamento")

    for reserva in Reserva.objects.all().iterator():
        locais = list(
            ReservaEquipamento.objects.filter(reserva_id=reserva.pk)
            .values_list("equipamento__local_id", flat=True)
            .distinct()
        )
        if len(locais) != 1:
            raise RuntimeError(
                f"A reserva {reserva.pk} não possui exatamente um local de retirada."
            )
        reserva.local_id = locais[0]
        reserva.save(update_fields=("local",))


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0002_reserva_em_lote"),
    ]

    operations = [
        migrations.AddField(
            model_name="reserva",
            name="local",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="inventario.local",
            ),
        ),
        migrations.RunPython(
            preencher_local_das_reservas,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="reserva",
            name="local",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="inventario.local",
            ),
        ),
        migrations.RemoveIndex(
            model_name="reserva",
            name="reserva_tipo_periodo_idx",
        ),
        migrations.AddIndex(
            model_name="reserva",
            index=models.Index(
                fields=["tipo_equipamento", "local", "inicio", "fim"],
                name="res_tipo_loc_periodo_idx",
            ),
        ),
    ]
