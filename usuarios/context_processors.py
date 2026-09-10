from .permissoes import pode_cadastrar_usuario


def permissoes_funcionais(request):
    return {
        "pode_cadastrar_usuario": pode_cadastrar_usuario(request.user),
    }
