from django.contrib import admin

from .models import AceiteDocumentosLegais


@admin.register(AceiteDocumentosLegais)
class AceiteDocumentosLegaisAdmin(admin.ModelAdmin):
    list_display = (
        "aceito_em",
        "usuario",
        "versao_termos",
        "versao_privacidade",
    )
    list_filter = ("versao_termos", "versao_privacidade", "aceito_em")
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "usuario__email",
    )
    readonly_fields = (
        "usuario",
        "versao_termos",
        "versao_privacidade",
        "aceito_em",
    )
    date_hierarchy = "aceito_em"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
