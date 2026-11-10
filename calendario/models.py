from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class CalendarioEscolar(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    versao = models.PositiveIntegerField(default=1)
    intervalo_minutos = models.PositiveSmallIntegerField(default=5, validators=[MaxValueValidator(32767)])

    class Meta:
        verbose_name = "calendário da escola"
        permissions = [("configurar_calendario", "Pode configurar o calendário da escola")]
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="calendario_unico_escola"),
            models.CheckConstraint(condition=Q(intervalo_minutos__lte=32767), name="calendario_intervalo_limite"),
        ]


class RegraCalendario(models.Model):
    class Finalidade(models.TextChoices):
        USO = "USO", "Uso dos equipamentos"
        ATENDIMENTO = "ATENDIMENTO", "Atendimento do Operador"

    DIAS = tuple(enumerate(("Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo")))
    finalidade = models.CharField(max_length=15, choices=Finalidade.choices)
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS, null=True, blank=True)
    data = models.DateField(null=True, blank=True)
    dia_inteiro = models.BooleanField(default=False)

    class Meta:
        ordering = ["data", "finalidade", "dia_semana"]
        constraints = [
            models.CheckConstraint(
                condition=Q(data__isnull=True, dia_semana__gte=0, dia_semana__lte=6, dia_semana__isnull=False)
                | Q(data__isnull=False, dia_semana__isnull=True), name="calendario_dia_ou_data",
            ),
            models.CheckConstraint(condition=Q(finalidade__in=["USO", "ATENDIMENTO"]), name="calendario_finalidade_valida"),
            models.UniqueConstraint(fields=["finalidade", "dia_semana"], condition=Q(data__isnull=True), name="calendario_semana_unica"),
            models.UniqueConstraint(fields=["finalidade", "data"], condition=Q(data__isnull=False), name="calendario_excecao_unica"),
        ]

    def clean(self):
        super().clean()
        if (self.data is None) == (self.dia_semana is None):
            raise ValidationError("Escolha um dia da semana ou uma data específica.")
        if self._state.adding and self.data and self.data < timezone.localdate():
            raise ValidationError({"data": "Escolha hoje ou uma data futura para a exceção."})

    def __str__(self):
        dia = self.data.strftime("%d/%m/%Y") if self.data else self.get_dia_semana_display()
        return f"{self.get_finalidade_display()} · {dia}"


class FaixaHorario(models.Model):
    regra = models.ForeignKey(RegraCalendario, on_delete=models.CASCADE, related_name="faixas")
    inicio = models.TimeField()
    fim = models.TimeField()

    class Meta:
        ordering = ["inicio", "fim"]
        constraints = [models.CheckConstraint(condition=Q(fim__gt=F("inicio")) | Q(fim=time.min), name="calendario_faixa_crescente")]

    def clean(self):
        super().clean()
        if self.inicio is not None and self.fim is not None and self.fim != time.min and self.fim <= self.inicio:
            raise ValidationError({"fim": "O término deve ser posterior ao início. Para encerrar à meia-noite, use 00:00."})


class AlteracaoCalendario(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_hora = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField()
    anterior = models.JSONField(default=dict)
    novo = models.JSONField(default=dict)
    versao = models.PositiveIntegerField()

    class Meta:
        ordering = ["-data_hora", "-pk"]
