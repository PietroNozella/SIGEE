from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from usuarios.permissoes import pode_gerenciar_cadastro_pedagogico, pode_gerenciar_utilizacao_pedagogica
from reservas.models import Reserva

from .forms import AtividadePedagogicaForm, DisciplinaForm, TurmaForm, UtilizacaoPedagogicaForm
from .models import AtividadePedagogica, Disciplina, Turma
from .services import retiradas_com_contexto, salvar_contexto_reserva


CADASTROS = {
    "turmas": {"modelo": Turma, "formulario": TurmaForm, "titulo": "Turmas", "singular": "turma"},
    "disciplinas": {"modelo": Disciplina, "formulario": DisciplinaForm, "titulo": "Disciplinas", "singular": "disciplina"},
    "atividades": {"modelo": AtividadePedagogica, "formulario": AtividadePedagogicaForm, "titulo": "Atividades pedagógicas", "singular": "atividade pedagógica"},
}


def _exigir_permissao(usuario, modelo, acao):
    if not pode_gerenciar_cadastro_pedagogico(usuario, modelo._meta.model_name, acao):
        raise PermissionDenied


def _contexto(cadastro, usuario):
    configuracao = CADASTROS[cadastro]
    modelo = configuracao["modelo"]
    return {
        "cadastro": cadastro,
        "titulo": configuracao["titulo"],
        "singular": configuracao["singular"],
        "url_lista": reverse(f"pedagogico:{cadastro}_lista"),
        "url_novo": reverse(f"pedagogico:{cadastro}_novo"),
        "rota_editar": f"pedagogico:{cadastro}_editar",
        "rota_inativar": f"pedagogico:{cadastro}_inativar",
        "rota_reativar": f"pedagogico:{cadastro}_reativar",
        "pode_criar": pode_gerenciar_cadastro_pedagogico(usuario, modelo._meta.model_name, "add"),
        "pode_alterar": pode_gerenciar_cadastro_pedagogico(usuario, modelo._meta.model_name, "change"),
    }


def _auditar(usuario, modelo, acao, resultado, registro_id=None):
    registrar_evento(
        usuario=usuario, acao=acao, resultado=resultado,
        entidade=modelo._meta.label,
        entidade_id=registro_id if registro_id is not None else "",
    )


@login_required
@require_GET
def cadastro_lista(request, cadastro):
    modelo = CADASTROS[cadastro]["modelo"]
    _exigir_permissao(request.user, modelo, "view")
    busca = request.GET.get("busca", "").strip()
    situacao = request.GET.get("situacao", "")
    registros = modelo.objects.all()
    if busca:
        registros = registros.filter(nome__icontains=busca)
    if situacao in ("ativos", "inativos"):
        registros = registros.filter(ativo=situacao == "ativos")
    else:
        situacao = ""
    pagina = Paginator(registros, 10).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    contexto = _contexto(cadastro, request.user)
    contexto.update({"pagina": pagina, "busca": busca, "situacao": situacao, "parametros_paginacao": parametros.urlencode()})
    return render(request, "pedagogico/cadastro_lista.html", contexto)


@login_required
@require_http_methods(["GET", "POST"])
def cadastro_form(request, cadastro, registro_id=None):
    configuracao = CADASTROS[cadastro]
    modelo = configuracao["modelo"]
    editando = registro_id is not None
    _exigir_permissao(request.user, modelo, "change" if editando else "add")
    registro = get_object_or_404(modelo, pk=registro_id) if editando else None
    form = configuracao["formulario"](
        request.POST if request.method == "POST" else None, instance=registro,
    )
    acao = AcaoAuditoria.CADASTRO_PEDAGOGICO_EDITADO if editando else AcaoAuditoria.CADASTRO_PEDAGOGICO_CRIADO
    if request.method == "POST":
        if form.is_valid():
            try:
                with transaction.atomic():
                    registro = form.save(commit=False)
                    if editando:
                        # A edição dos dados não sobrescreve uma mudança de situação concorrente.
                        registro.save(update_fields=form._meta.fields)
                    else:
                        registro.save()
                    _auditar(request.user, modelo, acao, RegistroAuditoria.Resultado.SUCESSO, registro.pk)
            except IntegrityError:
                duplicado = modelo.objects.filter(nome=form.cleaned_data["nome"]).exclude(pk=registro_id).exists()
                form.add_error("nome" if duplicado else None, (
                    "Já existe um cadastro com este nome." if duplicado
                    else "Não foi possível salvar. Nenhuma alteração foi gravada. Tente novamente."
                ))
            else:
                messages.success(request, "Cadastro atualizado com sucesso." if editando else "Cadastro criado com sucesso.")
                return redirect(f"pedagogico:{cadastro}_lista")
        _auditar(request.user, modelo, acao, RegistroAuditoria.Resultado.FALHA, registro_id)
    contexto = _contexto(cadastro, request.user)
    contexto.update({"form": form, "editando": editando})
    return render(request, "pedagogico/cadastro_form.html", contexto)


