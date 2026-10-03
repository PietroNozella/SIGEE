from django.urls import path

from . import views


app_name = "movimentacoes"

urlpatterns = [
    path("devolucao/", views.devolucao_lista, name="devolucao_lista"),
    path("devolucao/<int:retirada_id>/", views.devolucao_registrar, name="devolucao_registrar"),
    path("retirada/", views.retirada_sem_reserva, name="retirada_sem_reserva"),
    path("retirada/disponibilidade/", views.retirada_disponibilidade, name="retirada_disponibilidade"),
]
