"""
El cálculo del plan de comidas del día (unidad 005): sumar las comidas de hoy y sacar el %
que cubren del objetivo del día (R2, R3, R9). "Cómo" de la especificación: "sumar las comidas
del día y sacar el porcentaje del anillo son cálculo, no pantalla: van en `servicios/`, junto
al metabolismo, y se prueban llamándolos directamente. La plantilla no hace cuentas."

Mismo espíritu que `servicios/metabolismo.py` (unidad 004): funciones PURAS. Reciben números
y listas de diccionarios sencillos, no tocan la base de datos, no importan Django y no saben
qué es un `PlanDeDia` ni una petición HTTP — así se prueban solas, sin pasar por ninguna
pantalla (R8), y `planes/logica.py` es la única pieza que las conecta con los modelos.

El objetivo calórico del día (cuánto le toca comer hoy) NO se calcula aquí: eso ya lo resuelve
`servicios/metabolismo.py` (unidad 004) y `planes/logica.py` lo REUTILIZA llamando a
`perfiles/logica.py` — este módulo solo sabe sumar comidas y comparar esa suma con un número
que le llega ya calculado.
"""

_MAGNITUDES = ("calorias", "proteina_g", "grasa_g", "carbos_g")


def sumar_comidas(comidas):
    """
    Suma las calorías y los tres macros de una lista de comidas. Cada comida es un diccionario
    con las claves de `_MAGNITUDES` (quien llama —`planes/logica.py`— es quien convierte los
    `ComidaDelPlan` de la base de datos a esa forma sencilla).

    Con una lista vacía (sin plan puesto, R5: "el anillo vacío"), el total es CERO en las
    cuatro magnitudes, no un error.
    """
    totales = {magnitud: 0 for magnitud in _MAGNITUDES}
    for comida in comidas:
        for magnitud in _MAGNITUDES:
            totales[magnitud] += comida[magnitud]
    return totales


def calcular_porcentaje_cobertura(calorias_plan, calorias_objetivo):
    """
    R2/R3/C-79 — el % que el plan de hoy cubre del objetivo del día, redondeado al entero más
    cercano (2.800/3.006 ≈ 93%). Sin objetivo (`0`, negativo o `None`) no hay nada que cubrir:
    devuelve 0 en vez de reventar por una división entre cero.

    R9 (caso límite) — un plan que se PASA del objetivo no se capa aquí: puede devolver más de
    100 (p. ej. 120), a propósito, para no perder el dato real ("cuánto se ha pasado"). Capar
    la parte VISUAL de un anillo a 360° es decisión de quien lo pinta, no de este cálculo — de
    eso se encarga `calcular_resumen_del_dia` con `porcentaje_visual`, más abajo.
    """
    if not calorias_objetivo or calorias_objetivo <= 0:
        return 0
    return round((calorias_plan / calorias_objetivo) * 100)


def calcular_resumen_del_dia(comidas, calorias_objetivo):
    """
    El resumen completo que necesita una tarjeta del Inicio: los totales del plan de hoy, el %
    real de cobertura (R2/R3), el % ya capado a 100 para pintar el anillo sin desbordarlo
    (`porcentaje_visual`, R9), si el plan se ha pasado del objetivo (`pasado`, R9) y si hay
    alguna comida puesta (`tiene_comidas`, para distinguir "anillo vacío" de "anillo al 0%
    real" — R5).

    Es la función que llama el resto de la app (`planes/logica.py`), nunca una vista
    directamente (R8): "la plantilla no hace cuentas".
    """
    totales = sumar_comidas(comidas)
    porcentaje = calcular_porcentaje_cobertura(totales["calorias"], calorias_objetivo)
    pasado = bool(calorias_objetivo and calorias_objetivo > 0) and totales["calorias"] > calorias_objetivo

    return {
        **totales,
        "porcentaje": porcentaje,
        "porcentaje_visual": min(porcentaje, 100),
        "pasado": pasado,
        "tiene_comidas": bool(comidas),
    }
