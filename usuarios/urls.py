from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("", views.usuario_lista, name="usuario_lista"),
    path("novo/", views.usuario_novo, name="usuario_novo"),
    path("<uuid:usuario_id>/desativar/", views.usuario_situacao, {"ativo": False}, name="usuario_desativar"),
    path("<uuid:usuario_id>/reativar/", views.usuario_situacao, {"ativo": True}, name="usuario_reativar"),
]
