from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento

from .forms import CadastroUsuarioForm
from .permissoes import pode_cadastrar_usuario


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
