from django.conf import settings

from .models import AceiteDocumentosLegais


def versoes_atuais():
    return settings.TERMOS_USO_VERSAO, settings.POLITICA_PRIVACIDADE_VERSAO


def usuario_possui_aceite_vigente(usuario):
    if not getattr(usuario, "is_authenticated", False):
        return False

    versao_termos, versao_privacidade = versoes_atuais()
    return AceiteDocumentosLegais.objects.filter(
        usuario=usuario,
        versao_termos=versao_termos,
        versao_privacidade=versao_privacidade,
    ).exists()


def registrar_aceite_vigente(usuario):
    versao_termos, versao_privacidade = versoes_atuais()
    return AceiteDocumentosLegais.objects.get_or_create(
        usuario=usuario,
        versao_termos=versao_termos,
        versao_privacidade=versao_privacidade,
    )


def contexto_documentos():
    versao_termos, versao_privacidade = versoes_atuais()
    return {
        "versao_termos": versao_termos,
        "versao_privacidade": versao_privacidade,
        "contato_privacidade": settings.CONTATO_PRIVACIDADE,
    }
