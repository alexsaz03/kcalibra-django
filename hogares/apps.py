from django.apps import AppConfig


class HogaresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hogares"

    def ready(self):
        # Engancha el receptor de la señal `email_confirmed` de allauth (ver signals.py).
        # Se importa aquí, no arriba del todo del módulo, porque `ready()` es el punto que
        # Django garantiza que se ejecuta una sola vez, con todas las apps ya cargadas.
        from . import signals  # noqa: F401
