from django.contrib.auth import get_user_model
from django.db.models import Count


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
PERMISSAO_REGISTRAR_RETIRADA = "movimentacoes.add_movimentacao"

PERMISSOES_POR_GRUPO = {
    GRUPO_ADMINISTRADOR: (
        "inventario.view_equipamento",
        "inventario.add_equipamento",
        "inventario.change_equipamento",
        "inventario.delete_equipamento",
        "inventario.view_resumo_inventario",
        PERMISSAO_CADASTRAR_USUARIO,
        PERMISSAO_CONSULTAR_AUDITORIA,
        "movimentacoes.view_movimentacao",
        "pedagogico.view_turma",
        "pedagogico.add_turma",
        "pedagogico.change_turma",
        "pedagogico.view_disciplina",
        "pedagogico.add_disciplina",
        "pedagogico.change_disciplina",
        "pedagogico.view_atividadepedagogica",
        "pedagogico.add_atividadepedagogica",
        "pedagogico.change_atividadepedagogica",
    ),
    GRUPO_OPERADOR: (
        "inventario.view_equipamento",
        PERMISSAO_REGISTRAR_RETIRADA,
        "movimentacoes.view_movimentacao",
    ),
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


def e_operador_funcional(user):
    if not user.is_authenticated or not user.is_active or user.is_superuser:
        return False

    return set(user.groups.values_list("name", flat=True)) == {GRUPO_OPERADOR}


def pode_registrar_retirada(user):
    return e_operador_funcional(user) and user.has_perm(PERMISSAO_REGISTRAR_RETIRADA)


def pode_registrar_devolucao(user):
    return e_operador_funcional(user) and user.has_perm("movimentacoes.add_movimentacao")


def pode_consultar_historico(user):
    return (
        user.is_authenticated and user.is_active and not user.is_superuser
        and (e_administrador_funcional(user) or e_operador_funcional(user))
        and user.has_perm("movimentacoes.view_movimentacao")
    )


def usuarios_funcionais_ativos():
    # Conta com grupos adicionais também viola a atribuição exclusiva da RN-18.
    return (
        get_user_model().objects.filter(is_active=True, is_superuser=False)
        .annotate(total_grupos=Count("groups"))
        .filter(total_grupos=1, groups__name__in=GRUPOS_FUNCIONAIS)
        .order_by("first_name", "last_name", "username")
    )


def pode_cadastrar_usuario(user):
    return e_administrador_funcional(user) and user.has_perm(
        PERMISSAO_CADASTRAR_USUARIO
    )


def pode_gerenciar_cadastro_pedagogico(user, modelo, acao="view"):
    return (
        user.is_active
        and e_administrador_funcional(user)
        and user.has_perm(f"pedagogico.{acao}_{modelo}")
    )


def pode_consultar_auditoria(user):
    return e_administrador_funcional(user) and user.has_perm(
        PERMISSAO_CONSULTAR_AUDITORIA
    )
