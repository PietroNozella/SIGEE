from django import forms


class AceiteDocumentosLegaisForm(forms.Form):
    versao_termos = forms.CharField(widget=forms.HiddenInput())
    versao_privacidade = forms.CharField(widget=forms.HiddenInput())
    aceitou_termos = forms.BooleanField(
        required=True,
        error_messages={
            "required": "Você precisa aceitar os Termos de Uso para continuar."
        },
        widget=forms.CheckboxInput(attrs={"class": "legal-checkbox"}),
    )
    confirmou_ciencia_privacidade = forms.BooleanField(
        required=True,
        error_messages={
            "required": (
                "Você precisa confirmar a leitura da Política de Privacidade "
                "para continuar."
            )
        },
        widget=forms.CheckboxInput(attrs={"class": "legal-checkbox"}),
    )
