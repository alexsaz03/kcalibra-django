"""
El cálculo de un entreno (unidad 011, apuntar-un-entreno.md): la tabla de gasto por minuto de
G-71 y la fórmula que la ajusta al peso de quien entrenó (G-70).

R8 (arquitectura del proyecto, la misma promesa que `servicios/metabolismo.py` y
`servicios/planes.py`): funciones PURAS. Reciben datos y devuelven números; no tocan la base de
datos, no importan nada de Django, no saben qué es una petición HTTP.

La fórmula, ya despejada de los dos criterios del plano en la especificación de la unidad
(no se deduce otra vez — lo dice el aviso del padre):

    kcal = (kcal/min del deporte y la intensidad) × minutos × (peso_kg / 60)

G-71 da el gasto por minuto de "una persona de peso medio" sin decir cuál es ese peso; se
despeja de C-38 (Hyrox fuerte, 93 kg, 60 min → 1.302 kcal: 14 × 60 × (93/60) = 1.302 exacto) y
se confirma con C-37 (correr media, 62 kg, 35 min → 362 kcal: 10 × 35 × (62/60) = 361,67 → 362
con el redondeo de `Math.round`, no el bancario de `round()` — ver
conocimiento/round-python-vs-math-round-javascript.md). El peso de referencia es 60 kg.
"""

import math

PESO_REFERENCIA_KG = 60

# G-71 — kcal por minuto a peso de referencia (60 kg), por deporte e intensidad
# (suave/media/fuerte: las etiquetas del PLANO, no las de la app Node — la especificación de
# la unidad es explícita en que manda el plano aquí).
TABLA_KCAL_POR_MINUTO = {
    "correr": {"suave": 8, "media": 10, "fuerte": 13.5},
    "bici": {"suave": 6, "media": 8, "fuerte": 10},
    "nadar": {"suave": 6, "media": 8, "fuerte": 9.5},
    "fuerza": {"suave": 3.5, "media": 5, "fuerte": 6},
    "crossfit": {"suave": 6, "media": 9, "fuerte": 12},
    "hyrox": {"suave": 8, "media": 11, "fuerte": 14},
    "otro": {"suave": 4, "media": 6, "fuerte": 8},
}

DEPORTES_VALIDOS = frozenset(TABLA_KCAL_POR_MINUTO)
INTENSIDADES_VALIDAS = frozenset({"suave", "media", "fuerte"})


def _redondear(numero):
    """
    Mismo criterio de redondeo que `servicios/metabolismo.py` (la mitad SIEMPRE hacia arriba,
    como `Math.round` de JavaScript, no el redondeo bancario de `round()` de Python): C-37 da
    361,67 kcal exactos, y solo con este redondeo sube a 362. Se repite aquí (dos líneas, no
    una fórmula de dominio) en vez de importar el `_redondear` privado de `metabolismo.py`: son
    dos módulos de cálculo puro hermanos, cada uno autocontenido.
    """
    return math.floor(numero + 0.5)


def estimar_calorias(*, deporte, intensidad, minutos, peso_kg):
    """
    G-70/G-71 — cuánto ha quemado un entreno cuando la persona NO trae sus propias calorías (de
    su reloj o pulsómetro): el gasto por minuto del deporte y la intensidad, multiplicado por
    los minutos y ajustado del peso de referencia (60 kg) al peso de quien entrenó (G-70: "no
    tiene por qué ser el del titular", aunque en esta unidad siempre lo es — personas a cargo
    fuera de alcance).

    Asume `deporte`/`intensidad` ya validados (están en las listas de arriba) y `peso_kg`
    positivo: quien llama (`entrenos/logica.py`) es responsable de eso, igual que
    `servicios.metabolismo` confía en que sus llamadores ya filtraron los datos imposibles
    (R9: se rechazan en el FORMULARIO, antes de llegar aquí).
    """
    kcal_por_minuto = TABLA_KCAL_POR_MINUTO[deporte][intensidad]
    return _redondear(kcal_por_minuto * minutos * (peso_kg / PESO_REFERENCIA_KG))
