from django.conf import settings
from django.db import models


class DocumentoLegal(models.Model):
    class Tipo(models.TextChoices):
        TERMOS = "termos", "Termos de Uso"
        PRIVACIDADE = "privacidade", "Política de Privacidade"

    tipo = models.CharField(max_length=12, choices=Tipo.choices, primary_key=True)
    versao_vigente = models.ForeignKey(
        "VersaoDocumentoLegal", on_delete=models.PROTECT, null=True, related_name="+",
    )
    rascunho_conteudo = models.TextField()
    rascunho_contato = models.EmailField()
    rascunho_resumo = models.TextField(blank=True)
    revisao_rascunho = models.PositiveIntegerField(default=1)


class VersaoDocumentoLegal(models.Model):
    documento = models.ForeignKey(
        DocumentoLegal, on_delete=models.PROTECT, related_name="versoes",
    )
    numero = models.CharField(max_length=20)
    conteudo = models.JSONField()
    contato = models.EmailField()
    resumo = models.TextField(blank=True)
    vigente_desde = models.DateField()
    publicado_em = models.DateTimeField(null=True)
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+",
    )

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=("documento", "numero"), name="legal_numero_unico_por_documento",
            ),
        ]


class AceiteDocumentosLegais(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="aceites_documentos_legais",
    )
    versao_termos = models.CharField("versão dos Termos de Uso", max_length=20)
    versao_privacidade = models.CharField(
        "versão da Política de Privacidade",
        max_length=20,
    )
    aceito_em = models.DateTimeField("aceito em", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-aceito_em", "-pk"]
        verbose_name = "aceite de documentos legais"
        verbose_name_plural = "aceites de documentos legais"
        constraints = [
            models.UniqueConstraint(
                fields=("usuario", "versao_termos", "versao_privacidade"),
                name="legal_aceite_unico_por_versoes",
            ),
        ]

    def __str__(self):
        return (
            f"{self.usuario} — Termos {self.versao_termos} / "
            f"Privacidade {self.versao_privacidade}"
        )
