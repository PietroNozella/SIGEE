from django.db import models


class EquipamentoQuerySet(models.QuerySet):
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
    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
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

    def possui_registros_relacionados(self):
        return self.movimentacoes.exists()

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
        return f"{self.numero_patrimonio} - {self.nome}"