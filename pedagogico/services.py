from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from movimentacoes.models import Movimentacao
from reservas.models import Reserva
from usuarios.permissoes import pode_gerenciar_utilizacao_pedagogica

from .models import AtividadePedagogica, Disciplina, Turma, UtilizacaoPedagogica


def retiradas_com_contexto(reserva):
    return Movimentacao.objects.filter(
        reserva=reserva, tipo=Movimentacao.Tipo.RETIRADA,
    ).select_related(
        "equipamento__tipo", "utilizacao_pedagogica__turma",
        "utilizacao_pedagogica__disciplina", "utilizacao_pedagogica__atividade",
    ).prefetch_related("devolucoes").order_by("pk")


def salvar_contexto_reserva(*, professor, reserva_id, turma, disciplina, atividade, observacao=""):
    professor_atual = get_user_model().objects.filter(pk=professor.pk).first() if professor.is_authenticated else None
    if professor_atual is None or not pode_gerenciar_utilizacao_pedagogica(professor_atual):
        raise PermissionDenied
    reserva = get_object_or_404(Reserva, pk=reserva_id, professor=professor_atual)
    acao = AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA
    try:
        with transaction.atomic():
            # Mesma ordem da devolução, sem joins anuláveis no bloqueio do PostgreSQL.
            retiradas = list(Movimentacao.objects.select_for_update().filter(
                reserva=reserva, tipo=Movimentacao.Tipo.RETIRADA,
            ).order_by("pk"))
            if not retiradas:
                raise ValidationError("O contexto pedagógico só pode ser registrado após a retirada.")
            if any(retirada.destinatario_id != professor_atual.pk for retirada in retiradas):
                raise ValidationError("O Professor precisa ser o destinatário de todas as unidades retiradas.")
            existentes = {item.movimentacao_id: item for item in UtilizacaoPedagogica.objects.filter(
                movimentacao__in=retiradas,
            )}
            acao = AcaoAuditoria.UTILIZACAO_PEDAGOGICA_EDITADA if existentes else acao
            if not pode_gerenciar_utilizacao_pedagogica(professor_atual, "change" if existentes else "add"):
                raise PermissionDenied
            devolvidas = Movimentacao.objects.filter(
                tipo=Movimentacao.Tipo.DEVOLUCAO, retirada_origem__in=retiradas,
            ).count()
            if devolvidas == len(retiradas):
                raise ValidationError("A devolução integral encerrou o registro e a edição do contexto pedagógico.")
            if existentes and len(existentes) != len(retiradas):
                raise ValidationError("O contexto do lote está inconsistente. Solicite a conferência dos registros.")
            if any(item.professor_id != professor_atual.pk for item in existentes.values()):
                raise ValidationError("O Professor do contexto não corresponde ao proprietário da reserva.")

            escolhas = {}
            for campo, modelo, selecionado in (("turma", Turma, turma), ("disciplina", Disciplina, disciplina), ("atividade", AtividadePedagogica, atividade)):
                registro = modelo.objects.select_for_update().filter(pk=selecionado.pk).first()
                mantido = existentes and all(getattr(item, f"{campo}_id") == selecionado.pk for item in existentes.values())
                if registro is None or (not registro.ativo and not mantido):
                    raise ValidationError({campo: "Selecione um cadastro ativo ou mantenha o vínculo já registrado."})
                escolhas[campo] = registro
            observacao = observacao.strip()
            salvas = []
            for retirada in retiradas:
                utilizacao = existentes.get(retirada.pk)
                if utilizacao is not None and all(getattr(utilizacao, f"{campo}_id") == registro.pk for campo, registro in escolhas.items()) and utilizacao.observacao == observacao:
                    salvas.append(utilizacao)
                    continue
                if utilizacao is None:
                    utilizacao = UtilizacaoPedagogica(movimentacao=retirada, professor=professor_atual)
                for campo, registro in escolhas.items():
                    setattr(utilizacao, campo, registro)
                utilizacao.observacao = observacao
                utilizacao.full_clean()
                utilizacao.save()
                registrar_evento(
                    usuario=professor_atual, acao=acao, resultado=RegistroAuditoria.Resultado.SUCESSO,
                    entidade=UtilizacaoPedagogica._meta.label, entidade_id=utilizacao.pk,
                )
                salvas.append(utilizacao)
            return salvas
    except (ValidationError, IntegrityError):
        registrar_evento(
            usuario=professor_atual, acao=acao, resultado=RegistroAuditoria.Resultado.FALHA,
            entidade=Reserva._meta.label, entidade_id=reserva.pk,
        )
        raise
