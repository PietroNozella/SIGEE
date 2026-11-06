from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, CharField, Count, Exists, F, OuterRef, Q, Value, When
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from movimentacoes.models import Movimentacao
from manutencoes.models import Manutencao
from reservas.models import Reserva, ReservaEquipamento
from usuarios.permissoes import (
    e_operador_funcional, e_professor_funcional, pode_consultar_painel,
    pode_gerenciar_manutencao, pode_consultar_reservas_administrativas,
)

from .forms import EquipamentoForm, ImportacaoEquipamentosCSVForm
from .importacao_csv import CABECALHOS_CSV, validar_equipamentos_csv
from .models import Categoria, Equipamento, Local


@login_required
@require_GET
def painel(request):
    if not pode_consultar_painel(request.user):
        raise PermissionDenied

    agora = timezone.now()
    periodos = (("7", "Últimos 7 dias"), ("30", "Últimos 30 dias"), ("90", "Últimos 90 dias"))
    periodo = request.GET.get("periodo", "30")
    avisos = []
    if periodo not in dict(periodos):
        periodo = "30"
        avisos.append("Período inválido. Exibindo os últimos 30 dias; selecione um período e aplique os filtros.")
    dias_periodo = int(periodo)
    categorias = list(Categoria.objects.order_by("nome"))
    categoria = next(
        (item for item in categorias if str(item.pk) == request.GET.get("categoria")), None,
    )
    if request.GET.get("categoria") and categoria is None:
        avisos.append("Categoria inválida. Exibindo todas as categorias; selecione uma categoria e aplique os filtros.")
    equipamentos = Equipamento.objects.all()
    movimentacoes = Movimentacao.objects.all()
    manutencoes = Manutencao.objects.all()
    if categoria:
        equipamentos = equipamentos.filter(tipo__categoria=categoria)
        movimentacoes = movimentacoes.filter(equipamento__tipo__categoria=categoria)
        manutencoes = manutencoes.filter(equipamento__tipo__categoria=categoria)

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

    # Limites em horário local; a agregação usa o mesmo fuso e conta registros,
    # pois cada RETIRADA representa uma unidade física, inclusive em lotes.
    fuso = timezone.get_default_timezone()
    hoje = timezone.localtime(agora, fuso).date()
    inicio_periodo = hoje - timedelta(days=dias_periodo - 1)
    inicio = timezone.make_aware(datetime.combine(inicio_periodo, time.min), fuso)
    fim = timezone.make_aware(datetime.combine(hoje + timedelta(days=1), time.min), fuso)
    retiradas = movimentacoes.filter(tipo=Movimentacao.Tipo.RETIRADA)
    retiradas_periodo = retiradas.filter(data_hora__gte=inicio, data_hora__lt=fim)
    contagens = dict(
        retiradas_periodo
        .annotate(dia=TruncDate("data_hora", tzinfo=fuso))
        .values("dia").annotate(total=Count("pk")).order_by("dia")
        .values_list("dia", "total")
    )
    retiradas_diarias = [
        {"dia": inicio_periodo + timedelta(days=indice),
         "total": contagens.get(inicio_periodo + timedelta(days=indice), 0)}
        for indice in range(dias_periodo)
    ]
    maior_dia = max(contagens.values(), default=0)
    escala_retiradas = max(2, maior_dia + maior_dia % 2)
    for item in retiradas_diarias:
        item["percentual"] = item["total"] * 100 / escala_retiradas

    total_retiradas = sum(contagens.values())
    inicio_anterior = timezone.make_aware(
        datetime.combine(inicio_periodo - timedelta(days=dias_periodo), time.min), fuso,
    )
    total_anterior = retiradas.filter(data_hora__gte=inicio_anterior, data_hora__lt=inicio).count()
    variacao = (total_retiradas - total_anterior) * 100 / total_anterior if total_anterior else None
    resumo_uso = retiradas_periodo.aggregate(unidades=Count("equipamento_id", distinct=True))
    tipos_mais_retirados = list(
        retiradas_periodo.values("equipamento__tipo_id", "equipamento__tipo__nome")
        .annotate(total=Count("pk"), unidades=Count("equipamento_id", distinct=True))
        .order_by("-total", "equipamento__tipo__nome", "equipamento__tipo_id")[:5]
    )
    maior_tipo = tipos_mais_retirados[0]["total"] if tipos_mais_retirados else 0
    for item in tipos_mais_retirados:
        item["percentual"] = item["total"] * 100 / maior_tipo
        item["participacao"] = item["total"] * 100 / total_retiradas

    pode_ver_reservas = pode_consultar_reservas_administrativas(request.user)
    etapas_reservas = []
    total_reservas = 0
    atrasadas = Movimentacao.objects.none()
    total_atrasadas = 0
    if pode_ver_reservas:
        reservas = Reserva.objects.filter(inicio__gte=inicio, inicio__lt=fim)
        if categoria:
            reservas = reservas.filter(tipo_equipamento__categoria=categoria)
        # Aplica a tolerância já definida pelo domínio sem alterar reservas durante a consulta.
        contagens_reservas = dict(
            reservas.com_etapa().annotate(etapa_painel=Case(
                When(etapa="AGUARDANDO", inicio__lte=agora - Reserva.TOLERANCIA_RETIRADA,
                     then=Value("EXPIRADA")),
                default=F("etapa"), output_field=CharField(),
            )).order_by().values("etapa_painel").annotate(total=Count("pk"))
            .values_list("etapa_painel", "total")
        )
        total_reservas = sum(contagens_reservas.values())
        for chave, nome in (("AGUARDANDO", "Aguardando retirada"), ("EM_USO", "Em uso"),
                            ("ENCERRADA", "Devolvidas"), ("CANCELADA", "Canceladas"),
                            ("EXPIRADA", "Expiradas sem retirada")):
            total = contagens_reservas.get(chave, 0)
            etapas_reservas.append({"chave": chave, "nome": nome, "total": total,
                                   "percentual": total * 100 / total_reservas if total_reservas else 0})
        pendentes = retiradas.filter(
            devolucoes__isnull=True, reserva__fim__lt=agora,
        )
        total_atrasadas = pendentes.count()
        atrasadas = list(pendentes.select_related("equipamento__tipo", "reserva")
                         .order_by("reserva__fim", "pk")[:5])

    pode_ver_manutencoes = pode_gerenciar_manutencao(request.user)
    abertas = Manutencao.objects.none()
    total_manutencoes = 0
    if pode_ver_manutencoes:
        pendentes = manutencoes.filter(estado__in=[Manutencao.Estado.PENDENTE, Manutencao.Estado.EM_ANDAMENTO])
        total_manutencoes = pendentes.count()
        abertas = list(pendentes.select_related("equipamento__tipo").order_by("data_abertura", "pk")[:5])
        for item in abertas:
            item.dias_em_aberto = (hoje - timezone.localtime(item.data_abertura, fuso).date()).days
    recentes = movimentacoes.filter(data_hora__gte=inicio, data_hora__lt=fim).select_related(
        "equipamento__tipo", "operador", "destinatario",
    ).order_by("-data_hora", "-pk")[:10]
    return render(request, "inventario/painel.html", {
        "indicadores": indicadores, "distribuicao": distribuicao,
        "percentuais": percentuais, "atualizado_em": agora,
        "periodos_painel": periodos, "periodo_selecionado": periodo,
        "dias_periodo": dias_periodo, "avisos_filtros": avisos,
        "movimentacoes_recentes": recentes,
        "categorias_painel": categorias, "categoria_selecionada": categoria,
        "situacao_por_categoria": por_categoria, "maior_categoria": maior_categoria,
        "retiradas_diarias": retiradas_diarias, "inicio_periodo": inicio_periodo,
        "fim_periodo": hoje, "fuso_painel": str(fuso),
        "total_retiradas": total_retiradas, "maior_dia": maior_dia,
        "total_anterior": total_anterior, "variacao_retiradas": variacao,
        "variacao_absoluta": abs(variacao) if variacao is not None else None,
        "inicio_anterior": inicio_anterior.date(), "fim_anterior": inicio_periodo - timedelta(days=1),
        "unidades_utilizadas": resumo_uso["unidades"], "tipos_mais_retirados": tipos_mais_retirados,
        "etapas_reservas": etapas_reservas, "total_reservas": total_reservas,
        "pode_ver_reservas_painel": pode_ver_reservas,
        "devolucoes_atrasadas": atrasadas, "total_atrasadas": total_atrasadas,
        "total_manutencoes_abertas": total_manutencoes,
        "escala_retiradas": escala_retiradas, "meia_escala_retiradas": escala_retiradas // 2,
        "manutencoes_abertas": abertas, "pode_ver_manutencoes_painel": pode_ver_manutencoes,
    })


