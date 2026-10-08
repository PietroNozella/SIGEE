from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


ERROS_NOME = {"unique": "Já existe um cadastro com este nome."}


class CadastroPedagogico(models.Model):
    nome = models.CharField(max_length=100, unique=True, error_messages=ERROS_NOME)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["nome", "pk"]

    def clean(self):
        super().clean()
        self.nome = self.nome.strip()
        if not self.nome:
            raise ValidationError({"nome": "Informe um nome."})

    def __str__(self):
        return self.nome


class Turma(CadastroPedagogico):
    class Meta(CadastroPedagogico.Meta):
        abstract = False
        verbose_name = "turma"
        verbose_name_plural = "turmas"


class Disciplina(CadastroPedagogico):
    class Meta(CadastroPedagogico.Meta):
        abstract = False
        verbose_name = "disciplina"
        verbose_name_plural = "disciplinas"


class AtividadePedagogica(CadastroPedagogico):
    nome = models.CharField(max_length=150, unique=True, error_messages=ERROS_NOME)
    descricao = models.TextField(blank=True)

    class Meta(CadastroPedagogico.Meta):
        abstract = False
        verbose_name = "atividade pedagógica"
        verbose_name_plural = "atividades pedagógicas"


class UtilizacaoPedagogica(models.Model):
    movimentacao = models.OneToOneField(
        "movimentacoes.Movimentacao", on_delete=models.PROTECT,
        related_name="utilizacao_pedagogica",
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="utilizacoes_pedagogicas",
    )
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT)
    atividade = models.ForeignKey(AtividadePedagogica, on_delete=models.PROTECT)
    observacao = models.TextField("observação", blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_criacao", "-pk"]
        verbose_name = "utilização pedagógica"
        verbose_name_plural = "utilizações pedagógicas"
        default_permissions = ("view", "add", "change")

    def clean(self):
        super().clean()
        if not self.movimentacao_id:
            return
        retirada = self.movimentacao
        if retirada.tipo != "RETIRADA" or not retirada.reserva_id:
            raise ValidationError({"movimentacao": "Selecione uma retirada originada de reserva."})
        if self.professor_id != retirada.destinatario_id or self.professor_id != retirada.reserva.professor_id:
            raise ValidationError({"professor": "O Professor precisa ser o proprietário da reserva e destinatário da retirada."})

    def __str__(self):
        return f"Utilização da retirada #{self.movimentacao_id}"
