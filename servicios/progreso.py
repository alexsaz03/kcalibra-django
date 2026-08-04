"""
El cálculo de la unidad 010 (ver-tu-progreso.md): cuántas semanas mirar, qué mediciones caen
dentro de ese periodo, y cómo convertir una serie de mediciones en los puntos de un SVG.

Mismo espíritu que `servicios/metabolismo.py` (unidad 004) y `servicios/planes.py` (unidad
005): funciones PURAS. Reciben números, fechas y listas de diccionarios sencillos, no tocan la
base de datos, no importan Django y no saben qué es una `MedicionPeso` ni una petición HTTP
—así se prueban solas (ROADMAP: "las vistas no calculan; llaman")—; `progreso/views.py` es la
única pieza que las conecta con los modelos.

Nada de librerías de gráficos (bias.md, "Cómo" de la especificación de la unidad): el dibujo
es SVG generado aquí como texto (una cadena de puntos "x,y"), coherente con el precedente de
la unidad 005 (el anillo del plan, con "conic-gradient" puro) — aquí, en vez de un donut de
CSS, hace falta una LÍNEA, así que la pieza que dibuja es un `<polyline>` de SVG servido desde
la plantilla; este módulo solo calcula sus coordenadas.
"""

from datetime import timedelta

# R5: el periodo que se mira, entre 4 y 52 semanas, con 12 de fábrica (§7 del plano).
SEMANAS_MIN = 4
SEMANAS_MAX = 52
SEMANAS_POR_DEFECTO = 12

# Tamaño del lienzo de cada gráfica (mismas unidades para las tres: peso, grasa, cintura).
ANCHO_SVG = 600
ALTO_SVG = 160
MARGEN_SVG = 12

CAMPOS_MEDICION = ("peso_kg", "grasa_pct", "cintura_cm")


def semanas_desde_parametro(valor):
    """
    R5/R6 — cuántas semanas mirar, a partir de lo que llegó en la URL como parámetro
    `semanas` (`valor`: puede ser `None`, una cadena vacía, "abc", "-3", "9999", con espacios
    de más...). Fuera de [SEMANAS_MIN, SEMANAS_MAX], no numérico o ausente: cae al valor por
    DEFECTO y la pantalla SIGUE funcionando.

    R6, caso límite de entrada explícito: esto NO se parece a la unidad 009 (una variable de
    entorno que no se entiende TUMBA el arranque a propósito, porque es configuración de
    despliegue). Aquí es una persona tecleando algo en la URL — jamás debe romper una
    pantalla, así que no hay ninguna rama que levante una excepción.
    """
    if valor is None:
        return SEMANAS_POR_DEFECTO
    try:
        semanas = int(str(valor).strip())
    except (TypeError, ValueError):
        return SEMANAS_POR_DEFECTO
    if semanas < SEMANAS_MIN or semanas > SEMANAS_MAX:
        return SEMANAS_POR_DEFECTO
    return semanas


def recortar_por_periodo(mediciones, semanas, hoy):
    """
    Las `mediciones` (lista de dicts con al menos la clave "fecha") que caen entre
    `hoy - semanas` semanas y `hoy`, ambos incluidos (R5). `mediciones` puede llegar en
    cualquier orden; el resultado sale ordenado por fecha ASCENDENTE — el orden que necesita
    una gráfica de evolución (la primera pesada a la izquierda, la última a la derecha).
    """
    limite = hoy - timedelta(weeks=semanas)
    return sorted(
        (m for m in mediciones if limite <= m["fecha"] <= hoy),
        key=lambda m: m["fecha"],
    )


def _escalar(valor, minimo, maximo, longitud_util, margen, invertir=False):
    """
    Lleva `valor` (dentro de [minimo, maximo]) a una coordenada de píxel dentro de
    [margen, margen + longitud_util]. Con `minimo == maximo` (una fecha única, o un valor que
    no varió en todo el periodo — el caso EXACTO de C-88, "el peso sigue en 93 kg") no hay
    ningún rango que repartir: se centra, en vez de dividir entre cero.

    `invertir=True` es para el eje Y de un SVG: en SVG "abajo" es "y grande", así que un valor
    más ALTO tiene que acabar en una coordenada más PEQUEÑA (más arriba en el dibujo) — sin
    esto, una línea de peso que SUBE se pintaría bajando.
    """
    rango = maximo - minimo
    if not rango:
        return margen + longitud_util / 2
    fraccion = (valor - minimo) / rango
    if invertir:
        fraccion = 1 - fraccion
    return margen + fraccion * longitud_util


def construir_grafica(mediciones, campo, ancho=ANCHO_SVG, alto=ALTO_SVG, margen=MARGEN_SVG):
    """
    R1/R2/R4 — la gráfica de UN campo (`"peso_kg"`, `"grasa_pct"` o `"cintura_cm"`) a partir
    de `mediciones` YA recortadas por periodo (`recortar_por_periodo`, arriba). Ignora los
    días donde ESE campo concreto esté vacío (R4: "se dibuja con los días que tenga, sin
    inventar los que faltan") — no rellena huecos ni interpola entre ellos.

    R2/Q-152 — si NINGÚN día del periodo tiene ese dato, devuelve `None`: la plantilla, al
    recibir `None`, no pinta nada en absoluto (ni un hueco vacío, ni un aviso de que faltan
    datos). Si hay al menos uno, devuelve un dict con los puntos ya convertidos a coordenadas
    de un SVG de `ancho`×`alto`, y el primer/último valor real (para el resumen de texto
    encima del dibujo, y para poder distinguir "sube" de "baja" sin volver a mirar los
    puntos).
    """
    puntos = [
        (m["fecha"], float(m[campo])) for m in mediciones if m.get(campo) is not None
    ]
    if not puntos:
        return None

    fechas = [fecha for fecha, _ in puntos]
    valores = [valor for _, valor in puntos]
    fecha_min, fecha_max = min(fechas), max(fechas)
    valor_min, valor_max = min(valores), max(valores)

    ancho_util = ancho - 2 * margen
    alto_util = alto - 2 * margen

    coordenadas = [
        (
            round(
                _escalar(
                    (fecha - fecha_min).days, 0, (fecha_max - fecha_min).days,
                    ancho_util, margen,
                ),
                1,
            ),
            round(_escalar(valor, valor_min, valor_max, alto_util, margen, invertir=True), 1),
        )
        for fecha, valor in puntos
    ]

    return {
        "puntos_svg": " ".join(f"{x},{y}" for x, y in coordenadas),
        "coordenadas": coordenadas,
        "primero": puntos[0][1],
        "ultimo": puntos[-1][1],
        "primero_fecha": puntos[0][0],
        "ultimo_fecha": puntos[-1][0],
        "ancho": ancho,
        "alto": alto,
    }


def construir_evolucion(mediciones):
    """
    Las tres gráficas de Progreso (R1/R2/G-172) a partir de `mediciones` ya recortadas por
    periodo: peso, grasa y cintura, cada una construida con `construir_grafica`. Cualquiera de
    las tres puede salir `None` (R2, R11) — la propia de peso incluida, si `mediciones` está
    vacía del todo (R11: nadie ha apuntado nada todavía).
    """
    return {campo: construir_grafica(mediciones, campo) for campo in CAMPOS_MEDICION}
