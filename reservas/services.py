from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento, Local, TipoEquipamento
from usuarios.permissoes import e_professor_funcional

from .models import Reserva, ReservaEquipamento, SubstituicaoReserva


def _substituir_unidades_bloqueadas(reserva, usuario):
    """Exige bloqueios do tipo e da reserva, nesta ordem, na transação chamadora."""
    from movimentacoes.models import Movimentacao

    agora = timezone.now()
    if reserva.status != Reserva.Status.ATIVA or reserva.fim <= agora:
        return 0
    if reserva.inicio + Reserva.TOLERANCIA_RETIRADA <= agora and not _possui_retirada_vinculada(reserva):
        return 0
    entregues = Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA").values("equipamento_id")
    afetados = list(reserva.itens.select_related("equipamento").filter(
        equipamento__situacao=Equipamento.Situacao.MANUTENCAO,
    ).exclude(equipamento_id__in=entregues).order_by("pk"))
    trocas = 0
    for item in afetados:
        manutencao = item.equipamento.manutencoes.order_by("-pk").first()
        if manutencao is None:
            continue
        substituto = _equipamentos_disponiveis(
            reserva.tipo_equipamento, reserva.local, reserva.inicio, reserva.fim, bloquear=True,
        ).exclude(pk__in=entregues).exclude(pk__in=reserva.itens.values("equipamento_id")).first()
        if substituto is None:
            continue
        troca = SubstituicaoReserva.objects.create(
            reserva=reserva, equipamento_anterior=item.equipamento,
            equipamento_substituto=substituto, manutencao=manutencao, registrado_por=usuario,
        )
        item.equipamento = substituto
        item.save(update_fields=("equipamento",))
        registrar_evento(
            usuario=usuario, acao=AcaoAuditoria.EQUIPAMENTO_RESERVADO_SUBSTITUIDO,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="reservas.SubstituicaoReserva", entidade_id=troca.pk,
        )
        trocas += 1
    return trocas


@transaction.atomic
def substituir_equipamentos_em_manutencao(*, reserva_id, usuario):
    from usuarios.permissoes import pode_registrar_retirada

    atual = get_user_model().objects.filter(pk=usuario.pk).first() if usuario.is_authenticated else None
    if atual is None or not pode_registrar_retirada(atual):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    tipo_id = Reserva.objects.values_list("tipo_equipamento_id", flat=True).get(pk=reserva_id)
    TipoEquipamento.objects.select_for_update().get(pk=tipo_id)
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    return _substituir_unidades_bloqueadas(reserva, atual)


def substituir_reservas_do_equipamento(equipamento, usuario):
    """Chamado na abertura da manutenção, com o tipo já bloqueado."""
    reservas = Reserva.objects.filter(
        pk__in=ReservaEquipamento.objects.filter(equipamento=equipamento).values("reserva_id"),
        status=Reserva.Status.ATIVA, fim__gt=timezone.now(),
    ).order_by("inicio", "pk")
    for reserva in reservas.select_for_update():
        _substituir_unidades_bloqueadas(reserva, usuario)


def resumo_entrega(reserva):
    from movimentacoes.models import Movimentacao

    retiradas = Movimentacao.objects.filter(reserva=reserva, tipo="RETIRADA")
    ids_entregues = set(retiradas.values_list("equipamento_id", flat=True))
    unidades = list(reserva.itens.select_related("equipamento__tipo", "equipamento__local").order_by("equipamento__numero_patrimonio"))
    sem_custodia = set(Equipamento.objects.filter(
        pk__in=[item.equipamento_id for item in unidades],
    ).sem_retirada_aberta().values_list("pk", flat=True))
    aptas = 0
    for item in unidades:
        equipamento = item.equipamento
        item.ja_entregue = equipamento.pk in ids_entregues
        item.apta_para_entrega = (
            not item.ja_entregue and equipamento.ativo
            and equipamento.pk in sem_custodia
            and equipamento.situacao == Equipamento.Situacao.DISPONIVEL
            and equipamento.tipo_id == reserva.tipo_equipamento_id and equipamento.local_id == reserva.local_id
        )
        aptas += int(item.apta_para_entrega)
    saldo = max(0, reserva.quantidade - len(ids_entregues))
    encerrado = reserva.fim <= timezone.now()
    return {
        "unidades": unidades, "entregues": len(ids_entregues), "aptas": aptas,
        "saldo": saldo, "pendentes": 0 if encerrado else saldo,
        "nao_atendidas": saldo if encerrado else 0, "prazo_encerrado": encerrado,
        "devolucoes_pendentes": retiradas.filter(devolucoes__isnull=True).count(),
        "entrega_parcial": aptas > 0 and aptas < saldo,
        "tem_indisponiveis": aptas < saldo,
    }


