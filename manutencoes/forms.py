from django import forms
from django.db.models import Exists, OuterRef

from inventario.models import Equipamento

from .models import Manutencao


class FormularioManutencao(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            if isinstance(campo.widget, forms.Textarea):
                campo.widget.attrs["rows"] = 4

    def configurar_erros(self):
        if self.is_bound:
            for nome in self.errors:
                if nome in self.fields:
                    self.fields[nome].widget.attrs.update({
                        "aria-invalid": "true", "aria-describedby": f"id_{nome}_error",
                    })


class AberturaManutencaoForm(FormularioManutencao):
    equipamento = forms.ModelChoiceField(queryset=Equipamento.objects.none(), label="Equipamento")
    descricao_problema = forms.CharField(label="Descrição do problema", widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        abertas = Manutencao.objects.filter(equipamento_id=OuterRef("pk")).exclude(estado=Manutencao.Estado.CONCLUIDA)
        self.fields["equipamento"].queryset = Equipamento.objects.filter(
            ativo=True, situacao=Equipamento.Situacao.DISPONIVEL,
        ).annotate(manutencao_aberta=Exists(abertas)).filter(manutencao_aberta=False).select_related("tipo")
        self.fields["equipamento"].empty_label = "Selecione um equipamento disponível"
        self.configurar_erros()


class ConclusaoManutencaoForm(FormularioManutencao):
    resultado = forms.ChoiceField(label="Resultado", choices=[("", "Selecione o resultado"), *Manutencao.Resultado.choices])
    descricao_solucao = forms.CharField(label="Solução ou conclusão da análise", widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configurar_erros()
