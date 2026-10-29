"""Fixtures históricas: simulam dados anteriores à exigência de reserva.

Não representam uma entrada funcional de gravação do sistema.
"""
from uuid import uuid4

from inventario.models import Equipamento
from .models import Movimentacao


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
