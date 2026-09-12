from django import forms

from .eventos import rotulo_acao
from .models import RegistroAuditoria


class AuditoriaFiltroForm(forms.Form):
    usuario = forms.CharField(
        required=False,
        label="Usuário",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome ou usuário",
            }
        ),
    )
    acao = forms.ChoiceField(
        required=False,
        label="Ação",
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    resultado = forms.ChoiceField(
        required=False,
        label="Resultado",
        choices=(("", "Todos os resultados"), *RegistroAuditoria.Resultado.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    data_inicial = forms.DateField(
        required=False,
        label="Data inicial",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    data_final = forms.DateField(
        required=False,
        label="Data final",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        acoes = (
            RegistroAuditoria.objects.order_by("acao")
            .values_list("acao", flat=True)
            .distinct()
        )
        self.fields["acao"].choices = [
            ("", "Todas as ações"),
            *((acao, rotulo_acao(acao)) for acao in acoes),
        ]

    def clean(self):
        dados = super().clean()
        data_inicial = dados.get("data_inicial")
        data_final = dados.get("data_final")

        if data_inicial and data_final and data_inicial > data_final:
            self.add_error(
                "data_final",
                "A data final deve ser igual ou posterior à data inicial.",
            )

        return dados
