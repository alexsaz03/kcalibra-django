"""
Las recetas de la casa (unidad 021, guardar-tus-recetas.md): R-67 (nombre, raciones y al menos
un ingrediente son obligatorios; comidas y preparación, opcionales), R-69 la mitad que sí se
construye (la preparación se guarda literal, sin trocear en pasos — R-68 y "ordenar en pasos
más tarde" son la IA, y no hay IA en este proyecto: ver "Fuera de alcance" de la
especificación), y R-70 (las recetas son del hogar y no tienen dueño).

Cuelga del HOGAR, no de la persona (G-43), igual que `despensa.models.ProductoDespensa` y
`planes.models.PlanDeDia`: cualquiera del hogar apunta, ve, corrige y borra sin pedir permiso
a nadie. **Sin campo de autor** — R-70 lo prohíbe expresamente, y "ya que estamos" no es un
motivo (nombrado así, literal, en el "Cómo" de la especificación).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from despensa.models import UNIDADES
from hogares.models import ModeloDeHogar
from planes.models import MOMENTOS_DEL_DIA

# Las unidades de cantidad de un ingrediente son las MISMAS que las de la despensa
# (`despensa/models.py:UNIDADES`, unidad 014): el "Cómo" de la especificación pide
# expresamente reutilizarlas, no inventar un catálogo nuevo. A diferencia de la despensa, aquí
# NO se canonicaliza a la unidad pequeña (no hay "fusión" de líneas: cada ingrediente de una
# receta se guarda TAL CUAL se escribió, en la unidad que eligió la persona) — R1/R5 piden que
# la receta se reabra con "sus cantidades y sus unidades intactos", no convertidas.


def _raciones_positivas(valor):
    """R2/G-140 — las raciones tienen que ser al menos 1. Mismo criterio de "los datos
    imposibles se rechazan al entrar" que `despensa.models._cantidad_positiva`."""
    if valor is None or valor <= 0:
        raise ValidationError("Las raciones tienen que ser al menos 1.")


class Receta(ModeloDeHogar):
    """
    Un plato que la casa ya sabe hacer (R-67, C-73): su nombre, para cuántas raciones es, para
    qué comidas vale y la preparación escrita de corrido. Es DEL HOGAR (R-70): no hay "la
    receta DE alguien" — no existe ningún campo que diga quién la escribió, ni falta que hace
    (lo que decide si se usa en un plan es si respeta las manías de quien va a comer, G-142,
    fuera de esta unidad porque el planificador no existe todavía).

    `comidas` (R2/G-140) es la lista de momentos del día para los que vale, reutilizando el
    catálogo YA existente de `planes.models.MOMENTOS_DEL_DIA` (desayuno/comida/merienda/
    cena/snack) en vez de inventar uno nuevo — mismo espíritu que reutilizar `UNIDADES` de la
    despensa. Una lista VACÍA significa "vale para cualquier comida" (así se lee en pantalla,
    nunca como "ninguna"): se guarda en un `JSONField` porque es una lista corta de cadenas de
    un catálogo cerrado, sin necesidad de una tabla aparte ni de nada específico de Postgres.

    `preparacion` (R3/R-69, Q-120) se guarda LITERAL: de corrido, tal cual se escribió, sin
    trocear en pasos (eso es R-68, la IA, fuera de esta unidad — ver "Fuera de alcance" de la
    especificación). Es opcional (R2): una receta con un solo ingrediente y nada más se guarda.
    """

    nombre = models.CharField(max_length=150)
    raciones = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    comidas = models.JSONField(default=list, blank=True)
    preparacion = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.hogar})"


class IngredienteDeReceta(models.Model):
    """
    Un ingrediente de una `Receta`, con su cantidad y su unidad. Cuelga de `Receta` por FK y
    **NO hereda de `ModeloDeHogar` por separado**: hereda su aislamiento A TRAVÉS de su receta,
    exactamente igual que `planes.models.ComidaDelPlan` cuelga de `PlanDeDia`
    (`planes/models.py:12` explica por qué: "quien puede ver o tocar un plan, ve y toca sus
    comidas. No hace falta una segunda puerta"). Aquí: quien puede ver o tocar una receta —ya
    filtrada por `hogares.acceso.obtener_de_mi_hogar_o_404`— ve y toca sus ingredientes.

    R5 (la lección de la 017) — `cantidad` usa el mismo `DecimalField(max_digits=9,
    decimal_places=2)` que `despensa.models.ProductoDespensa.cantidad`: dos decimales bastan
    para "0,5" y no pierden nada, y es el mismo campo cuyo formato de entrada/salida (punto en
    el `<input>`, coma en la lectura) ya se resolvió allí — mismo patrón, mismo cuidado.
    """

    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="ingredientes")
    nombre = models.CharField(max_length=150)
    cantidad = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    unidad = models.CharField(max_length=10, choices=UNIDADES)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.cantidad} {self.unidad} de {self.nombre} ({self.receta.nombre})"
