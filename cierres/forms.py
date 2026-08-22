"""
Los formularios de "cerrar el día" (unidad 012, decir-si-cumpliste.md): el de un toque, para
la pregunta al abrir la app (Q-140, solo la respuesta, sin pantalla intermedia), y el completo,
para el cierre a mano desde Progreso (R10: cualquier día, también cambiar uno ya cerrado).

Mismo patrón que `perfiles/forms.py:FormularioMedicion` y `entrenos/forms.py:
FormularioEntreno`: los `clean_*` repiten lo que ya cubren los validadores del modelo, para que
el aviso salga en el FORMULARIO, antes de tocar la base de datos, señalando el campo exacto
(R11: "no lo guarda y lo dice").
"""

from django import forms
from django.utils import timezone

from .models import CierreDeDia


class FormularioRespuestaRapida(forms.Form):
    """
    R6/Q-140 — la pregunta al abrir la app: UN solo campo, la respuesta, para que contestar sea
    un toque de verdad (el día es SIEMPRE el que decide el servidor —el último pendiente—,
    nunca un valor que traiga el formulario: ver `cierres/views.py:responder`). Calorías y
    nota no aparecen aquí (R2: son opcionales y este es el camino corto; quien quiera
    añadirlas usa el cierre a mano desde Progreso con `FormularioCierre`, abajo).
    """

    respuesta = forms.ChoiceField(choices=CierreDeDia.RESPUESTAS)


class FormularioCierre(forms.ModelForm):
    """El cierre completo (R10): cualquier día, con calorías y nota opcionales."""

    class Meta:
        model = CierreDeDia
        fields = ["fecha", "respuesta", "calorias_comidas", "nota"]
        widgets = {
            # Mismo arreglo que `FormularioMedicion`/`FormularioEntreno`: con
            # `LANGUAGE_CODE="es"` Django localizaría a `dd/mm/yyyy`, que un
            # `<input type="date">` descarta en silencio.
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "nota": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "fecha": "Día",
            "respuesta": "¿Siguió el plan?",
            "calorias_comidas": "Calorías comidas de verdad — opcional",
            "nota": "Nota — opcional",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and "fecha" not in (self.initial or {}):
            self.fields["fecha"].initial = timezone.localdate()
        # R2 — "la app ofrece EXACTAMENTE tres respuestas... ninguna más": sin esto, Django
        # añade solo una opción en blanco ("---------") de fábrica a cualquier `ModelForm`
        # sobre un `CharField` con `choices` que no tiene `default` (aunque sea `required`,
        # como aquí) — una CUARTA fila en el desplegable que no es ninguna de las tres
        # respuestas del negocio. Se fuerza la lista exacta del modelo.
        self.fields["respuesta"].choices = CierreDeDia.RESPUESTAS

    def clean_calorias_comidas(self):
        # R11 — calorías negativas se rechazan al entrar. En blanco (None) sí es válido: R2
        # las declara opcionales de verdad.
        valor = self.cleaned_data.get("calorias_comidas")
        if valor is not None and valor < 0:
            raise forms.ValidationError("Las calorías no pueden ser negativas.")
        return valor

    def clean_fecha(self):
        # R11 — una fecha futura se rechaza al entrar (R10 sí permite pasadas, cualquiera).
        valor = self.cleaned_data.get("fecha")
        if valor is not None and valor > timezone.localdate():
            raise forms.ValidationError("La fecha no puede ser futura.")
        return valor
