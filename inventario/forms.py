from django import forms

from .models import Equipamento


class EquipamentoForm(forms.ModelForm):
    """Valida os dados de cadastro antes da persistência do equipamento."""

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
