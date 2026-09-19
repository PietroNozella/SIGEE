from django.contrib import admin

from .models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("equipamento", "professor", "inicio", "fim", "status")
    list_filter = ("status", "inicio", "fim")
    search_fields = (
        "equipamento__numero_patrimonio",
        "equipamento__nome",
        "professor__username",
        "professor__first_name",
        "professor__last_name",
    )
    autocomplete_fields = ("equipamento", "professor")

    # O admin é apenas uma consulta técnica. A criação e as futuras alterações
    # funcionais devem passar pelo fluxo do Professor e pelas regras do serviço.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
