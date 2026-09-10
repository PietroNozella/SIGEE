from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .forms import CadastroUsuarioForm
from .permissoes import pode_cadastrar_usuario


@login_required
def usuario_novo(request):
    if not pode_cadastrar_usuario(request.user):
        raise PermissionDenied

    form = CadastroUsuarioForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuário cadastrado com sucesso.")
        return redirect("usuarios:usuario_novo")

    return render(request, "usuarios/usuario_form.html", {"form": form})
