from .permissoes import (
    e_operador_funcional,
    e_professor_funcional,
    pode_cadastrar_usuario,
    pode_consultar_auditoria,
    pode_registrar_retirada,
)


def permissoes_funcionais(request):
    return {
        "e_operador": e_operador_funcional(request.user),
        "e_professor": e_professor_funcional(request.user),
        "pode_cadastrar_usuario": pode_cadastrar_usuario(request.user),
        "pode_consultar_auditoria": pode_consultar_auditoria(request.user),
        "pode_registrar_retirada": pode_registrar_retirada(request.user),
    }
