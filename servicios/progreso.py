"""
El cálculo de la unidad 010 (ver-tu-progreso.md): cuántas semanas mirar, qué mediciones caen
dentro de ese periodo, y cómo convertir una serie de mediciones en los puntos de un SVG.

La unidad 013 (completar-progreso.md) AÑADE aquí mismo el cálculo de los entrenos por semana
(R-79) y el cumplimiento (R-80): mismo espíritu, funciones puras, mismo módulo — no un tercero,
porque siguen siendo "el cálculo de la pantalla de Progreso" (Cómo, punto 1: "Ya tienes dos
módulos hermanos donde mirar el estilo", este es uno de ellos).

Mismo espíritu que `servicios/metabolismo.py` (unidad 004) y `servicios/planes.py` (unidad
005): funciones PURAS. Reciben números, fechas y listas de diccionarios sencillos, no tocan la
base de datos, no importan Django y no saben qué es una `MedicionPeso` ni una petición HTTP
—así se prueban solas (ROADMAP: "las vistas no calculan; llaman")—; `progreso/views.py` es la
única pieza que las conecta con los modelos.

Nada de librerías de gráficos (bias.md, "Cómo" de la especificación de la unidad): el dibujo
es SVG generado aquí como texto (una cadena de puntos "x,y"), coherente con el precedente de
la unidad 005 (el anillo del plan, con "conic-gradient" puro) — aquí, en vez de un donut de
CSS, hace falta una LÍNEA, así que la pieza que dibuja es un `<polyline>` de SVG servido desde
la plantilla; este módulo solo calcula sus coordenadas. Las barras de entrenos por semana (R-79)
no usan SVG: son divs con una altura porcentual (Cómo, punto 4 — "aquí encaja o SVG o divs con
altura porcentual"), calculada también aquí, no en la plantilla.
"""

