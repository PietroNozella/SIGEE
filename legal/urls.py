from django.urls import path

from . import views


app_name = "legal"

urlpatterns = [
    path("termos-de-uso/", views.termos_de_uso, name="termos_de_uso"),
    path(
        "politica-de-privacidade/",
        views.politica_privacidade,
        name="politica_privacidade",
    ),
    path("aceite/", views.aceite_documentos, name="aceite_documentos"),
]
