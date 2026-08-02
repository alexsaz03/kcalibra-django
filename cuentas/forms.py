"""
Los campos propios del formulario de alta: el código de hogar (unidad 003) y, desde la unidad
004, los datos físicos, la actividad, el objetivo y las manías — "el alta crece" (ver el
"Cómo" de la especificación de la unidad 004): el flujo aprobado (crear-cuenta.md, "con la
app") pide contarlos ya en el registro, no en una pantalla aparte después.

`allauth` ya construye el resto del formulario (correo, contraseña dos veces); esto se
engancha mediante `ACCOUNT_SIGNUP_FORM_CLASS` (ver settings.py), el punto de extensión que la
propia librería deja preparado para añadir campos sin tocar sus vistas.

Importante (y no evidente): esta clase NO puede heredar de `allauth.account.forms.SignupForm`.
`allauth` construye su formulario final MEZCLANDO esta clase con el suyo propio en tiempo de
arranque (`base_signup_form_class()`); si esta clase ya importase el formulario de allauth,
se produce un import circular (allauth todavía se está montando cuando intenta cargar esto).
Por eso hereda solo de `forms.Form`, con el único método que allauth espera: `signup(self,
request, user)`, llamado justo después de crear la cuenta.
"""

from django import forms
from django.contrib import messages
from django.utils import timezone

from hogares.logica import crear_hogar_propio
from hogares.models import Hogar
from perfiles import constantes
from perfiles.logica import crear_perfil_desde_alta


class FormularioAlta(forms.Form):
    codigo_hogar = forms.CharField(
        label="Código de hogar (si ya tienes uno)",
        required=False,
        help_text=(
            "Déjalo en blanco para empezar tu propio hogar. Si alguien de tu casa ya tiene "
            "cuenta en KCalibra, pon aquí su código para pedir entrar."
        ),
    )

    # ------------------------------------------------------------------------------------
    # Unidad 004: los datos físicos, la actividad, el objetivo y las manías. R11 — los datos
    # imposibles se rechazan AQUÍ, al entrar (validación de formulario), no después: la
    # altura y el peso positivos vienen de `min_value` en el propio campo (Django ya avisa
    # "de cuál está mal" con un mensaje señalando ese campo en concreto); el sexo, la
    # actividad y el objetivo solo pueden ser uno de la lista porque son `ChoiceField`
    # (cualquier otro valor es, para Django, "no es una opción válida"); la fecha de
    # nacimiento futura se rechaza en `clean_fecha_nacimiento` de aquí abajo.
    # ------------------------------------------------------------------------------------
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
        label="Ajuste manual (%) sobre lo que gastas",
        required=False,
        help_text="Déjalo en blanco para usar el ajuste de fábrica de tu objetivo.",
    )
    dieta = forms.CharField(label="Tipo de dieta", required=False)
    alergias = forms.CharField(
        label="Alergias", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    intolerancias = forms.CharField(
        label="Intolerancias", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    no_le_gusta = forms.CharField(
        label="Lo que no te gusta", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def clean_fecha_nacimiento(self):
        # R11: una fecha de nacimiento futura es un dato imposible (calcularía una edad
        # negativa, ver servicios/metabolismo.py:calcular_edad) — se rechaza aquí, no cuando
        # ya reviente el cálculo.
        valor = self.cleaned_data["fecha_nacimiento"]
        if valor > timezone.localdate():
            raise forms.ValidationError("La fecha de nacimiento no puede ser futura.")
        return valor

    def signup(self, request, user):
        # `allauth` ya ha creado el Usuario y su EmailAddress sin verificar; el envío del
        # correo lo dispara el flujo de alta justo después de esto (no hace falta mandarlo a
        # mano aquí).
        #
        # Unidad 004: el perfil y la primera medición de peso se crean AQUÍ, antes de mirar
        # el código de hogar — son independientes de a qué hogar acabe yendo esta persona
        # (R7: "el peso que se teclea al crear la cuenta es la primera medición, con su
        # fecha"), y hacerlo antes de los `return` de más abajo evita que cualquier camino
        # del hogar se olvide de crearlos.
        crear_perfil_desde_alta(user, self.cleaned_data)

        codigo = self.cleaned_data.get("codigo_hogar", "").strip().upper()

        if not codigo:
            # R1: sin código, hogar propio de inmediato. No hace falta esperar a que verifique
            # el correo para MONTARLO (nadie va a poder verlo hasta que verifique, R14); solo
            # hace falta esperar para dejárselo ver.
            crear_hogar_propio(user)
            return

        if not Hogar.objects.filter(codigo=codigo).exists():
            # R6/G-30: código que no existe. Se avisa y se le monta igualmente su propio
            # hogar, sin esperar a la verificación (el aviso solo lo verá si de verdad
            # verifica; hasta entonces está "dormida", R14).
            messages.warning(
                request,
                "Ese código de hogar no existe. Te hemos creado tu propio hogar; podrás "
                "invitar a los tuyos con el código que te daremos en cuanto verifiques tu "
                "correo.",
            )
            crear_hogar_propio(user)
            return

        # R5/G-37: código válido. NO se toca `hogar` (queda sin asignar) y NO se crea todavía
        # ninguna `SolicitudEntrada`: eso solo pasa al verificar el correo (ver
        # hogares.signals.al_confirmar_correo), que es el momento en que "la petición llega
        # al hogar" según los planos.
        user.codigo_hogar_pendiente = codigo
        user.save(update_fields=["codigo_hogar_pendiente"])
