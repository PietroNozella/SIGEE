from django.urls import path

from . import views


app_name = "pedagogico"
urlpatterns = [
    path("reservas/<int:reserva_id>/utilizacao/", views.utilizacao_reserva, name="utilizacao_reserva"),
]
for cadastro in views.CADASTROS:
    urlpatterns.extend([
        path(f"{cadastro}/", views.cadastro_lista, {"cadastro": cadastro}, name=f"{cadastro}_lista"),
        path(f"{cadastro}/novo/", views.cadastro_form, {"cadastro": cadastro}, name=f"{cadastro}_novo"),
        path(f"{cadastro}/<int:registro_id>/editar/", views.cadastro_form, {"cadastro": cadastro}, name=f"{cadastro}_editar"),
        path(f"{cadastro}/<int:registro_id>/inativar/", views.cadastro_situacao, {"cadastro": cadastro, "ativo": False}, name=f"{cadastro}_inativar"),
        path(f"{cadastro}/<int:registro_id>/reativar/", views.cadastro_situacao, {"cadastro": cadastro, "ativo": True}, name=f"{cadastro}_reativar"),
    ])
