from django.db import models


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

    class Meta:
        ordering = ["numero_patrimonio"]
        verbose_name = "equipamento"
        verbose_name_plural = "equipamentos"

    def __str__(self):
        return f"{self.numero_patrimonio} - {self.nome}"
