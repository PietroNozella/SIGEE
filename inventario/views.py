from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import EquipamentoForm
from .models import Categoria, Equipamento, Local


def equipamento_lista(request):
    equipamentos = Equipamento.objects.select_related("categoria", "local")

    total_equipamentos = equipamentos.count()
    indicadores = {
        "total": total_equipamentos,
        "disponiveis": equipamentos.filter(
            situacao=Equipamento.Situacao.DISPONIVEL
        ).count(),
        "em_uso": equipamentos.filter(
            situacao=Equipamento.Situacao.EM_USO
        ).count(),
        "manutencao": equipamentos.filter(
            situacao=Equipamento.Situacao.MANUTENCAO
        ).count(),
    }

    busca = request.GET.get("busca", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    local = request.GET.get("local", "").strip()
    situacao = request.GET.get("situacao", "").strip()

    if busca:
        equipamentos = equipamentos.filter(
            Q(numero_patrimonio__icontains=busca) | Q(nome__icontains=busca)
        )
    if categoria.isdigit():
        equipamentos = equipamentos.filter(categoria_id=categoria)
    if local.isdigit():
        equipamentos = equipamentos.filter(local_id=local)
    if situacao in Equipamento.Situacao.values:
        equipamentos = equipamentos.filter(situacao=situacao)

    paginator = Paginator(equipamentos, 5)
    pagina = paginator.get_page(request.GET.get("pagina"))

    parametros = request.GET.copy()
    parametros.pop("pagina", None)

    context = {
        "pagina": pagina,
        "indicadores": indicadores,
        "categorias": Categoria.objects.all(),
        "locais": Local.objects.all(),
        "situacoes": Equipamento.Situacao.choices,
        "filtros": {
            "busca": busca,
            "categoria": categoria,
            "local": local,
            "situacao": situacao,
        },
        "parametros_paginacao": parametros.urlencode(),
        "ha_filtros": any((busca, categoria, local, situacao)),
        "total_equipamentos": total_equipamentos,
    }
    return render(request, "inventario/equipamento_lista.html", context)


def equipamento_novo(request):
    form = EquipamentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(
                "numero_patrimonio",
                Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO,
            )
        else:
            messages.success(request, "Equipamento cadastrado com sucesso.")
            return redirect("inventario:equipamento_lista")

    return render(
        request,
        "inventario/equipamento_form.html",
        {"form": form},
    )
