from datetime import datetime

from django import forms
from django.utils import timezone

from inventario.models import Local, TipoEquipamento
from pedagogico.forms import UtilizacaoPedagogicaForm

from .models import Reserva


class PeriodoReservaForm(forms.Form):
    data_reserva = forms.DateField(
        label="Data",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"class": "form-control", "type": "date"},
        ),
    )
    hora_inicio = forms.TimeField(
        label="Início",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            format="%H:%M",
            attrs={"class": "form-control", "type": "time"},
        ),
    )
    hora_fim = forms.TimeField(
        label="Término",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            format="%H:%M",
            attrs={"class": "form-control", "type": "time"},
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_reserva"].widget.attrs.update({
            "min": timezone.localdate().isoformat(),
            "max": Reserva.data_limite_agendamento().isoformat(),
        })
        self.fields["data_reserva"].help_text = (
            f"Agende para hoje ou até {Reserva.ANTECEDENCIA_MAXIMA_DIAS} dias corridos à frente."
        )

    def clean(self):
        cleaned_data = super().clean()
        data_reserva = cleaned_data.get("data_reserva")
        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fim = cleaned_data.get("hora_fim")
        if data_reserva and hora_inicio:
            cleaned_data["inicio"] = timezone.make_aware(
                datetime.combine(data_reserva, hora_inicio),
                timezone.get_current_timezone(),
            )
        if data_reserva and hora_fim:
            cleaned_data["fim"] = timezone.make_aware(
                datetime.combine(data_reserva, hora_fim),
                timezone.get_current_timezone(),
            )
        return cleaned_data


class ReservaForm(PeriodoReservaForm, UtilizacaoPedagogicaForm):
    tipo_equipamento = forms.ModelChoiceField(
        queryset=TipoEquipamento.objects.none(),
        label="Equipamento",
        empty_label="Selecione um tipo/modelo",
    )
    local = forms.ModelChoiceField(
        queryset=Local.objects.none(),
        label="Local",
        empty_label="Selecione o local de retirada",
    )
    quantidade = forms.IntegerField(
        label="Quantidade",
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 1,
                "inputmode": "numeric",
                "disabled": True,
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, marcar_erros=False, **kwargs)

        self.fields["tipo_equipamento"].queryset = (
            TipoEquipamento.objects.select_related("categoria")
            .filter(ativo=True, equipamentos__ativo=True)
            .distinct()
            .order_by("categoria__nome", "nome")
        )
        self.fields["tipo_equipamento"].widget.attrs.update(
            {"class": "form-select", "data-reservation-type": ""}
        )
        self.fields["local"].queryset = (
            Local.objects.filter(
                ativo=True,
                equipamento__ativo=True,
                equipamento__tipo__ativo=True,
            )
            .distinct()
            .order_by("nome")
        )
        self.fields["local"].widget.attrs.update(
            {"class": "form-select", "data-reservation-location": ""}
        )
        self.fields["quantidade"].widget.attrs["data-reservation-quantity"] = ""
        self.fields["data_reserva"].widget.attrs["data-reservation-date"] = ""
        self.fields["hora_inicio"].widget.attrs["data-reservation-start"] = ""
        self.fields["hora_fim"].widget.attrs["data-reservation-end"] = ""
        self.fields["hora_inicio"].help_text = ""
        self.fields["hora_fim"].help_text = ""
        self.fields["quantidade"].help_text = ""

        self.order_fields(
            (
                "tipo_equipamento",
                "local",
                "data_reserva",
                "hora_inicio",
                "hora_fim",
                "quantidade",
                "turma", "disciplina", "atividade", "observacao",
            )
        )

        if self.is_bound:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if field is None:
                    continue
                classes = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{classes} is-invalid".strip()
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"id_{field_name}_error"


class DisponibilidadeReservaForm(PeriodoReservaForm):
    tipo_equipamento = forms.ModelChoiceField(queryset=TipoEquipamento.objects.none())
    local = forms.ModelChoiceField(queryset=Local.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo_equipamento"].queryset = TipoEquipamento.objects.filter(
            ativo=True
        )
        self.fields["local"].queryset = Local.objects.filter(ativo=True)
        self.order_fields(
            ("tipo_equipamento", "local", "data_reserva", "hora_inicio", "hora_fim")
        )


class CancelamentoOperacionalForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo da desistência",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        error_messages={"required": "Informe o motivo da desistência comunicada pelo Professor."},
    )
    desistencia_confirmada = forms.BooleanField(
        label="Confirmo que o Professor comunicou que não utilizará os equipamentos desta reserva.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={"required": "Confirme que o Professor comunicou a desistência da reserva."},
    )
