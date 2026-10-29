from django import forms
from django.db.models import Q

from .models import AtividadePedagogica, Disciplina, Turma


class CadastroPedagogicoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].widget.attrs["class"] = "form-control"
        if "descricao" in self.fields:
            self.fields["descricao"].widget.attrs.update({"class": "form-control", "rows": 4})
        if self.is_bound:
            for nome in self.errors:
                if nome in self.fields:
                    self.fields[nome].widget.attrs.update({
                        "class": "form-control is-invalid",
                        "aria-invalid": "true",
                        "aria-describedby": f"id_{nome}_error",
                    })


class TurmaForm(CadastroPedagogicoForm):
    class Meta:
        model = Turma
        fields = ("nome",)


class DisciplinaForm(CadastroPedagogicoForm):
    class Meta:
        model = Disciplina
        fields = ("nome",)


class AtividadePedagogicaForm(CadastroPedagogicoForm):
    class Meta:
        model = AtividadePedagogica
        fields = ("nome", "descricao")
        labels = {"descricao": "Descrição"}


class UtilizacaoPedagogicaForm(forms.Form):
    turma = forms.ModelChoiceField(queryset=Turma.objects.none(), label="Turma")
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.none(), label="Disciplina")
    atividade = forms.ModelChoiceField(queryset=AtividadePedagogica.objects.none(), label="Atividade pedagógica")
    observacao = forms.CharField(label="Observação", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, utilizacao=None, reserva=None, marcar_erros=True, **kwargs):
        contexto = utilizacao or reserva
        if utilizacao is not None:
            kwargs["initial"] = {
                "turma": utilizacao.turma_id, "disciplina": utilizacao.disciplina_id,
                "atividade": utilizacao.atividade_id, "observacao": utilizacao.observacao,
            }
        elif reserva is not None:
            kwargs["initial"] = {
                "turma": reserva.turma_id, "disciplina": reserva.disciplina_id,
                "atividade": reserva.atividade_id, "observacao": reserva.observacao_pedagogica,
            }
        super().__init__(*args, **kwargs)
        self.cadastros_faltantes = []
        for campo, modelo in (("turma", Turma), ("disciplina", Disciplina), ("atividade", AtividadePedagogica)):
            criterio = Q(ativo=True)
            if contexto is not None:
                criterio |= Q(pk=getattr(contexto, f"{campo}_id"))
            self.fields[campo].queryset = modelo.objects.filter(criterio)
            if not self.fields[campo].queryset.exists():
                self.cadastros_faltantes.append(self.fields[campo].label)
        for campo in ("turma", "disciplina", "atividade", "observacao"):
            field = self.fields[campo]
            field.widget.attrs["class"] = "form-control" if campo == "observacao" else "form-select"
            if marcar_erros and self.is_bound and campo in self.errors:
                field.widget.attrs.update({
                    "class": field.widget.attrs["class"] + " is-invalid",
                    "aria-invalid": "true", "aria-describedby": f"id_{campo}_error",
                })
