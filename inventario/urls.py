from django.urls import path

from . import views

app_name = "inventario"

urlpatterns = [
    path("inicio/", views.inicio_operador, name="inicio_operador"),
    path("painel/", views.painel, name="painel"),
    path("", views.equipamento_lista, name="equipamento_lista"),
    path("novo/", views.equipamento_novo, name="equipamento_novo"),
    path("<int:equipamento_id>/reativar/", views.equipamento_reativar, name="equipamento_reativar"),
    path(
        "<int:equipamento_id>/editar/",
        views.equipamento_editar,
        name="equipamento_editar",
    ),
    path("importar/", views.equipamento_importar, name="equipamento_importar"),
    path(
        "importar/modelo.csv/",
        views.equipamento_modelo_csv,
        name="equipamento_modelo_csv",
    ),
    path(
        "<int:equipamento_id>/excluir/",
        views.equipamento_excluir,
        name="equipamento_excluir",
    ),
]

for cadastro in views.CADASTROS_INVENTARIO:
    urlpatterns += [
        path(f"{cadastro}/", views.cadastro_lista, {"cadastro": cadastro}, name=f"{cadastro}_lista"),
        path(f"{cadastro}/novo/", views.cadastro_form, {"cadastro": cadastro}, name=f"{cadastro}_novo"),
        path(f"{cadastro}/<int:registro_id>/editar/", views.cadastro_form, {"cadastro": cadastro}, name=f"{cadastro}_editar"),
        path(f"{cadastro}/<int:registro_id>/inativar/", views.cadastro_situacao, {"cadastro": cadastro, "ativo": False}, name=f"{cadastro}_inativar"),
        path(f"{cadastro}/<int:registro_id>/reativar/", views.cadastro_situacao, {"cadastro": cadastro, "ativo": True}, name=f"{cadastro}_reativar"),
    ]
