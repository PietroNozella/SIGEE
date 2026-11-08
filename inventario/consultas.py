from django.db.models import Count, Q

from .models import Equipamento


def resumo_situacao_equipamentos(equipamentos):
    indicadores = equipamentos.aggregate(
        ativos=Count("pk", filter=Q(ativo=True)),
        disponiveis=Count("pk", filter=Q(ativo=True, situacao=Equipamento.Situacao.DISPONIVEL)),
        em_uso=Count("pk", filter=Q(ativo=True, situacao=Equipamento.Situacao.EM_USO)),
        manutencao=Count("pk", filter=Q(ativo=True, situacao=Equipamento.Situacao.MANUTENCAO)),
        inativos=Count("pk", filter=Q(ativo=False)),
    )
    distribuicao = [
        {"nome": "Disponíveis", "chave": "disponiveis"},
        {"nome": "Em uso", "chave": "em_uso"},
        {"nome": "Em manutenção", "chave": "manutencao"},
    ]
    percentuais = {
        chave: indicadores[chave] * 100 / indicadores["ativos"] if indicadores["ativos"] else None
        for chave in ("disponiveis", "em_uso", "manutencao")
    }
    por_categoria = list(
        equipamentos.filter(ativo=True)
        .values("tipo__categoria_id", "tipo__categoria__nome")
        .annotate(
            total=Count("pk"),
            disponiveis=Count("pk", filter=Q(situacao=Equipamento.Situacao.DISPONIVEL)),
            em_uso=Count("pk", filter=Q(situacao=Equipamento.Situacao.EM_USO)),
            manutencao=Count("pk", filter=Q(situacao=Equipamento.Situacao.MANUTENCAO)),
        )
        .order_by("tipo__categoria__nome", "tipo__categoria_id")
    )
    maior_categoria = max((item["total"] for item in por_categoria), default=0)
    for item in por_categoria:
        item["id"] = item["tipo__categoria_id"]
        item["nome"] = item["tipo__categoria__nome"]
        item["indisponiveis"] = item["em_uso"] + item["manutencao"]
        item["segmentos"] = [
            {"chave": estado["chave"], "percentual": item[estado["chave"]] * 100 / maior_categoria}
            for estado in distribuicao
        ]
    por_categoria.sort(key=lambda item: (-item["indisponiveis"], -item["total"], item["nome"]))

    return {
        "indicadores": indicadores, "distribuicao": distribuicao, "percentuais": percentuais,
        "situacao_por_categoria": por_categoria, "maior_categoria": maior_categoria,
    }
