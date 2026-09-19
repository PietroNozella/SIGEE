from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction

from .permissoes import GRUPOS_FUNCIONAIS


class CadastroUsuarioForm(UserCreationForm):
    first_name = forms.CharField(label="Nome", max_length=150)
    last_name = forms.CharField(label="Sobrenome", max_length=150)
    email = forms.EmailField(label="E-mail", max_length=254)
    perfil = forms.ModelChoiceField(
        label="Perfil",
        queryset=Group.objects.none(),
        empty_label="Selecione um perfil",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("first_name", "last_name", "email", "username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            (
                "first_name",
                "last_name",
                "email",
                "username",
                "perfil",
                "password1",
                "password2",
            )
        )
        self.fields["perfil"].queryset = Group.objects.filter(
            name__in=GRUPOS_FUNCIONAIS
        ).order_by("name")
        self.fields["username"].label = "Nome de usuário"
        self.fields["password1"].label = "Senha inicial"
        self.fields["password2"].label = "Confirmação da senha"

        atributos = {
            "first_name": {"autocomplete": "given-name"},
            "last_name": {"autocomplete": "family-name"},
            "email": {"autocomplete": "email"},
            "username": {"autocomplete": "username"},
            "password1": {"autocomplete": "new-password"},
            "password2": {"autocomplete": "new-password"},
        }
        for nome, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs.update(atributos.get(nome, {}))
            if self.is_bound and self.errors.get(nome):
                field.widget.attrs.update(
                    {"class": "form-control is-invalid", "aria-invalid": "true"}
                )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if get_user_model()._default_manager.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Já existe um usuário cadastrado com este e-mail."
            )
        return email

    # Ao persistir, o cadastro cria apenas contas funcionais comuns e as vincula
    # atomicamente a um único perfil da matriz de acesso.
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False

        if not commit:
            return user

        with transaction.atomic():
            user.save()
            user.groups.set([self.cleaned_data["perfil"]])

        return user
