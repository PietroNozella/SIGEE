from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from reservas.models import Reserva
from reservas.services import _possui_retirada_vinculada
from usuarios.permissoes import pode_configurar_calendario

from .models import AlteracaoCalendario, FechamentoEscolar, ReservaAfetadaFechamento
from .services import bloquear_calendario


def _administrador_atual(usuario):
    atual = get_user_model().objects.filter(pk=usuario.pk).first() if usuario.is_authenticated else None
    if atual is None or not pode_configurar_calendario(atual):
        raise PermissionDenied
    return atual


def _validar_versao(calendario, versao):
    if calendario.versao != versao:
        raise ValidationError("O calendário mudou. Reabra a página e confira a configuração atual.")


def _registrar_alteracao(calendario, *, usuario, motivo, titulo, anterior, novo):
    calendario.versao += 1
    calendario.save(update_fields=["versao"])
    alteracao = AlteracaoCalendario.objects.create(
        usuario=usuario, motivo=motivo, versao=calendario.versao,
        anterior={"titulo": titulo, "resumo": anterior}, novo={"titulo": titulo, "resumo": novo},
    )
    registrar_evento(
        usuario=usuario, acao=AcaoAuditoria.CALENDARIO_ALTERADO, resultado=RegistroAuditoria.Resultado.SUCESSO,
        entidade="calendario.AlteracaoCalendario", entidade_id=alteracao.pk,
    )
    return alteracao


@transaction.atomic
def registrar_fechamento(*, usuario, data, motivo, versao):
    calendario = bloquear_calendario()
    atual = _administrador_atual(usuario)
    _validar_versao(calendario, versao)
    agora = timezone.now()
    if data < timezone.localdate(agora):
        raise ValidationError("Escolha hoje ou uma data futura para o fechamento.")
    if not motivo.strip():
        raise ValidationError("Informe o motivo do fechamento.")
    if FechamentoEscolar.objects.filter(data=data, reabertura__isnull=True).exists():
        raise ValidationError("Já existe um fechamento ativo para essa data.")

    inicio = timezone.make_aware(datetime.combine(data, time.min))
    fim = inicio + timedelta(days=1)
    # O calendário serializa novos agendamentos. As reservas serializam entregas,
    # cancelamentos e expirações, na mesma ordem adotada pela manutenção.
    bloqueadas = list(
        Reserva.objects.filter(status=Reserva.Status.ATIVA, inicio__lt=fim, fim__gt=max(inicio, agora))
        .order_by("inicio", "pk").select_for_update().values_list("pk", flat=True)
    )
    # Uma entrega pode ter terminado enquanto aguardávamos a linha da reserva.
    # Leia o saldo em uma nova consulta, já com todos os bloqueios adquiridos.
    afetadas = list(
        Reserva.objects.com_etapa().filter(pk__in=bloqueadas, tem_entrega_pendente=True)
        .filter(Q(tem_retirada=True) | Q(inicio__gt=agora - Reserva.TOLERANCIA_RETIRADA))
        .values_list("pk", flat=True)
    )
    alteracao = _registrar_alteracao(
        calendario, usuario=atual, motivo=motivo.strip(), titulo=f"Fechamento da escola · {data:%d/%m/%Y}",
        anterior="Funcionamento conforme o calendário", novo="Fechamento de dia inteiro",
    )
    fechamento = FechamentoEscolar.objects.create(data=data, abertura=alteracao)
    ReservaAfetadaFechamento.objects.bulk_create(
        ReservaAfetadaFechamento(fechamento=fechamento, reserva_id=reserva_id) for reserva_id in afetadas
    )
    return fechamento


@transaction.atomic
def reabrir_fechamento(*, usuario, fechamento_id, motivo, versao):
    calendario = bloquear_calendario()
    atual = _administrador_atual(usuario)
    _validar_versao(calendario, versao)
    fechamento = FechamentoEscolar.objects.get(pk=fechamento_id)
    if fechamento.reabertura_id or fechamento.data < timezone.localdate():
        raise ValidationError("Somente um fechamento ativo para hoje ou uma data futura pode ser retirado.")
    if not motivo.strip():
        raise ValidationError("Informe o motivo da reabertura.")
    fechamento.reabertura = _registrar_alteracao(
        calendario, usuario=atual, motivo=motivo.strip(), titulo=f"Reabertura da escola · {fechamento.data:%d/%m/%Y}",
        anterior="Fechamento de dia inteiro", novo="Funcionamento conforme o calendário",
    )
    fechamento.save(update_fields=["reabertura"])
    return fechamento


