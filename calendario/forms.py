from datetime import time

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import FaixaHorario, RegraCalendario


class RegraCalendarioForm(forms.ModelForm):
    funcionamento = forms.ChoiceField(label="Funcionamento", choices=[
        ("FECHADO", "Fechado"), ("INTEIRO", "Dia inteiro"), ("FAIXAS", "Faixas de horário"),
    ], widget=forms.RadioSelect)
    motivo = forms.CharField(label="Motivo da alteração", widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    versao = forms.IntegerField(widget=forms.HiddenInput, min_value=1)

    class Meta:
        model = RegraCalendario
        fields = ["finalidade", "data"]
        labels = {"finalidade": "Horário afetado", "data": "Data da exceção"}
        widgets = {"finalidade": forms.Select(attrs={"class": "form-select"}),
                   "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})}

    def __init__(self, *args, semanal=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.semanal = semanal
        if "data" in self.fields:
            self.fields["data"].widget.attrs["min"] = timezone.localdate().isoformat()
            self.fields["data"].widget.attrs["data-calendar-date-input"] = ""
        if semanal:
            self.fields["finalidade"].disabled = True
            self.fields.pop("data")
        elif self.instance.pk:
            self.fields["data"].disabled = True
            self.fields["finalidade"].disabled = True
        else:
            self.fields["data"].required = True

    def clean(self):
        dados = super().clean()
        self.instance.dia_inteiro = dados.get("funcionamento") == "INTEIRO"
        return dados


class FaixaHorarioForm(forms.ModelForm):
    class Meta:
        model = FaixaHorario
        fields = ["inicio", "fim"]
        labels = {"inicio": "Início", "fim": "Término"}
        widgets = {campo: forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control"}) for campo in ("inicio", "fim")}


class FaixasFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        faixas = sorted([f.cleaned_data for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")], key=lambda f: f["inicio"])
        for anterior, atual in zip(faixas, faixas[1:]):
            if anterior["fim"] == time.min or atual["inicio"] < anterior["fim"]:
                raise ValidationError("As faixas de horário não podem se sobrepor. Revise os intervalos.")


FaixaHorarioFormSet = inlineformset_factory(RegraCalendario, FaixaHorario, form=FaixaHorarioForm, formset=FaixasFormSet, extra=1, can_delete=True)


class RemoverExcecaoForm(forms.Form):
    motivo = forms.CharField(label="Motivo da remoção", widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    versao = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
