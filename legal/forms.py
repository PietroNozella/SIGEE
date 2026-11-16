from django import forms

from .conteudo import interpretar_conteudo


class RevisaoRascunhoForm(forms.Form):
    revisao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class RascunhoDocumentoForm(RevisaoRascunhoForm):
    contato = forms.EmailField(
        label="E-mail de contato", max_length=254,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    conteudo = forms.CharField(
        label="Conteúdo", max_length=40000,
        help_text=(
            "Comece títulos com ## e itens de lista com -. Use uma linha em branco "
            "entre títulos, parágrafos e listas. Digite [[contato]] para inserir o link "
            "do e-mail no texto."
        ),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 18}),
    )
    resumo = forms.CharField(
        label="Resumo das mudanças", max_length=2000, required=False,
        help_text="Obrigatório para publicar. O resumo ficará visível aos usuários.",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def clean_conteudo(self):
        conteudo = self.cleaned_data["conteudo"]
        interpretar_conteudo(conteudo)
        return conteudo


class AceiteDocumentosLegaisForm(forms.Form):
    versao_termos = forms.CharField(max_length=20, widget=forms.HiddenInput())
    versao_privacidade = forms.CharField(max_length=20, widget=forms.HiddenInput())
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
