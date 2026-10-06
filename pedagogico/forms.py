from django import forms

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
