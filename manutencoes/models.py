from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Manutencao(models.Model):
    class Estado(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDA = "CONCLUIDA", "Concluída"

    class Resultado(models.TextChoices):
        REPARADO = "REPARADO", "Reparado"
        SEM_REPARO = "SEM_REPARO", "Sem possibilidade de reparo"

    equipamento = models.ForeignKey(
        "inventario.Equipamento", on_delete=models.PROTECT, related_name="manutencoes",
    )
    devolucao_origem = models.OneToOneField(
        "movimentacoes.Movimentacao", on_delete=models.PROTECT,
        related_name="manutencao", null=True, blank=True,
    )
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="manutencoes_abertas",
    )
    descricao_problema = models.TextField("Descrição do problema")
    data_abertura = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDENTE)
    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="manutencoes_iniciadas", null=True, blank=True,
    )
    data_inicio = models.DateTimeField(null=True, blank=True)
    concluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="manutencoes_concluidas", null=True, blank=True,
    )
    data_conclusao = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=20, choices=Resultado.choices, blank=True)
    descricao_solucao = models.TextField("Solução ou conclusão da análise", blank=True)

    class Meta:
        ordering = ["-data_abertura", "-pk"]
        verbose_name = "manutenção"
        verbose_name_plural = "manutenções"
        constraints = [
            models.UniqueConstraint(
                fields=["equipamento"], condition=models.Q(estado__in=["PENDENTE", "EM_ANDAMENTO"]),
                name="manutencao_aberta_unica_equip",
            ),
            models.CheckConstraint(
                condition=~models.Q(descricao_problema=""), name="manutencao_exige_problema",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(estado="PENDENTE", data_inicio__isnull=True, iniciado_por__isnull=True)
                    | models.Q(estado__in=["EM_ANDAMENTO", "CONCLUIDA"], data_inicio__isnull=False, iniciado_por__isnull=False)
                ),
                name="manutencao_inicio_coerente",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(estado__in=["PENDENTE", "EM_ANDAMENTO"], data_conclusao__isnull=True,
                             concluido_por__isnull=True, resultado="", descricao_solucao="")
                    | (models.Q(estado="CONCLUIDA", data_conclusao__isnull=False, concluido_por__isnull=False,
                                resultado__in=["REPARADO", "SEM_REPARO"]) & ~models.Q(descricao_solucao=""))
                ),
                name="manutencao_conclusao_coerente",
            ),
            models.CheckConstraint(
                condition=models.Q(data_inicio__isnull=True) | models.Q(data_inicio__gte=models.F("data_abertura")),
                name="manutencao_inicio_apos_abertura",
            ),
            models.CheckConstraint(
                condition=models.Q(data_conclusao__isnull=True) | models.Q(data_conclusao__gte=models.F("data_inicio")),
                name="manutencao_conclusao_apos_inicio",
            ),
        ]

    def clean(self):
        super().clean()
        self.descricao_problema = self.descricao_problema.strip()
        self.descricao_solucao = self.descricao_solucao.strip()
        erros = {}
        if not self.descricao_problema:
            erros["descricao_problema"] = "Descreva o problema do equipamento."
        if self.estado == self.Estado.CONCLUIDA and not self.descricao_solucao:
            erros["descricao_solucao"] = "Descreva a solução ou a conclusão da análise."
        if self.devolucao_origem_id:
            origem = self.devolucao_origem
            if origem.tipo != "DEVOLUCAO" or origem.equipamento_id != self.equipamento_id:
                erros["devolucao_origem"] = "A origem deve ser uma devolução deste equipamento."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"Manutenção #{self.pk} — {self.equipamento}"
