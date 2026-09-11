from django.conf import settings
from django.db import models


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
