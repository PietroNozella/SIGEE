from django.urls import path

from . import views


app_name = "movimentacoes"

urlpatterns = [
    path("historico/", views.historico_lista, name="historico_lista"),
    path("retirada/reservas/", views.retirada_reserva_lista, name="retirada_reserva_lista"),
    path("retirada/reservas/<int:reserva_id>/", views.retirada_reserva_registrar, name="retirada_reserva_registrar"),
    path("devolucao/", views.devolucao_lista, name="devolucao_lista"),
    path("devolucao/<int:retirada_id>/", views.devolucao_registrar, name="devolucao_registrar"),
    path("retirada/", views.retirada_sem_reserva, name="retirada_sem_reserva"),
    path("retirada/disponibilidade/", views.retirada_disponibilidade, name="retirada_disponibilidade"),
]
