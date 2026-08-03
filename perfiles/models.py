"""
Los datos de una persona (R7, "Dónde viven los datos" de la especificación de la unidad):
`Perfil` (sexo, fecha de nacimiento, altura, actividad, objetivo, ajuste y manías) y
`MedicionPeso` (una pesada, con su fecha).

Ninguno de los dos hereda de `hogares.models.ModeloDeHogar`: son datos DE LA PERSONA, no del
hogar (G-43 de darle-cuenta-propia-a-los-de-casa.md) — el resto del hogar los VE a través de
`usuario.hogar` (ver `perfiles/acceso.py`), pero no son "cosas del hogar" como la despensa.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from . import constantes


def _fecha_no_futura(valor):
    """
    R11/R10 — los datos imposibles se rechazan al entrar: una fecha futura no tiene sentido
    ni en `Perfil.fecha_nacimiento` (daría una edad negativa en `calcular_edad`) ni en
    `MedicionPeso.fecha` (unidad 006, R10: nadie se pesa "mañana"). Un único validador para
    los dos campos: el mensaje se generalizó al reutilizarlo (antes decía "de nacimiento").
    """
    if valor > timezone.localdate():
        raise ValidationError("La fecha no puede ser futura.")


class Perfil(models.Model):
    """
    Los datos físicos y el objetivo de UNA persona. El peso NO está aquí (R7/G-61 de
    cambiar-tus-datos.md): el cálculo usa siempre la media de las mediciones de los últimos 7
    días de `MedicionPeso`, nunca un campo editable de esta ficha.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    sexo = models.CharField(max_length=10, choices=constantes.SEXO_CHOICES)
    fecha_nacimiento = models.DateField(validators=[_fecha_no_futura])
    altura_cm = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    actividad = models.CharField(max_length=15, choices=constantes.ACTIVIDAD_CHOICES)
    objetivo = models.CharField(max_length=30, choices=constantes.OBJETIVO_CHOICES)
    # Puede ser negativo (perder grasa trae un −10 % de fábrica): sin MinValueValidator.
    ajuste_pct = models.SmallIntegerField()

    # Las manías (decisión del usuario, 2026-08-02, ver "Las manías" en la especificación de
    # la unidad): se recogen y se guardan aunque hoy nada las lea todavía — las leerá la IA
    # del menú, fuera de alcance de esta unidad. Texto libre, sin estructura inventada: no
    # hay ninguna regla de negocio sobre su forma que esta unidad deba imponer.
    dieta = models.CharField(max_length=100, blank=True, default="")
    alergias = models.TextField(blank=True, default="")
    intolerancias = models.TextField(blank=True, default="")
    no_le_gusta = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Perfil de {self.usuario}"


class MedicionPeso(models.Model):
    """
    Una pesada de una persona, con su fecha (R7/G-61 de la unidad 004; R-63/R-66/G-130/G-131
    de "apuntar-el-peso.md", unidad 006). El peso es obligatorio; la grasa corporal y la
    cintura son opcionales (`null=True, blank=True`): no toda báscula las mide, y que falten
    no impide nada (G-131). Desde la unidad 006 SÍ tiene pantalla propia (el histórico de
    pesadas, dentro de `perfiles/`) — antes de esa unidad este docstring decía "sin pantalla
    propia a propósito"; ya no es verdad.

    `UniqueConstraint` de abajo es G-130/Q-110 escrito en la base de datos: como mucho UNA
    medición por persona y día. Apuntar dos veces el mismo día no son dos datos, es una
    corrección — `perfiles.logica.apuntar_medicion` hace el `update_or_create` que la
    aprovecha, nunca un `create` suelto que reventaría contra esta restricción.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mediciones_peso"
    )
    fecha = models.DateField(default=timezone.localdate, validators=[_fecha_no_futura])
    peso_kg = models.DecimalField(
        max_digits=5, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))]
    )
    # R-66/G-131 — opcionales a propósito: no toda báscula mide la grasa ni la cintura.
    grasa_pct = models.DecimalField(
        "grasa corporal (%)",
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    cintura_cm = models.DecimalField(
        "cintura (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )

    class Meta:
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "fecha"], name="una_medicion_por_persona_y_dia"
            )
        ]

    def __str__(self):
        return f"{self.peso_kg} kg de {self.usuario} el {self.fecha}"
