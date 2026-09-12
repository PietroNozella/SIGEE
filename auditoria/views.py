from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from usuarios.permissoes import pode_consultar_auditoria

from .forms import AuditoriaFiltroForm
from .models import RegistroAuditoria


@login_required
def registro_lista(request):
    if not pode_consultar_auditoria(request.user):
        raise PermissionDenied

    registros = RegistroAuditoria.objects.select_related("usuario").all()
    formulario = AuditoriaFiltroForm(request.GET or None)

    if formulario.is_valid():
        usuario = formulario.cleaned_data["usuario"]
        acao = formulario.cleaned_data["acao"]
        resultado = formulario.cleaned_data["resultado"]
        data_inicial = formulario.cleaned_data["data_inicial"]
        data_final = formulario.cleaned_data["data_final"]

        if usuario:
            registros = registros.filter(
                Q(usuario__username__icontains=usuario)
                | Q(usuario__first_name__icontains=usuario)
                | Q(usuario__last_name__icontains=usuario)
            )
        if acao:
            registros = registros.filter(acao=acao)
        if resultado:
            registros = registros.filter(resultado=resultado)
        if data_inicial:
            registros = registros.filter(data_hora__date__gte=data_inicial)
        if data_final:
            registros = registros.filter(data_hora__date__lte=data_final)

    paginador = Paginator(registros, 20)
    pagina = paginador.get_page(request.GET.get("pagina"))

    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    campos_filtro = ("usuario", "acao", "resultado", "data_inicial", "data_final")

    contexto = {
        "formulario": formulario,
        "pagina": pagina,
        "parametros_paginacao": parametros.urlencode(),
        "ha_filtros": any(request.GET.get(campo) for campo in campos_filtro),
    }
    return render(request, "auditoria/registro_lista.html", contexto)
