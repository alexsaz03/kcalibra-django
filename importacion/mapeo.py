"""
El mapeo de una fila de Node a los datos que espera cada puerta de la app nueva (`despensa.
logica.anadir_producto`, `entrenos.logica.apuntar_entreno`, `recetas.logica.crear_receta`, y
`perfiles.models.MedicionPeso` directamente — ver el porqué en el docstring del comando).
Funciones PURAS a propósito (bias.md §3, "Cómo" de la especificación): reciben datos ya leídos
(no tocan la base de datos ni abren la SQLite de Node) y devuelven datos, para poder probarlas
sin base de datos y sin la base real — igual que `servicios/metabolismo.py` o `despensa.logica.
convertir_a_canonica`, del que este módulo importa directamente (nunca reimplementa la
conversión a unidad canónica: sería resucitar exactamente lo que la unidad 017 cerró).

## Las cuatro exclusiones deliberadas, y por qué viven en `origen.py`, no aquí

Este módulo nunca ve `usuarios`, `miembros_hogar`, `strava_cuentas` ni `memoria`: `origen.py`
jamás las consulta ("Fuera de alcance" de la especificación), así que ninguna fila de esas
tablas llega hasta aquí para que este módulo tenga que acordarse de descartarla. La frontera
está en el sitio que la lee, no en el que la traduce — así una fila que no debía salir de Node
no depende de que este fichero la filtre bien.

## Las claves de idempotencia (R2), UNA por tabla, elegidas y escritas aquí

La regla de "esto ya está" no es la misma para las cuatro tablas — depende de qué identifica a
una fila SIN un campo propio que lo diga (Node no numera "esta fila viene de tal importación"):

- **Despensa**: `(hogar, nombre_normalizado, unidad_canónica)` — el MISMO trío que ya vive en el
  `UniqueConstraint` de `ProductoDespensa` desde la unidad 017 (`una_linea_por_hogar_producto_y_
  unidad`). No hace falta inventar nada: dos filas de Node del mismo producto en unidades de la
  misma familia (kg y g) tienen que FUNDIRSE en la MISMA pasada (R1), así que la clave de
  idempotencia entre pasadas distintas es la clave de fusión dentro de una pasada — son la misma
  pregunta ("¿esta línea ya existe?") hecha en dos momentos distintos. Ver `clave_producto()`.
- **Entrenos**: la tupla completa `(fecha, deporte, intensidad, minutos, calorías)`. El "Cómo" de
  la especificación sugiere "por fecha + tipo", pero **se comprobó contra la base real** (no
  hipotéticamente) que esa clave más corta pierde datos: hay tres días con MÁS de un entreno de
  la misma fecha y el mismo deporte (dos o tres carreras el mismo día, con minutos y calorías
  distintos). Con "fecha + tipo" como clave, la SEGUNDA carrera del mismo día se leería como "ya
  existe" en la PRIMERA pasada (porque la primera ya se acaba de crear en esa misma pasada) y se
  perdería en silencio — justo lo que R4 prohíbe ("los 16 entrenos... llegan"). La tupla
  completa sí es única en los 16 (comprobado: `COUNT(*) == COUNT(DISTINCT ...)`) y sigue
  cumpliendo R2 (una repetición exacta de una fila ya importada se reconoce como "ya estaba").
  Ver `clave_entreno()`.
- **Pesadas**: `(persona, fecha)` — es LITERALMENTE la restricción `una_medicion_por_persona_y_
  dia` que la unidad 006 puso en la base de datos. Y no es solo la clave de idempotencia: es la
  MISMA pregunta que R4 exige responder para el caso límite ("si choca, se salta y lo dice"), así
  que una sola comprobación sirve para las dos cosas a la vez.
- **Recetas**: nombre normalizado (`strip().lower()`, la misma normalización que `despensa.
  models.ProductoDespensa.nombre_normalizado`) por hogar. `Receta` no trae un campo normalizado
  propio (no lo necesitaba: no tiene ninguna restricción de unicidad, unidad 021), así que el
  comando recalcula la comparación con `nombre_normalizado()` de aquí, en vez de añadir un campo
  al modelo (tocar `recetas/` está fuera de lo que esta unidad posee).
"""

import json
from decimal import Decimal, InvalidOperation

