"""
El acceso a la base de la app Node — **de solo lectura, siempre** (R7, "Fuera de alcance": "no
se borra ni se modifica la base de Node"). La ruta nunca se escribe en el código (está fuera del
repositorio y lleva datos personales, unidad 022): siempre llega como argumento del comando.

Se abre con `sqlite3` de la librería estándar (no hace falta ninguna dependencia nueva) y en
modo `mode=ro` de la URI de SQLite: eso hace que CUALQUIER intento de escritura (incluso uno
accidental, de un futuro cambio en este módulo) falle en el motor de la base, no solo por
convención de quien programa. Es la misma cautela que el resto del proyecto aplica a los datos
que no se pueden permitir perder (unidad 017, "una migración sin copia previa es pérdida de
datos"): aquí el riesgo no es perder el destino, es tocar el origen que sigue en uso.

R7 ("el comando falla diciendo qué falta, sin trazas crudas de Python") se resuelve aquí: todo
lo que puede ir mal al abrir el origen —ruta que no existe, fichero que no es una SQLite válida,
tabla que falta— se convierte en `OrigenNodeInvalido`, con un mensaje en cristiano. El comando
(`importacion/management/commands/importar_datos_node.py`) es quien la atrapa y la convierte en
un `CommandError` (que Django imprime SIN traceback).
"""

import os
import sqlite3

# Las cuatro tablas que esta unidad SÍ trae (R1/R4/R5, "Qué"): la despensa, los entrenos, las
# recetas y las pesadas. Deliberadamente NO incluye `usuarios`, `miembros_hogar` (identidad,
# "Fuera de alcance") ni `strava_cuentas` (tokens OAuth, "ni leerla") — ver el docstring del
# módulo hermano `mapeo.py` para el porqué completo de cada exclusión.
#
# Bug 033 — matiz sobre `miembros_hogar`: sigue SIN leerse como tabla (la identidad de un
# miembro de la casa — nombre, fecha de nacimiento, altura, peso — sigue fuera de alcance).
# Lo que SÍ se lee desde esta unidad es la columna `miembro_id` de `entrenos` y `pesos`: un
# entero suelto (NULL = titular, un id = un miembro de la casa) que el comando traduce a una
# `Persona` de KCalibra a través de `--miembro-node` (`importacion/miembros.py`), nunca
# consultando la tabla de identidad de Node.
TABLAS_REQUERIDAS = ("productos_stock", "entrenos", "recetas", "pesos")


class OrigenNodeInvalido(Exception):
    """La base de Node no se puede leer tal y como el comando la necesita: la ruta no existe,
    el fichero no es una SQLite válida, o le falta alguna de las TABLAS_REQUERIDAS (R7)."""