@login_required
@permission_required("inventario.view_equipamento", raise_exception=True)
def equipamento_lista(request):
    e_professor = e_professor_funcional(request.user)
    e_operador = e_operador_funcional(request.user)
    lista_tipos = e_operador
    equipamentos = Equipamento.objects.select_related("tipo__categoria", "local").annotate(
        possui_historico=(
            Exists(Movimentacao.objects.filter(equipamento_id=OuterRef("pk")))
            | Exists(
                ReservaEquipamento.objects.filter(equipamento_id=OuterRef("pk"))
            )
            | Exists(Manutencao.objects.filter(equipamento_id=OuterRef("pk")))
        )
    )

    total_equipamentos = equipamentos.count()
    indicadores = None
    if request.user.has_perm("inventario.view_resumo_inventario"):
        indicadores = {
            "total": total_equipamentos,
            "disponiveis": equipamentos.filter(
                ativo=True,
                situacao=Equipamento.Situacao.DISPONIVEL
            ).count(),
            "em_uso": equipamentos.filter(
                ativo=True,
                situacao=Equipamento.Situacao.EM_USO
            ).count(),
            "manutencao": equipamentos.filter(
                ativo=True,
                situacao=Equipamento.Situacao.MANUTENCAO
            ).count(),
        }

    busca = request.GET.get("busca", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    local = request.GET.get("local", "").strip()
    situacao = request.GET.get("situacao", "").strip()

    if busca:
        equipamentos = equipamentos.filter(
            Q(numero_patrimonio__icontains=busca)
            | Q(tipo__nome__icontains=busca)
        )
    if categoria.isdigit():
        equipamentos = equipamentos.filter(tipo__categoria_id=categoria)
    if local.isdigit():
        equipamentos = equipamentos.filter(local_id=local)
    if situacao in Equipamento.Situacao.values:
        equipamentos = equipamentos.filter(situacao=situacao)
        if situacao == Equipamento.Situacao.DISPONIVEL:
            equipamentos = equipamentos.filter(ativo=True)

    if e_professor:
        equipamentos = equipamentos.filter(
            ativo=True,
            tipo__ativo=True,
            local__ativo=True,
        )

    ha_filtros = any((busca, categoria, local, situacao))

    if request.user.is_authenticated and ha_filtros:
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.INVENTARIO_CONSULTADO,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="inventario.Equipamento",
        )

    unidades_fisicas = equipamentos
    if e_professor:
        equipamentos = (
            equipamentos.values(
                "tipo_id",
                "tipo__nome",
                "tipo__categoria__nome",
                "local_id",
                "local__nome",
            )
            .annotate(
                quantidade_total=Count("id"),
                quantidade_disponivel=Count(
                    "id",
                    filter=Q(situacao=Equipamento.Situacao.DISPONIVEL),
                ),
            )
            .order_by("tipo__categoria__nome", "tipo__nome", "local__nome")
        )
    elif lista_tipos:
        equipamentos = (
            equipamentos.values("tipo_id", "tipo__nome", "tipo__categoria__nome")
            .annotate(quantidade_total=Count("id"))
            .order_by("tipo__categoria__nome", "tipo__nome", "tipo_id")
        )

    paginator = Paginator(equipamentos, 5)
    pagina = paginator.get_page(request.GET.get("pagina"))

    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    parametros.pop("tipo", None)
    url_lista = reverse("inventario:equipamento_lista")
    if lista_tipos:
        unidades_por_tipo = {tipo["tipo_id"]: [] for tipo in pagina}
        for unidade in unidades_fisicas.filter(tipo_id__in=unidades_por_tipo):
            unidades_por_tipo[unidade.tipo_id].append(unidade)
        for tipo in pagina:
            tipo["unidades"] = unidades_por_tipo[tipo["tipo_id"]]

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
        "ha_filtros": ha_filtros,
        "total_equipamentos": total_equipamentos,
        "e_professor": e_professor,
        "lista_tipos": lista_tipos,
        "url_limpar": url_lista,
    }
    return render(request, "inventario/equipamento_lista.html", context)


