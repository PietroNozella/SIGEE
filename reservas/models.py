from datetime import timedelta

from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.db.models import BooleanField, Case, CharField, Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from usuarios.permissoes import e_professor_funcional


class ReservaQuerySet(models.QuerySet):
    def com_etapa(self):
        from movimentacoes.models import Movimentacao

        retiradas = Movimentacao.objects.filter(reserva_id=OuterRef("pk"), tipo="RETIRADA")
        return self.annotate(
            tem_retirada=Exists(retiradas),
            tem_pendentes=Exists(retiradas.filter(devolucoes__isnull=True)),
            quantidade_entregue=Coalesce(Subquery(retiradas.order_by().values("reserva_id").annotate(total=Count("pk")).values("total")), Value(0), output_field=IntegerField()),
        ).annotate(tem_entrega_pendente=Case(
            When(status="ATIVA", fim__gt=timezone.now(), quantidade__gt=F("quantidade_entregue"), then=Value(True)),
            default=Value(False), output_field=BooleanField(),
        )).annotate(etapa=Case(
            When(tem_pendentes=True, then=Value("EM_USO")),
            When(tem_retirada=True, tem_entrega_pendente=True, then=Value("AGUARDANDO")),
            When(tem_retirada=True, then=Value("ENCERRADA")),
            When(status="CANCELADA", then=Value("CANCELADA")),
            When(status="EXPIRADA", then=Value("EXPIRADA")),
            default=Value("AGUARDANDO"), output_field=CharField(),
        ))

    def aguardando_retirada(self):
        return self.com_etapa().filter(Q(etapa="AGUARDANDO") | Q(tem_entrega_pendente=True))

    def em_uso(self):
        return self.com_etapa().filter(etapa="EM_USO")

    def encerradas(self):
        return self.com_etapa().filter(etapa__in=("ENCERRADA", "CANCELADA", "EXPIRADA"))


class Reserva(models.Model):
    objects = ReservaQuerySet.as_manager()
    TOLERANCIA_RETIRADA = timedelta(minutes=30)
    ANTECEDENCIA_MAXIMA_DIAS = 15

    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        CANCELADA = "CANCELADA", "Cancelada"
        EXPIRADA = "EXPIRADA", "Expirada"

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
    # Nulos preservam reservas anteriores à exigência de contexto no cadastro.
    turma = models.ForeignKey("pedagogico.Turma", on_delete=models.PROTECT, null=True, blank=True)
    disciplina = models.ForeignKey("pedagogico.Disciplina", on_delete=models.PROTECT, null=True, blank=True)
    atividade = models.ForeignKey("pedagogico.AtividadePedagogica", on_delete=models.PROTECT, null=True, blank=True)
    observacao_pedagogica = models.TextField(blank=True)
    calendario_confirmado = models.JSONField(default=dict, db_default={}, blank=True, editable=False)
    # Reservas anteriores preservam a política sem margem entre usos.
    intervalo_apos_uso = models.DurationField(default=timedelta, db_default=timedelta(), editable=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ATIVA,
    )
    motivo_cancelamento = models.TextField(blank=True, default="", db_default="")
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reservas_canceladas",
    )
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-inicio", "-pk"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        permissions = [
            ("cancelar_reserva_operacional", "Pode registrar cancelamento operacional de reserva"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(intervalo_apos_uso__gte=timedelta()), name="reserva_intervalo_nao_negativo"),
            models.CheckConstraint(
                condition=(Q(turma__isnull=True, disciplina__isnull=True, atividade__isnull=True)
                           | Q(turma__isnull=False, disciplina__isnull=False, atividade__isnull=False)),
                name="reserva_contexto_completo_ou_legado",
            ),
            models.CheckConstraint(
                condition=Q(fim__gt=F("inicio")),
                name="reserva_fim_posterior_inicio",
            ),
            models.CheckConstraint(
                condition=Q(quantidade__gte=1),
                name="reserva_quantidade_positiva",
            ),
            models.CheckConstraint(
                condition=(
                    Q(motivo_cancelamento="", cancelada_por__isnull=True, data_cancelamento__isnull=True)
                    | (
                        Q(status="CANCELADA", cancelada_por__isnull=False, data_cancelamento__isnull=False)
                        & ~Q(motivo_cancelamento="")
                    )
                ),
                name="reserva_cancelamento_completo",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tipo_equipamento", "local", "inicio", "fim"],
                name="res_tipo_loc_periodo_idx",
            ),
        ]

    @classmethod
    def data_limite_agendamento(cls):
        return timezone.localdate() + timedelta(days=cls.ANTECEDENCIA_MAXIMA_DIAS)

    @property
    def intervalo_minutos(self):
        return int(self.intervalo_apos_uso.total_seconds() // 60)

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

        if (
            periodo_valido and self._state.adding
            and timezone.localtime(self.inicio).date() > self.data_limite_agendamento()
        ):
            erros["inicio"] = (
                f"A reserva pode ser agendada com até {self.ANTECEDENCIA_MAXIMA_DIAS} dias corridos de antecedência."
            )

        if periodo_valido and self._state.adding:
            from calendario.services import validar_periodo_reserva
            try:
                validar_periodo_reserva(self.inicio, self.fim)
            except ValidationError as erro:
                erros.update(erro.message_dict)

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


class SubstituicaoReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.PROTECT, related_name="substituicoes")
    equipamento_anterior = models.ForeignKey("inventario.Equipamento", on_delete=models.PROTECT, related_name="substituicoes_origem")
    equipamento_substituto = models.ForeignKey("inventario.Equipamento", on_delete=models.PROTECT, related_name="substituicoes_destino")
    manutencao = models.ForeignKey("manutencoes.Manutencao", on_delete=models.PROTECT, related_name="substituicoes")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data_registro", "pk"]
        verbose_name = "substituição de reserva"
