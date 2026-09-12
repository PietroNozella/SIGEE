import re

from .models import RegistroAuditoria


PADRAO_ACAO = re.compile(r"^[A-Z][A-Z0-9_]*$")


def registrar_evento(
    *,
    acao,
    resultado,
    usuario=None,
    entidade="",
    entidade_id="",
):
    acao = "" if acao is None else str(acao).strip()
    entidade = "" if entidade is None else str(entidade).strip()
    entidade_id = "" if entidade_id is None else str(entidade_id).strip()

    if not acao:
        raise ValueError("A ação do registro de auditoria não pode ficar vazia.")
    if len(acao) > 100:
        raise ValueError("A ação do registro de auditoria excede 100 caracteres.")
    if not PADRAO_ACAO.fullmatch(acao):
        raise ValueError("A ação deve ser um código técnico em letras maiúsculas.")
    if resultado not in RegistroAuditoria.Resultado.values:
        raise ValueError("Resultado de auditoria inválido.")
    if len(entidade) > 100 or len(entidade_id) > 100:
        raise ValueError("A identificação da entidade excede 100 caracteres.")


    # A auditoria associa somente identidades autenticadas e persistidas,
    # evitando registrar como usuário dados não verificados da requisição.
    usuario_persistido = (
        usuario
        if getattr(usuario, "is_authenticated", False) and usuario.pk is not None
        else None
    )

    return RegistroAuditoria.objects.create(
        usuario=usuario_persistido,
        acao=acao,
        resultado=resultado,
        entidade=entidade,
        entidade_id=entidade_id,
    )