@login_required
@permission_required("inventario.add_equipamento", raise_exception=True)
def equipamento_novo(request):
    form = EquipamentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                equipamento = form.save()
                registrar_evento(
                    usuario=request.user,
                    acao=AcaoAuditoria.EQUIPAMENTO_CADASTRADO,
                    resultado=RegistroAuditoria.Resultado.SUCESSO,
                    entidade="inventario.Equipamento",
                    entidade_id=equipamento.pk,
                )
        except IntegrityError:
            form.add_error(
                "numero_patrimonio",
                Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO,
            )
        else:
            messages.success(request, "Equipamento cadastrado com sucesso.")
            return redirect("inventario:equipamento_lista")

    if request.method == "POST":
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.EQUIPAMENTO_CADASTRADO,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="inventario.Equipamento",
        )

    return render(
        request,
        "inventario/equipamento_form.html",
        {"form": form},
    )


@login_required
@permission_required("inventario.change_equipamento", raise_exception=True)
@transaction.atomic
def equipamento_editar(request, equipamento_id):
    equipamentos = Equipamento.objects.select_for_update() if request.method == "POST" else Equipamento.objects.all()
    equipamento = get_object_or_404(equipamentos, pk=equipamento_id)
    form = EquipamentoForm(request.POST or None, instance=equipamento)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                equipamento = form.save()
                registrar_evento(
                    usuario=request.user,
                    acao=AcaoAuditoria.EQUIPAMENTO_EDITADO,
                    resultado=RegistroAuditoria.Resultado.SUCESSO,
                    entidade="inventario.Equipamento",
                    entidade_id=equipamento.pk,
                )
        except IntegrityError:
            form.add_error(
                "numero_patrimonio",
                Equipamento.MENSAGEM_PATRIMONIO_DUPLICADO,
            )
        else:
            messages.success(request, "Equipamento atualizado com sucesso.")
            return redirect("inventario:equipamento_lista")

    if request.method == "POST":
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.EQUIPAMENTO_EDITADO,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="inventario.Equipamento",
            entidade_id=equipamento.pk,
        )

    return render(
        request,
        "inventario/equipamento_form.html",
        {"form": form, "editando": True, "equipamento": equipamento},
    )


