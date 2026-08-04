"""
La lógica de negocio de los entrenos apuntados a mano (unidad 011, apuntar-un-entreno.md):
reunir los de una persona con cuánto lleva quemado hoy (§8 del plano), apuntar uno estimando
sus calorías si la persona no las trae (G-70), y corregirlo o borrarlo sin recalcular nada más
(R38/G-72: el objetivo del día se recalcula solo, la próxima vez que alguien llame a
`perfiles.logica.calcular_objetivo_del_dia` — este fichero no lo toca).

Vive separada de las vistas, igual que el resto de la app (perfiles/logica.py,
planes/logica.py...): las vistas reciben la petición HTTP y llaman aquí.

Dirección de las dependencias entre esta unidad y `perfiles` (para que no se cierre un ciclo):
este módulo importa `perfiles.logica.peso_medio_7_dias` (necesita el peso de quien entrenó,
G-70); `perfiles.logica.calcular_objetivo_del_dia` importa el MODELO `entrenos.models.Entreno`
directamente (no este módulo) para sumar las calorías del día — así el ciclo solo existe en un
sentido. Detalle completo en el docstring de `perfiles/logica.py:_calorias_de_entrenos`.
"""

from django.db.models import Sum
from django.utils import timezone

from perfiles.logica import peso_medio_7_dias
from servicios import entrenos as servicio_entrenos

from .models import Entreno


def todos_los_entrenos(usuario):
    """§8 del plano ("Qué ve nada más entrar: sus entrenos") — el histórico completo de
    `usuario`, más recientes primero (`Entreno.Meta.ordering`): R6/C-39 exige poder corregir
    uno de un día pasado, así que la pantalla no se limita a los de hoy."""
    return Entreno.objects.filter(usuario=usuario)


def calorias_del_dia(usuario, fecha):
    """Cuánto ha quemado `usuario` en `fecha` según sus entrenos apuntados; 0 si no tiene
    ninguno ese día."""
    total = Entreno.objects.filter(usuario=usuario, fecha=fecha).aggregate(total=Sum("calorias"))[
        "total"
    ]
    return total or 0


def calorias_de_hoy(usuario):
    """§8 del plano — "cuántas calorías lleva quemadas hoy": lo que enseña la pantalla nada
    más entrar."""
    return calorias_del_dia(usuario, timezone.localdate())


class SinPesoParaEstimar(Exception):
    """
    No se puede estimar un entreno sin el peso de quien entrenó (la fórmula lo necesita, G-70)
    y esa persona no tiene ninguna medición todavía — caso límite defensivo (no lo nombra
    ningún R* por número, pero es la misma cautela de R9: "sin romper la pantalla" ante una
    entrada que no se puede procesar). En la práctica no debería pasar nunca: el alta siempre
    deja la primera medición (unidad 004); solo ocurriría si se borraran todas después.
    """


def _resolver_calorias(usuario, datos):
    """
    G-70 — si la persona escribió calorías, se quedan TAL CUAL (R-36, R2: "la app no las
    discute"); si las dejó en blanco, se estiman con el deporte, la intensidad, los minutos y
    SU peso (`peso_medio_7_dias`, el mismo que usa el resto de la app — nunca la última pesada
    suelta). Devuelve `(calorias, calorias_manuales)`: el segundo valor es lo que permite que
    `corregir_entreno` sepa, la próxima vez, si debe respetar el número o volver a estimarlo
    (ver el docstring de `Entreno.calorias_manuales` en models.py).
    """
    calorias = datos.get("calorias")
    if calorias not in (None, ""):
        return calorias, True

    peso_kg = peso_medio_7_dias(usuario)
    if peso_kg is None:
        raise SinPesoParaEstimar(
            "No podemos estimar las calorías sin tu peso: apúntalo primero, o escribe las "
            "calorías de tu reloj."
        )
    estimadas = servicio_entrenos.estimar_calorias(
        deporte=datos["deporte"],
        intensidad=datos["intensidad"],
        minutos=datos["minutos"],
        peso_kg=peso_kg,
    )
    return estimadas, False


def apuntar_entreno(usuario, datos):
    """R-36/R-37 — crea un entreno para `usuario` con los datos ya validados por el
    formulario (deporte, intensidad, minutos, fecha, y calorías si las trajo)."""
    calorias, calorias_manuales = _resolver_calorias(usuario, datos)
    return Entreno.objects.create(
        usuario=usuario,
        fecha=datos["fecha"],
        deporte=datos["deporte"],
        intensidad=datos["intensidad"],
        minutos=datos["minutos"],
        calorias=calorias,
        calorias_manuales=calorias_manuales,
    )


def corregir_entreno(entreno, datos):
    """
    R-38/G-72 — corrige cualquier dato de un entreno ya apuntado y recalcula sus calorías
    IGUAL que al crearlo (misma regla G-70, vía `_resolver_calorias`): si la corrección trae
    calorías escritas, se respetan; si no, se estiman de nuevo con los datos YA corregidos —
    es lo que hace que "cambia el minuto, el deporte o el día, y las calorías se rehacen
    solas" (contrato de la especificación) sin que la persona tenga que tocar ese campo.

    Sin avisar de nada (R6/C-39): esta función no dispara ningún mensaje ni notificación, sea
    el día que sea el entreno — es la vista (`entrenos/views.py`) quien no añade ninguno,
    nunca esta capa.
    """
    calorias, calorias_manuales = _resolver_calorias(entreno.usuario, datos)
    entreno.fecha = datos["fecha"]
    entreno.deporte = datos["deporte"]
    entreno.intensidad = datos["intensidad"]
    entreno.minutos = datos["minutos"]
    entreno.calorias = calorias
    entreno.calorias_manuales = calorias_manuales
    entreno.save()
    return entreno


def borrar_entreno(entreno):
    """§8 del plano ("Qué puede hacer... Borrarlo") — borrado definitivo: el plano excluye
    expresamente "recuperar un entreno borrado" (§10), así que no hace falta ningún estado
    intermedio ni papelera — mismo criterio que `perfiles.logica.borrar_medicion`."""
    entreno.delete()
