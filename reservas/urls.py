from django.urls import path

from . import views


app_name = "reservas"

urlpatterns = [
    path("<int:reserva_id>/", views.reserva_detalhe, name="reserva_detalhe"),
    path("consulta/", views.reserva_consulta, name="reserva_consulta"),
    path("", views.reserva_lista, name="reserva_lista"),
    path("nova/", views.reserva_nova, name="reserva_nova"),
    path(
        "disponibilidade/",
        views.reserva_disponibilidade,
        name="reserva_disponibilidade",
    ),
    path(
        "feriados/",
        views.reserva_feriados,
        name="reserva_feriados",
    ),
    path(
        "<int:reserva_id>/cancelar/",
        views.reserva_cancelar,
        name="reserva_cancelar",
    ),
]
