"""
Bug 033 — la traducción de un `miembro_id` de Node (un entero suelto en `entrenos`/`pesos`,
`NULL` = titular) a la `Persona` de KCalibra de la que cuelga esa fila. Comparten este módulo
`importar_datos_node.py` (la importación) y `mover_filas_de_miembro.py` (la corrección de las
filas que ya se importaron mal, antes de que existiera esta traducción).

## Por qué un parámetro explícito, y no emparejar por nombre

La decisión se midió, no se razonó a priori (ver la sección 4 de la ficha del bug): emparejar
`miembros_hogar.nombre` (Node) con `Persona.nombre` (Django) funciona hoy porque los dos
"Euridice" coinciden, pero `Persona.nombre` no tiene ninguna restricción de unicidad — se
comprobó que basta una segunda persona con el mismo nombre en la misma casa para que la
búsqueda deje de tener una única respuesta, y de ahí solo hay dos salidas: fallar (dejar de ser
"lo cómodo") o elegir a ciegas (colgar una fila de quien no es: este mismo bug, otra vez). Por
eso la traducción la declara la persona que ejecuta el comando, con `--miembro-node
<id-de-node>:<correo>` (repetible, uno por cada miembro de la casa que Node distingue del
titular) — y si aparece un `miembro_id` sin declarar, el comando revienta ANTES de escribir
nada, diciendo cuál falta. Ni titular por defecto, ni descarte callado: la ficha del bug lo
pide explícitamente.

## Por qué la persona de destino tiene que ser de la MISMA casa

`--cuenta` ya fija el hogar de esta importación/corrección (R6, "sin salirse del hogar"). Un
`--miembro-node` que apuntara a una persona de OTRA casa colaría un entreno o una pesada fuera
del hogar del titular — el mismo tipo de fuga que R6 ya prohíbe para el resto del comando, así
que se comprueba aquí igual que se comprobaría en cualquier otra puerta de la app.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from hogares.models import Persona, persona_de

Usuario = get_user_model()


def resolver_mapa_miembros(valores, hogar):
    """
    `--miembro-node id:destino` (repetible) a `{id_de_node: Persona}`. `destino` admite DOS
    formas, para cubrir los dos tipos de miembro de una casa que la app ya distingue (unidad
    024): un CORREO, resuelto exactamente igual que `--cuenta` (`persona_de`, unidad 023), para
    quien tiene cuenta propia; o el ID NUMÉRICO de una `Persona` que ya existe, para quien no la
    tiene (una "persona a cargo", dada de alta por su responsable —
    `hogares/views.py:dar_de_alta_persona_a_cargo`). Se distinguen mirando si `destino` es un
    número: nunca hay ambigüedad porque un correo de verdad no lo es. Cualquier problema
    —formato, id de Node que no es un número, cuenta o Persona que no existen, persona de OTRA
    casa, el mismo `miembro_id` de Node declarado dos veces— revienta con `CommandError` en
    cristiano, antes de tocar nada (se llama siempre ANTES de abrir la transacción de escritura).
    """
    mapa = {}
    for valor in valores:
        if ":" not in valor:
            raise CommandError(
                f"--miembro-node '{valor}' no tiene el formato <id-de-node>:<correo-o-id-de-persona>."
            )
        id_texto, destino_texto = valor.split(":", 1)
        id_texto = id_texto.strip()
        destino_texto = destino_texto.strip()
        try:
            miembro_id = int(id_texto)
        except ValueError:
            raise CommandError(
                f"--miembro-node '{valor}': '{id_texto}' no es un id de Node válido (un número)."
            ) from None

        persona_miembro = _resolver_persona_destino(valor, destino_texto)
        if persona_miembro.hogar_id != hogar.id:
            raise CommandError(
                f"--miembro-node '{valor}': no es una persona de la misma casa que --cuenta. "
                "No se ha tocado nada."
            )
        if miembro_id in mapa:
            raise CommandError(
                f"--miembro-node repite el id de Node {miembro_id} más de una vez."
            )
        mapa[miembro_id] = persona_miembro
    return mapa


def _resolver_persona_destino(valor_completo, destino_texto):
    """La mitad de `--miembro-node` tras los ':'. Un número es el id de una `Persona` que ya
    existe; cualquier otra cosa es un correo, resuelto como `--cuenta`. La comprobación de
    hogar la hace quien llama (`resolver_mapa_miembros`): aquí solo se resuelve QUIÉN es, no SI
    es de la casa correcta."""
    if destino_texto.isdigit():
        persona_miembro = Persona.objects.filter(id=int(destino_texto)).first()
        if persona_miembro is None:
            raise CommandError(
                f"--miembro-node '{valor_completo}': no existe ninguna Persona con id "
                f"{destino_texto}."
            )
        return persona_miembro

    usuario = Usuario.objects.filter(email__iexact=destino_texto).first()
    if usuario is None:
        raise CommandError(
            f"--miembro-node '{valor_completo}': no existe ninguna cuenta con el correo "
            f"'{destino_texto}'."
        )
    persona_miembro = persona_de(usuario)
    if persona_miembro is None:
        raise CommandError(
            f"--miembro-node '{valor_completo}': la cuenta '{destino_texto}' no tiene persona."
        )
    return persona_miembro


def persona_de_fila(fila, persona_titular, mapa_miembros):
    """A qué `Persona` cuelga esta fila de Node: el titular si `miembro_id` es `NULL` (la
    cuenta que se le indicó a `--cuenta`), o la persona que `--miembro-node` declaró para ese
    id. Se asume que `miembros_sin_mapear()` ya se comprobó ANTES de llamar aquí (si no, un
    `miembro_id` sin declarar revienta con `KeyError` en vez de con un mensaje en cristiano —
    por diseño no debería llegar a pasar: es la comprobación previa la que existe para eso)."""
    miembro_id = fila["miembro_id"]
    if miembro_id is None:
        return persona_titular
    return mapa_miembros[miembro_id]


def miembros_sin_mapear(conexion, mapa_miembros):
    """
    Recorre TODAS las filas de `entrenos` y `pesos` (import tardío de `origen`, para no crear
    un ciclo con `origen.py`) y devuelve, ordenados, los `miembro_id` que aparecen en Node y NO
    tienen correspondencia declarada con `--miembro-node`. Lista vacía = todo declarado.

    Se recorre TODO antes de fallar (R7 generalizado: el comando dice de una vez qué falta, no
    revienta con el primero y deja que la persona lo repita id a id) y esto se llama SIEMPRE
    ANTES de abrir la transacción de escritura — la fila con un `miembro_id` sin declarar no
    llega nunca a `apuntar_entreno` ni a `MedicionPeso.objects.create`.
    """
    from . import origen  # tardío: origen.py no necesita saber nada de este módulo

    vistos = set()
    for fila in origen.entrenos(conexion):
        miembro_id = fila["miembro_id"]
        if miembro_id is not None and miembro_id not in mapa_miembros:
            vistos.add(miembro_id)
    for fila in origen.pesadas(conexion):
        miembro_id = fila["miembro_id"]
        if miembro_id is not None and miembro_id not in mapa_miembros:
            vistos.add(miembro_id)
    return sorted(vistos)
