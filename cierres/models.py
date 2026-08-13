"""
Cerrar el día (unidad 012, decir-si-cumpliste.md): decir si se siguió el plan, a medias o
nada, con calorías y nota opcionales (R-75), y —solo cuando la respuesta es "lo seguí
entero"— guardar el menú de ese día como historia (R-77/G-161/Q-142).

Son datos DE LA PERSONA, no del hogar: mismo criterio que `perfiles.models.MedicionPeso` y
`entrenos.models.Entreno` (cerrar el día de otra persona no está permitido ni siquiera dentro
del mismo hogar, R12 — ver `cierres/acceso.py`), no el de `planes.models.PlanDeDia`.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from planes.models import MOMENTOS_DEL_DIA


def _fecha_no_futura(valor):
    """Mismo criterio que `perfiles.models.MedicionPeso.fecha` y `entrenos.models.Entreno.
    fecha` (R11: una fecha futura no tiene sentido — nadie cierra "mañana")."""
    if valor > timezone.localdate():
        raise ValidationError("La fecha no puede ser futura.")


class CierreDeDia(models.Model):
    """
    Si una persona siguió su plan un día concreto (R-75). `UniqueConstraint` de abajo es R3
    escrito en la base de datos —el mismo precedente exacto que `MedicionPeso.
    una_medicion_por_persona_y_dia` (unidad 006)—: como mucho UN cierre por persona y día;
    volver a cerrar el mismo día SUSTITUYE al anterior, nunca lo duplica
    (`cierres/logica.py:cerrar_dia` hace el `update_or_create` que lo aprovecha).
    """

    LO_SEGUI = "lo_segui"
    A_MEDIAS = "a_medias"
    NO_LO_SEGUI = "no_lo_segui"
    RESPUESTAS = [
        (LO_SEGUI, "Lo seguí"),
        (A_MEDIAS, "A medias"),
        (NO_LO_SEGUI, "No lo seguí"),
    ]

    persona = models.ForeignKey(
        "hogares.Persona", on_delete=models.CASCADE, related_name="cierres_de_dia"
    )
    fecha = models.DateField(default=timezone.localdate, validators=[_fecha_no_futura])
    respuesta = models.CharField(max_length=12, choices=RESPUESTAS)
    # R-75/R2 — opcionales de verdad: se puede cerrar sin ninguno de los dos (R1, el episodio
    # de Alejandro: "a medias", sin calorías ni nota, y el día queda cerrado igual).
    calorias_comidas = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    nota = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(
                fields=["persona", "fecha"], name="un_cierre_por_persona_y_dia"
            )
        ]

    def __str__(self):
        return f"Cierre de {self.persona} el {self.fecha}: {self.get_respuesta_display()}"


class MenuSeguido(models.Model):
    """
    La FOTO del `PlanDeDia` de ese día, congelada en el momento en que la persona dijo que lo
    siguió ENTERO (R4/G-161/Q-142). Es una foto, no una marca booleana sobre `PlanDeDia`: el
    motivo está verificado en el código y escrito en la especificación de la unidad —
    `planes/views.py:apuntar_plan` sigue admitiendo comidas nuevas para HOY después de cerrar
    el día, así que una marca sobre el plan cambiaría "a tus espaldas" según se siguiera
    apuntando. Congelar las comidas AQUÍ, en `ComidaSeguida` (más abajo), es lo que hace que
    "lo que se comparó" sea justo lo que había en el instante de cerrar, ni una comida más ni
    una menos.

    `OneToOneField` porque solo puede haber UNA foto por cierre: si la persona cambia de
    respuesta (R3, "el nuevo sustituye al anterior"), `cierres/logica.py:cerrar_dia` borra la
    foto vieja antes de decidir si hace falta una nueva.
    """

    cierre = models.OneToOneField(
        CierreDeDia, on_delete=models.CASCADE, related_name="menu_seguido"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Menú seguido de {self.cierre}"


class ComidaSeguida(models.Model):
    """
    Una comida dentro de la foto de `MenuSeguido`: mismos campos que `planes.models.
    ComidaDelPlan` (nombre, momento del día, calorías y macros), copiados TAL CUAL en el
    momento de cerrar — nunca una referencia al `ComidaDelPlan` original, que podría seguir
    cambiando después (esa es justamente la razón de ser de esta foto, ver `MenuSeguido`).
    """

    menu = models.ForeignKey(MenuSeguido, on_delete=models.CASCADE, related_name="comidas")
    nombre = models.CharField(max_length=150)
    momento_del_dia = models.CharField(max_length=10, choices=MOMENTOS_DEL_DIA)
    calorias = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    proteina_g = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    grasa_g = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    carbos_g = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.nombre} ({self.get_momento_del_dia_display()}) de {self.menu}"


class DiaSaltado(models.Model):
    """
    R8/Q-141 — la última fecha que esa persona se saltó la pregunta al abrir la app, para no
    volver a preguntarle jamás por ese día (G-162: "si tampoco se contesta [al abrir], no se
    vuelve a insistir"). "Cómo" punto 4 de la especificación: "un campo con la última fecha
    que esa persona se saltó es lo más simple" — aquí es un modelo de un único campo en vez de
    un campo suelto en `Usuario` porque el `AGENTS.md` de esta unidad no autoriza tocar
    `cuentas/` (fuera de la lista de ficheros de la especificación); funcionalmente es
    idéntico a "un campo" (un valor por persona, se sobrescribe, nunca un historial).

    Por qué basta con la ÚLTIMA fecha, sin guardar un historial de saltos: R7 dice que la app
    SOLO pregunta por el día más reciente pendiente (siempre "ayer" en el momento de abrir, ver
    `servicios/cierres.py:calcular_dia_pendiente`) — un día más antiguo que ese NUNCA vuelve a
    ofrecerse como pregunta, se haya saltado o no, así que no hace falta recordar saltos
    anteriores al último: ya quedaron fuera de la ventana de la pregunta por definición.
    `OneToOneField`: como mucho un registro por persona, se sustituye siempre que se salta un
    día nuevo (`cierres/logica.py:saltar_dia_pendiente`).
    """

    persona = models.OneToOneField(
        "hogares.Persona", on_delete=models.CASCADE, related_name="dia_saltado_cierre"
    )
    fecha = models.DateField()

    def __str__(self):
        return f"{self.persona} se saltó el {self.fecha}"