from despensa.logica import convertir_a_canonica
from despensa.models import CATEGORIAS as CATEGORIAS_DESPENSA
from despensa.models import UNIDADES as UNIDADES_DESPENSA
from entrenos.models import DEPORTES, INTENSIDADES
from planes.models import MOMENTOS_DEL_DIA

_UNIDADES_VALIDAS = {clave for clave, _ in UNIDADES_DESPENSA}
_CATEGORIAS_VALIDAS = {clave for clave, _ in CATEGORIAS_DESPENSA}
_DEPORTES_VALIDOS = {clave for clave, _ in DEPORTES}
_MOMENTOS_VALIDOS = {clave for clave, _ in MOMENTOS_DEL_DIA}

# G-71 en `entrenos/models.py`: las intensidades de Node ("baja/media/alta") NO son las mismas
# palabras que las del plano que usa Django ("suave/media/fuerte") — la especificación de la
# unidad 011 ya dejó dicho que el plano manda sobre Node en esto. Traducción 1:1, sin invención:
# ninguna intensidad de Node se queda sin una intensidad de Django a la que ir.
_TRADUCCION_INTENSIDAD = {"baja": "suave", "media": "media", "alta": "fuerte"}


class DatosNodeInvalidos(Exception):
    """Una fila de Node trae un valor que no encaja en ningún catálogo de la app nueva (una
    unidad, una categoría, un deporte, una intensidad que no existen). Se levanta con un
    mensaje en cristiano; el comando la convierte en `CommandError` (R7, generalizado a
    cualquier dato de origen que no se pueda traducir, no solo a la ruta que falta)."""


def _decimal(valor):
    """
    `cantidad`/`peso_kg`/etc. llegan de `sqlite3` como `float` (SQLite los guarda como `REAL`,
    y Python los lee así). Pasar un `float` directamente a `Decimal(...)` arrastra el error de
    coma flotante binaria (`Decimal(0.249)` da un número con quince decimales de ruido, no
    0.249). `Decimal(str(valor))` usa la representación más corta que Python ya calculó para
    ESE float (la que se ve al hacer `print`), que es la que de verdad escribió quien tecleó el
    dato en Node — el mismo principio que aplican los formularios de esta app al leer un
    `<input>` (nunca pasan por `float`, ver `recetas/logica.py:validar_ingredientes`).
    """
    return Decimal(str(valor))


def clave_producto(nombre, unidad):
    """
    La identidad de una línea de despensa DESPUÉS de convertir a la unidad canónica de su
    familia (R1/unidad 017): `(nombre_normalizado, unidad_canónica)`. Se usa DOS veces con el
    mismo sentido — dentro de una pasada, es lo que hace que "arroz 1 kg" y "arroz 500 g" se
    reconozcan como la misma línea (R1); entre pasadas, es lo que hace que la segunda ejecución
    reconozca "esto ya está" (R2). `nombre` se recorta pero NO se convierte todavía: la
    conversión de cantidad la hace `datos_producto_despensa`; aquí solo hace falta saber a qué
    unidad canónica iría, para poder mirar si ya existe.
    """
    if unidad not in _UNIDADES_VALIDAS:
        raise DatosNodeInvalidos(
            f"La despensa de Node trae la unidad '{unidad}', que no existe en la app nueva."
        )
    _, unidad_canonica = convertir_a_canonica(Decimal(0), unidad)
    return nombre.strip().lower(), unidad_canonica


def datos_producto_despensa(fila):
    """
    A partir de una fila de `productos_stock` de Node, los `datos` que espera `despensa.logica.
    anadir_producto(hogar, datos)`: nombre, cantidad (todavía SIN convertir — la conversión a
    canónica la hace `anadir_producto` por dentro, es su trabajo, R1), unidad y categoría.
    Valida unidad y categoría contra los catálogos de la app nueva (`despensa.models.UNIDADES`/
    `CATEGORIAS`): las tres categorías y las ocho unidades que Node usa hoy coinciden con los de
    Django (medido contra la base real), pero si algún día no coincidiera, es mejor un error en
    cristiano aquí que una fila a medio guardar o un `ValidationError` críptico dentro del
    formulario que nunca se llegó a usar.
    """
    nombre = (fila["nombre"] or "").strip()
    if not nombre:
        raise DatosNodeInvalidos("La despensa de Node trae un producto sin nombre.")
    unidad = fila["unidad"]
    categoria = fila["categoria"]
    if unidad not in _UNIDADES_VALIDAS:
        raise DatosNodeInvalidos(
            f"La despensa de Node trae la unidad '{unidad}', que no existe en la app nueva."
        )
    if categoria not in _CATEGORIAS_VALIDAS:
        raise DatosNodeInvalidos(
            f"La despensa de Node trae la categoría '{categoria}', que no existe en la app nueva."
        )
    return {
        "nombre": nombre,
        "cantidad": _decimal(fila["cantidad"]),
        "unidad": unidad,
        "categoria": categoria,
    }


