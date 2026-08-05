"""
Lo que hay en casa (unidad 014, llevar-la-despensa.md): R-55 (añadir lo mismo suma, no
duplica) y R-56 (corregir cantidad/unidad/categoría, y quitar). Cuelga del HOGAR, no de la
persona (G-43) — a diferencia de `perfiles.models.MedicionPeso` o `entrenos.models.Entreno`
(datos DE LA PERSONA), y COMO `planes.models.PlanDeDia`: es el segundo modelo que repite el
precedente de "el hogar también ESCRIBE" (`planes/acceso.py`) — cualquiera del hogar añade,
corrige y quita sin pedir permiso a nadie (R9, R-24).

Las 15 categorías y las 8 unidades vienen resueltas por la especificación de la unidad, ya
verificadas contra la app Node de referencia (`backend/src/models/stock.js:5-21` en el otro
repo): no se inventan ni se buscan otra vez aquí.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from hogares.models import ModeloDeHogar

# Las 15 categorías (orden = el de la app Node de referencia, no alfabético): la lista es
# también el orden en que `despensa/logica.py:productos_por_categoria` agrupa la pantalla (R8).
CATEGORIAS = [
    ("verdura", "Verdura"),
    ("fruta", "Fruta"),
    ("carne", "Carne"),
    ("pescado", "Pescado"),
    ("huevos", "Huevos"),
    ("lacteo", "Lácteo"),
    ("cereal_pan", "Cereales y pan"),
    ("legumbre", "Legumbres"),
    ("fruto_seco", "Frutos secos"),
    ("aceite_grasa", "Aceites y grasas"),
    ("bebida", "Bebidas"),
    ("dulce_snack", "Dulces y snacks"),
    ("condimento", "Condimentos"),
    ("congelado", "Congelados"),
    ("otro", "Otro"),
]

# Las 8 unidades, las mismas que nombra el plano en su §3 ("unidades, gramos, kilos,
# mililitros, litros, paquetes, latas o botes").
UNIDADES = [
    ("ud", "Unidades"),
    ("g", "Gramos"),
    ("kg", "Kilos"),
    ("ml", "Mililitros"),
    ("l", "Litros"),
    ("paquete", "Paquetes"),
    ("lata", "Latas"),
    ("bote", "Botes"),
]


def _cantidad_positiva(valor):
    """R11 — cero o negativo se rechaza al entrar: una despensa no guarda "menos cero" de
    nada. Mismo criterio de "los datos imposibles se rechazan al entrar" que
    `perfiles.models._fecha_no_futura` o `entrenos.models.Entreno.minutos`."""
    if valor is None or valor <= 0:
        raise ValidationError("La cantidad tiene que ser mayor que cero.")


class ProductoDespensa(ModeloDeHogar):
    """
    Una línea de la despensa: UN producto con SU cantidad y SU unidad, del hogar entero
    (R-55, R-56). "Una línea" es la unidad de Q-92 ("la despensa nunca muestra dos líneas del
    mismo producto con la misma unidad"): la clave que identifica una línea es
    (hogar, nombre normalizado, unidad) — nunca solo el nombre.

    `nombre_normalizado` es lo que hace que R4 viva en la BASE DE DATOS, no solo en la vista:
    se recalcula SIEMPRE dentro de `save()` (nunca a mano, para que ninguna vía de escritura
    —vista, admin, shell, un test que inserte saltándose la vista— pueda dejarlo
    desincronizado del `nombre` real) como `nombre.strip().lower()`, que ignora a la vez
    mayúsculas Y espacios de sobra (R2: "Tomate " y "tomate" son el mismo producto).

    Se eligió un CAMPO normalizado con su propio `UniqueConstraint`, en vez de una
    restricción sobre una expresión `Lower("nombre")`: la comparación de R2 no es solo
    "ignorar mayúsculas", también hay que recortar espacios de sobra — una expresión de base
    de datos habría necesitado combinar `Lower` y `Trim` (dos funciones SQL en vez de una
    normalización de Python ya escrita, ya legible y ya fácil de probar sola), y un campo
    aparte además se ve tal cual en el admin, sin tener que leer la definición de la
    restricción para saber cómo se compara. El `nombre` que se GUARDA y se ENSEÑA es siempre
    el que escribió la persona, tal cual (regla del "Cómo" de la especificación);
    `nombre_normalizado` es solo para comparar, nunca para mostrar.
    """

    nombre = models.CharField(max_length=150)
    nombre_normalizado = models.CharField(max_length=150, editable=False, db_index=True)
    cantidad = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    unidad = models.CharField(max_length=10, choices=UNIDADES)
    categoria = models.CharField(max_length=15, choices=CATEGORIAS)
    # "Cómo" punto 4 de la especificación — §7 del plano pide guardar "desde cuándo está en
    # casa", pero §10 excluye expresamente avisar de caducidades: un campo con su fecha, sin
    # ninguna pantalla que lo enseñe todavía (no se construye nada que dependa de él).
    en_casa_desde = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["categoria", "nombre"]
        constraints = [
            # R4/Q-92, escrito en la base de datos: como mucho UNA línea por hogar, producto
            # (normalizado) y unidad. Precedente exacto: `MedicionPeso.
            # una_medicion_por_persona_y_dia` (unidad 006) y `CierreDeDia.
            # un_cierre_por_persona_y_dia` (unidad 012) — aquí la "persona y día" se cambia
            # por "hogar, producto y unidad".
            models.UniqueConstraint(
                fields=["hogar", "nombre_normalizado", "unidad"],
                name="una_linea_por_hogar_producto_y_unidad",
            )
        ]
        indexes = [models.Index(fields=["hogar", "categoria"])]

    def save(self, *args, **kwargs):
        self.nombre_normalizado = self.nombre.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} {self.unidad} de {self.nombre} ({self.hogar})"
