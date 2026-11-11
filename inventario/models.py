from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef
from django.utils import timezone


class EquipamentoQuerySet(models.QuerySet):
    def sem_retirada_aberta(self):
        from movimentacoes.models import Movimentacao

        retiradas = Movimentacao.objects.filter(
            equipamento_id=OuterRef("pk"), tipo=Movimentacao.Tipo.RETIRADA,
            devolucoes__isnull=True,
        )
        return self.alias(tem_retirada_aberta=Exists(retiradas)).filter(tem_retirada_aberta=False)

    # Preserva a RN-06 também nas exclusões em lote do Django.
    def delete(self):
        total_excluido = 0
        detalhes_exclusao = {}

        for equipamento in self:
            quantidade, detalhes = equipamento.delete()
            total_excluido += quantidade

            for modelo, total in detalhes.items():
                detalhes_exclusao[modelo] = detalhes_exclusao.get(modelo, 0) + total

        return total_excluido, detalhes_exclusao


class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.CharField(max_length=255, blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "categoria"
        verbose_name_plural = "categorias"

    def __str__(self):
        return self.nome


class Local(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.CharField(max_length=255, blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "local"
        verbose_name_plural = "locais"

    def __str__(self):
        return self.nome


class TipoEquipamento(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="tipos_equipamento",
    )
    nome = models.CharField("tipo/modelo", max_length=150)
    ativo = models.BooleanField(default=True)
    cota_por_professor = models.PositiveIntegerField(
        null=True, blank=True, default=None, db_default=None,
        validators=[MinValueValidator(1), MaxValueValidator(2147483647)],
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["categoria__nome", "nome"]
        verbose_name = "tipo de equipamento"
        verbose_name_plural = "tipos de equipamento"
        constraints = [
            models.CheckConstraint(condition=models.Q(cota_por_professor__isnull=True)
                | models.Q(cota_por_professor__gte=1, cota_por_professor__lte=2147483647), name="tipo_cota_professor_valida"),
            models.UniqueConstraint(
                fields=("categoria", "nome"),
                name="tipo_equip_categoria_nome_unicos",
            ),
        ]

    def __str__(self):
        return f"{self.categoria.nome} — {self.nome}"


class Equipamento(models.Model):
    MENSAGEM_PATRIMONIO_DUPLICADO = (
        "Já existe um equipamento cadastrado com este número de patrimônio."
    )

    class Situacao(models.TextChoices):
        DISPONIVEL = "DISPONIVEL", "Disponível"
        EM_USO = "EM_USO", "Em uso"
        MANUTENCAO = "MANUTENCAO", "Manutenção"

    numero_patrimonio = models.CharField(
        "número de patrimônio",
        max_length=50,
        unique=True,
        error_messages={"unique": MENSAGEM_PATRIMONIO_DUPLICADO},
    )
    descricao = models.TextField(blank=True)
    tipo = models.ForeignKey(
        TipoEquipamento,
        on_delete=models.PROTECT,
        related_name="equipamentos",
    )
    local = models.ForeignKey(Local, on_delete=models.PROTECT)
    situacao = models.CharField(
        max_length=30,
        choices=Situacao.choices,
        default=Situacao.DISPONIVEL,
    )
    ativo = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    objects = EquipamentoQuerySet.as_manager()

    class Meta:
        ordering = ["numero_patrimonio"]
        verbose_name = "equipamento"
        verbose_name_plural = "equipamentos"
        permissions = [
            ("view_resumo_inventario", "Pode visualizar o resumo do inventário"),
        ]

    def possui_registros_relacionados(self):
        return self.movimentacoes.exists() or self.itens_reserva.exists() or self.manutencoes.exists()

    def possui_compromisso_vigente(self):
        return self.pk is not None and (
            self.itens_reserva.filter(reserva__status="ATIVA", reserva__fim__gt=timezone.now()).exists()
            or not Equipamento.objects.filter(pk=self.pk).sem_retirada_aberta().exists()
        )

    @property
    def situacao_operacional(self):
        return self.situacao if self.ativo else "INATIVO"

    @property
    def rotulo_situacao_operacional(self):
        return self.get_situacao_display() if self.ativo else "Inativo — indisponível para uso"

    def clean(self):
        super().clean()
        sem_custodia = not self.pk or Equipamento.objects.filter(pk=self.pk).sem_retirada_aberta().exists()
        if self.situacao == self.Situacao.EM_USO and sem_custodia:
            raise ValidationError({"situacao": "A situação Em uso exige uma retirada registrada. Confirme a entrega pelo fluxo de reservas."})
        if (
            not sem_custodia and self.situacao != self.Situacao.EM_USO
        ):
            raise ValidationError({"situacao": "Registre a devolução física antes de disponibilizar o equipamento."})
        if (
            self.pk and self.situacao != self.Situacao.MANUTENCAO
            and self.manutencoes.exclude(estado="CONCLUIDA").exists()
        ):
            raise ValidationError({"situacao": "Conclua a manutenção antes de alterar a situação do equipamento."})
        if self.pk:
            original = Equipamento.objects.filter(pk=self.pk).values("tipo_id", "local_id").first()
            if (
                original and (original["tipo_id"] != self.tipo_id or original["local_id"] != self.local_id)
                and self.possui_compromisso_vigente()
            ):
                raise ValidationError("Não altere o tipo/modelo ou local de uma unidade com reserva vigente ou retirada em aberto.")

    # RN-06: equipamentos com movimentações são inativados para preservar
    # o histórico; somente itens sem registros relacionados são excluídos.
    def delete(self, using=None, keep_parents=False):
        if self.possui_registros_relacionados():
            if self.ativo:
                self.ativo = False
                self.save(
                    using=using,
                    update_fields=["ativo", "data_atualizacao"],
                )
            return 0, {}

        return super().delete(using=using, keep_parents=keep_parents)

    def __str__(self):
        return f"{self.numero_patrimonio} - {self.tipo.nome}"