def traducir_intensidad(intensidad_node):
    """G-71: 'baja'/'media'/'alta' de Node -> 'suave'/'media'/'fuerte' del plano."""
    if intensidad_node not in _TRADUCCION_INTENSIDAD:
        raise DatosNodeInvalidos(
            f"Los entrenos de Node traen la intensidad '{intensidad_node}', que no se sabe "
            "traducir (se esperaba 'baja', 'media' o 'alta')."
        )
    return _TRADUCCION_INTENSIDAD[intensidad_node]


def clave_entreno(datos):
    """La identidad de un entreno YA TRADUCIDO (ver el porqué de esta clave, y no 'fecha+tipo',
    en el docstring del módulo): la tupla completa de sus valores, sin la `persona` (quien
    llama ya sabe de quién está comparando)."""
    return (datos["fecha"], datos["deporte"], datos["intensidad"], datos["minutos"], datos["calorias"])


def datos_entreno(fila):
    """
    A partir de una fila de `entrenos` de Node, los `datos` que espera `entrenos.logica.
    apuntar_entreno(persona, datos)`: fecha (ya como `date`, no como texto ISO), deporte (el
    'tipo' de Node: las claves coinciden 1:1 con `entrenos.models.DEPORTES`, sin traducir),
    intensidad (traducida, ver `traducir_intensidad`) y minutos. `calorias` SIEMPRE viene
    puesta (Node no permite NULL en esa columna): así `apuntar_entreno` nunca entra en su rama
    de ESTIMAR (`_resolver_calorias`, que necesitaría el peso de la persona) — R4 exige los
    valores intactos, no un recálculo con la fórmula de Django.
    """
    from datetime import date

    deporte = fila["tipo"]
    if deporte not in _DEPORTES_VALIDOS:
        raise DatosNodeInvalidos(
            f"Los entrenos de Node traen el deporte '{deporte}', que no existe en la app nueva."
        )
    return {
        "fecha": date.fromisoformat(fila["fecha"]),
        "deporte": deporte,
        "intensidad": traducir_intensidad(fila["intensidad"]),
        "minutos": int(fila["duracion_min"]),
        "calorias": int(fila["calorias"]),
    }


def datos_pesada(fila):
    """
    A partir de una fila de `pesos` de Node, los datos para crear una `perfiles.models.
    MedicionPeso` (fecha, peso, grasa y cintura opcionales). NO pasa por `perfiles.logica.
    apuntar_medicion`: esa función hace `update_or_create` por (persona, fecha) — la puerta
    correcta para que UNA PERSONA corrija su propia pesada del día, pero PELIGROSA para un
    import repetible, porque SOBRESCRIBIRÍA en silencio una medición que ya estuviera en Django
    (importada antes, o apuntada a mano por la persona) en vez de reconocerla y saltarse la
    fila (R2/R4 piden justo lo segundo). El comando comprueba la colisión ANTES de llamar aquí
    (ver `importar_datos_node.py`) y solo entonces crea directamente — ver hallazgos.md, "la
    puerta que no encajaba".
    """
    from datetime import date

    grasa = fila["grasa_pct"]
    cintura = fila["cintura_cm"]
    return {
        "fecha": date.fromisoformat(fila["fecha"]),
        "peso_kg": _decimal(fila["peso_kg"]),
        "grasa_pct": _decimal(grasa) if grasa is not None else None,
        "cintura_cm": _decimal(cintura) if cintura is not None else None,
    }