import math
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
    Los `mediciones` (lista de dicts con al menos la clave "fecha") que caen entre
    `hoy - semanas` semanas y `hoy`, ambos incluidos (R5). `mediciones` puede llegar en
    cualquier orden; el resultado sale ordenado por fecha ASCENDENTE — el orden que necesita
    una gráfica de evolución (la primera pesada a la izquierda, la última a la derecha).

    Genérica a propósito (unidad 013, Cómo punto 3: "si no te sirve tal cual, generalízala"):
    solo mira la clave "fecha", así que sirve TAL CUAL para recortar `MedicionPeso` (unidad
    010), `Entreno` (R-79) o `CierreDeDia` (R-80) — no hizo falta escribir una tercera copia de
    esta resta de fechas, cada llamador solo pasa sus propios dicts con esa clave.
    """
    limite = hoy - timedelta(weeks=semanas)
    return sorted(
        (m for m in mediciones if limite <= m["fecha"] <= hoy),
        key=lambda m: m["fecha"],
    )


def agrupar_entrenos_por_semana(entrenos_del_periodo, hoy, semanas):
    """
    R-79/R1/C-89 — los `entrenos_del_periodo` (YA recortados con `recortar_por_periodo`, arriba
    — lista de dicts con "fecha", "minutos" y "calorias") agrupados en bloques de 7 días
    contando hacia atrás desde `hoy`: el bloque 0 son los últimos 7 días (hoy incluido), el 1
    los 7 anteriores, etc. — el mismo criterio de "semana" que ya usa el recorte por periodo de
    arriba (semanas de 7 días desde hoy, no semanas de calendario lunes-domingo).

    Solo aparecen las semanas con AL MENOS un entreno real (mismo espíritu que R2/R11/R6: nunca
    un hueco vacío inventado). El resultado sale ordenado de la semana MÁS ANTIGUA a la MÁS
    RECIENTE, igual que `construir_grafica` — mismo orden de lectura que el peso.

    Cada semana trae, además de los tres números que pide R1 (cuántos entrenos, minutos y
    calorías, sumados), una `altura_pct` (0-100) para dibujar la barra sin librerías (Cómo,
    punto 4): la altura es relativa al máximo de entrenos de UNA semana dentro de este mismo
    resultado, así que la barra más alta del periodo siempre llega al 100%.

    Ronda 2 (hueco de la revisión, `hallazgos.md`) — `semanas` es NUEVO: hace falta para saber
    dónde está el borde real del periodo. `recortar_por_periodo` usa un límite INCLUSIVO
    (`hoy - semanas semanas` hasta `hoy`, ambos dentro), así que el periodo tiene
    `semanas*7 + 1` días, no `semanas*7`. Teselar en bloques fijos de 7 (`dias_atras // 7`) deja
    un día suelto que antes desbordaba a un cubo extra de índice `semanas`, con un solo día
    dentro pero etiquetado con un rango de 7 completos — la barra más antigua mentía sobre lo
    que cubría. Aquí el índice se recorta a `semanas - 1` (el día sobrante se funde en el cubo
    más antiguo, nunca abre uno nuevo) y ESE cubo extiende su `inicio` hasta el límite real del
    periodo (`hoy - semanas*7` días, el mismo que calcula `recortar_por_periodo`): así su
    etiqueta pasa a cubrir 8 días de verdad, en vez de 7 fingidos. Ni un entreno cambia de
    bando: solo cambia dónde se traza la frontera del cubo más antiguo y qué dice su etiqueta.
    """
    ultimo_indice = semanas - 1
    semanas_por_indice = {}
    for entreno in entrenos_del_periodo:
        dias_atras = (hoy - entreno["fecha"]).days
        indice = min(dias_atras // 7, ultimo_indice)
        if indice not in semanas_por_indice:
            # El cubo más antiguo (índice `ultimo_indice`) no mide 7 días como los demás: mide
            # lo que de verdad le queda del periodo, `semanas*7` días hacia atrás desde `hoy`
            # (el límite de `recortar_por_periodo`) — normalmente 8 con el día sobrante fundido.
            dias_de_inicio = (
                semanas * 7 if indice == ultimo_indice else indice * 7 + 6
            )
            semanas_por_indice[indice] = {
                "inicio": hoy - timedelta(days=dias_de_inicio),
                "fin": hoy - timedelta(days=indice * 7),
                "entrenos": 0,
                "minutos": 0,
                "calorias": 0,
            }
        semana = semanas_por_indice[indice]
        semana["entrenos"] += 1
        semana["minutos"] += entreno["minutos"]
        semana["calorias"] += entreno["calorias"]

    semanas = [semanas_por_indice[indice] for indice in sorted(semanas_por_indice, reverse=True)]

    maximo = max((s["entrenos"] for s in semanas), default=0)
    for semana in semanas:
        semana["altura_pct"] = round(semana["entrenos"] / maximo * 100) if maximo else 0

    return semanas


# R-80/Q-153/C-87 — las tres respuestas de `CierreDeDia.RESPUESTAS` (cierres/models.py),
# repetidas aquí como cadenas literales a propósito: este módulo es cálculo puro y no importa
# NADA de Django ni de otra app (mismo criterio que servicios/entrenos.py, que tampoco importa
# `entrenos.models` para su tabla de kcal/minuto) — quien llama (progreso/views.py) es quien
# conecta esto con el modelo de verdad.
_LO_SEGUI = "lo_segui"
_A_MEDIAS = "a_medias"
_NO_LO_SEGUI = "no_lo_segui"


def calcular_cumplimiento(cierres_del_periodo):
    """
    R-80/R3/R4/R5/C-87 — el cumplimiento a partir de los `cierres_del_periodo` (YA recortados
    con `recortar_por_periodo` — lista de dicts con "respuesta"): cuántos días cerró, cuántos
    siguió el plan entero, cuántos a medias, cuántos no, y el PORCENTAJE de cumplimiento.

    Q-153/C-87, EL error más fácil de cometer leyendo R-80 deprisa: el porcentaje va sobre los
    días que la persona CERRÓ, nunca sobre los días del periodo — 14 de 20 cerrados es 70%, no
    14 de 30. Por eso esta función ni siquiera RECIBE cuántos días tiene el periodo: solo puede
    calcular sobre lo que sí le llega, que son los cierres.

    R5, caso límite: sin ningún cierre en el periodo, `porcentaje` sale `None` (ni se inventa un
    número ni se divide entre cero) — la plantilla decide cómo decirlo con naturalidad.
    """
    cerrados = len(cierres_del_periodo)
    lo_segui = sum(1 for c in cierres_del_periodo if c["respuesta"] == _LO_SEGUI)
    a_medias = sum(1 for c in cierres_del_periodo if c["respuesta"] == _A_MEDIAS)
    no_lo_segui = sum(1 for c in cierres_del_periodo if c["respuesta"] == _NO_LO_SEGUI)

    porcentaje = None
    if cerrados:
        # Mismo criterio de redondeo que servicios/entrenos.py y servicios/metabolismo.py: la
        # mitad SIEMPRE hacia arriba (Math.round de JS), no el redondeo bancario de round().
        porcentaje = math.floor((lo_segui / cerrados) * 100 + 0.5)

    return {
        "cerrados": cerrados,
        "lo_segui": lo_segui,
        "a_medias": a_medias,
        "no_lo_segui": no_lo_segui,
        "porcentaje": porcentaje,
    }


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
