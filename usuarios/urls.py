from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("novo/", views.usuario_novo, name="usuario_novo"),
]
