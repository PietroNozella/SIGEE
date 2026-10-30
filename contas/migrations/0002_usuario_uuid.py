import uuid

from django.db import migrations, models

from contas.migration_operations import ConverterChaveUsuarioUUID


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0001_initial"),
        ("usuarios", "0003_permissao_consulta_reservas_administrador"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auditoria", "0001_initial"),
        ("inventario", "0005_tipo_equipamento"),
        ("legal", "0001_initial"),
        ("manutencoes", "0001_initial"),
        ("movimentacoes", "0004_movimentacao_lote_retirada"),
        ("pedagogico", "0002_utilizacaopedagogica"),
        ("reservas", "0006_reserva_reserva_contexto_completo_ou_legado"),
        ("sessions", "0001_initial"),
    ]

    operations = [
        ConverterChaveUsuarioUUID(
            model_name="user", name="id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
    ]
