from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from usuarios.permissoes import pode_configurar_calendario

from .models import AlteracaoCalendario, CalendarioEscolar, RegraCalendario


def bloquear_calendario():
    CalendarioEscolar.objects.get_or_create(pk=1)
    return CalendarioEscolar.objects.select_for_update().get(pk=1)


def intervalo_vigente():
    calendario = CalendarioEscolar.objects.filter(pk=1).first() or CalendarioEscolar()
    return timedelta(minutes=calendario.intervalo_minutos)


def salvar_intervalo(*, usuario, minutos, motivo, versao):
    with transaction.atomic():
        calendario = bloquear_calendario()
        atual = get_user_model().objects.filter(pk=usuario.pk).first() if usuario.is_authenticated else None
        if atual is None or not pode_configurar_calendario(atual):
            raise PermissionDenied
        if calendario.versao != versao:
            raise ValidationError("O calendário foi alterado por outro Administrador. Reabra a página e confira a versão atual.")
        if not motivo.strip():
            raise ValidationError("Informe o motivo da alteração do intervalo.")
        anterior = {"titulo": "Intervalo entre reservas", "intervalo_minutos": calendario.intervalo_minutos,
                    "resumo": f"{calendario.intervalo_minutos} minuto(s) após o uso"}
        calendario.intervalo_minutos = minutos
        calendario.versao += 1
        calendario.full_clean()
        calendario.save(update_fields=["intervalo_minutos", "versao"])
        novo = {"titulo": "Intervalo entre reservas", "intervalo_minutos": minutos,
                "resumo": f"{minutos} minuto(s) após o uso"}
        alteracao = AlteracaoCalendario.objects.create(usuario=atual, motivo=motivo.strip(), anterior=anterior, novo=novo, versao=calendario.versao)
        registrar_evento(usuario=atual, acao=AcaoAuditoria.CALENDARIO_ALTERADO,
                        resultado=RegistroAuditoria.Resultado.SUCESSO,
                        entidade="calendario.AlteracaoCalendario", entidade_id=alteracao.pk)
    return alteracao


def regras_vigentes():
    regras = list(RegraCalendario.objects.prefetch_related("faixas"))
    return {(r.finalidade, r.data if r.data else r.dia_semana): r for r in regras}


def faixas_do_dia(data, finalidade, regras):
    regra = regras.get((finalidade, data)) or regras.get((finalidade, data.weekday()))
    if regra is None:
        return [(time.min, time.min)] if data.weekday() < 5 else []
    if regra.dia_inteiro:
        return [(time.min, time.min)]
    return [(f.inicio, f.fim) for f in regra.faixas.all()]


def intervalos_do_dia(data, finalidade, regras):
    fuso = timezone.get_default_timezone()
    return [(
        timezone.make_aware(datetime.combine(data, inicio), fuso),
        timezone.make_aware(datetime.combine(data + timedelta(days=fim == time.min), fim), fuso),
    ) for inicio, fim in faixas_do_dia(data, finalidade, regras)]


def validar_periodo_reserva(inicio, fim, *, regras=None):
    regras = regras_vigentes() if regras is None else regras
    inicio, fim = timezone.localtime(inicio), timezone.localtime(fim)
    dia = inicio.date()
    ultimo_dia = fim.date() - timedelta(days=fim.time() == time.min)
    uso, atendimento = [], []
    while dia <= ultimo_dia:
        faixas = intervalos_do_dia(dia, RegraCalendario.Finalidade.USO, regras)
        inicio_dia = max(inicio, timezone.make_aware(datetime.combine(dia, time.min)))
        fim_dia = min(fim, timezone.make_aware(datetime.combine(dia + timedelta(days=1), time.min)))
        coberto_ate = inicio_dia
        for abertura, fechamento in faixas:
            if abertura <= coberto_ate < fechamento:
                coberto_ate = max(coberto_ate, fechamento)
        if coberto_ate < fim_dia:
            orientacao = "Para reservar no sábado ou domingo, é necessária liberação no calendário da escola." if dia.weekday() >= 5 else "Confira as faixas de uso dessa data."
            raise ValidationError({NON_FIELD_ERRORS: f"O período está fora do calendário de uso dos equipamentos em {dia:%d/%m/%Y}. {orientacao}"})
        uso.extend([[a.isoformat(), b.isoformat()] for a, b in faixas])
        atendimento.extend([[a.isoformat(), b.isoformat()] for a, b in intervalos_do_dia(dia, RegraCalendario.Finalidade.ATENDIMENTO, regras)])
        dia += timedelta(days=1)
    for instante, campo, nome in ((inicio, "inicio", "retirada"), (fim, "fim", "devolução prevista")):
        faixas = intervalos_do_dia(instante.date(), RegraCalendario.Finalidade.ATENDIMENTO, regras)
        if instante.time() == time.min and campo == "fim":
            faixas += intervalos_do_dia(instante.date() - timedelta(days=1), RegraCalendario.Finalidade.ATENDIMENTO, regras)
        if not any(a <= instante <= b if campo == "fim" else a <= instante < b for a, b in faixas):
            raise ValidationError({campo: f"O horário de {nome} está fora do atendimento do Operador em {instante:%d/%m/%Y}."})
        for a, b in faixas:
            if [a.isoformat(), b.isoformat()] not in atendimento:
                atendimento.append([a.isoformat(), b.isoformat()])
    return {"uso": uso, "atendimento": atendimento}


