"""
El adaptador de `allauth`: el punto que la propia librería deja preparado para que un
proyecto ajuste su comportamiento sin tener que copiar y modificar sus vistas. Aquí se
resuelven tres cosas que la especificación pide y `allauth` no trae puestas por defecto:

- R12: el registro se abre o se cierra con una variable de entorno (la misma palanca en los
  dos casos, ver `settings.py` y `is_open_for_signup`).
- R2: el mensaje de "ese correo ya existe" en español, señalando la pantalla de entrar.
- R15/R5: a dónde va la persona justo después de darse de alta, y qué necesita esa pantalla
  para saber a qué correo se mandó el aviso (se lo pasamos por sesión, ver
  `respond_email_verification_sent`).
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.urls import reverse


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
