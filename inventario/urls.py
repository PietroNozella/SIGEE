from django.urls import path

from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.equipamento_lista, name="equipamento_lista"),
    path("novo/", views.equipamento_novo, name="equipamento_novo"),
]
