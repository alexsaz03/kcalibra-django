"""
La lógica de negocio del plan de comidas (unidad 005): reunir el plan de HOY de una persona,
sus comidas, y el resumen que necesita su tarjeta del Inicio. Vive separada de las vistas,
igual que `perfiles/logica.py` y `hogares/logica.py` (el AGENTS.md del repo pide justo eso:
las vistas llaman a la capa de lógica, nunca calculan ellas mismas).

Aquí se unen dos piezas que NO se reimplementan (R8 y "Cómo" de la especificación):
- El objetivo calórico del día sale de `perfiles.logica.calcular_objetivo_del_dia` (unidad
  004, que a su vez llama a `servicios.metabolismo`): se LLAMA, no se recalcula aquí.
- La suma de las comidas y el % de cobertura salen de `servicios.planes` (el cálculo puro que
  estrena esta unidad).
Este fichero es el único que toca la base de datos para el plan: `servicios.planes` no sabe
qué es un `PlanDeDia`, y las vistas no hacen ninguna cuenta.
"""

from django.utils import timezone

from perfiles.logica import calcular_objetivo_del_dia
from servicios import planes as servicio_planes

from .models import PlanDeDia


def _comidas_como_diccionarios(comidas):
    """Convierte objetos `ComidaDelPlan` a los diccionarios sencillos que espera
    `servicios.planes` (que no sabe qué es un modelo de Django, a propósito — R8)."""
    return [
        {
            "calorias": comida.calorias,
            "proteina_g": comida.proteina_g,
            "grasa_g": comida.grasa_g,
            "carbos_g": comida.carbos_g,
        }
        for comida in comidas
    ]


def obtener_plan_de(usuario, fecha):
    """
    El plan de `usuario` en `fecha` (cualquiera, no solo hoy), o `None` si no tiene ninguno
    puesto ese día. Unidad 012 (decir-si-cumpliste.md, R4) — la foto del menú al cerrar el día
    necesita el plan de ESE día concreto, no el de hoy: `obtener_plan_de_hoy` (abajo) queda
    como el caso particular con `fecha=timezone.localdate()`, sin cambiar su comportamiento.
    """
    return (
        PlanDeDia.objects.filter(usuario=usuario, fecha=fecha).prefetch_related("comidas").first()
    )


def obtener_plan_de_hoy(usuario):
    """
    R11 — el plan de HOY de `usuario`, o `None` si no tiene ninguno puesto todavía. La fecha
    NUNCA es un parámetro: es SIEMPRE `timezone.localdate()` en el momento de la llamada,
    porque la pregunta que responde el Inicio es "¿cuánto puedo comer HOY?", nunca la de otro
    día (un plan de ayer o de mañana, aunque exista, no se ve ni se cuenta aquí).
    """
    return obtener_plan_de(usuario, timezone.localdate())


def resumen_del_dia(usuario):
    """
    El resumen completo de HOY para `usuario`: su plan (o `None`), sus comidas, su objetivo
    del día (unidad 004, reutilizado tal cual) y lo que suma el plan frente a ese objetivo —
    calorías, macros, % de cobertura y si se ha pasado (R2, R3, R8, R9). Es lo que pinta cada
    tarjeta del Inicio (`paginas/views.py`) y la pantalla de "apuntar el plan"
    (`planes/views.py`).
    """
    plan = obtener_plan_de_hoy(usuario)
    comidas = list(plan.comidas.all()) if plan else []
    objetivo = calcular_objetivo_del_dia(usuario)
    calorias_objetivo = objetivo["calorias"] if objetivo else 0

    resumen = servicio_planes.calcular_resumen_del_dia(
        _comidas_como_diccionarios(comidas), calorias_objetivo
    )
    return {
        "plan": plan,
        "comidas": comidas,
        "objetivo": objetivo,
        "resumen": resumen,
    }


def apuntar_comida(usuario, datos):
    """
    R1/R6 — añade una comida al plan de HOY de `usuario`, creando el plan si todavía no
    existía. Cualquiera del hogar puede llamar a esto con cualquier `usuario` del mismo hogar:
    la comprobación de que pertenece a su hogar se hace ANTES de llegar aquí, en
    `planes/acceso.py` (R7) — esta función ya no vuelve a mirarlo, confía en quien la llama.
    `datos` es el `cleaned_data` de `FormularioComida`, ya validado por Django (R10).

    "Una persona, un plan por día" ("Cómo" de la especificación): `get_or_create` es lo que
    hace que la SEGUNDA comida del día de la misma persona cuelgue del MISMO `PlanDeDia`, no
    de uno nuevo — la restricción única del modelo (`un_plan_por_persona_y_dia`) lo garantiza
    incluso si dos peticiones llegaran a la vez.
    """
    plan, _ = PlanDeDia.objects.get_or_create(
        usuario=usuario,
        fecha=timezone.localdate(),
        defaults={"hogar": usuario.hogar},
    )
    return plan.comidas.create(**datos)
