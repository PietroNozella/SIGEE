GRUPO_ADMINISTRADOR = "Administrador"
GRUPO_OPERADOR = "Operador"
GRUPO_PROFESSOR = "Professor"

GRUPOS_FUNCIONAIS = (
    GRUPO_ADMINISTRADOR,
    GRUPO_OPERADOR,
    GRUPO_PROFESSOR,
)

PERMISSAO_CADASTRAR_USUARIO = "auth.add_user"

PERMISSOES_POR_GRUPO = {
    GRUPO_ADMINISTRADOR: (
        "inventario.view_equipamento",
        "inventario.add_equipamento",
        "inventario.change_equipamento",
        "inventario.delete_equipamento",
        "inventario.view_resumo_inventario",
        PERMISSAO_CADASTRAR_USUARIO,
    ),
    GRUPO_OPERADOR: ("inventario.view_equipamento",),
    GRUPO_PROFESSOR: ("inventario.view_equipamento",),
}


def pode_cadastrar_usuario(user):
    if not user.is_authenticated or user.is_superuser:
        return False

    if not user.has_perm(PERMISSAO_CADASTRAR_USUARIO):
        return False

    grupos_do_usuario = set(user.groups.values_list("name", flat=True))
    return grupos_do_usuario == {GRUPO_ADMINISTRADOR}
