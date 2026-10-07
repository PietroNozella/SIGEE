from .permissoes import (
    e_operador_funcional,
    e_professor_funcional,
    pode_cadastrar_usuario,
    pode_consultar_auditoria,
    pode_registrar_retirada,
    pode_registrar_devolucao,
    pode_consultar_historico,
    pode_gerenciar_cadastro_pedagogico,
    pode_gerenciar_manutencao,
)


def permissoes_funcionais(request):
    return {
        "e_operador": e_operador_funcional(request.user),
        "e_professor": e_professor_funcional(request.user),
        "pode_cadastrar_usuario": pode_cadastrar_usuario(request.user),
        "pode_consultar_auditoria": pode_consultar_auditoria(request.user),
        "pode_registrar_retirada": pode_registrar_retirada(request.user),
        "pode_registrar_devolucao": pode_registrar_devolucao(request.user),
        "pode_consultar_historico": pode_consultar_historico(request.user),
        "pode_consultar_manutencoes": pode_gerenciar_manutencao(request.user),
        "pode_abrir_manutencao": pode_gerenciar_manutencao(request.user, "add"),
        "pode_alterar_manutencao": pode_gerenciar_manutencao(request.user, "change"),
        "pode_consultar_turmas": pode_gerenciar_cadastro_pedagogico(request.user, "turma"),
        "pode_consultar_disciplinas": pode_gerenciar_cadastro_pedagogico(request.user, "disciplina"),
        "pode_consultar_atividades": pode_gerenciar_cadastro_pedagogico(request.user, "atividadepedagogica"),
    }
