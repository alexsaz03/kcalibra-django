"""
El cálculo del metabolismo, el gasto diario, el objetivo calórico y el reparto de macros
(unidad 004): metabolismo basal, gasto diario, objetivo calórico y reparto de macros.

R8 (arquitectura de la unidad): estas son funciones PURAS. Reciben datos y devuelven números.
No tocan la base de datos, no importan nada de Django, no saben qué es una petición HTTP. Así
se prueban solas (sin pasar por ninguna pantalla) y así sirven el día que haya una app nativa
que quiera el mismo cálculo sin repetir la fórmula en otro sitio.

La fórmula es Mifflin-St Jeor, la misma que resuelve la app vieja en
`backend/src/services/metabolism.js` (bias.md, punto 3: se consulta para entender qué se
resolvió, no se traduce línea a línea — aquí se reescribe a la manera de Python, con nombres
en español y un catálogo de objetivos ampliado con "recomposición corporal", que en la
referencia Node no existía).

  Basal (BMR):      10·peso(kg) + 6,25·altura(cm) − 5·edad, +5 si es hombre, −161 si es mujer
  Gasto diario:      BMR × factor de actividad
  Objetivo calórico: gasto diario × (1 + ajuste_pct/100)
  Macros:            proteína = g/kg del objetivo × peso · grasa = 28% de las kcal (25% si el
                      objetivo es rendimiento) ÷ 9 · los carbohidratos son lo que sobra ÷ 4

Se redondea al entero más próximo, y SOLO al final de cada magnitud (nunca a mitad de una
cuenta): redondear antes de tiempo desplaza los números finales, y aquí "los números deciden
lo que la gente come" (especificación de la unidad).
"""

import calendar
import math
from datetime import date

# Sexos aceptados. La fórmula de Mifflin-St Jeor solo tiene dos ramas (+5 / −161): no hay un
# tercer término que inventar sin una fuente médica que lo respalde (bias.md: mínima
# invención de la IA).
SEXOS = ("hombre", "mujer")

# Factor multiplicador del gasto diario según cuánto se mueve la persona en su día a día.
ACTIVIDADES = {
    "sedentario": 1.2,
    "ligero": 1.375,
    "moderado": 1.55,
    "activo": 1.725,
    "muy_activo": 1.9,
}

# El catálogo de los CINCO objetivos (R4/G-60): el ajuste de fábrica sobre el gasto diario, y
# los gramos de proteína por kilo de peso que trae cada uno de fábrica. "recomposicion_corporal"
# es el quinto, nuevo en esta unidad (no existía en la app vieja).
OBJETIVOS = {
    "mantener": {"ajuste_pct": 0, "proteina_por_kg": 1.8},
    "perder_grasa": {"ajuste_pct": -10, "proteina_por_kg": 2.2},
    "ganar_musculo": {"ajuste_pct": 10, "proteina_por_kg": 2.0},
    "rendimiento": {"ajuste_pct": 5, "proteina_por_kg": 1.8},
    "recomposicion_corporal": {"ajuste_pct": 10, "proteina_por_kg": 2.2},
}


def _redondear(numero):
    """
    Redondea al entero más próximo con la mitad SIEMPRE hacia arriba (igual que `Math.round`
    de JavaScript en la referencia Node), no con el redondeo bancario de `round()` de Python
    (que en un `x,5` exacto puede ir hacia el par más cercano). Como aquí solo se redondean
    magnitudes positivas (calorías, gramos, edad, kg), `floor(n + 0,5)` es equivalente y
    evita esa diferencia de comportamiento en los casos límite.
    """
    return math.floor(numero + 0.5)


