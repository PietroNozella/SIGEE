from django.contrib import admin

from .models import Movimentacao


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("equipamento", "tipo", "operador", "destinatario", "data_hora")
    list_filter = ("tipo", "data_hora")
    search_fields = ("equipamento__numero_patrimonio", "equipamento__nome")
