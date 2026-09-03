from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import EquipamentoForm, ImportacaoEquipamentosCSVForm
from .importacao_csv import CABECALHOS_CSV, validar_equipamentos_csv
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


def equipamento_importar(request):
    form = ImportacaoEquipamentosCSVForm(request.POST or None, request.FILES or None)
    erros_importacao = []

    if request.method == "POST" and form.is_valid():
        formularios_validos, erros_importacao = validar_equipamentos_csv(
            form.cleaned_data["arquivo"]
        )

        if not erros_importacao:
            try:
                with transaction.atomic():
                    for formulario in formularios_validos:
                        formulario.save()
            except IntegrityError:
                erros_importacao = [
                    "Não foi possível concluir a importação porque um número de "
                    "patrimônio já foi cadastrado. Corrija o arquivo e tente novamente."
                ]
            else:
                quantidade = len(formularios_validos)
                messages.success(
                    request,
                    f"{quantidade} equipamento(s) cadastrado(s) com sucesso.",
                )
                return redirect("inventario:equipamento_lista")

    return render(
        request,
        "inventario/equipamento_importar.html",
        {"form": form, "erros_importacao": erros_importacao},
    )


def equipamento_modelo_csv(request):
    resposta = HttpResponse(
        "\ufeff" + ";".join(CABECALHOS_CSV) + "\n",
        content_type="text/csv; charset=utf-8",
    )
    resposta["Content-Disposition"] = 'attachment; filename="modelo-equipamentos.csv"'
    return resposta


@require_POST
def equipamento_excluir(request, equipamento_id):
    equipamento = get_object_or_404(Equipamento, pk=equipamento_id)
    possui_historico = equipamento.possui_registros_relacionados()

    equipamento.delete()

    if possui_historico:
        messages.success(
            request,
            "Equipamento inativado e histórico de movimentações preservado.",
        )
    else:
        messages.success(request, "Equipamento excluído com sucesso.")

    return redirect("inventario:equipamento_lista")
