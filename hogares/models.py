"""
El hogar: con quién se comparte, y el mecanismo de aislamiento que usará TODA la app.

Dos piezas conviven aquí:

1. `Hogar` y `SolicitudEntrada`: los datos concretos de esta unidad (el código para invitar,
   y las peticiones de entrada con su aceptación/rechazo/caducidad).
2. `ModeloDeHogar`: la base abstracta que hace que "pertenecer a un hogar" sea un mecanismo
   reutilizable, no una columna que cada unidad futura tenga que acordarse de añadir. La
   despensa, las recetas y el calendario de las unidades 004+ heredarán de aquí.
"""

import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

# Alfabeto del código de hogar: sin caracteres que se confunden a simple vista (0/O, 1/I/l).
# Q-11 exige que el código no sea corto ni adivinable: con 12 caracteres de este alfabeto de
# 32 símbolos hay 32**12 (~1.2 * 10^18) combinaciones posibles, así que probar códigos al azar
# no es un ataque practicable.
_ALFABETO_CODIGO = "".join(
    c for c in (string.ascii_uppercase + string.digits) if c not in "0O1IL"
)
LONGITUD_CODIGO_HOGAR = 12


def generar_codigo_hogar() -> str:
    """
    Genera un código de hogar aleatorio (no correlativo, Q-11): usa `secrets`, el generador
    pensado para tokens de seguridad (no `random`, que no es apto para esto). No depende de
    ningún contador ni de la fecha, así que dos hogares creados seguidos no tienen códigos
    parecidos entre sí.
    """
    return "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(LONGITUD_CODIGO_HOGAR))


class Hogar(models.Model):
    """
    El hogar: la unidad que comparte despensa, recetas y calendario (en las unidades que
    vienen). Aquí, en la 003, solo guarda su código y quién es miembro.
    """

    codigo = models.CharField(
        max_length=LONGITUD_CODIGO_HOGAR,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Código para invitar a los tuyos. Aleatorio y largo (Q-11): no se adivina.",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Genera el código solo la primera vez (al crear), con reintento por si chocara con
        # uno ya existente. Con el espacio de combinaciones de generar_codigo_hogar() una
        # colisión es prácticamente imposible, pero el reintento es barato y quita la duda.
        if not self.codigo:
            for _ in range(10):
                candidato = generar_codigo_hogar()
                if not Hogar.objects.filter(codigo=candidato).exists():
                    self.codigo = candidato
                    break
            else:  # pragma: no cover - solo saltaría si el espacio estuviera casi agotado
                raise RuntimeError("No se pudo generar un código de hogar libre.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Hogar {self.codigo}"


def crear_hogar_propio(usuario) -> Hogar:
    """
    Le monta a `usuario` su propio hogar y lo deja asignado. Es lo que pasa al registrarse sin
    código (R1), con un código que no vale (R6), y cuando una petición de entrada se rechaza o
    caduca (R7, R8): en los tres casos la persona termina con SU hogar, nunca sin ninguno.
    """
    hogar = Hogar.objects.create()
    usuario.hogar = hogar
    usuario.save(update_fields=["hogar"])
    return hogar


class ModeloDeHogar(models.Model):
    """
    Base abstracta para cualquier modelo que sea DEL HOGAR (R9, R24, G-43): trae el campo
    `hogar` y deja un manager con el que filtrar por él. Es el mecanismo que evita que cada
    unidad futura (la despensa, las recetas, el calendario) reinvente el aislamiento con un
    `if` suelto en cada vista: hereda de aquí y ya viene aislado.

    No se usa para `Hogar` en sí (el hogar no pertenece a un hogar), pero sí para
    `SolicitudEntrada` de aquí abajo, y será la base de los modelos de las unidades 004+.
    """

    hogar = models.ForeignKey(Hogar, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    @classmethod
    def del_hogar(cls, hogar):
        """Todo lo de ESTE modelo que pertenece a `hogar`, y nada más. La consulta base de la
        que debe partir cualquier vista que liste algo de un hogar."""
        return cls.objects.filter(hogar=hogar)


class SolicitudEntrada(ModeloDeHogar):
    """
    Alguien pidió entrar en `hogar` con su código. Vive PENDIENTE una hora desde que se creó
    (que es el momento en que quien la pidió verificó su correo, G-34/G-37) y en ese tiempo
    cualquiera de dentro del hogar puede aceptarla o rechazarla.
    """

    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    CADUCADA = "caducada"
    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (ACEPTADA, "Aceptada"),
        (RECHAZADA, "Rechazada"),
        (CADUCADA, "Caducada"),
    ]

    # Quien pide entrar. related_name explícito porque en unidades futuras puede haber más de
    # un modelo con FK a Usuario y no queremos que Django tenga que inventarse un nombre.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitudes_de_entrada",
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)

    # El momento en que la petición "llegó al hogar": no es cuando se registró, es cuando
    # verificó su correo (G-37, G-104). De aquí cuenta la hora de plazo (G-34, Q-10).
    creada_en = models.DateTimeField(default=timezone.now)
    resuelta_en = models.DateTimeField(null=True, blank=True)
    resuelta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_resueltas",
    )

    class Meta:
        indexes = [models.Index(fields=["hogar", "estado"])]

    def ha_caducado(self) -> bool:
        """Q-10: caduca EXACTAMENTE a los 60 minutos de haberse creado (de haber llegado al
        hogar), sin importar si alguien la ha mirado antes o no."""
        limite = self.creada_en + timezone.timedelta(hours=1)
        return timezone.now() >= limite

    def __str__(self):
        return f"Solicitud de {self.usuario} a {self.hogar} ({self.estado})"
