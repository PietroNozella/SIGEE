from django.urls import path

from . import views

app_name = "calendario"
urlpatterns = [
    path("", views.calendario_escola, name="calendario_escola"),
    path("feriados/", views.feriados, name="feriados"),
    path("intervalo/", views.intervalo_form, name="intervalo"),
    path("semana/<str:finalidade>/<int:dia>/", views.regra_form, name="regra_semanal"),
    path("excecoes/nova/", views.regra_form, name="excecao_nova"),
    path("excecoes/<int:regra_id>/", views.regra_form, name="excecao_editar"),
    path("excecoes/<int:regra_id>/remover/", views.remover_excecao, name="excecao_remover"),
]