def _equipamentos_disponiveis(
    tipo_equipamento,
    local,
    inicio,
    fim,
    *,
    bloquear=False,
):
    conflitos = ReservaEquipamento.objects.filter(
        equipamento_id=OuterRef("pk"),
        reserva__status=Reserva.Status.ATIVA,
        reserva_id__in=Reserva.objects.com_etapa().filter(etapa__in=("AGUARDANDO", "EM_USO")),
        reserva__inicio__lt=fim,
        reserva__fim__gt=inicio,
    )
    equipamentos = (
        Equipamento.objects.filter(
            tipo=tipo_equipamento,
            local=local,
            ativo=True,
            situacao=Equipamento.Situacao.DISPONIVEL,
        ).sem_retirada_aberta()
        .annotate(possui_conflito=Exists(conflitos))
        .filter(possui_conflito=False)
        .order_by("numero_patrimonio")
    )
    if bloquear:
        equipamentos = equipamentos.select_for_update()
    return equipamentos


def _possui_retirada_vinculada(reserva):
    from movimentacoes.models import Movimentacao

    return Movimentacao.objects.filter(
        reserva=reserva,
        tipo=Movimentacao.Tipo.RETIRADA,
    ).exists()


def _expirar_reserva_bloqueada(reserva, agora):
    if reserva.status != Reserva.Status.ATIVA:
        return False
    if reserva.inicio + Reserva.TOLERANCIA_RETIRADA > agora:
        return False
    if _possui_retirada_vinculada(reserva):
        return False

    reserva.status = Reserva.Status.EXPIRADA
    reserva.save(update_fields=("status", "data_atualizacao"))

    if not RegistroAuditoria.objects.filter(
        acao=AcaoAuditoria.RESERVA_EXPIRADA,
        entidade="reservas.Reserva",
        entidade_id=str(reserva.pk),
    ).exists():
        registrar_evento(
            usuario=None,
            acao=AcaoAuditoria.RESERVA_EXPIRADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="reservas.Reserva",
            entidade_id=reserva.pk,
        )

    return True


def expirar_reservas_vencidas(agora=None):
    from movimentacoes.models import Movimentacao

    agora = agora or timezone.now()
    limite = agora - Reserva.TOLERANCIA_RETIRADA
    retiradas = Movimentacao.objects.filter(
        reserva_id=OuterRef("pk"), tipo=Movimentacao.Tipo.RETIRADA,
    )
    candidatos = list(
        Reserva.objects.filter(
            status=Reserva.Status.ATIVA,
            inicio__lte=limite,
        ).filter(~Exists(retiradas)).values_list("pk", flat=True)
    )

    expiradas = 0
    for reserva_id in candidatos:
        with transaction.atomic():
            try:
                reserva = Reserva.objects.select_for_update().get(
                    pk=reserva_id,
                    status=Reserva.Status.ATIVA,
                )
            except Reserva.DoesNotExist:
                continue
            if _expirar_reserva_bloqueada(reserva, agora):
                expiradas += 1

    return expiradas


def consultar_disponibilidade(*, professor, tipo_equipamento, local, inicio, fim):
    expirar_reservas_vencidas()
    reserva = Reserva(
        professor=professor,
        tipo_equipamento=tipo_equipamento,
        local=local,
        quantidade=1,
        inicio=inicio,
        fim=fim,
    )
    reserva.full_clean()
    return _equipamentos_disponiveis(
        tipo_equipamento,
        local,
        inicio,
        fim,
    ).count()


def criar_reserva(
    *,
    professor,
    tipo_equipamento,
    local,
    quantidade,
    inicio,
    fim,
    turma=None,
    disciplina=None,
    atividade=None,
    observacao="",
):
    if not e_professor_funcional(professor):
        raise ValidationError(
            {
                "professor": (
                    "Somente um usuário com perfil Professor pode criar uma reserva."
                )
            }
        )
    if getattr(tipo_equipamento, "pk", None) is None:
        raise ValidationError(
            {"tipo_equipamento": "Selecione um tipo de equipamento cadastrado."}
        )
    if getattr(local, "pk", None) is None:
        raise ValidationError({"local": "Selecione um local cadastrado."})

    expirar_reservas_vencidas()

    reserva = Reserva(
        professor=professor,
        tipo_equipamento=tipo_equipamento,
        local=local,
        quantidade=quantidade,
        inicio=inicio,
        fim=fim,
    )
    reserva.full_clean()

    with transaction.atomic():
        # A desativação bloqueia esta mesma conta antes de conferir suas reservas.
        professor_atual = get_user_model().objects.select_for_update(no_key=True).get(pk=professor.pk)
        if not e_professor_funcional(professor_atual):
            raise ValidationError({"professor": "O Professor precisa estar ativo para criar uma reserva."})
        reserva.professor = professor_atual
        from pedagogico.services import validar_contexto_pedagogico

        escolhas = validar_contexto_pedagogico(turma=turma, disciplina=disciplina, atividade=atividade)
        for campo, registro in escolhas.items():
            setattr(reserva, campo, registro)
        reserva.observacao_pedagogica = observacao.strip()
        try:
            tipo_bloqueado = TipoEquipamento.objects.select_for_update().get(
                pk=tipo_equipamento.pk,
                ativo=True,
            )
        except TipoEquipamento.DoesNotExist as erro:
            raise ValidationError(
                {
                    "tipo_equipamento": (
                        "O tipo de equipamento selecionado não está disponível."
                    )
                }
            ) from erro

        try:
            local_bloqueado = Local.objects.select_for_update().get(
                pk=local.pk,
                ativo=True,
            )
        except Local.DoesNotExist as erro:
            raise ValidationError(
                {"local": "O local selecionado não está disponível."}
            ) from erro

        reserva.tipo_equipamento = tipo_bloqueado
        reserva.local = local_bloqueado
        reserva.full_clean()
        equipamentos = list(
            _equipamentos_disponiveis(
                tipo_bloqueado,
                local_bloqueado,
                inicio,
                fim,
                bloquear=True,
            )[:quantidade]
        )
        if len(equipamentos) < quantidade:
            raise ValidationError(
                {
                    "quantidade": (
                        f"Há somente {len(equipamentos)} unidade(s) disponível(is) "
                        "para o período informado."
                    )
                }
            )

        reserva.save()
        ReservaEquipamento.objects.bulk_create(
            ReservaEquipamento(reserva=reserva, equipamento=equipamento)
            for equipamento in equipamentos
        )

        registrar_evento(
            usuario=professor,
            acao=AcaoAuditoria.RESERVA_CRIADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="reservas.Reserva",
            entidade_id=reserva.pk,
        )

    return reserva


