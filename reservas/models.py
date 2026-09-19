from datetime import timedelta

from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from usuarios.permissoes import e_professor_funcional


def periodo_inclui_fim_de_semana(inicio, fim):
    inicio_local = timezone.localtime(inicio)
    fim_local = timezone.localtime(fim)
    quantidade_dias = (fim_local.date() - inicio_local.date()).days

    # Todo intervalo de sete dias consecutivos necessariamente alcança
    # sábado ou domingo. Para intervalos menores, no máximo seis datas
    # precisam ser verificadas.
    if quantidade_dias >= 6:
        return True

    return any(
        (inicio_local.date() + timedelta(days=deslocamento)).weekday() >= 5
        for deslocamento in range(quantidade_dias + 1)
    )


class Reserva(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        CANCELADA = "CANCELADA", "Cancelada"

    tipo_equipamento = models.ForeignKey(
        "inventario.TipoEquipamento",
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    local = models.ForeignKey(
        "inventario.Local",
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    inicio = models.DateTimeField("início")
    fim = models.DateTimeField()
    quantidade = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ATIVA,
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-inicio", "-pk"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        constraints = [
            models.CheckConstraint(
                condition=Q(fim__gt=F("inicio")),
                name="reserva_fim_posterior_inicio",
            ),
            models.CheckConstraint(
                condition=Q(quantidade__gte=1),
                name="reserva_quantidade_positiva",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tipo_equipamento", "local", "inicio", "fim"],
                name="res_tipo_loc_periodo_idx",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}

        if self.professor_id and not e_professor_funcional(self.professor):
            erros["professor"] = (
                "Somente um usuário com perfil Professor pode criar uma reserva."
            )

        if self.tipo_equipamento_id and not self.tipo_equipamento.ativo:
            erros["tipo_equipamento"] = (
                "Somente um tipo de equipamento ativo pode ser reservado."
            )

        if self.local_id and not self.local.ativo:
            erros["local"] = "Somente um local ativo pode ser selecionado para a reserva."

        if self.quantidade is not None and self.quantidade < 1:
            erros["quantidade"] = "Informe uma quantidade maior que zero."

        periodo_valido = self.inicio is not None and self.fim is not None
        if periodo_valido and (
            timezone.is_naive(self.inicio) or timezone.is_naive(self.fim)
        ):
            erros[NON_FIELD_ERRORS] = (
                "As datas e horas da reserva devem incluir o fuso horário."
            )
            periodo_valido = False

        if periodo_valido and self.fim <= self.inicio:
            erros["fim"] = (
                "A hora final deve ser posterior ao inicio da reserva"
            )
            periodo_valido = False

        if periodo_valido and self._state.adding and self.inicio < timezone.now():
            erros["inicio"] = (
                "A data e a hora inicial da reserva não podem estar no passado."
            )

        if periodo_valido and periodo_inclui_fim_de_semana(self.inicio, self.fim):
            erros[NON_FIELD_ERRORS] = (
                "Não é permitido reservar equipamentos para períodos que incluam "
                "sábado ou domingo."
            )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return (
            f"{self.quantidade}x {self.tipo_equipamento.nome} — {self.local.nome} — "
            f"{timezone.localtime(self.inicio):%d/%m/%Y %H:%M}"
        )


class ReservaEquipamento(models.Model):
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    equipamento = models.ForeignKey(
        "inventario.Equipamento",
        on_delete=models.PROTECT,
        related_name="itens_reserva",
    )

    class Meta:
        ordering = ["equipamento__numero_patrimonio"]
        verbose_name = "equipamento reservado"
        verbose_name_plural = "equipamentos reservados"
        constraints = [
            models.UniqueConstraint(
                fields=("reserva", "equipamento"),
                name="reserva_equipamento_unico",
            ),
        ]

    def __str__(self):
        return f"{self.reserva} — {self.equipamento.numero_patrimonio}"
