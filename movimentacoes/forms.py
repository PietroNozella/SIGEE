from django import forms
from django.contrib.auth import get_user_model

from inventario.models import Equipamento, Local, TipoEquipamento
from usuarios.permissoes import usuarios_funcionais_ativos

from .models import Movimentacao


class DestinatarioRetiradaField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        nome = usuario.get_full_name() or usuario.username
        return f"{nome} ({usuario.username})"


class DevolucaoForm(forms.Form):
    retiradas = forms.ModelMultipleChoiceField(
        label="Patrimônios recebidos", queryset=Movimentacao.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Marque pelo menos um patrimônio recebido.",
            "invalid_choice": "Uma unidade selecionada já foi devolvida ou não pertence a este grupo. Revise a lista.",
            "invalid_pk_value": "Selecione unidades válidas deste grupo.",
        },
    )
    observacao = forms.CharField(
        label="Observação", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, retiradas, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["retiradas"].queryset = retiradas
        self.initial.setdefault("retiradas", list(retiradas.values_list("pk", flat=True)))
        for retirada in retiradas:
            self.fields[f"problema_{retirada.pk}"] = forms.BooleanField(
                label=f"Problema no patrimônio {retirada.equipamento.numero_patrimonio}", required=False,
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )
            self.fields[f"descricao_problema_{retirada.pk}"] = forms.CharField(
                label=f"Descrição do problema — {retirada.equipamento.numero_patrimonio}", required=False,
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            )
        if self.is_bound:
            for nome in self.errors:
                if nome in self.fields:
                    self.fields[nome].widget.attrs.update({
                        "aria-invalid": "true", "aria-describedby": f"id_{nome}_error",
                    })

    def clean(self):
        dados = super().clean()
        recebidas = {item.pk for item in dados.get("retiradas", [])}
        problemas = {}
        for retirada in self.fields["retiradas"].queryset:
            marcado = dados.get(f"problema_{retirada.pk}")
            descricao = dados.get(f"descricao_problema_{retirada.pk}", "")
            if (marcado or descricao) and retirada.pk not in recebidas:
                self.add_error(f"problema_{retirada.pk}", "Registre problemas somente em patrimônios recebidos.")
            elif marcado and not descricao:
                self.add_error(f"descricao_problema_{retirada.pk}", "Descreva o problema deste patrimônio.")
            elif descricao and not marcado:
                self.add_error(f"problema_{retirada.pk}", "Marque o encaminhamento para manutenção ou remova a descrição.")
            elif marcado:
                problemas[retirada.pk] = descricao
        dados["problemas"] = problemas
        return dados

    def clean_retiradas(self):
        valores = self.fields["retiradas"].widget.value_from_datadict(self.data, self.files, "retiradas")
        if len(valores) != len(self.cleaned_data["retiradas"]):
            raise forms.ValidationError("Não repita o mesmo patrimônio na devolução.")
        return self.cleaned_data["retiradas"]


class RetiradaReservaForm(forms.Form):
    observacao = forms.CharField(
        label="Observação", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class HistoricoFiltroForm(forms.Form):
    busca = forms.CharField(
        label="Patrimônio, equipamento ou pessoa", required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "type": "search"}),
    )
    tipo = forms.ChoiceField(
        label="Movimentação", required=False,
        choices=[("", "Todas")] + list(Movimentacao.Tipo.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reserva = forms.IntegerField(
        label="Número da reserva", required=False, min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    retirada = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    inicio = forms.DateField(
        label="De", required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    fim = forms.DateField(
        label="Até", required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["fim"] < dados["inicio"]:
            self.add_error("fim", "A data final deve ser igual ou posterior à inicial.")
        return dados


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
