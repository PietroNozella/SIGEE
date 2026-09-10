from .permissoes import pode_cadastrar_usuario, pode_consultar_auditoria


def permissoes_funcionais(request):
    return {
        "pode_cadastrar_usuario": pode_cadastrar_usuario(request.user),
        "pode_consultar_auditoria": pode_consultar_auditoria(request.user),
    }