@login_required
@permission_required("inventario.add_equipamento", raise_exception=True)
def equipamento_importar(request):
    form = ImportacaoEquipamentosCSVForm(request.POST or None, request.FILES or None)
    erros_importacao = []

    if request.method == "POST" and form.is_valid():

        formularios_validos, erros_importacao = validar_equipamentos_csv(
            form.cleaned_data["arquivo"]
        )

        # O lote só é persistido quando todas as linhas são válidas; a transação
        # impede registros parciais e auditoria sem a operação correspondente.
        if not erros_importacao:
            try:
                with transaction.atomic():
                    for formulario in formularios_validos:
                        formulario.save()
                    registrar_evento(
                        usuario=request.user,
                        acao=AcaoAuditoria.EQUIPAMENTOS_IMPORTADOS,
                        resultado=RegistroAuditoria.Resultado.SUCESSO,
                        entidade="inventario.Equipamento",
                    )
            # Mantém a RN-01 mesmo se outro cadastro ocorrer após a validação inicial.
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

    if request.method == "POST":
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.EQUIPAMENTOS_IMPORTADOS,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="inventario.Equipamento",
        )

    return render(
        request,
        "inventario/equipamento_importar.html",
        {"form": form, "erros_importacao": erros_importacao},
    )


@login_required
@permission_required("inventario.add_equipamento", raise_exception=True)
def equipamento_modelo_csv(request):
    resposta = HttpResponse(
        "\ufeff" + ";".join(CABECALHOS_CSV) + "\n",
        content_type="text/csv; charset=utf-8",
    )
    resposta["Content-Disposition"] = 'attachment; filename="modelo-equipamentos.csv"'

    if request.user.is_authenticated:
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.MODELO_CSV_BAIXADO,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="inventario.Equipamento",
        )

    return resposta


@login_required
@permission_required("inventario.delete_equipamento", raise_exception=True)
@require_POST
@transaction.atomic
def equipamento_excluir(request, equipamento_id):
    equipamento = get_object_or_404(Equipamento.objects.select_for_update(), pk=equipamento_id)
    possui_historico = equipamento.possui_registros_relacionados()

    acao = (
        AcaoAuditoria.EQUIPAMENTO_INATIVADO
        if possui_historico
        else AcaoAuditoria.EQUIPAMENTO_EXCLUIDO
    )

    with transaction.atomic():
        equipamento.delete()
        registrar_evento(
            usuario=request.user,
            acao=acao,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade="inventario.Equipamento",
            entidade_id=equipamento_id,
        )

    if possui_historico:
        messages.success(
            request,
            "Equipamento inativado e histórico de movimentações preservado, incluindo as manutenções.",
        )
    else:
        messages.success(request, "Equipamento excluído com sucesso.")

    return redirect("inventario:equipamento_lista")
