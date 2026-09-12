from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    class Resultado(models.TextChoices):
        SUCESSO = "SUCESSO", "Sucesso"
        FALHA = "FALHA", "Falha"
        ACESSO_NEGADO = "ACESSO_NEGADO", "Acesso negado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="registros_auditoria",
    )
    acao = models.CharField(max_length=100)
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    data_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    entidade = models.CharField(max_length=100, blank=True)
    entidade_id = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-data_hora", "-pk"]
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(acao=""),
                name="auditoria_acao_nao_vazia",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    resultado__in=["SUCESSO", "FALHA", "ACESSO_NEGADO"]
                ),
                name="auditoria_resultado_valido",
            ),
        ]

    def __str__(self):
        return f"{self.acao} - {self.get_resultado_display()}"

    @property
    def acao_exibicao(self):
        from .eventos import rotulo_acao

        return rotulo_acao(self.acao)
