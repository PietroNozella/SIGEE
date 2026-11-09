"""Preparação de cenários de teste, incluindo retiradas históricas.

Não representam uma entrada funcional de gravação do sistema.
"""
from uuid import uuid4

from inventario.models import Equipamento
from .models import Movimentacao


def registrar_entrega_conferida(*, operador, reserva_id, **dados):
    """Simula uma nova conferência; testes de reenvio devem preservar o token original."""
    from reservas.models import Reserva
    from reservas.services import resumo_entrega, substituir_equipamentos_em_manutencao
    from .services import criar_conferencia_retirada, registrar_retirada_reserva

    reserva = Reserva.objects.filter(pk=reserva_id).first()
    conferencia = "reserva-inexistente"
    if reserva is not None:
        substituir_equipamentos_em_manutencao(reserva_id=reserva_id, usuario=operador)
        conferencia = criar_conferencia_retirada(
            reserva=reserva, operador=operador, resumo=resumo_entrega(reserva),
        )
    return registrar_retirada_reserva(
        operador=operador, reserva_id=reserva_id, conferencia=conferencia, **dados,
    )


def criar_retirada_legada(*, operador, destinatario, equipamentos, observacao="", **kwargs):
    lote = uuid4()
    registros = []
    for equipamento in equipamentos:
        registros.append(Movimentacao.objects.create(
            operador=operador, destinatario=destinatario, equipamento=equipamento,
            tipo="RETIRADA", lote_retirada=lote, observacao=observacao,
        ))
        equipamento.situacao = Equipamento.Situacao.EM_USO
        equipamento.save(update_fields=("situacao",))
    return registros
