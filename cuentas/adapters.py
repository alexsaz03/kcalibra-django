"""
El adaptador de `allauth`: el punto que la propia librería deja preparado para que un
proyecto ajuste su comportamiento sin tener que copiar y modificar sus vistas. Aquí se
resuelven cuatro cosas que la especificación pide y `allauth` no trae puestas por defecto:

- R12: el registro se abre o se cierra con una variable de entorno (la misma palanca en los
  dos casos, ver `settings.py` y `is_open_for_signup`).
- R2: el mensaje de "ese correo ya existe" en español, señalando la pantalla de entrar.
- R15/R5: a dónde va la persona justo después de darse de alta, y qué necesita esa pantalla
  para saber a qué correo se mandó el aviso (se lo pasamos por sesión, ver
  `respond_email_verification_sent`).
- R5/R6/R7 (unidad 008): que un fallo al ENVIAR un correo no tumbe la petición (ver
  `send_mail` más abajo) — el fallo que destapó el ADR-004 y que
  docs/conocimiento/dominios-y-correo-transaccional.md (punto 4) documenta: `allauth` hace
  `msg.send()` a pelo, sin capturar nada, y Django trae `fail_silently=False` de fábrica.
"""

import logging
from smtplib import SMTPException

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class AdaptadorDeCuentas(DefaultAccountAdapter):
    error_messages = {
        **DefaultAccountAdapter.error_messages,
        "email_taken": (
            "Ya existe una cuenta con ese correo. Inicia sesión en vez de crear otra."
        ),
        "email_password_mismatch": "El correo o la contraseña no son correctos.",
        "too_many_login_attempts": (
            "Demasiados intentos fallidos desde aquí. Prueba de nuevo dentro de un rato."
        ),
    }

    def is_open_for_signup(self, request):
        """
        R12: la misma palanca, en dos posiciones. `settings.REGISTRO_ABIERTO` sale de la
        variable de entorno `DJANGO_REGISTRO_ABIERTO` (por defecto CERRADO: la app está en
        internet y abrirla a cualquiera sin querer gastaría cupo de verdad — ver
        `settings.py`).
        """
        return settings.REGISTRO_ABIERTO

    def send_mail(self, template_prefix, email, context):
        """
        R5/R6/R7 de la unidad 008 — el fallo que destapó el ADR-004, con sus tres piezas:

        1. `DefaultAccountAdapter.send_mail` (la clase de la que heredamos) hace `msg.send()`
           sin ningún `try`/`except` alrededor.
        2. Django trae `fail_silently=False` por defecto en `EmailMessage.send()`, así que esa
           excepción sube tal cual hasta la vista que la disparó.
        3. No hay `ATOMIC_REQUESTS` en este proyecto, así que cuando eso pasa DURANTE el alta,
           el `Usuario` y su `EmailAddress` sin verificar ya están guardados en la base — la
           petición revienta con un 500 sobre una cuenta a medio crear.

        Esta es la única llamada de la que salen TODOS los correos de la app (verificación de
        alta, reenvío, corrección de dirección, y la recuperación de contraseña que monta esta
        misma unidad — `ResetPasswordForm.save()` y `send_unknown_account_mail()` de allauth
        pasan por aquí igual que el resto): es el sitio natural para envolver el envío una
        sola vez, en vez de perseguir cada punto de la app que manda un correo.

        Se captura `SMTPException` (los fallos de protocolo SMTP: autenticación, remitente
        rechazado...) y también `OSError` — la clase de la que heredan los fallos de socket
        (DNS que no resuelve, conexión rechazada, y sobre todo el `TimeoutError` que dispara
        `EMAIL_TIMEOUT` en cuanto el proveedor no contesta a tiempo). Sin `OSError` en la
        lista, el propio timeout que se añade en esta unidad para no colgar la petición
        seguiría colgándola con una excepción sin capturar.

        Deliberadamente NO se captura `Exception` a secas: un fallo de verdad en la
        construcción del correo (una plantilla rota, una variable de contexto que falta) es
        un bug de la app, no un fallo del proveedor — y ese sí tiene que reventar y verse,
        no quedar tragado en silencio junto con los fallos de red.

        Al no dejar que la excepción suba, la persona que llamó a `send_mail` (`allauth`, en
        `send_verification_email_at_login`, o nuestras propias vistas) sigue su camino como si
        el envío hubiera ido bien: la sesión se guarda igual (R5: "queda un camino de vuelta"),
        y las vistas de `cuentas/views.py` (R6: reenviar, corregir) tampoco ven ninguna
        excepción que las tumbe. El "orden" que la especificación pedía invertir —guardar en
        sesión antes de enviar— se vuelve irrelevante en la práctica: como el fallo nunca sale
        de aquí, todo lo que allauth hace DESPUÉS de intentar enviar (incluida
        `respond_email_verification_sent`, que guarda el correo en sesión) se ejecuta siempre,
        haya ido bien el envío o no. Reordenar el código de la propia librería no es una
        opción razonable (viviría fuera de este proyecto); absorber el fallo en la única
        puerta por la que pasan todos los envíos consigue el mismo resultado sin tocarla.

        R7: el fallo queda registrado con `logger.exception` (log de errores, con la traza
        completa) para que quien mantenga la app se entere — hoy nadie lo hace.
        """
        try:
            super().send_mail(template_prefix, email, context)
        except (SMTPException, OSError):
            logger.exception(
                "No se pudo enviar el correo '%s' a %s. La petición sigue adelante: quien lo "
                "pidió no debe quedarse atrapado por un fallo del proveedor de correo.",
                template_prefix,
                email,
            )

    def respond_email_verification_sent(self, request, user):
        """
        Sustituye la pantalla de espera de `allauth` (que no dice a qué correo se mandó nada,
        ver la investigación de esta unidad) por la propia (`cuentas:esperando_verificacion`).
        Guarda el correo en sesión: es la única forma de que esa pantalla sepa "a quién" sin
        tener a nadie autenticado todavía (R14: mientras no verifica, no hay sesión).
        """
        from django.http import HttpResponseRedirect

        request.session["cuentas_correo_pendiente"] = user.email
        return HttpResponseRedirect(reverse("cuentas:esperando_verificacion"))

    def get_login_redirect_url(self, request):
        return reverse("hogares:mi_hogar")

    def get_signup_redirect_url(self, request):
        return reverse("hogares:mi_hogar")
