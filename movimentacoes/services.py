from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, CharField, Count, Exists, Max, Min, OuterRef, Q, Value, When
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from inventario.models import Equipamento
from manutencoes.services import _abrir_manutencao_bloqueada
from reservas.models import Reserva
from reservas.services import _expirar_reserva_bloqueada
from usuarios.permissoes import pode_registrar_devolucao, pode_registrar_retirada, usuarios_funcionais_ativos

from .models import Movimentacao


def reservas_para_retirada(*, busca="", status=Reserva.Status.ATIVA):
    retiradas = Movimentacao.objects.filter(
        reserva_id=OuterRef("pk"), tipo=Movimentacao.Tipo.RETIRADA,
    )
    reservas = Reserva.objects.select_related("professor", "tipo_equipamento", "local").annotate(
        retirada_registrada=Exists(retiradas),
        nome_professor=Concat("professor__first_name", Value(" "), "professor__last_name"),
    )
    if status:
        reservas = reservas.filter(status=status)
    if busca:
        criterio = (
            Q(professor__username__icontains=busca) | Q(nome_professor__icontains=busca)
            | Q(tipo_equipamento__nome__icontains=busca) | Q(local__nome__icontains=busca)
            | Q(itens__equipamento__numero_patrimonio__icontains=busca)
        )
        if busca.isdecimal():
            criterio |= Q(pk=busca)
        reservas = reservas.filter(criterio).distinct()
    return reservas.order_by("inicio", "pk")


