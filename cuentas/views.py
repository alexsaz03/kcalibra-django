"""
Las vistas propias de esta unidad que `allauth` no da resueltas del todo (ver el "Cómo" de la
unidad 003): la vista de alta con la conducción a iniciar sesión cuando el correo ya existe
(R2), y pedir otro correo de verificación / corregir la dirección desde la pantalla de espera,
sin tener que rellenar el alta otra vez (R15) y sin estar autenticado (R14: mientras no se
verifica, no hay sesión).

¿Cómo sabemos "para quién" es esto, si no hay sesión de usuario? Por la sesión del NAVEGADOR
(no la de Django-auth): `AdaptadorDeCuentas.respond_email_verification_sent` deja el correo
guardado ahí en el momento del alta. Solo quien pasó por ESE alta, en ESE navegador, tiene ese
valor — no es un dato que se pueda adivinar ni pedir desde fuera.
"""

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from allauth.account.views import SignupView as _VistaAltaDeAllauth
from allauth.core import ratelimit
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import redirect, render

Usuario = get_user_model()

CLAVE_SESION_CORREO_PENDIENTE = "cuentas_correo_pendiente"

# H1 de la revisión (2ª ronda): "pedir otro correo" y "corregir la dirección" son la MISMA
# superficie de abuso — sin límite, la app se convierte en un relé que manda enlaces a
# cualquier dirección que alguien teclee. Comparten acción y clave (el correo sobre el que se
# actúa), así que da igual por cuál de las dos rutas se abuse: el límite es el mismo.
_ACCION_LIMITE_CORREO_PENDIENTE = "cuentas_correo_pendiente"


class _VistaAlta(_VistaAltaDeAllauth):
    """
    La vista de alta de `allauth`, con un único cambio (R2/C-14, H2 de la revisión): si el
    formulario no es válido PORQUE el correo ya tiene cuenta, no se queda en el formulario de
    alta — lleva a la pantalla de iniciar sesión, con el aviso ya puesto. Es lo que el
    contrato pide literalmente ("avisa... y le lleva a la pantalla de iniciar sesión") y
    justo lo que la app vieja no hacía (R-14 de los planos: "solo pinta el mensaje de error;
    no lleva a iniciar sesión").

    Cualquier OTRO motivo de formulario inválido (contraseña floja, código de hogar raro...)
    se comporta exactamente igual que antes: se queda en el formulario con sus errores.
    """

    def form_invalid(self, form):
        adaptador = get_adapter(self.request)
        mensaje_correo_duplicado = adaptador.error_messages["email_taken"]
        errores_de_email = [str(error) for error in form.errors.get("email", [])]
        if mensaje_correo_duplicado in errores_de_email:
            messages.info(self.request, mensaje_correo_duplicado)
            return redirect("account_login")
        return super().form_invalid(form)


signup = _VistaAlta.as_view()


def _correo_pendiente_de(request):
    return request.session.get(CLAVE_SESION_CORREO_PENDIENTE)


def esperando_verificacion(request):
    """
    La pantalla de espera (R13, R14, R15): a qué dirección se mandó el correo, que el enlace
    vale 24 horas, y los botones de pedir otro / corregir la dirección.
    """
    if request.user.is_authenticated:
        return redirect("hogares:mi_hogar")

    correo = _correo_pendiente_de(request)
    if not correo:
        # Nadie ha pasado por un alta reciente en este navegador: no hay nada que enseñar.
        return redirect("account_signup")

    return render(request, "cuentas/esperando_verificacion.html", {"correo": correo})


def _direccion_pendiente_de_verificar(correo):
    """
    La `EmailAddress` sin verificar de ese correo, o `None` si no existe o ya se verificó
    (en cuyo caso esta pantalla ya no pinta nada: esa cuenta se maneja desde dentro de la
    app, no desde aquí).
    """
    return EmailAddress.objects.filter(email__iexact=correo, verified=False).first()


def _limite_de_correo_superado(request, correo):
    """
    H1 de la revisión: sin esto, `reenviar_verificacion` y `corregir_correo` dejan que
    cualquiera use la app como un relé de correo hacia una dirección arbitraria (no hace
    falta ni acertar una cuenta ajena: basta con rellenar "corregir" con el correo de la
    víctima una y otra vez). El límite se lleva por correo Y por IP a la vez (la sintaxis de
    allauth, `"N/ventana/clave"` separada por comas, exige las dos), igual que el límite de
    accesos fallidos que ya trae la app (R4).
    """
    return not ratelimit.consume(
        request, action=_ACCION_LIMITE_CORREO_PENDIENTE, key=correo.lower()
    )


