from django.contrib import admin

from .models import Movimentacao


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("equipamento", "tipo", "operador", "destinatario", "data_hora")
    list_filter = ("tipo", "data_hora")
    search_fields = ("equipamento__numero_patrimonio", "equipamento__tipo__nome")

    # A escrita direta contornaria a transação e a atualização do equipamento.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
