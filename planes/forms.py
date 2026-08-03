"""
El formulario de "apuntar una comida" (R1, R10): nombre, momento del día, calorías y los tres
macros. Al ser un `ModelForm`, hereda directamente los validadores del modelo
(`MinValueValidator(0)` en las cuatro magnitudes numéricas, `nombre` obligatorio) — no hace
falta repetirlos aquí a mano; Django los copia del campo del modelo al campo del formulario.
"""

from django import forms

from .models import ComidaDelPlan


class FormularioComida(forms.ModelForm):
    class Meta:
        model = ComidaDelPlan
        fields = [
            "nombre",
            "momento_del_dia",
            "calorias",
            "proteina_g",
            "grasa_g",
            "carbos_g",
        ]
        labels = {
            "nombre": "Nombre de la comida",
            "momento_del_dia": "Momento del día",
            "calorias": "Calorías (kcal)",
            "proteina_g": "Proteína (g)",
            "grasa_g": "Grasa (g)",
            "carbos_g": "Carbohidratos (g)",
        }
