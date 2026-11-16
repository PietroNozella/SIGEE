from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Subquery
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from usuarios.permissoes import pode_gerenciar_documentos_legais

from .conteudo import interpretar_conteudo, texto_editavel
from .models import AceiteDocumentosLegais, DocumentoLegal, VersaoDocumentoLegal


TERMOS = DocumentoLegal.Tipo.TERMOS
PRIVACIDADE = DocumentoLegal.Tipo.PRIVACIDADE


class RascunhoDesatualizado(ValidationError):
    def __init__(self):
        super().__init__("O rascunho mudou. Confira a versão atual antes de continuar.")


def documentos_vigentes():
    return DocumentoLegal.objects.select_related("versao_vigente").defer(
        "rascunho_conteudo", "rascunho_contato", "rascunho_resumo",
    ).in_bulk()


def par_de_versoes(documentos):
    return documentos[TERMOS].versao_vigente.numero, documentos[PRIVACIDADE].versao_vigente.numero


def versoes_atuais():
    numeros = dict(DocumentoLegal.objects.values_list("tipo", "versao_vigente__numero"))
    return numeros[TERMOS], numeros[PRIVACIDADE]


def usuario_possui_aceite_vigente(usuario):
    if not getattr(usuario, "is_authenticated", False):
        return False

    def numero_vigente(tipo):
        return Subquery(DocumentoLegal.objects.filter(pk=tipo).values("versao_vigente__numero"))

    return AceiteDocumentosLegais.objects.filter(
        usuario=usuario,
        versao_termos=numero_vigente(TERMOS),
        versao_privacidade=numero_vigente(PRIVACIDADE),
    ).exists()


def _bloquear_conta(usuario):
    atual = get_user_model().objects.select_for_update().filter(pk=usuario.pk, is_active=True).first()
    if atual is None:
        raise PermissionDenied
    return atual


def _bloquear_documentos():
    # Bloqueie primeiro as linhas fixas e leia as versões em outra instrução.
    # Após uma espera, a nova versão pode ter sido criada pela outra transação.
    list(DocumentoLegal.objects.order_by("pk").select_for_update().values_list("pk", flat=True))


@transaction.atomic
def registrar_aceite_vigente(usuario, *, versoes_enviadas=None):
    atual = _bloquear_conta(usuario)
    _bloquear_documentos()
    par_vigente = versoes_atuais()
    if versoes_enviadas is not None and versoes_enviadas != par_vigente:
        return None, False

    aceite, criado = AceiteDocumentosLegais.objects.get_or_create(
        usuario=atual, versao_termos=par_vigente[0], versao_privacidade=par_vigente[1],
    )
    if criado and versoes_enviadas is not None:
        registrar_evento(
            usuario=atual, acao=AcaoAuditoria.DOCUMENTOS_LEGAIS_ACEITOS,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="AceiteDocumentosLegais", entidade_id=aceite.pk,
        )
    return aceite, criado


def alteracoes_desde_ultimo_aceite(usuario, documentos):
    anterior = AceiteDocumentosLegais.objects.filter(usuario=usuario).first()
    alteracoes = {}
    for tipo, campo in ((TERMOS, "versao_termos"), (PRIVACIDADE, "versao_privacidade")):
        vigente = documentos[tipo].versao_vigente
        numero_anterior = getattr(anterior, campo, None)
        if numero_anterior == vigente.numero:
            continue
        versoes = VersaoDocumentoLegal.objects.filter(documento_id=tipo, pk__lte=vigente.pk)
        if numero_anterior is None:
            versoes = versoes.filter(pk=vigente.pk)
        else:
            pk_anterior = versoes.filter(numero=numero_anterior).values_list("pk", flat=True).first()
            if pk_anterior is not None:
                versoes = versoes.filter(pk__gt=pk_anterior)
        alteracoes[documentos[tipo].get_tipo_display()] = list(
            versoes.exclude(resumo="").only("numero", "resumo").order_by("pk")
        )
    return {titulo: historico for titulo, historico in alteracoes.items() if historico}


def _rascunho_para_alteracao(usuario, tipo, revisao):
    atual = _bloquear_conta(usuario)
    if not pode_gerenciar_documentos_legais(atual):
        raise PermissionDenied

    _bloquear_documentos()
    documento = DocumentoLegal.objects.select_related("versao_vigente").get(pk=tipo)
    if documento.revisao_rascunho != revisao:
        raise RascunhoDesatualizado
    return atual, documento


def _gravar_rascunho(documento, *, conteudo, contato, resumo):
    documento.rascunho_conteudo = conteudo
    documento.rascunho_contato = contato
    documento.rascunho_resumo = resumo
    documento.revisao_rascunho += 1
    documento.save(update_fields=[
        "rascunho_conteudo", "rascunho_contato", "rascunho_resumo", "revisao_rascunho",
    ])


@transaction.atomic
def salvar_rascunho(*, usuario, tipo, revisao, conteudo, contato, resumo):
    _, documento = _rascunho_para_alteracao(usuario, tipo, revisao)
    _gravar_rascunho(documento, conteudo=conteudo, contato=contato, resumo=resumo)


@transaction.atomic
def copiar_versao_para_rascunho(*, usuario, tipo, revisao, numero):
    _, documento = _rascunho_para_alteracao(usuario, tipo, revisao)
    anterior = documento.versoes.get(numero=numero)
    _gravar_rascunho(
        documento, conteudo=texto_editavel(anterior.conteudo), contato=anterior.contato, resumo="",
    )


def _proximo_numero(documento):
    campo_legado = "versao_termos" if documento.tipo == TERMOS else "versao_privacidade"
    principal, revisao = map(int, documento.versao_vigente.numero.split("."))
    while True:
        revisao += 1
        numero = f"{principal}.{revisao}"
        if not (
            documento.versoes.filter(numero=numero).exists()
            or AceiteDocumentosLegais.objects.filter(**{campo_legado: numero}).exists()
        ):
            return numero


@transaction.atomic
def publicar_rascunho(*, usuario, tipo, revisao):
    atual, documento = _rascunho_para_alteracao(usuario, tipo, revisao)
    resumo = documento.rascunho_resumo.strip()
    if not resumo:
        raise ValidationError("Informe o resumo das mudanças antes de publicar.")

    agora = timezone.now()
    versao = documento.versoes.create(
        numero=_proximo_numero(documento), conteudo=interpretar_conteudo(documento.rascunho_conteudo),
        contato=documento.rascunho_contato, resumo=resumo, vigente_desde=timezone.localdate(agora),
        publicado_em=agora, publicado_por=atual,
    )
    documento.versao_vigente = versao
    documento.rascunho_resumo = ""
    documento.revisao_rascunho += 1
    documento.save(update_fields=["versao_vigente", "rascunho_resumo", "revisao_rascunho"])
    registrar_evento(
        usuario=atual, acao=AcaoAuditoria.DOCUMENTO_LEGAL_PUBLICADO,
        resultado=RegistroAuditoria.Resultado.SUCESSO, entidade="VersaoDocumentoLegal", entidade_id=versao.pk,
    )
    return versao