def registrar_retirada_reserva(*, operador, reserva_id, observacao=""):
    if not operador.is_authenticated:
        raise PermissionDenied
    operador_atual = get_user_model().objects.filter(pk=operador.pk).first()
    if operador_atual is None or not pode_registrar_retirada(operador_atual):
        raise PermissionDenied

    expirou = False
    movimentacoes = []
    with transaction.atomic():
        # O cancelamento e a expiração bloqueiam esta mesma linha antes de agir.
        try:
            reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
        except Reserva.DoesNotExist as erro:
            raise ValidationError("A reserva informada não existe.") from erro
        if reserva.status != Reserva.Status.ATIVA:
            raise ValidationError("Esta reserva está cancelada ou expirada e não pode ser retirada.")
        if Movimentacao.objects.filter(reserva=reserva, tipo=Movimentacao.Tipo.RETIRADA).exists():
            raise ValidationError("Esta reserva já possui retirada registrada.")
        agora = timezone.now()
        if agora < reserva.inicio:
            raise ValidationError("A retirada só pode ser registrada a partir do início da reserva.")
        if _expirar_reserva_bloqueada(reserva, agora):
            # Como no cancelamento, a expiração legítima persiste com sua auditoria.
            # A tentativa de retirada não grava movimentações nem altera unidades.
            expirou = True
        else:
            destinatario = usuarios_funcionais_ativos().filter(
                pk=reserva.professor_id, groups__name="Professor",
            ).first()
            if destinatario is None:
                raise ValidationError("O Professor desta reserva precisa estar ativo e possuir somente o perfil Professor.")
            ids = list(reserva.itens.select_for_update().order_by("pk").values_list("equipamento_id", flat=True))
            if not ids or len(ids) != reserva.quantidade or len(set(ids)) != len(ids):
                raise ValidationError("As unidades alocadas não correspondem à quantidade da reserva. Nenhuma alteração foi salva.")
            equipamentos = list(Equipamento.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            if len(equipamentos) != len(ids):
                raise ValidationError("Uma unidade alocada não está mais cadastrada.")
            for equipamento in equipamentos:
                if (
                    equipamento.tipo_id != reserva.tipo_equipamento_id
                    or equipamento.local_id != reserva.local_id
                    or not equipamento.ativo
                    or equipamento.situacao != Equipamento.Situacao.DISPONIVEL
                ):
                    raise ValidationError(
                        f"O patrimônio {equipamento.numero_patrimonio} está indisponível, inativo "
                        "ou não corresponde ao tipo/local da reserva. Nenhuma alteração foi salva."
                    )
            lote = uuid4()
            for equipamento in equipamentos:
                movimentacao = Movimentacao(
                    equipamento=equipamento, operador=operador_atual,
                    destinatario=destinatario, tipo=Movimentacao.Tipo.RETIRADA,
                    reserva=reserva, lote_retirada=lote, observacao=observacao,
                )
                movimentacao.full_clean()
                movimentacao.save()
                equipamento.situacao = Equipamento.Situacao.EM_USO
                equipamento.save(update_fields=("situacao", "data_atualizacao"))
                registrar_evento(
                    usuario=operador_atual, acao=AcaoAuditoria.RETIRADA_REGISTRADA,
                    resultado=RegistroAuditoria.Resultado.SUCESSO,
                    entidade="movimentacoes.Movimentacao", entidade_id=movimentacao.pk,
                )
                movimentacoes.append(movimentacao)
    if expirou:
        raise ValidationError("Esta reserva expirou após os 30 minutos de tolerância. Nenhum equipamento foi retirado.")
    return movimentacoes


def consultar_historico(filtros):
    movimentacoes = Movimentacao.objects.select_related(
        "equipamento__tipo", "operador", "destinatario", "retirada_origem", "manutencao",
    ).prefetch_related("devolucoes").order_by("-data_hora", "-pk")
    if filtros.get("busca"):
        busca = filtros["busca"]
        movimentacoes = movimentacoes.annotate(
            nome_operador=Concat("operador__first_name", Value(" "), "operador__last_name"),
            nome_destinatario=Concat("destinatario__first_name", Value(" "), "destinatario__last_name"),
        ).filter(
            Q(equipamento__numero_patrimonio__icontains=busca) | Q(equipamento__tipo__nome__icontains=busca)
            | Q(operador__username__icontains=busca) | Q(destinatario__username__icontains=busca)
            | Q(nome_operador__icontains=busca) | Q(nome_destinatario__icontains=busca)
        )
    if filtros.get("tipo"):
        movimentacoes = movimentacoes.filter(tipo=filtros["tipo"])
    if filtros.get("reserva"):
        movimentacoes = movimentacoes.filter(reserva_id=filtros["reserva"])
    if filtros.get("retirada"):
        movimentacoes = movimentacoes.filter(
            Q(pk=filtros["retirada"], tipo=Movimentacao.Tipo.RETIRADA)
            | Q(retirada_origem_id=filtros["retirada"]),
        )
    if filtros.get("inicio"):
        movimentacoes = movimentacoes.filter(data_hora__date__gte=filtros["inicio"])
    if filtros.get("fim"):
        movimentacoes = movimentacoes.filter(data_hora__date__lte=filtros["fim"])
    return movimentacoes


def equipamentos_disponiveis_para_retirada(*, tipo_equipamento, local=None):
    equipamentos = Equipamento.objects.filter(
        tipo=tipo_equipamento, ativo=True,
        situacao=Equipamento.Situacao.DISPONIVEL,
    )
    if local is not None:
        equipamentos = equipamentos.filter(local=local)
    return equipamentos.order_by("numero_patrimonio")


def registrar_retirada_sem_reserva(
    *, operador, tipo_equipamento, local, quantidade, equipamentos,
    destinatario, observacao="",
):
    if not operador.is_authenticated:
        raise PermissionDenied
    operador_atual = get_user_model().objects.filter(pk=operador.pk).first()
    if operador_atual is None or not pode_registrar_retirada(operador_atual):
        raise PermissionDenied

    ids = [equipamento.pk for equipamento in equipamentos]
    if quantidade < 1 or len(ids) != quantidade or len(set(ids)) != quantidade:
        raise ValidationError({
            "equipamentos": "Selecione exatamente a quantidade informada, sem repetir patrimônios.",
        })

    with transaction.atomic():
        # Ordem estável evita bloqueios cruzados entre lotes que compartilham unidades.
        # Revalidar os mesmos IDs conferidos evita substituições silenciosas.
        bloqueados = list(
            Equipamento.objects.select_for_update()
            .filter(pk__in=ids).order_by("pk")
        )
        if len(bloqueados) != quantidade:
            raise ValidationError({
                "equipamentos": "Um dos equipamentos não está mais cadastrado. Revise o lote.",
            })
        for equipamento in bloqueados:
            if equipamento.tipo_id != tipo_equipamento.pk or equipamento.local_id != local.pk:
                raise ValidationError({
                    "equipamentos": "Todos os patrimônios devem pertencer ao tipo/modelo e local selecionados.",
                })
            if not equipamento.ativo or equipamento.situacao != Equipamento.Situacao.DISPONIVEL:
                raise ValidationError({
                    "equipamentos": (
                        f"O equipamento {equipamento.numero_patrimonio} está inativo ou "
                        "não está disponível para retirada. Revise o lote."
                    ),
                })

        try:
            destinatario_atual = usuarios_funcionais_ativos().get(pk=destinatario.pk)
        except get_user_model().DoesNotExist as erro:
            raise ValidationError({
                "destinatario": "Selecione um destinatário ativo com um único perfil funcional.",
            }) from erro

        lote_retirada = uuid4()
        movimentacoes = []
        for equipamento in bloqueados:
            movimentacao = Movimentacao(
                equipamento=equipamento, operador=operador_atual,
                destinatario=destinatario_atual, tipo=Movimentacao.Tipo.RETIRADA,
                observacao=observacao,
                lote_retirada=lote_retirada,
            )
            movimentacao.full_clean()
            movimentacao.save()
            equipamento.situacao = Equipamento.Situacao.EM_USO
            equipamento.save(update_fields=("situacao", "data_atualizacao"))
            registrar_evento(
                usuario=operador_atual, acao=AcaoAuditoria.RETIRADA_REGISTRADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="movimentacoes.Movimentacao", entidade_id=movimentacao.pk,
            )
            movimentacoes.append(movimentacao)

    return movimentacoes


def _retiradas_com_devolucao():
    devolucoes = Movimentacao.objects.filter(
        tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem_id=OuterRef("pk"),
    )
    return (
        Movimentacao.objects.filter(tipo=Movimentacao.Tipo.RETIRADA)
        .annotate(devolvida=Exists(devolucoes))
        .select_related("equipamento__tipo", "equipamento__local", "destinatario", "operador")
        .order_by("data_hora", "pk")
    )


def retiradas_abertas():
    return _retiradas_com_devolucao().filter(devolvida=False)


def retiradas_do_grupo(retirada):
    retiradas = _retiradas_com_devolucao()
    if retirada.reserva_id is not None:
        return retiradas.filter(reserva_id=retirada.reserva_id)
    if retirada.lote_retirada is not None:
        return retiradas.filter(lote_retirada=retirada.lote_retirada, reserva__isnull=True)
    # Registros antigos não permitem deduzir um lote por proximidade de horários.
    return retiradas.filter(
        lote_retirada__isnull=True, reserva__isnull=True,
        destinatario_id=retirada.destinatario_id,
    )


def grupos_devolucao(busca=""):
    retiradas = _retiradas_com_devolucao().annotate(chave_grupo=Case(
        When(reserva__isnull=False, then=Concat(Value("reserva:"), Cast("reserva_id", CharField()))),
        When(lote_retirada__isnull=False, then=Concat(Value("lote:"), Cast("lote_retirada", CharField()))),
        default=Concat(Value("anteriores:"), Cast("destinatario_id", CharField())),
        output_field=CharField(),
    ))
    if busca:
        correspondencias = retiradas.annotate(nome_destinatario=Concat(
            "destinatario__first_name", Value(" "), "destinatario__last_name",
        )).filter(devolvida=False).filter(
            Q(equipamento__numero_patrimonio__icontains=busca)
            | Q(equipamento__tipo__nome__icontains=busca)
            | Q(destinatario__username__icontains=busca)
            | Q(nome_destinatario__icontains=busca)
        ).order_by().values("chave_grupo")
        # A busca localiza o grupo; não reduz silenciosamente as suas unidades.
        retiradas = retiradas.filter(chave_grupo__in=correspondencias)
    return retiradas.order_by().values("chave_grupo").annotate(
        retirada_id=Min("pk"), total=Count("pk"),
        pendentes=Count("pk", filter=Q(devolvida=False)),
        inicio=Min("data_hora"), fim=Max("data_hora"),
        tipos=Count("equipamento__tipo_id", distinct=True),
    ).filter(pendentes__gt=0).order_by("inicio", "retirada_id")


def registrar_devolucoes(*, operador, retirada_id, retiradas_ids, observacao="", problemas=None):
    if not operador.is_authenticated:
        raise PermissionDenied
    operador_atual = get_user_model().objects.filter(pk=operador.pk).first()
    if operador_atual is None or not pode_registrar_devolucao(operador_atual):
        raise PermissionDenied

    ids = list(retiradas_ids)
    if not ids or len(ids) != len(set(ids)):
        raise ValidationError("Selecione pelo menos uma unidade, sem repetir patrimônios.")
    problemas = {} if problemas is None else problemas
    if not set(problemas).issubset(ids):
        raise ValidationError("Informe problemas somente para os patrimônios recebidos.")
    if any(not descricao.strip() for descricao in problemas.values()):
        raise ValidationError("Descreva o problema de cada patrimônio encaminhado para manutenção.")
    with transaction.atomic():
        # Ordem estável também quando dois lotes selecionam subconjuntos diferentes.
        # Sem joins anuláveis no SELECT FOR UPDATE do PostgreSQL.
        bloqueadas = list(Movimentacao.objects.select_for_update().filter(
            pk__in=set(ids) | {retirada_id}, tipo=Movimentacao.Tipo.RETIRADA,
        ).order_by("pk"))
        retirada = next((item for item in bloqueadas if item.pk == retirada_id), None)
        if retirada is None:
            raise ValidationError("A retirada informada não existe.")
        selecionadas = [item for item in bloqueadas if item.pk in ids]
        if len(selecionadas) != len(ids) or retiradas_do_grupo(retirada).filter(pk__in=ids).count() != len(ids):
            raise ValidationError("Selecione somente unidades desta retirada ou reserva. Nenhuma alteração foi salva.")
        if Movimentacao.objects.filter(
            tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem_id__in=ids,
        ).exists():
            raise ValidationError("Esta retirada já foi devolvida. Nenhuma alteração foi salva.")

        equipamentos = {
            item.pk: item for item in Equipamento.objects.select_for_update().filter(
                pk__in=[item.equipamento_id for item in selecionadas],
            ).order_by("pk")
        }
        devolucoes = []
        for origem in selecionadas:
            equipamento = equipamentos[origem.equipamento_id]
            devolucao = Movimentacao(
                tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem=origem,
                equipamento=equipamento, destinatario_id=origem.destinatario_id,
                operador=operador_atual, reserva_id=origem.reserva_id, observacao=observacao,
                lote_retirada=origem.lote_retirada,
            )
            devolucao.full_clean()
            devolucao.save()
            # RN-05/RN-06/RN-10: devolver não libera manutenção nem reativa um item.
            if origem.pk in problemas:
                _abrir_manutencao_bloqueada(
                    equipamento=equipamento, usuario=operador_atual,
                    descricao_problema=problemas[origem.pk], devolucao=devolucao,
                )
            elif equipamento.ativo and equipamento.situacao != Equipamento.Situacao.MANUTENCAO:
                equipamento.situacao = Equipamento.Situacao.DISPONIVEL
                equipamento.save(update_fields=("situacao", "data_atualizacao"))
            registrar_evento(
                usuario=operador_atual, acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="movimentacoes.Movimentacao", entidade_id=devolucao.pk,
            )
            devolucoes.append(devolucao)
    return devolucoes


def registrar_devolucao(*, operador, retirada_id, observacao="", descricao_problema=None):
    return registrar_devolucoes(
        operador=operador, retirada_id=retirada_id,
        retiradas_ids=[retirada_id], observacao=observacao,
        problemas=None if descricao_problema is None else {retirada_id: descricao_problema},
    )[0]
