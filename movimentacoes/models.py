from django.conf import settings
from django.db import models


class Movimentacao(models.Model):
    class Tipo(models.TextChoices):
        RETIRADA = "RETIRADA", "Retirada"
        DEVOLUCAO = "DEVOLUCAO", "Devolução"

    equipamento = models.ForeignKey(
        "inventario.Equipamento",
        on_delete=models.PROTECT,
        related_name="movimentacoes",
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimentacoes_operadas",
    )
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimentacoes_recebidas",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    data_hora = models.DateTimeField(auto_now_add=True)
    reserva = models.ForeignKey(
        "reservas.Reserva",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimentacoes",
    )
    retirada_origem = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devolucoes",
    )
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "movimentação"
        verbose_name_plural = "movimentações"

    def __str__(self):
        return f"{self.tipo} - {self.equipamento}"
