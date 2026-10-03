from django.urls import path

from . import views


app_name = "movimentacoes"

urlpatterns = [
    path("retirada/", views.retirada_sem_reserva, name="retirada_sem_reserva"),
    path("retirada/disponibilidade/", views.retirada_disponibilidade, name="retirada_disponibilidade"),
]
