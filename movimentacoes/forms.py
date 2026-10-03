from django import forms
from django.contrib.auth import get_user_model

from inventario.models import Equipamento, Local, TipoEquipamento
from usuarios.permissoes import usuarios_funcionais_ativos


class DestinatarioRetiradaField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        nome = usuario.get_full_name() or usuario.username
        return f"{nome} ({usuario.username})"


class ConsultaRetiradaForm(forms.Form):
    tipo_equipamento = forms.ModelChoiceField(
        label="Tipo/modelo do equipamento", queryset=TipoEquipamento.objects.none(),
        empty_label="Selecione um tipo/modelo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    local = forms.ModelChoiceField(
        label="Local de retirada", queryset=Local.objects.none(), required=False,
        empty_label="Selecione um local",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    quantidade = forms.IntegerField(
        label="Quantidade", min_value=1, required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tipo e local são filtros; sua inativação não acrescenta uma nova regra
        # de disponibilidade aos equipamentos físicos da RN-02.
        self.fields["tipo_equipamento"].queryset = TipoEquipamento.objects.filter(
            equipamentos__ativo=True,
        ).distinct().order_by("nome")
        tipo_id = (self.data if self.is_bound else self.initial).get("tipo_equipamento")
        locais = Local.objects.filter(equipamento__ativo=True)
        if tipo_id:
            try:
                tipo_id = int(tipo_id)
            except (TypeError, ValueError):
                locais = Local.objects.none()
            else:
                locais = locais.filter(equipamento__tipo_id=tipo_id)
        else:
            locais = Local.objects.none()
        self.fields["local"].queryset = locais.distinct().order_by("nome")


class RetiradaSemReservaForm(ConsultaRetiradaForm):
    destinatario = DestinatarioRetiradaField(
        label="Destinatário", queryset=get_user_model().objects.none(),
        empty_label="Selecione quem receberá os equipamentos",
        error_messages={
            "invalid_choice": "Selecione um destinatário ativo com um único perfil funcional.",
        },
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    observacao = forms.CharField(
        label="Observação", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    equipamentos = forms.ModelMultipleChoiceField(
        label="Patrimônios da retirada", queryset=Equipamento.objects.all(),
        widget=forms.MultipleHiddenInput,
        error_messages={
            "required": "Consulte a disponibilidade e confira os patrimônios da retirada.",
            "invalid_choice": "Um dos patrimônios informados não está cadastrado. Revise o lote.",
            "invalid_pk_value": "Informe patrimônios cadastrados para a retirada.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["local"].required = True
        self.fields["quantidade"].required = True
        self.fields["destinatario"].queryset = usuarios_funcionais_ativos()

    def clean_equipamentos(self):
        valores = self.fields["equipamentos"].widget.value_from_datadict(
            self.data, self.files, "equipamentos",
        )
        if len(valores) != len(set(valores)):
            raise forms.ValidationError("Não repita o mesmo patrimônio no lote.")
        return self.cleaned_data["equipamentos"]

    def clean(self):
        dados = super().clean()
        quantidade = dados.get("quantidade")
        equipamentos = dados.get("equipamentos")
        if quantidade is not None and equipamentos is not None and len(equipamentos) != quantidade:
            self.add_error("equipamentos", "Selecione exatamente a quantidade informada.")
        return dados

    def add_error(self, field, error):
        super().add_error(field, error)
        for nome in self.errors:
            if nome in self.fields:
                widget = self.fields[nome].widget
                classes = widget.attrs.get("class", "").split()
                if "is-invalid" not in classes:
                    classes.append("is-invalid")
                widget.attrs.update({
                    "class": " ".join(classes), "aria-invalid": "true",
                    "aria-describedby": f"id_{nome}_error",
                })
