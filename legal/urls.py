from django.urls import path

from . import views, views_gestao


app_name = "legal"

urlpatterns = [
    path("termos-de-uso/", views.termos_de_uso, name="termos_de_uso"),
    path(
        "politica-de-privacidade/",
        views.politica_privacidade,
        name="politica_privacidade",
    ),
    path("aceite/", views.aceite_documentos, name="aceite_documentos"),
    path("documentos-legais/", views_gestao.documentos_legais, name="documentos_legais"),
    path("documentos-legais/<slug:tipo>/", views_gestao.editar_documento, name="editar_documento"),
    path("documentos-legais/<slug:tipo>/previa/", views_gestao.previa_documento, name="previa_documento"),
    path("documentos-legais/<slug:tipo>/versoes/<str:numero>/", views_gestao.historico_documento, name="historico_documento"),
]