def traducir_comidas(tipo_comida_node):
    """
    R5 — el `tipo_comida` de Node (un único valor) a la lista `comidas` de Django. 'cualquiera'
    se traduce a lista VACÍA (R-67: una lista vacía es lo que la app nueva entiende como "vale
    para cualquier comida", ver `recetas.logica.comidas_legibles`); cualquier otro valor válido
    se traduce a una lista de un solo elemento. 'merienda' no existe en Node (R5: "no hay que
    inventarlo") y por tanto nunca puede llegar aquí desde una fila real; si llegara CUALQUIER
    valor que no sea 'cualquiera' ni una de las claves de `planes.models.MOMENTOS_DEL_DIA`, es
    un dato que la app nueva no sabe representar y se declara inválido en vez de guardarlo a
    ciegas.
    """
    if tipo_comida_node == "cualquiera":
        return []
    if tipo_comida_node not in _MOMENTOS_VALIDOS:
        raise DatosNodeInvalidos(
            f"Las recetas de Node traen el tipo de comida '{tipo_comida_node}', que no existe "
            "en la app nueva."
        )
    return [tipo_comida_node]


def nombre_normalizado(nombre):
    """La MISMA normalización que `despensa.models.ProductoDespensa.nombre_normalizado`
    (`strip().lower()`): recortar espacios de sobra e ignorar mayúsculas. `recetas.models.
    Receta` no trae este campo (no lo necesitaba, unidad 021, sin restricción de unicidad), así
    que el comando lo recalcula aquí para poder preguntar "¿ya hay una receta con este nombre?"
    (R2) sin añadir ningún campo a un modelo que esta unidad no posee."""
    return nombre.strip().lower()


def mapear_ingredientes(ingredientes_json_texto):
    """
    El texto JSON de `recetas.ingredientes` de Node (`[{"alimento", "cantidad", "unidad"}, ...]`)
    a la lista de dicts que espera `recetas.logica.crear_receta(hogar, datos, ingredientes)`:
    `{"nombre", "cantidad" (Decimal), "unidad"}` — los mismos tres nombres de clave que ya usa
    `recetas.logica.validar_ingredientes` para las filas que llegan del formulario, así que
    `crear_receta` no necesita saber que estos datos vinieron de una importación y no de una
    persona escribiendo. Las cantidades de un ingrediente NO se convierten a unidad canónica
    (a diferencia de la despensa): `recetas/logica.py` deja dicho que "cada ingrediente se
    guarda TAL CUAL se escribió, en la unidad que eligió la persona" (R1/R5 de la unidad 021).
    """
    try:
        crudos = json.loads(ingredientes_json_texto)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DatosNodeInvalidos(
            f"Una receta de Node trae ingredientes que no son JSON válido: {exc}"
        ) from exc
    if not isinstance(crudos, list) or not crudos:
        raise DatosNodeInvalidos("Una receta de Node no trae ningún ingrediente.")

    ingredientes = []
    for indice, crudo in enumerate(crudos, start=1):
        nombre = (crudo.get("alimento") or "").strip()
        unidad = crudo.get("unidad")
        if not nombre:
            raise DatosNodeInvalidos(f"El ingrediente {indice} de una receta de Node no tiene nombre.")
        if unidad not in _UNIDADES_VALIDAS:
            raise DatosNodeInvalidos(
                f"El ingrediente '{nombre}' trae la unidad '{unidad}', que no existe en la app nueva."
            )
        try:
            cantidad = _decimal(crudo.get("cantidad"))
        except (InvalidOperation, TypeError):
            raise DatosNodeInvalidos(
                f"El ingrediente '{nombre}' trae una cantidad que no es un número."
            ) from None
        if cantidad <= 0:
            raise DatosNodeInvalidos(f"El ingrediente '{nombre}' trae una cantidad que no es mayor que cero.")
        ingredientes.append({"nombre": nombre, "cantidad": cantidad, "unidad": unidad})
    return ingredientes


def datos_receta(fila):
    """A partir de una fila de `recetas` de Node, el par `(datos, ingredientes)` que espera
    `recetas.logica.crear_receta(hogar, datos, ingredientes)`. `preparacion` viaja LITERAL,
    carácter por carácter (R5, Q-120): ni se recorta ni se retoca."""
    nombre = (fila["nombre"] or "").strip()
    if not nombre:
        raise DatosNodeInvalidos("Una receta de Node no tiene nombre.")
    raciones = int(fila["raciones_base"])
    if raciones < 1:
        raise DatosNodeInvalidos(f"La receta '{nombre}' trae {raciones} raciones, y tienen que ser al menos 1.")
    datos = {
        "nombre": nombre,
        "raciones": raciones,
        "comidas": traducir_comidas(fila["tipo_comida"]),
        "preparacion": fila["preparacion"] or "",
    }
    ingredientes = mapear_ingredientes(fila["ingredientes"])
    return datos, ingredientes
