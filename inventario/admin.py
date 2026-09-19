from django.contrib import admin

from .models import Categoria, Equipamento, Local, TipoEquipamento


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "data_criacao")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "data_criacao")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(TipoEquipamento)
class TipoEquipamentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "ativo", "data_criacao")
    list_filter = ("ativo", "categoria")
    search_fields = ("nome", "categoria__nome")


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_patrimonio",
        "tipo",
        "local",
        "situacao",
        "ativo",
    )
    list_filter = ("ativo", "situacao", "tipo__categoria", "tipo", "local")
    search_fields = ("numero_patrimonio", "tipo__nome")

    def delete_queryset(self, request, queryset):
        for equipamento in queryset:
            equipamento.delete()