def permite_cancelamento_operacional(reserva):
    return (
        reserva.status == Reserva.Status.ATIVA
        and timezone.now() < reserva.inicio + Reserva.TOLERANCIA_RETIRADA
        and not _possui_retirada_vinculada(reserva)
    )


def _validar_cancelamento_bloqueado(reserva, agora):
    if reserva.status == Reserva.Status.CANCELADA:
        raise ValidationError("Esta reserva já está cancelada.")
    if reserva.status == Reserva.Status.EXPIRADA:
        raise ValidationError("Esta reserva já expirou e não pode ser cancelada.")
    if reserva.status != Reserva.Status.ATIVA:
        raise ValidationError("Esta reserva não está ativa.")
    if _expirar_reserva_bloqueada(reserva, agora):
        return False
    if _possui_retirada_vinculada(reserva):
        raise ValidationError("Esta reserva já possui retirada registrada e não pode ser cancelada.")
    return True


def cancelar_reserva_operacional(*, operador, reserva_id, motivo, desistencia_confirmada):
    from django.core.exceptions import PermissionDenied
    from usuarios.permissoes import pode_cancelar_reserva_operacional

    def operador_autorizado():
        atual = get_user_model().objects.filter(pk=operador.pk).first() if operador.is_authenticated else None
        if atual is None or not pode_cancelar_reserva_operacional(atual):
            raise PermissionDenied
        return atual

    operador_autorizado()
    motivo = motivo.strip()
    if not motivo:
        raise ValidationError({"motivo": "Informe o motivo da desistência comunicada pelo Professor."})
    if desistencia_confirmada is not True:
        raise ValidationError({"desistencia_confirmada": "Confirme que o Professor comunicou a desistência da reserva."})

    with transaction.atomic():
        try:
            reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
        except Reserva.DoesNotExist as erro:
            raise ValidationError("A reserva informada não existe.") from erro
        operador_atual = operador_autorizado()
        agora = timezone.now()
        cancelavel = _validar_cancelamento_bloqueado(reserva, agora)
        if cancelavel:
            reserva.status = Reserva.Status.CANCELADA
            reserva.motivo_cancelamento = motivo
            reserva.cancelada_por = operador_atual
            reserva.data_cancelamento = agora
            reserva.save(update_fields=(
                "status", "motivo_cancelamento", "cancelada_por", "data_cancelamento", "data_atualizacao",
            ))
            registrar_evento(
                usuario=operador_atual, acao=AcaoAuditoria.RESERVA_CANCELADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="reservas.Reserva", entidade_id=reserva.pk,
            )
    if not cancelavel:
        raise ValidationError("Esta reserva já expirou e não pode ser cancelada.")
    return reserva


def cancelar_reserva(*, professor, reserva):
    professor = get_user_model().objects.get(pk=professor.pk)
    if not e_professor_funcional(professor):
        raise ValidationError(
            "Somente um usuário com perfil Professor pode cancelar uma reserva."
        )
    if reserva.professor_id != professor.pk:
        raise ValidationError("A reserva só pode ser cancelada pelo próprio Professor.")

    expirou_durante_cancelamento = False
    with transaction.atomic():
        reserva_bloqueada = Reserva.objects.select_for_update().get(
            pk=reserva.pk,
            professor=professor,
        )
        if not _validar_cancelamento_bloqueado(reserva_bloqueada, timezone.now()):
            expirou_durante_cancelamento = True
        else:
            reserva_bloqueada.status = Reserva.Status.CANCELADA
            reserva_bloqueada.full_clean()
            reserva_bloqueada.save(update_fields=("status", "data_atualizacao"))

            registrar_evento(
                usuario=professor,
                acao=AcaoAuditoria.RESERVA_CANCELADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="reservas.Reserva",
                entidade_id=reserva_bloqueada.pk,
            )

    if expirou_durante_cancelamento:
        raise ValidationError("Esta reserva já expirou e não pode ser cancelada.")

    return reserva_bloqueada
