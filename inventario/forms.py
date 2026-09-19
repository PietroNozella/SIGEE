from django import forms
from django.core.validators import FileExtensionValidator

from .models import Categoria, Equipamento, TipoEquipamento


class EquipamentoForm(forms.ModelForm):
    """Valida os dados de cadastro antes da persistência do equipamento."""

    nome = forms.CharField(label="Tipo/modelo do equipamento", max_length=150)
    categoria = forms.ModelChoiceField(
        label="Categoria",
        queryset=Categoria.objects.filter(ativo=True).order_by("nome"),
        empty_label="Selecione uma categoria",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["numero_patrimonio"].label = "Número de patrimônio"
        self.fields["descricao"].label = "Descrição"
        self.fields["local"].label = "Local"
        self.fields["situacao"].label = "Situação"

        self.fields["local"].empty_label = "Selecione um local"
        self.fields["situacao"].choices = [
            ("", "Selecione uma situação"),
            *Equipamento.Situacao.choices,
        ]

        field_configuration = {
            "numero_patrimonio": {
                "class": "form-control",
                "placeholder": "Ex.: PAT-001",
            },
            "nome": {
                "class": "form-control",
                "placeholder": "Ex.: Notebook Dell Latitude 5420",
            },
            "descricao": {
                "class": "form-control",
                "placeholder": "Informações complementares sobre o equipamento",
                "rows": 4,
            },
            "categoria": {"class": "form-select"},
            "local": {"class": "form-select"},
            "situacao": {"class": "form-select"},
        }

        for field_name, attributes in field_configuration.items():
            self.fields[field_name].widget.attrs.update(attributes)

        self.order_fields(
            (
                "numero_patrimonio",
                "nome",
                "descricao",
                "categoria",
                "local",
                "situacao",
            )
        )

        if self.instance.pk and not self.is_bound:
            self.initial.setdefault("nome", self.instance.tipo.nome)
            self.initial.setdefault("categoria", self.instance.tipo.categoria)

        if self.is_bound:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if field is None:
                    continue
                current_classes = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{current_classes} is-invalid".strip()
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"id_{field_name}_error"

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def save(self, commit=True):
        equipamento = super().save(commit=False)
        tipo, _ = TipoEquipamento.objects.get_or_create(
            categoria=self.cleaned_data["categoria"],
            nome=self.cleaned_data["nome"],
        )
        equipamento.tipo = tipo

        if commit:
            equipamento.save()
            self.save_m2m()

        return equipamento

    class Meta:
        model = Equipamento
        fields = (
            "numero_patrimonio",
            "descricao",
            "local",
            "situacao",
        )


class ImportacaoEquipamentosCSVForm(forms.Form):
    """Valida o arquivo enviado para o cadastro em lote de equipamentos."""

    TAMANHO_MAXIMO_ARQUIVO = 2 * 1024 * 1024

    arquivo = forms.FileField(
        label="Arquivo CSV",
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".csv,text/csv"}
        ),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]

        if arquivo.size > self.TAMANHO_MAXIMO_ARQUIVO:
            raise forms.ValidationError(
                "O arquivo CSV deve ter no máximo 2 MB.",
            )

        return arquivo
