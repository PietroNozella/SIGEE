GRUPO_ADMINISTRADOR = "Administrador"
GRUPO_OPERADOR = "Operador"
GRUPO_PROFESSOR = "Professor"

GRUPOS_FUNCIONAIS = (
    GRUPO_ADMINISTRADOR,
    GRUPO_OPERADOR,
    GRUPO_PROFESSOR,
)

PERMISSAO_CADASTRAR_USUARIO = "auth.add_user"
PERMISSAO_CONSULTAR_AUDITORIA = "auditoria.view_registroauditoria"
PERMISSAO_CRIAR_RESERVA = "reservas.add_reserva"
PERMISSAO_CONSULTAR_RESERVA = "reservas.view_reserva"
PERMISSAO_ALTERAR_RESERVA = "reservas.change_reserva"

PERMISSOES_POR_GRUPO = {
    GRUPO_ADMINISTRADOR: (
        "inventario.view_equipamento",
        "inventario.add_equipamento",
        "inventario.change_equipamento",
        "inventario.delete_equipamento",
        "inventario.view_resumo_inventario",
        PERMISSAO_CADASTRAR_USUARIO,
        PERMISSAO_CONSULTAR_AUDITORIA,
    ),
    GRUPO_OPERADOR: ("inventario.view_equipamento",),
    GRUPO_PROFESSOR: (
        "inventario.view_equipamento",
        PERMISSAO_CRIAR_RESERVA,
        PERMISSAO_CONSULTAR_RESERVA,
        PERMISSAO_ALTERAR_RESERVA,
    ),
}

# A RN-18 diferencia o Superuser técnico do perfil funcional Administrador.
# Por isso, o Administrador deve pertencer exclusivamente ao seu grupo funcional.
def e_administrador_funcional(user):
    if not user.is_authenticated or user.is_superuser:
        return False

    grupos_do_usuario = set(user.groups.values_list("name", flat=True))
    return grupos_do_usuario == {GRUPO_ADMINISTRADOR}


def e_professor_funcional(user):
    if not user.is_authenticated or user.is_superuser:
        return False

    grupos_do_usuario = set(user.groups.values_list("name", flat=True))
    return grupos_do_usuario == {GRUPO_PROFESSOR}


def pode_cadastrar_usuario(user):
    return e_administrador_funcional(user) and user.has_perm(
        PERMISSAO_CADASTRAR_USUARIO
    )


def pode_consultar_auditoria(user):
    return e_administrador_funcional(user) and user.has_perm(
        PERMISSAO_CONSULTAR_AUDITORIA
    )
