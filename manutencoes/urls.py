from django.urls import path

from . import views


app_name = "manutencoes"
urlpatterns = [
    path("", views.manutencao_lista, name="manutencao_lista"),
    path("nova/", views.manutencao_abrir, name="manutencao_abrir"),
    path("<int:manutencao_id>/", views.manutencao_detalhe, name="manutencao_detalhe"),
    path("<int:manutencao_id>/iniciar/", views.manutencao_iniciar, name="manutencao_iniciar"),
    path("<int:manutencao_id>/concluir/", views.manutencao_concluir, name="manutencao_concluir"),
]
