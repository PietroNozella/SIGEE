from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection

from .models import DocumentoLegal


def criar_conta(username, grupo=None, **campos):
    conta = get_user_model().objects.create_user(username=username, **campos)
    if grupo:
        conta.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return conta


def garantir_documentos_legais():
    # TransactionTestCase limpa as linhas provenientes de migrações de dados.
    if not DocumentoLegal.objects.exists():
        migracao = import_module("legal.migrations.0002_versionar_documentos")
        with connection.schema_editor() as schema_editor:
            migracao.inicializar_versoes(apps, schema_editor)
