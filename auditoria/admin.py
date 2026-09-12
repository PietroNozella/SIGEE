from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "data_hora",
        "usuario",
        "acao",
        "resultado",
        "entidade",
        "entidade_id",
    )
    list_filter = ("resultado", "acao", "entidade", "data_hora")
    search_fields = ("usuario__username", "acao", "entidade", "entidade_id")
    readonly_fields = (
        "data_hora",
        "usuario",
        "acao",
        "resultado",
        "entidade",
        "entidade_id",
    )
    date_hierarchy = "data_hora"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
