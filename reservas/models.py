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

    equipamento = models.ForeignKey(
        "inventario.Equipamento",
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
        ]
        indexes = [
            models.Index(
                fields=["equipamento", "inicio", "fim"],
                name="reserva_equip_periodo_idx",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}

        if self.professor_id and not e_professor_funcional(self.professor):
            erros["professor"] = (
                "Somente um usuário com perfil Professor pode criar uma reserva."
            )

        if self._state.adding and self.equipamento_id:
            equipamento_indisponivel = (
                not self.equipamento.ativo
                or self.equipamento.situacao
                != self.equipamento.Situacao.DISPONIVEL
            )
            if equipamento_indisponivel:
                erros["equipamento"] = (
                    "Somente um equipamento ativo e disponível pode ser reservado."
                )

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
                "A data e a hora final devem ser posteriores ao início da reserva."
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

        if (
            periodo_valido
            and self.equipamento_id
            and self.status == self.Status.ATIVA
        ):
            conflito = (
                type(self)
                .objects.filter(
                    equipamento_id=self.equipamento_id,
                    status=self.Status.ATIVA,
                    inicio__lt=self.fim,
                    fim__gt=self.inicio,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if conflito:
                erros[NON_FIELD_ERRORS] = (
                    "O equipamento já possui uma reserva ativa nesse período."
                )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return (
            f"{self.equipamento} — {timezone.localtime(self.inicio):%d/%m/%Y %H:%M}"
        )
