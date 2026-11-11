from django.urls import path

from . import views

app_name = "calendario"
urlpatterns = [
    path("", views.calendario_escola, name="calendario_escola"),
    path("feriados/", views.feriados, name="feriados"),
    path("intervalo/", views.intervalo_form, name="intervalo"),
    path("cotas/", views.cotas, name="cotas"),
    path("cotas/<int:tipo_id>/", views.cota_form, name="cota"),
    path("semana/<str:finalidade>/<int:dia>/", views.regra_form, name="regra_semanal"),
    path("excecoes/nova/", views.regra_form, name="excecao_nova"),
    path("excecoes/<int:regra_id>/", views.regra_form, name="excecao_editar"),
    path("excecoes/<int:regra_id>/remover/", views.remover_excecao, name="excecao_remover"),
    path("fechamentos/novo/", views.fechamento_form, name="fechamento_novo"),
    path("fechamentos/politica/", views.politica_fechamento, name="politica_fechamento"),
    path("fechamentos/<int:fechamento_id>/", views.fechamento_detalhe, name="fechamento_detalhe"),
    path("fechamentos/<int:fechamento_id>/reabrir/", views.reabertura_form, name="fechamento_reabrir"),
    path("fechamentos/reservas/<int:impacto_id>/", views.decisao_fechamento, name="decisao_fechamento"),
]
