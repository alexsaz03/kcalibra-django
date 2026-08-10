"""
El formulario de una receta (R1-R3): nombre, raciones, para qué comidas vale y la preparación.
Los ingredientes NO son parte de este `ModelForm` — se leen aparte, en `recetas.logica`, desde
las listas paralelas que manda el formulario (ver el docstring de `logica.py`).

Mismo patrón que `despensa/forms.py`: los `clean_*` repiten lo que ya cubren los validadores del
modelo, para que el aviso salga en el FORMULARIO, antes de tocar la base de datos, señalando el
campo exacto (R2: "no lo guarda y lo dice en cristiano").
"""

from django import forms

from .models import MOMENTOS_DEL_DIA, Receta


class FormularioReceta(forms.ModelForm):
    # `comidas` se guarda como `JSONField` (lista de claves), pero se RELLENA como una lista de
    # casillas — MultipleChoiceField + CheckboxSelectMultiple, no el widget de texto que
    # generaría un ModelForm por defecto para un JSONField.
    comidas = forms.MultipleChoiceField(
        choices=MOMENTOS_DEL_DIA,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Para qué comidas vale",
        help_text="Si no marcas ninguna, la receta vale para cualquier comida.",
    )

    # R3 — la preparación se guarda LITERAL: `strip=False` a propósito, porque
    # `forms.CharField` recorta espacios de sobra por defecto (`strip=True` de fábrica) y R3
    # prohíbe "recortarla, normalizarla o reformatearla". Es la misma familia de trampa de
    # formato que ya mordió tres veces en este proyecto (localización de Django con
    # `<input type="date">`, SVG, `<input type="number">`): aquí el peligro no es Django
    # localizando, es Django "ayudando" a limpiar un texto que tiene que quedar intacto.
    preparacion = forms.CharField(
        required=False,
        strip=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Preparación",
        help_text="Escríbela de corrido, como te salga. Es opcional.",
    )

    class Meta:
        model = Receta
        fields = ["nombre", "raciones", "comidas", "preparacion"]
        labels = {"nombre": "Nombre del plato", "raciones": "Para cuántas raciones"}
        widgets = {
            "raciones": forms.NumberInput(attrs={"step": "1", "min": "1"}),
        }

    def clean_nombre(self):
        # R2 — un nombre vacío (o solo espacios) no se guarda.
        valor = (self.cleaned_data.get("nombre") or "").strip()
        if not valor:
            raise forms.ValidationError("Escribe el nombre de la receta.")
        return valor

    def clean_raciones(self):
        # R2 — raciones cero o negativas se rechazan al entrar. El `MinValueValidator` del
        # modelo ya lo cubriría al guardar; se repite aquí para que el aviso salga en el
        # FORMULARIO.
        valor = self.cleaned_data.get("raciones")
        if valor is None or valor <= 0:
            raise forms.ValidationError("Las raciones tienen que ser al menos 1.")
        return valor