def validar_atendimento_retirada(reserva, agora):
    # Reservas legadas preservam as condições anteriores à adoção do calendário.
    if not reserva.calendario_confirmado:
        return
    if not any(datetime.fromisoformat(a) <= agora < datetime.fromisoformat(b)
               for a, b in reserva.calendario_confirmado["atendimento"]):
        raise ValidationError("A entrega está fora do atendimento do Operador acordado nesta reserva. A devolução física continua permitida.")


def reservas_afetadas(*, regras=None):
    from reservas.models import Reserva

    regras = regras_vigentes() if regras is None else regras
    afetadas = []
    candidatas = Reserva.objects.filter(status=Reserva.Status.ATIVA, fim__gt=timezone.now()).select_related("professor", "tipo_equipamento", "local")
    for reserva in candidatas.order_by("inicio", "pk"):
        try:
            validar_periodo_reserva(reserva.inicio, reserva.fim, regras=regras)
        except ValidationError as erro:
            reserva.impacto_calendario = erro.messages[0]
            afetadas.append(reserva)
    return afetadas


def descrever_regra(regra):
    faixas = [{"inicio": f.inicio.strftime("%H:%M"), "fim": f.fim.strftime("%H:%M")} for f in regra.faixas.all()]
    resumo = "Dia inteiro" if regra.dia_inteiro else "; ".join(f"{f['inicio']} às {f['fim'] if f['fim'] != '00:00' else '24:00'}" for f in faixas) or "Fechado"
    return {"finalidade": regra.finalidade, "dia_semana": regra.dia_semana,
            "data": regra.data.isoformat() if regra.data else None, "dia_inteiro": regra.dia_inteiro,
            "faixas": faixas, "titulo": str(regra), "resumo": resumo}


def descrever_funcionamento(data, finalidade, regras):
    faixas = faixas_do_dia(data, finalidade, regras)
    return "; ".join("Dia inteiro" if a == b == time.min else f"{a:%H:%M} às {b:%H:%M}" if b != time.min else f"{a:%H:%M} às 24:00" for a, b in faixas) or "Fechado"


def dias_para_agendamento():
    from reservas.models import Reserva

    regras = regras_vigentes()
    hoje = timezone.localdate()
    dias = {}
    for deslocamento in range(Reserva.ANTECEDENCIA_MAXIMA_DIAS + 1):
        data = hoje + timedelta(days=deslocamento)
        uso = intervalos_do_dia(data, RegraCalendario.Finalidade.USO, regras)
        atendimento = intervalos_do_dia(data, RegraCalendario.Finalidade.ATENDIMENTO, regras)
        aberto = any(max(a, c) < min(b, d) for a, b in uso for c, d in atendimento)
        dias[data.isoformat()] = {"aberto": aberto,
                                  "uso": descrever_funcionamento(data, "USO", regras),
                                  "atendimento": descrever_funcionamento(data, "ATENDIMENTO", regras)}
    return dias


def salvar_regra(*, usuario, regra, faixas, motivo, versao, remover=False):
    with transaction.atomic():
        calendario = bloquear_calendario()
        atual = get_user_model().objects.filter(pk=usuario.pk).first() if usuario.is_authenticated else None
        if atual is None or not pode_configurar_calendario(atual):
            raise PermissionDenied
        if calendario.versao != versao:
            raise ValidationError("O calendário foi alterado por outro Administrador. Reabra a página e confira a versão atual.")
        if not motivo.strip():
            raise ValidationError("Informe o motivo da alteração do calendário.")
        original = RegraCalendario.objects.filter(pk=regra.pk).prefetch_related("faixas").first() if regra.pk else None
        anterior = descrever_regra(original) if original else {
            "titulo": str(regra),
            "resumo": descrever_funcionamento(regra.data, regra.finalidade, regras_vigentes()) if regra.data else "Dia inteiro" if regra.dia_semana < 5 else "Fechado",
        }
        if remover:
            if original is None or original.data is None:
                raise ValidationError("Somente exceções por data podem ser removidas.")
            original.delete()
            novo = {"titulo": anterior["titulo"], "resumo": descrever_funcionamento(original.data, original.finalidade, regras_vigentes())}
        else:
            regra.full_clean()
            if regra.dia_inteiro and faixas:
                raise ValidationError("Escolha dia inteiro ou faixas de horário.")
            ordenadas = sorted(faixas, key=lambda f: f.inicio)
            for indice, faixa in enumerate(ordenadas):
                faixa.clean()
                if indice and (ordenadas[indice - 1].fim == time.min or faixa.inicio < ordenadas[indice - 1].fim):
                    raise ValidationError("As faixas de horário não podem se sobrepor.")
            regra.save()
            regra.faixas.all().delete()
            for faixa in ordenadas:
                faixa.pk = None
                faixa.regra = regra
                faixa.save()
            regra = RegraCalendario.objects.prefetch_related("faixas").get(pk=regra.pk)
            novo = descrever_regra(regra)
        calendario.versao += 1
        calendario.save(update_fields=["versao"])
        alteracao = AlteracaoCalendario.objects.create(usuario=atual, motivo=motivo.strip(), anterior=anterior, novo=novo, versao=calendario.versao)
        registrar_evento(usuario=atual, acao=AcaoAuditoria.CALENDARIO_ALTERADO,
                        resultado=RegistroAuditoria.Resultado.SUCESSO,
                        entidade="calendario.AlteracaoCalendario", entidade_id=alteracao.pk)
    return alteracao
