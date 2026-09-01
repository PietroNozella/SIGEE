from django.contrib import admin

from .models import Categoria, Equipamento, Local


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


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_patrimonio",
        "nome",
        "categoria",
        "local",
        "situacao",
        "ativo",
    )
    list_filter = ("ativo", "situacao", "categoria", "local")
    search_fields = ("numero_patrimonio", "nome")
