"""
El formulario de "tus datos" (R3, R6): lo que se puede cambiar desde el perfil una vez creada
la cuenta, según el flujo aprobado (cambiar-tus-datos.md, "Cómo se cambiarán con la app
terminada"): altura, actividad, objetivo, ajuste y las manías.

Fuera de este formulario, a propósito, quedan tres campos de `Perfil`:
- **El peso**: no se edita nunca desde el perfil (R7/G-61) — se apunta en Progreso, otra
  unidad futura.
- **El sexo y la fecha de nacimiento**: el flujo "con la app" de cambiar-tus-datos.md solo
  lista "altura, cuánto se mueve, dieta, alergias, intolerancias o lo que no le gusta" como
  editable aquí, y R3 solo dispara el recálculo con "altura, actividad, objetivo o ajuste" —
  ninguno de los dos aparece. Se fijan en el alta y no cambian después en esta unidad (ver
  hallazgos.md para la decisión completa).
"""

from django import forms
from django.utils import timezone

from .models import MedicionPeso, Perfil


class FormularioPerfil(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = [
            "altura_cm",
            "actividad",
            "objetivo",
            "ajuste_pct",
            "dieta",
            "alergias",
            "intolerancias",
            "no_le_gusta",
        ]
        widgets = {
            "alergias": forms.Textarea(attrs={"rows": 2}),
            "intolerancias": forms.Textarea(attrs={"rows": 2}),
            "no_le_gusta": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "altura_cm": "Altura (cm)",
            "actividad": "Actividad diaria",
            "objetivo": "Objetivo",
            "ajuste_pct": "Ajuste manual (%) sobre el gasto diario",
            "dieta": "Tipo de dieta",
            "alergias": "Alergias",
            "intolerancias": "Intolerancias",
            "no_le_gusta": "Lo que no te gusta",
        }
        help_texts = {
            "ajuste_pct": (
                "Al cambiar de objetivo este campo vuelve siempre al de fábrica del "
                "objetivo nuevo; puedes volver a ponerlo a mano después si quieres."
            ),
        }

    def clean_altura_cm(self):
        # R11: los datos imposibles se rechazan al entrar. El validador del modelo
        # (`MinValueValidator`) ya lo cubriría al guardar, pero se repite aquí para que el
        # mensaje salga en la validación del FORMULARIO (antes de tocar la base de datos),
        # con el campo señalado, tal como pide R11 ("se avisa de cuál está mal").
        valor = self.cleaned_data["altura_cm"]
        if valor is None or valor <= 0:
            raise forms.ValidationError("La altura tiene que ser mayor que cero.")
        return valor


class FormularioMedicion(forms.ModelForm):
    """
    El formulario de "apuntar el peso" (unidad 006, R1/R3/R10): el día, el peso —obligatorio—
    y, opcionales, la grasa corporal y la cintura. Mismo patrón que `FormularioPerfil` de
    arriba: los `clean_*` repiten lo que ya cubren los validadores del modelo, para que el
    aviso salga en el FORMULARIO, antes de tocar la base de datos, señalando el campo exacto
    (R10: "se rechazan al entrar, con su mensaje").
    """

    class Meta:
        model = MedicionPeso
        fields = ["fecha", "peso_kg", "grasa_pct", "cintura_cm"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "fecha": "Día",
            "peso_kg": "Peso (kg)",
            "grasa_pct": "Grasa corporal (%) — opcional",
            "cintura_cm": "Cintura (cm) — opcional",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un formulario recién abierto (sin datos enviados todavía) propone "hoy" de fábrica:
        # el gesto tiene que ser corto (§8, "descalzo y con prisa"), no obligar a teclear la
        # fecha cada vez.
        if not self.is_bound:
            self.fields["fecha"].initial = timezone.localdate()

    def clean_peso_kg(self):
        valor = self.cleaned_data.get("peso_kg")
        if valor is None or valor <= 0:
            raise forms.ValidationError("El peso tiene que ser mayor que cero.")
        return valor

    def clean_grasa_pct(self):
        valor = self.cleaned_data.get("grasa_pct")
        if valor is not None and not (0 <= valor <= 100):
            raise forms.ValidationError("La grasa corporal tiene que estar entre 0 y 100.")
        return valor

    def clean_fecha(self):
        valor = self.cleaned_data.get("fecha")
        if valor is not None and valor > timezone.localdate():
            raise forms.ValidationError("La fecha no puede ser futura.")
        return valor
