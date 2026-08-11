"""
El entreno apuntado a mano (unidad 011, apuntar-un-entreno.md): el gasto de un ejercicio, para
que cuente en las calorías que le tocan a la persona ese día (R-36 a R-38, C-37/C-38/C-39).

Es un dato DE LA PERSONA, no del hogar — mismo criterio que `perfiles.models.MedicionPeso`, no
`planes.models.PlanDeDia`: esta unidad no abre ninguna lectura del hogar sobre entrenos ajenos
(R-23 los nombra, pero llega con R-79 en Progreso, otra unidad) ni "de quién es" (personas a
cargo, R-26/R-27, sin construir todavía: ni `a_cargo` ni `responsable` existen en `cuentas/` ni
`hogares/`). Apuntar, corregir y borrar son SIEMPRE sobre uno mismo (R10).

Nota para quien revise esto contra la especificación: `Entreno` NO hereda de
`hogares.models.ModeloDeHogar` — fijado por
`kcalibra/tests_aislamiento.py::test_los_modelos_del_hogar_se_descubren_solos` con un
`assertNotIn` para que nadie lo "arregle" al revés. El punto 3 del "Cómo" de la especificación
decía que este modelo cuelga de `ModeloDeHogar` "como MedicionPeso y PlanDeDia", pero
`MedicionPeso` tampoco hereda de `ModeloDeHogar` (ver el docstring de `perfiles/models.py`:
"Ninguno de los dos hereda... son datos DE LA PERSONA, no del hogar"); de las dos comparaciones
que trae esa frase, se siguió la de `MedicionPeso`, que es la que coincide con el resto del
contrato de esta unidad (acceso "solo sobre uno mismo", sin lectura de hogar). Detalle completo
en hallazgos.md — es una desviación de "cómo" (R8 de las reglas del constructor), no de
contrato: ningún R* de esta unidad pide un campo `hogar`.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# R-37/G-71 — los siete deportes que se pueden apuntar. Las claves son las que usa
# `servicios/entrenos.py` para buscar en la tabla de kcal/minuto: un cambio aquí sin cambiar
# allí rompe la estimación en silencio, así que viven cerca (ver ese módulo).
DEPORTES = [
    ("correr", "Correr"),
    ("bici", "Bici"),
    ("nadar", "Nadar"),
    ("fuerza", "Fuerza"),
    ("crossfit", "CrossFit"),
    ("hyrox", "Hyrox"),
    ("otro", "Otro"),
]

# G-71 — las intensidades son las del PLANO (suave/media/fuerte), no las de la app Node
# ("baja/media/alta"): la especificación de la unidad es explícita en que manda el plano.
INTENSIDADES = [
    ("suave", "Suave"),
    ("media", "Media"),
    ("fuerte", "Fuerte"),
]

# "Cómo" punto 3 — dejado preparado con su valor por defecto "a mano" para cuando
# `conectar-strava` (otra unidad) empiece a escribir aquí: un campo, no una migración futura.
ORIGENES = [
    ("mano", "A mano"),
    ("strava", "Strava"),
]


def _fecha_no_futura(valor):
    """
    Mismo criterio que `perfiles.models.MedicionPeso.fecha` (R10 de apuntar-el-peso.md): un
    entreno no se apunta "para mañana" en esta unidad — los previstos
    (`dejar-planeada-la-semana`) son otra actividad, fuera de alcance aquí (ver el "Alcance" de
    la especificación). Se aplica también al CORREGIR (R5/R38 permite cambiar el día): sin este
    límite, corregir un entreno a una fecha futura colaría por la puerta de atrás justo lo que
    el "Alcance" excluye a propósito.
    """
    if valor > timezone.localdate():
        raise ValidationError("El día no puede ser futuro.")


class Entreno(models.Model):
    """
    Un entreno de UNA persona en UN día. `calorias` es SIEMPRE el número final (las que
    escribió la persona, o las que estimó la app — G-70): nunca se recalcula al leer, solo al
    apuntar o al corregir (`entrenos/logica.py`).

    `calorias_manuales` (no lo pide ningún R* por su nombre, pero sí lo que promete la
    especificación bajo "Qué": "cambia el minuto, el deporte o el día, y las calorías se
    rehacen solas") — distingue si esas calorías las escribió la persona (True, G-70: "la app
    no las discute") o las estimó la app (False). Sin este dato, corregir el entreno no podría
    saber si debe RESPETAR el número que ya había o volver a estimarlo con los datos nuevos: los
    dos casos se ven idénticos en la base de datos si no se guarda cuál fue. Ver hallazgos.md.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entrenos"
    )
    fecha = models.DateField(default=timezone.localdate, validators=[_fecha_no_futura])
    deporte = models.CharField(max_length=10, choices=DEPORTES)
    intensidad = models.CharField(max_length=10, choices=INTENSIDADES)
    # R9 — minutos cero o negativos se rechazan al entrar.
    minutos = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # R9 — calorías negativas se rechazan al entrar; 0 sí es un valor válido (una persona podría
    # escribir 0 a propósito, y no hay ningún R* que lo prohíba).
    calorias = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    calorias_manuales = models.BooleanField(default=False)
    origen = models.CharField(max_length=10, choices=ORIGENES, default="mano")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]
        indexes = [models.Index(fields=["usuario", "fecha"])]

    def __str__(self):
        return f"{self.get_deporte_display()} de {self.usuario} el {self.fecha}"
