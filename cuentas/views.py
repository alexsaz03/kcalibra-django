"""
Las dos vistas que la especificación pide y que `allauth` no da resueltas del todo (ver el
"Cómo" de la unidad 003): pedir otro correo de verificación, y corregir la dirección si se
escribió mal, las dos SIN tener que rellenar el alta otra vez (R15) y SIN estar autenticado
(R14: mientras no se verifica, no hay sesión).

¿Cómo sabemos "para quién" es esto, si no hay sesión de usuario? Por la sesión del NAVEGADOR
(no la de Django-auth): `AdaptadorDeCuentas.respond_email_verification_sent` deja el correo
guardado ahí en el momento del alta. Solo quien pasó por ESE alta, en ESE navegador, tiene ese
valor — no es un dato que se pueda adivinar ni pedir desde fuera.
"""

from allauth.account.models import EmailAddress
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render

Usuario = get_user_model()

CLAVE_SESION_CORREO_PENDIENTE = "cuentas_correo_pendiente"


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


def reenviar_verificacion(request):
    """R15: "pedir otro" correo de verificación, sin rellenar el alta de nuevo."""
    if request.method != "POST":
        return redirect("cuentas:esperando_verificacion")

    correo = _correo_pendiente_de(request)
    direccion = _direccion_pendiente_de_verificar(correo) if correo else None
    if direccion is None:
        messages.error(request, "No hay ninguna verificación pendiente que reenviar.")
        return redirect("account_signup")

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

    usuario.email = nuevo_correo
    usuario.save(update_fields=["email"])
    direccion.email = nuevo_correo
    direccion.save(update_fields=["email"])

    request.session[CLAVE_SESION_CORREO_PENDIENTE] = nuevo_correo
    direccion.send_confirmation(request, signup=False)
    messages.success(request, f"Te hemos mandado un enlace a {nuevo_correo}.")
    return redirect("cuentas:esperando_verificacion")
