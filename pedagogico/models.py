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
