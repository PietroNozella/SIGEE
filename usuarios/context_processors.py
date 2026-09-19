from .permissoes import (
    e_professor_funcional,
    pode_cadastrar_usuario,
    pode_consultar_auditoria,
)


def permissoes_funcionais(request):
    return {
        "e_professor": e_professor_funcional(request.user),
        "pode_cadastrar_usuario": pode_cadastrar_usuario(request.user),
        "pode_consultar_auditoria": pode_consultar_auditoria(request.user),
    }
