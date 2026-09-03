from django.urls import path

from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.equipamento_lista, name="equipamento_lista"),
    path("novo/", views.equipamento_novo, name="equipamento_novo"),
    path("importar/", views.equipamento_importar, name="equipamento_importar"),
    path(
        "importar/modelo.csv/",
        views.equipamento_modelo_csv,
        name="equipamento_modelo_csv",
    ),
    path(
        "<int:equipamento_id>/excluir/",
        views.equipamento_excluir,
        name="equipamento_excluir",
    ),
]
