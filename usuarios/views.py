from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetConfirmView, PasswordResetView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento

from .forms import CadastroUsuarioForm
from .permissoes import (
    pode_cadastrar_usuario,
    pode_consultar_painel,
    pode_gerenciar_usuarios,
    usuarios_funcionais,
)
from .services import alterar_situacao_usuario


class EntrarView(LoginView):
    def get_default_redirect_url(self):
        if pode_consultar_painel(self.request.user):
            return reverse("inventario:painel")
        return super().get_default_redirect_url()


class SolicitarRecuperacaoSenhaView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    extra_email_context = {
        "site_name": "SIGEE",
        "password_reset_timeout_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        registrar_evento(
            acao=AcaoAuditoria.RECUPERACAO_SENHA_SOLICITADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        )
        return response


class ConfirmarRecuperacaoSenhaView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def form_valid(self, form):
        usuario = self.user
        with transaction.atomic():
            response = super().form_valid(form)
            registrar_evento(
                usuario=usuario,
                acao=AcaoAuditoria.SENHA_REDEFINIDA,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade=usuario._meta.label,
                entidade_id=usuario.pk,
            )
        return response


@login_required
def usuario_novo(request):
    if not pode_cadastrar_usuario(request.user):
        raise PermissionDenied

    form = CadastroUsuarioForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario_cadastrado = form.save()
            registrar_evento(
                usuario=request.user,
                acao=AcaoAuditoria.USUARIO_CADASTRADO,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade=usuario_cadastrado._meta.label,
                entidade_id=usuario_cadastrado.pk,
            )
        messages.success(request, "Usuário cadastrado com sucesso.")
        return redirect("usuarios:usuario_novo")

    if request.method == "POST":
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.USUARIO_CADASTRADO,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade=get_user_model()._meta.label,
        )

    return render(request, "usuarios/usuario_form.html", {"form": form})


@login_required
@require_GET
def usuario_lista(request):
    if not pode_gerenciar_usuarios(request.user):
        raise PermissionDenied

    usuarios = usuarios_funcionais().prefetch_related("groups")
    busca = request.GET.get("busca", "").strip()
    situacao = request.GET.get("situacao", "")
    if busca:
        usuarios = usuarios.filter(
            Q(first_name__icontains=busca) | Q(last_name__icontains=busca)
            | Q(username__icontains=busca) | Q(email__icontains=busca)
        )
    if situacao in ("ativos", "inativos"):
        usuarios = usuarios.filter(is_active=situacao == "ativos")
    else:
        situacao = ""
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "usuarios/usuario_lista.html", {
        "pagina": Paginator(usuarios, 15).get_page(request.GET.get("pagina")),
        "busca": busca, "situacao": situacao,
        "parametros_paginacao": parametros.urlencode(),
    })


@login_required
@require_POST
def usuario_situacao(request, usuario_id, ativo):
    if not pode_gerenciar_usuarios(request.user, "change"):
        raise PermissionDenied

    try:
        alterar_situacao_usuario(
            administrador=request.user, usuario_id=usuario_id, ativo=ativo,
        )
    except (ValidationError, IntegrityError) as erro:
        registrar_evento(
            usuario=request.user,
            acao=AcaoAuditoria.USUARIO_REATIVADO if ativo else AcaoAuditoria.USUARIO_DESATIVADO,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade=get_user_model()._meta.label, entidade_id=usuario_id,
        )
        mensagem = " ".join(erro.messages) if isinstance(erro, ValidationError) else (
            "Não foi possível alterar a conta. Nenhuma alteração foi gravada."
        )
        messages.error(request, mensagem)
    else:
        messages.success(request, "Usuário reativado." if ativo else "Usuário desativado. Os dados foram preservados.")
    return redirect("usuarios:usuario_lista")
