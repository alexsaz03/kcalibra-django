"""
El campo propio del formulario de alta: el código de hogar (opcional). `allauth` ya construye
el resto del formulario (correo, contraseña dos veces); esto se engancha mediante
`ACCOUNT_SIGNUP_FORM_CLASS` (ver settings.py), el punto de extensión que la propia librería
deja preparado para añadir campos sin tocar sus vistas.

Importante (y no evidente): esta clase NO puede heredar de `allauth.account.forms.SignupForm`.
`allauth` construye su formulario final MEZCLANDO esta clase con el suyo propio en tiempo de
arranque (`base_signup_form_class()`); si esta clase ya importase el formulario de allauth,
se produce un import circular (allauth todavía se está montando cuando intenta cargar esto).
Por eso hereda solo de `forms.Form`, con el único método que allauth espera: `signup(self,
request, user)`, llamado justo después de crear la cuenta.
"""

from django import forms
from django.contrib import messages

from hogares.logica import crear_hogar_propio
from hogares.models import Hogar


class FormularioAlta(forms.Form):
    codigo_hogar = forms.CharField(
        label="Código de hogar (si ya tienes uno)",
        required=False,
        help_text=(
            "Déjalo en blanco para empezar tu propio hogar. Si alguien de tu casa ya tiene "
            "cuenta en KCalibra, pon aquí su código para pedir entrar."
        ),
    )

    def signup(self, request, user):
        # `allauth` ya ha creado el Usuario y su EmailAddress sin verificar; el envío del
        # correo lo dispara el flujo de alta justo después de esto (no hace falta mandarlo a
        # mano aquí).
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
