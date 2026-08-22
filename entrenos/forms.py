"""
El formulario de "apuntar un entreno" (R1-R12, apuntar-un-entreno.md): el día, el deporte, la
intensidad, los minutos y —opcional— las calorías del reloj o pulsómetro (G-70).

Mismo patrón que `perfiles/forms.py:FormularioMedicion`: los `clean_*` repiten lo que ya cubren
los validadores del modelo, para que el aviso salga en el FORMULARIO, antes de tocar la base de
datos, señalando el campo exacto (R9: "no los guarda y lo dice").

`calorias` se declara a mano (no se deja que `ModelForm` la derive de `Entreno.calorias`,
que en el modelo es obligatoria): aquí es SIEMPRE opcional — dejarla en blanco es la manera de
pedir la estimación (G-70) — y `entrenos/logica.py` es quien decide el valor final antes de
guardar, nunca este formulario.
"""

from django import forms
from django.utils import timezone

from .models import Entreno


class FormularioEntreno(forms.ModelForm):
    calorias = forms.IntegerField(
        required=False,
        label="Calorías (si las sabes) — opcional",
        help_text=(
            "Déjalo en blanco y la app las estima con el deporte, la intensidad, los minutos "
            "y el peso de esa persona."
        ),
    )

    class Meta:
        model = Entreno
        fields = ["fecha", "deporte", "intensidad", "minutos", "calorias"]
        widgets = {
            # H1 de la revisión de la unidad 006 (peso.html): un `<input type="date">` solo
            # acepta `yyyy-mm-dd`; con `LANGUAGE_CODE="es"` Django localizaría a `dd/mm/yyyy` y
            # el navegador lo descartaría en silencio. Mismo arreglo, mismo sitio.
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        labels = {
            "fecha": "Día",
            "deporte": "Deporte",
            "intensidad": "Intensidad",
            "minutos": "Minutos",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Q-50 ("en pocos toques"): un formulario recién abierto propone "hoy" de fábrica,
        # igual que `FormularioMedicion` — no hay que teclear la fecha cada vez.
        if not self.is_bound and "fecha" not in (self.initial or {}):
            self.fields["fecha"].initial = timezone.localdate()

    def clean_minutos(self):
        # R9 — minutos cero o negativos se rechazan al entrar. El `MinValueValidator(1)` del
        # modelo ya lo cubriría al guardar; se repite aquí para que el aviso salga en el
        # FORMULARIO, antes de tocar la base de datos.
        valor = self.cleaned_data.get("minutos")
        if valor is None or valor <= 0:
            raise forms.ValidationError("Los minutos tienen que ser mayores que cero.")
        return valor

    def clean_calorias(self):
        # R9 — calorías negativas se rechazan al entrar. En blanco (None) SÍ es válido: es la
        # manera de pedir la estimación (G-70), no un error.
        valor = self.cleaned_data.get("calorias")
        if valor is not None and valor < 0:
            raise forms.ValidationError("Las calorías no pueden ser negativas.")
        return valor

    def clean_fecha(self):
        # Mismo criterio que `Entreno._fecha_no_futura` (ver models.py): se repite en el
        # formulario para que el aviso salga antes de tocar la base de datos.
        valor = self.cleaned_data.get("fecha")
        if valor is not None and valor > timezone.localdate():
            raise forms.ValidationError("El día no puede ser futuro.")
        return valor
