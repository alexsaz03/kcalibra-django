"""
Los formularios de la despensa (R1-R3, R5, R6, R11): añadir un producto (nombre, cuánto hay,
unidad y categoría) y corregir cantidad/unidad/categoría de uno que ya existe. Mismo patrón
que el resto de la app (`entrenos/forms.py`, `perfiles/forms.py:FormularioMedicion`): los
`clean_*` repiten lo que ya cubren los validadores del modelo, para que el aviso salga en el
FORMULARIO, antes de tocar la base de datos, señalando el campo exacto (R11: "no lo guarda y
lo dice").
"""

from django import forms

from .models import ProductoDespensa


class FormularioProducto(forms.ModelForm):
    """R1-R3 — añadir un producto a mano: nombre, cantidad, unidad y categoría."""

    class Meta:
        model = ProductoDespensa
        fields = ["nombre", "cantidad", "unidad", "categoria"]
        labels = {
            "nombre": "Producto",
            "cantidad": "Cuánto hay",
            "unidad": "Unidad",
            "categoria": "Categoría",
        }
        widgets = {
            "cantidad": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }

    def clean_nombre(self):
        # R11 — un nombre vacío (o solo espacios) no se guarda. El recorte de espacios de
        # sobra en sí (R2) lo hace `ProductoDespensa.save()`; aquí solo se rechaza el vacío.
        valor = (self.cleaned_data.get("nombre") or "").strip()
        if not valor:
            raise forms.ValidationError("Escribe el nombre del producto.")
        return valor

    def clean_cantidad(self):
        # R11 — cantidad cero o negativa se rechaza al entrar. El `MinValueValidator` del
        # modelo ya lo cubriría al guardar; se repite aquí para que el aviso salga en el
        # FORMULARIO, antes de tocar la base de datos.
        valor = self.cleaned_data.get("cantidad")
        if valor is None or valor <= 0:
            raise forms.ValidationError("La cantidad tiene que ser mayor que cero.")
        return valor


class FormularioCorregirProducto(forms.ModelForm):
    """R5 — corregir cantidad, unidad y categoría de una línea ya existente. El nombre NO se
    corrige aquí: R5 solo nombra esas tres cosas, y ninguna otra parte del contrato pide poder
    renombrar una línea."""

    class Meta:
        model = ProductoDespensa
        fields = ["cantidad", "unidad", "categoria"]
        labels = {"cantidad": "Cantidad", "unidad": "Unidad", "categoria": "Categoría"}
        widgets = {
            "cantidad": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }

    def clean_cantidad(self):
        valor = self.cleaned_data.get("cantidad")
        if valor is None or valor <= 0:
            raise forms.ValidationError("La cantidad tiene que ser mayor que cero.")
        return valor
