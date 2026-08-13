"""
Dos enganches automáticos del hogar.

1. **Con `allauth`** (unidad 003): en cuanto una dirección de correo queda verificada, si esa
   persona tenía un código de hogar pendiente, aquí es donde se convierte en una
   `SolicitudEntrada` de verdad (R5, G-37). Ver
   `hogares.logica.procesar_codigo_al_verificar` para el porqué del momento exacto.

2. **Con el modelo de cuentas** (unidad 023): toda cuenta nueva nace con SU `Persona`.

Sobre el punto 2, porque un `post_save` es justo la clase de cosa que el `bias.md` llama
"magia silenciosa" si nadie la escribe: se hace con una señal, y no dentro de
`UsuarioManager.create_user`, porque en esta app las cuentas se crean por CUATRO caminos
distintos y solo uno pasa por el manager:

- `allauth` al darse de alta (`DefaultAccountAdapter.save_user` -> `user.save()`),
- `Usuario.objects.create_user(...)` (los tests, la importación),
- `manage.py createsuperuser` (-> `create_superuser`),
- el formulario "añadir usuario" del admin de Django (`UserCreationForm.save()` -> `user.save()`).

Una señal `post_save` es el único punto por el que pasan los cuatro. Si esto se escribiera en
el manager, una cuenta creada desde el admin se quedaría sin persona y sin hogar posible — y
nadie se enteraría hasta que esa cuenta intentara entrar en una pantalla.
"""

from allauth.account.signals import email_confirmed
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .logica import procesar_codigo_al_verificar
from .models import Persona


@receiver(email_confirmed)
def al_confirmar_correo(request, email_address, **kwargs):
    procesar_codigo_al_verificar(email_address.user)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_persona_de_la_cuenta(sender, instance, created, raw=False, **kwargs):
    """
    Unidad 023 — toda cuenta nueva estrena su `Persona`, vacía de hogar. Quién le asigna el
    hogar sigue siendo lo de siempre (`crear_hogar_propio` al darse de alta, o aceptar su
    petición de entrada): esta señal solo garantiza que la fila exista.

    `raw=True` es lo que Django pone cuando la fila viene de un `loaddata`: ahí los datos se
    cargan tal cual del fichero, y crear filas extra a mano por detrás rompería justo eso.

    `get_or_create` y no `create`: así la señal es idempotente y no estorba a la migración de
    datos de esta unidad, que crea las personas de las cuentas que ya existían.
    """
    if raw or not created:
        return
    Persona.objects.get_or_create(usuario=instance)