def calcular_edad(fecha_nacimiento, hoy=None):
    """
    Años completos a partir de la fecha de nacimiento (R10, caso límite del cumpleaños): si
    hoy no ha llegado aún el día y el mes de su cumpleaños de este año, tiene un año menos.
    `hoy` es opcional (por defecto, la fecha real) precisamente para que quien llama pueda
    fijarla en un test y así no depender del reloj de la máquina que ejecuta la suite.

    R11 (hueco H1 de la revisión) — quien nació el 29 de febrero: en un año NO bisiesto no
    existe un `date(ese_año, 2, 29)`, y construirlo revienta con `ValueError` (no con un dato
    imposible que R11 pudiera rechazar al entrar: el 29/02/2000 es una fecha de nacimiento
    perfectamente válida, y el fallo aparecía después, al calcular). Regla de negocio, para
    que quede escrita y no se repita esta pregunta: en un año no bisiesto, quien nació el 29
    de febrero cumple años el 28 de febrero (el último día de su mes de nacimiento), no el 1
    de marzo — es la convención más extendida en el software que ya resuelve este caso.
    """
    hoy = hoy or date.today()
    edad = hoy.year - fecha_nacimiento.year

    dia_cumpleanos = fecha_nacimiento.day
    if fecha_nacimiento.month == 2 and dia_cumpleanos == 29 and not calendar.isleap(hoy.year):
        dia_cumpleanos = 28

    cumple_este_anio = date(hoy.year, fecha_nacimiento.month, dia_cumpleanos)
    if hoy < cumple_este_anio:
        edad -= 1
    return edad


def calcular_bmr(*, sexo, peso_kg, altura_cm, edad):
    """Metabolismo basal (kcal/día) con Mifflin-St Jeor. Sin redondear: es un paso
    intermedio, y solo se redondea el resultado final (ver el docstring del módulo)."""
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * edad
    return base + 5 if sexo == "hombre" else base - 161


def calcular_gasto_diario(bmr, actividad):
    """Gasto total diario (BMR × factor de actividad), sin entrenos concretos (fuera de
    alcance de esta unidad: eso son Strava y los entrenos a mano, otra área)."""
    factor = ACTIVIDADES[actividad]
    return bmr * factor


def calcular_objetivo_calorico(gasto_diario, ajuste_pct):
    """El gasto diario, aplicando el % de déficit/superávit del objetivo (de fábrica, o el
    que la persona haya puesto a mano — R6: eso ya viene decidido en `ajuste_pct`, esta
    función no distingue de dónde salió)."""
    return gasto_diario * (1 + ajuste_pct / 100)


def calcular_macros(*, objetivo, calorias, peso_kg):
    """
    Reparto de macros (gramos) para unas calorías objetivo: la proteína se fija por kilo de
    peso según el objetivo, la grasa como % de las calorías (28%, o 25% si el objetivo es
    rendimiento), y los carbohidratos son lo que sobra de las calorías totales.
    """
    proteina_por_kg = OBJETIVOS[objetivo]["proteina_por_kg"]
    pct_grasa = 0.25 if objetivo == "rendimiento" else 0.28

    proteina_g = proteina_por_kg * peso_kg
    grasa_g = (calorias * pct_grasa) / 9  # 1 g de grasa = 9 kcal

    kcal_proteina = proteina_g * 4  # 1 g de proteína = 4 kcal
    kcal_grasa = grasa_g * 9
    kcal_carbos = max(0, calorias - kcal_proteina - kcal_grasa)
    carbos_g = kcal_carbos / 4  # 1 g de carbohidrato = 4 kcal

    return {
        "proteina_g": _redondear(proteina_g),
        "grasa_g": _redondear(grasa_g),
        "carbos_g": _redondear(carbos_g),
    }


def calcular_perfil_nutricional(
    *, sexo, fecha_nacimiento, altura_cm, peso_kg, actividad, objetivo, ajuste_pct, hoy=None
):
    """
    El cálculo completo, de un tirón: la edad, el metabolismo basal, el gasto diario, el
    objetivo calórico y los macros. Es la función que llama el resto de la app (la capa de
    lógica de `perfiles/`, nunca una vista directamente — R8).
    """
    edad = calcular_edad(fecha_nacimiento, hoy)
    bmr = calcular_bmr(sexo=sexo, peso_kg=peso_kg, altura_cm=altura_cm, edad=edad)
    gasto_diario = calcular_gasto_diario(bmr, actividad)
    objetivo_calorico = calcular_objetivo_calorico(gasto_diario, ajuste_pct)
    macros = calcular_macros(objetivo=objetivo, calorias=objetivo_calorico, peso_kg=peso_kg)

    return {
        "edad": edad,
        "bmr": _redondear(bmr),
        "gasto_diario": _redondear(gasto_diario),
        "calorias": _redondear(objetivo_calorico),
        "ajuste_pct": ajuste_pct,
        **macros,
    }
