"""
El plan de comidas del día (unidad 005): quién come qué hoy, con sus calorías y sus macros ya
guardados por comida (R1, "Dónde viven los datos" de la especificación).

`PlanDeDia` hereda de `hogares.models.ModeloDeHogar` (R6/R7/G-43): el calendario de comidas es
DEL HOGAR, no de la persona — lo ve y lo cambia cualquiera que esté dentro, igual que la
despensa o las recetas de las unidades que vienen (a diferencia del perfil, unidad 004, que es
de la persona y solo lo cambia su dueña). Es el PRIMER modelo de negocio de verdad que cuelga
de `ModeloDeHogar`: la unidad 003 dejó el mecanismo listo, esta unidad lo estrena (ver
hallazgos.md para el veredicto de si sirvió tal cual).

`ComidaDelPlan` no hereda de `ModeloDeHogar` por separado: cuelga de `PlanDeDia` por FK y
hereda su aislamiento A TRAVÉS de él — quien puede ver o tocar un plan, ve y toca sus comidas.
No hace falta una segunda puerta para las comidas.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from hogares.models import ModeloDeHogar

# Los momentos del día en los que puede caer una comida (nota de alcance de la especificación:
# solo se apunta a mano, sin IA; el catálogo es el habitual, sin inventar nada más).
MOMENTOS_DEL_DIA = [
    ("desayuno", "Desayuno"),
    ("comida", "Comida"),
    ("merienda", "Merienda"),
    ("cena", "Cena"),
    ("snack", "Snack / tentempié"),
]


class PlanDeDia(ModeloDeHogar):
    """
    El plan de comidas de UNA persona para UN día. "Una persona, un plan por día" ("Cómo" de
    la especificación): la restricción `un_plan_por_persona_y_dia` de abajo hace imposible
    colgar dos planes del mismo día para la misma persona a nivel de base de datos —G-20 lo
    trata como sustitución, no como acumulación. En esta unidad "sustituir" es sencillamente
    seguir añadiendo comidas al MISMO plan (`planes/logica.py:apuntar_comida` hace
    `get_or_create`); sustituir un plan ENTERO por otro de un tirón es cosa de la IA, fuera de
    alcance aquí (ver la nota de alcance de la especificación).
    """

    persona = models.ForeignKey(
        "hogares.Persona",
        on_delete=models.CASCADE,
        related_name="planes_de_dia",
    )
    fecha = models.DateField(default=timezone.localdate)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["persona", "fecha"], name="un_plan_por_persona_y_dia"
            )
        ]
        indexes = [models.Index(fields=["hogar", "fecha"])]

    def __str__(self):
        return f"Plan de {self.persona} para el {self.fecha}"


class ComidaDelPlan(models.Model):
    """
    Una comida concreta dentro de un `PlanDeDia`: nombre, momento del día, calorías y macros
    (R1). Los macros se guardan AQUÍ, por comida —no se recalculan a partir de nada—: es lo
    que permite sumar el día sin volver a tocar ninguna fórmula ("Cómo" de la especificación).

    R10 (caso límite) — "los valores imposibles se rechazan al apuntar": ninguna magnitud
    puede ser negativa (`PositiveIntegerField` + `MinValueValidator(0)`, que en Postgres desde
    Django 4.1 añade además su propia restricción `CHECK` en la base de datos: doble cinturón)
    y el nombre no puede quedar vacío (`CharField` sin `blank=True`, de fábrica obligatorio).
    Esas mismas reglas se repiten en el FORMULARIO (`planes/forms.py`), para que el aviso
    salga ANTES de tocar la base de datos y señalando el campo exacto — el mismo patrón que ya
    usa `perfiles/forms.py` con la altura.
    """

    plan = models.ForeignKey(PlanDeDia, on_delete=models.CASCADE, related_name="comidas")
    nombre = models.CharField(max_length=150)
    momento_del_dia = models.CharField(max_length=10, choices=MOMENTOS_DEL_DIA)
    calorias = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    proteina_g = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    grasa_g = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    carbos_g = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creada_en"]

    def __str__(self):
        return f"{self.nombre} ({self.get_momento_del_dia_display()}) de {self.plan}"