@login_required
@require_POST
def cadastro_situacao(request, cadastro, registro_id, ativo):
    modelo = CADASTROS[cadastro]["modelo"]
    _exigir_permissao(request.user, modelo, "change")
    acao = AcaoAuditoria.CADASTRO_PEDAGOGICO_SITUACAO_ALTERADA
    try:
        with transaction.atomic():
            registro = get_object_or_404(modelo.objects.select_for_update(), pk=registro_id)
            if registro.ativo != ativo:
                registro.ativo = ativo
                registro.save(update_fields=("ativo",))
                _auditar(request.user, modelo, acao, RegistroAuditoria.Resultado.SUCESSO, registro.pk)
    except IntegrityError:
        _auditar(request.user, modelo, acao, RegistroAuditoria.Resultado.FALHA, registro_id)
        messages.error(request, "Não foi possível alterar a situação. Nenhuma alteração foi gravada.")
    else:
        messages.success(request, "Cadastro ativo." if ativo else "Cadastro inativo. Os dados foram preservados.")
    return redirect(f"pedagogico:{cadastro}_lista")


@login_required
@require_http_methods(["GET", "POST"])
def utilizacao_reserva(request, reserva_id):
    if not pode_gerenciar_utilizacao_pedagogica(request.user):
        raise PermissionDenied
    reserva = get_object_or_404(
        Reserva.objects.select_related("tipo_equipamento", "local"),
        pk=reserva_id, professor=request.user,
    )
    retiradas = list(retiradas_com_contexto(reserva))
    utilizacao = getattr(retiradas[0], "utilizacao_pedagogica", None) if retiradas else None
    pendentes = sum(not retirada.devolucoes.all() for retirada in retiradas)
    acao_permissao = "change" if utilizacao else "add"
    pode_gravar = pode_gerenciar_utilizacao_pedagogica(request.user, acao_permissao)
    form = UtilizacaoPedagogicaForm(
        request.POST if request.method == "POST" else None, utilizacao=utilizacao,
    )
    if request.method == "POST":
        if not pode_gravar:
            raise PermissionDenied
        if form.is_valid():
            try:
                salvar_contexto_reserva(
                    professor=request.user, reserva_id=reserva.pk, **form.cleaned_data,
                )
            except ValidationError as erro:
                if hasattr(erro, "message_dict"):
                    for campo, mensagens in erro.message_dict.items():
                        form.add_error(campo if campo in form.fields else None, mensagens)
                else:
                    form.add_error(None, erro)
            except IntegrityError:
                form.add_error(None, "Não foi possível salvar. Nenhuma alteração foi gravada. Tente novamente.")
            else:
                messages.success(request, "Contexto pedagógico salvo para todo o lote.")
                return redirect("pedagogico:utilizacao_reserva", reserva_id=reserva.pk)
        else:
            registrar_evento(
                usuario=request.user,
                acao=AcaoAuditoria.UTILIZACAO_PEDAGOGICA_EDITADA if utilizacao else AcaoAuditoria.UTILIZACAO_PEDAGOGICA_CRIADA,
                resultado=RegistroAuditoria.Resultado.FALHA,
                entidade=Reserva._meta.label, entidade_id=reserva.pk,
            )
    return render(request, "pedagogico/utilizacao_reserva.html", {
        "reserva": reserva, "retiradas": retiradas, "utilizacao": utilizacao,
        "pendentes": pendentes, "form": form,
        "pode_editar": bool(pendentes and pode_gravar),
    })
