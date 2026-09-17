from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento

from .forms import CadastroUsuarioForm
from .permissoes import pode_cadastrar_usuario


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
