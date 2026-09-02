from django import forms

from .models import Equipamento


class EquipamentoForm(forms.ModelForm):
    """Valida os dados de cadastro antes da persistência do equipamento."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["numero_patrimonio"].label = "Número de patrimônio"
        self.fields["nome"].label = "Nome do equipamento"
        self.fields["descricao"].label = "Descrição"
        self.fields["categoria"].label = "Categoria"
        self.fields["local"].label = "Local"
        self.fields["situacao"].label = "Situação"

        self.fields["categoria"].empty_label = "Selecione uma categoria"
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
                "placeholder": "Ex.: Notebook Dell",
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

        if self.is_bound:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if field is None:
                    continue
                current_classes = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{current_classes} is-invalid".strip()
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"id_{field_name}_error"

    class Meta:
        model = Equipamento
        fields = (
            "numero_patrimonio",
            "nome",
            "descricao",
            "categoria",
            "local",
            "situacao",
        )