def abrir(ruta):
    """
    Abre la SQLite de Node en modo ESTRICTAMENTE de lectura y comprueba que trae las cuatro
    tablas que hacen falta. Devuelve la conexión abierta (quien llama es responsable de
    cerrarla) o levanta `OrigenNodeInvalido` con un mensaje que dice exactamente qué falta.
    """
    if not ruta:
        raise OrigenNodeInvalido("No se ha indicado la ruta de la base de datos de Node.")
    if not os.path.exists(ruta):
        raise OrigenNodeInvalido(f"No existe ninguna base de datos en '{ruta}'.")
    if not os.path.isfile(ruta):
        raise OrigenNodeInvalido(f"'{ruta}' no es un fichero.")

    try:
        # uri=True + mode=ro: SQLite rechaza cualquier escritura a nivel de motor, no solo
        # por convención de este código. `ruta` puede traer espacios o símbolos que rompan la
        # URI si se concatenan a pelo, así que se cuela por el parámetro `check_same_thread`
        # de una conexión normal PERO forzando la apertura de solo lectura con el URI
        # `file:...?mode=ro` — la forma documentada por sqlite3 para esto.
        ruta_absoluta = os.path.abspath(ruta)
        conexion = sqlite3.connect(f"file:{ruta_absoluta}?mode=ro", uri=True)
        conexion.row_factory = sqlite3.Row
        # Un `SELECT` trivial fuerza a SQLite a comprobar que el fichero es una base de datos
        # de verdad (una SQLite corrupta o un fichero cualquiera con extensión .db no falla al
        # `connect()`, solo al primer uso real).
        conexion.execute("SELECT 1")
    except sqlite3.Error as exc:
        raise OrigenNodeInvalido(
            f"'{ruta}' no se puede leer como una base de datos SQLite: {exc}"
        ) from exc

    tablas_presentes = {
        fila["name"]
        for fila in conexion.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    faltan = [tabla for tabla in TABLAS_REQUERIDAS if tabla not in tablas_presentes]
    if faltan:
        conexion.close()
        raise OrigenNodeInvalido(
            f"A '{ruta}' le falta la tabla {faltan[0]}."
            if len(faltan) == 1
            else f"A '{ruta}' le faltan las tablas: {', '.join(faltan)}."
        )

    return conexion


def productos_despensa(conexion):
    """Las filas de `productos_stock`, tal cual, como diccionarios. Ni una columna de más:
    esta tabla no tiene ningún dato de identidad ni de Strava, así que se lee entera."""
    cursor = conexion.execute(
        "SELECT nombre, cantidad, unidad, categoria FROM productos_stock ORDER BY id"
    )
    return [dict(fila) for fila in cursor.fetchall()]


def entrenos(conexion):
    """
    Las filas de `entrenos`, tal cual. Se leen TODAS, sin filtrar por `origen` ('manual' o
    'strava'): el contrato de la unidad (R4, "Qué") promete que los 16 entrenos llegan, sin
    excepción por cómo se apuntaron en Node — "Nada de Strava" (Fuera de alcance) se refiere a
    la tabla `strava_cuentas` (los tokens OAuth), nunca leída por este módulo, no a los
    entrenos que ya están en la app Node sea cual sea su origen. `strava_id` NO se lee: el
    modelo `entrenos.models.Entreno` de Django no tiene ningún campo para guardarlo (está
    "preparado" para cuando `conectar-strava` exista, ver su docstring), así que no hay dónde
    ponerlo ni falta que hace para esta unidad.

    Bug 033 — `miembro_id` SÍ se lee (antes no): es lo único que distingue un entreno del
    titular (`NULL`) de uno de otro miembro de la casa (un id). Es un entero suelto, no la fila
    de `miembros_hogar` — el comando (`importacion/miembros.py`) es quien lo traduce a una
    `Persona`, nunca este módulo (que sigue sin tocar `miembros_hogar`, "Fuera de alcance")."""
    cursor = conexion.execute(
        "SELECT fecha, tipo, intensidad, duracion_min, calorias, miembro_id FROM entrenos ORDER BY id"
    )
    return [dict(fila) for fila in cursor.fetchall()]


def recetas(conexion):
    """Las filas de `recetas`, tal cual (nombre, raciones, tipo_comida, ingredientes en JSON
    de texto, preparación literal)."""
    cursor = conexion.execute(
        "SELECT nombre, raciones_base, tipo_comida, ingredientes, preparacion "
        "FROM recetas ORDER BY id"
    )
    return [dict(fila) for fila in cursor.fetchall()]


def pesadas(conexion):
    """Las filas de `pesos`, tal cual (fecha, peso, grasa y cintura opcionales).

    Bug 033 — `miembro_id` SÍ se lee (antes no, y este docstring lo prometía: "esta unidad
    cuelga TODO de la única cuenta que se le indica al comando" dejó de ser cierto el día que
    `hogares.Persona` pudo representar a alguien más de la casa, unidad 023/024). Sigue siendo
    un entero suelto, nunca la fila de `miembros_hogar` (identidad, fuera de alcance) — la
    traducción a `Persona` vive en `importacion/miembros.py`, no aquí."""
    cursor = conexion.execute(
        "SELECT fecha, peso_kg, grasa_pct, cintura_cm, miembro_id FROM pesos ORDER BY id"
    )
    return [dict(fila) for fila in cursor.fetchall()]
