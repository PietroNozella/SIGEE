from django.urls import path

from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.registro_lista, name="registro_lista"),
]
