from django.contrib import admin

from .models import Reserva, ReservaEquipamento


class ReservaEquipamentoInline(admin.TabularInline):
    model = ReservaEquipamento
    extra = 0
    can_delete = False
    readonly_fields = ("equipamento",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_equipamento",
        "local",
        "quantidade",
        "professor",
        "inicio",
        "fim",
        "status",
    )
    list_filter = ("status", "tipo_equipamento", "local", "inicio", "fim")
    search_fields = (
        "tipo_equipamento__nome",
        "itens__equipamento__numero_patrimonio",
        "professor__username",
        "professor__first_name",
        "professor__last_name",
    )
    autocomplete_fields = ("tipo_equipamento", "professor")
    inlines = (ReservaEquipamentoInline,)

    # O admin é apenas uma consulta técnica. A criação e as futuras alterações
    # funcionais devem passar pelo fluxo do Professor e pelas regras do serviço.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
