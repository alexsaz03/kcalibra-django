"""
El formulario de alta de una persona de la casa que NO va a tener cuenta propia (R2/R-99,
"El alta de quien no entra" del "Cómo" de la especificación de la unidad 024).

Pide los mismos datos que cualquier alta con cuenta (`cuentas.forms.FormularioAlta`: sexo,
fecha de nacimiento, altura, peso, actividad, objetivo, ajuste y manías) más su nombre — sin
correo ni contraseña, porque quien no entra en la app no los necesita. Con ellos,
`perfiles.logica.crear_perfil_desde_alta` calcula su objetivo diario exactamente igual que a
cualquiera (R2: "la app le calcula su objetivo diario igual que a cualquiera").

Los campos físicos se repiten a mano en vez de heredar de `cuentas.forms.FormularioAlta`
—`cuentas/forms.py` NO puede tocarse aquí para extraer un formulario base sin arriesgar el
formulario de alta ya aprobado y probado por la unidad 004/023 (fuera del contrato de esta
unidad)—: queda anotado en hallazgos.md como duplicación consciente.
"""

from django import forms
from django.utils import timezone

from perfiles import constantes

from .models import Persona


class FormularioAltaPersonaACargo(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=100)
    sexo = forms.ChoiceField(label="Sexo", choices=constantes.SEXO_CHOICES)
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento", widget=forms.DateInput(attrs={"type": "date"})
    )
    altura_cm = forms.IntegerField(label="Altura (cm)", min_value=1)
    peso_kg = forms.DecimalField(
        label="Peso (kg)", min_value=0.1, max_digits=5, decimal_places=1
    )
    actividad = forms.ChoiceField(label="Actividad diaria", choices=constantes.ACTIVIDAD_CHOICES)
    objetivo = forms.ChoiceField(label="Objetivo", choices=constantes.OBJETIVO_CHOICES)
    ajuste_pct = forms.IntegerField(
        label="Ajuste manual (%) sobre lo que gasta",
        required=False,
        help_text="Déjalo en blanco para usar el ajuste de fábrica de su objetivo.",
    )
    dieta = forms.CharField(label="Tipo de dieta", required=False)
    alergias = forms.CharField(
        label="Alergias", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    intolerancias = forms.CharField(
        label="Intolerancias", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    no_le_gusta = forms.CharField(
        label="Lo que no le gusta", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def clean_nombre(self):
        # R-98/G-196: un nombre en blanco (o solo espacios) sería exactamente el hueco que
        # esta unidad existe para cerrar.
        valor = self.cleaned_data["nombre"].strip()
        if not valor:
            raise forms.ValidationError("El nombre no puede estar vacío.")
        return valor

    def clean_fecha_nacimiento(self):
        # R11 (unidad 004), el mismo validador que ya usa cuentas.forms.FormularioAlta.
        valor = self.cleaned_data["fecha_nacimiento"]
        if valor > timezone.localdate():
            raise forms.ValidationError("La fecha de nacimiento no puede ser futura.")
        return valor


class FormularioPasarACargo(forms.Form):
    """
    R1/R4 (unidad 026) — a quién se le puede pasar la ficha de una persona a cargo: alguien
    del MISMO hogar, que entre con su PROPIA cuenta, y que no sea quien pide (`excluir`). La
    validación vive AQUÍ, en el `ModelChoiceField`, no en la plantilla: un `<select>` que solo
    PINTA las opciones válidas no protege de nada si alguien postea otro id a mano (lección de
    la unidad 021, "lo que solo pinta el navegador, ningún test lo ve").

    El hogar de `destino` se comprueba dos veces a propósito, y no es redundante: la puerta
    `persona_del_hogar_o_404` (llamada ANTES de construir este formulario, en la vista) es la
    que decide qué le pasa a un id de OTRA casa — 404, nunca un error de formulario, para no
    confirmar que existe aunque sea en otro sitio (Q-11/Q-20). Este formulario solo decide
    entre las opciones que YA son del hogar correcto: sin cuenta propia (una persona a cargo)
    o la propia persona que pide, ninguna de las dos es un destino válido, y eso sí es un
    rechazo corriente (R4: "se rechaza"), no un 404.
    """

    destino = forms.ModelChoiceField(
        queryset=Persona.objects.none(),
        label="Nuevo responsable",
        error_messages={
            "invalid_choice": (
                "Ese destino no vale: tiene que ser otra persona de la casa que entre con su "
                "propia cuenta."
            ),
            "required": "Elige a quién le pasas la ficha.",
        },
    )

    def __init__(self, *args, hogar, excluir, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destino"].queryset = (
            Persona.objects.filter(hogar=hogar, usuario__isnull=False)
            .exclude(pk=excluir.pk)
            .order_by("nombre")
        )