def reenviar_verificacion(request):
    """R15: "pedir otro" correo de verificación, sin rellenar el alta de nuevo."""
    if request.method != "POST":
        return redirect("cuentas:esperando_verificacion")

    correo = _correo_pendiente_de(request)
    direccion = _direccion_pendiente_de_verificar(correo) if correo else None
    if direccion is None:
        messages.error(request, "No hay ninguna verificación pendiente que reenviar.")
        return redirect("account_signup")

    if _limite_de_correo_superado(request, correo):
        messages.error(request, "Demasiados intentos. Prueba de nuevo dentro de un rato.")
        return redirect("cuentas:esperando_verificacion")

    direccion.send_confirmation(request, signup=False)
    messages.success(request, f"Te hemos mandado un nuevo enlace a {direccion.email}.")
    return redirect("cuentas:esperando_verificacion")


def corregir_correo(request):
    """R15: corregir la dirección desde la pantalla de espera, sin rellenar el alta de nuevo."""
    if request.method != "POST":
        return redirect("cuentas:esperando_verificacion")

    correo_actual = _correo_pendiente_de(request)
    direccion = _direccion_pendiente_de_verificar(correo_actual) if correo_actual else None
    if direccion is None:
        messages.error(request, "No hay ninguna verificación pendiente que corregir.")
        return redirect("account_signup")

    nuevo_correo = request.POST.get("nuevo_correo", "").strip().lower()
    try:
        validate_email(nuevo_correo)
    except ValidationError:
        messages.error(request, "Esa no es una dirección de correo válida.")
        return redirect("cuentas:esperando_verificacion")

    usuario = direccion.user
    ya_existe = (
        Usuario.objects.exclude(pk=usuario.pk).filter(email__iexact=nuevo_correo).exists()
    )
    if ya_existe:
        messages.error(request, "Ya existe una cuenta con esa dirección de correo.")
        return redirect("cuentas:esperando_verificacion")

    if _limite_de_correo_superado(request, correo_actual):
        messages.error(request, "Demasiados intentos. Prueba de nuevo dentro de un rato.")
        return redirect("cuentas:esperando_verificacion")

    # H1 de la revisión (el hueco de seguridad grave): el enlace de verificación de allauth es
    # una firma HMAC sobre el PK de la fila `EmailAddress`, NO sobre su dirección. Si aquí nos
    # limitáramos a cambiar `direccion.email` sobre la MISMA fila (como hacía la versión
    # anterior), el enlace YA ENVIADO seguiría resolviendo a esa fila — y acabaría verificando
    # la dirección CORREGIDA, que es justo lo que un atacante querría: pedir el alta con su
    # propio correo, dejar el enlace sin pulsar, "corregir" la dirección a la de una víctima, y
    # pulsar el enlace viejo para acabar con una cuenta VERIFICADA sobre un correo que nunca
    # demostró controlar.
    #
    # La solución es no mutar nunca esa fila: se da de baja la `EmailAddress` pendiente (su PK
    # deja de existir) y se crea una NUEVA para la dirección corregida, con un PK distinto. El
    # enlace viejo, cuyo HMAC firma el PK que ya no existe, deja de resolver a nada — igual que
    # un enlace caducado (R15/Q-14: "caducado o ya usado, no vuelve a dar acceso").
    #
    # `transaction.atomic()` (3ª revisión): el peligro real no es que el proceso muera a medio
    # camino, es que lleguen DOS peticiones a la vez (dos pestañas, un doble clic). Sin esto,
    # si el `create()` fallara (por ejemplo, por una carrera con OTRA petición corrigiendo el
    # mismo correo al mismo tiempo) DESPUÉS de que el `delete()` ya se hubiera confirmado en la
    # base, la persona se quedaría sin ninguna `EmailAddress` pendiente: la pantalla de espera
    # le diría "no hay ninguna verificación pendiente", no podría ni reenviar ni corregir, y R2
    # le impediría registrarse otra vez con ese correo — fuera de su propia cuenta. Con las tres
    # escrituras dentro del mismo bloque atómico, o se confirman las tres juntas, o no se
    # confirma ninguna: nunca queda a medias.
    with transaction.atomic():
        primaria = direccion.primary
        direccion.delete()
        nueva_direccion = EmailAddress.objects.create(
            user=usuario, email=nuevo_correo, verified=False, primary=primaria
        )
        usuario.email = nuevo_correo
        usuario.save(update_fields=["email"])

    request.session[CLAVE_SESION_CORREO_PENDIENTE] = nuevo_correo
    nueva_direccion.send_confirmation(request, signup=False)
    messages.success(request, f"Te hemos mandado un enlace a {nuevo_correo}.")
    return redirect("cuentas:esperando_verificacion")