@transaction.atomic
def configurar_excecao_fechamento(*, usuario, permite_manter, motivo, versao):
    calendario = bloquear_calendario()
    atual = _administrador_atual(usuario)
    _validar_versao(calendario, versao)
    if not motivo.strip():
        raise ValidationError("Informe o motivo da alteração da política.")
    rotulos = {False: "Cancelamento institucional", True: "Cancelamento ou autorização excepcional para manter"}
    anterior = rotulos[calendario.permite_manter_em_fechamento]
    calendario.permite_manter_em_fechamento = permite_manter
    calendario.save(update_fields=["permite_manter_em_fechamento"])
    return _registrar_alteracao(
        calendario, usuario=atual, motivo=motivo.strip(), titulo="Política de fechamento da escola",
        anterior=anterior, novo=rotulos[permite_manter],
    )


def pendencias_de_fechamento():
    return ReservaAfetadaFechamento.objects.filter(
        decisao=ReservaAfetadaFechamento.Decisao.PENDENTE, fechamento__reabertura__isnull=True,
    )


def historico_fechamentos_reserva(reserva):
    return reserva.impactos_fechamento.select_related(
        "fechamento__abertura", "fechamento__reabertura", "decidido_por",
    ).order_by("-fechamento__data", "-pk")


def validar_entrega_em_fechamento(reserva):
    if pendencias_de_fechamento().filter(reserva=reserva).exists():
        raise ValidationError("A entrega está suspensa por fechamento da escola, aguardando decisão do Administrador.")


@transaction.atomic
def decidir_reserva_afetada(*, usuario, impacto_id, decisao, motivo, atendimento_confirmado=False):
    calendario = bloquear_calendario()
    atual = _administrador_atual(usuario)
    impacto = ReservaAfetadaFechamento.objects.select_related("fechamento").get(pk=impacto_id)
    reserva = Reserva.objects.select_for_update().get(pk=impacto.reserva_id)
    opcoes = ReservaAfetadaFechamento.Decisao
    if impacto.fechamento.reabertura_id or impacto.decisao != opcoes.PENDENTE or reserva.status != Reserva.Status.ATIVA:
        raise ValidationError("Esta reserva já foi resolvida ou deixou de ser afetada pelo fechamento.")
    if not motivo.strip():
        raise ValidationError("Informe o motivo da decisão.")
    tem_retirada = _possui_retirada_vinculada(reserva)
    agora = timezone.now()
    if decisao == opcoes.CANCELADA:
        if tem_retirada:
            raise ValidationError("A reserva tem retirada registrada. As devoluções devem continuar disponíveis.")
        reserva.status = Reserva.Status.CANCELADA
        reserva.motivo_cancelamento = motivo.strip()
        reserva.cancelada_por = atual
        reserva.data_cancelamento = agora
        reserva.save(update_fields=["status", "motivo_cancelamento", "cancelada_por", "data_cancelamento", "data_atualizacao"])
    elif decisao == opcoes.MANTIDA:
        if not calendario.permite_manter_em_fechamento or atendimento_confirmado is not True:
            raise ValidationError("Manter a reserva exige política habilitada e atendimento excepcional confirmado.")
        limite = reserva.fim if tem_retirada else min(reserva.fim, reserva.inicio + Reserva.TOLERANCIA_RETIRADA)
        if agora >= limite:
            raise ValidationError("O prazo de entrega da reserva terminou.")
    else:
        raise ValidationError("Selecione uma decisão válida.")

    impacto.decisao = decisao
    impacto.motivo = motivo.strip()
    impacto.decidido_por = atual
    impacto.decidido_em = agora
    impacto.save(update_fields=["decisao", "motivo", "decidido_por", "decidido_em"])
    registrar_evento(
        usuario=atual,
        acao=AcaoAuditoria.RESERVA_CANCELADA if decisao == opcoes.CANCELADA else AcaoAuditoria.RESERVA_MANTIDA_FECHAMENTO,
        resultado=RegistroAuditoria.Resultado.SUCESSO, entidade="reservas.Reserva", entidade_id=reserva.pk,
    )
    return impacto
