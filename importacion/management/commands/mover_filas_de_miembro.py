"""
`python manage.py mover_filas_de_miembro <ruta-a-la-sqlite-de-node> --cuenta <correo>
--miembro-node <id-de-node>:<correo-o-id-de-persona> [...] [--dry-run]`

Bug 033, decisión 2 (RESUELTA, ficha del bug, sección 4): las filas de `entrenos`/`pesos` que
se importaron ANTES de que `importar_datos_node` supiera traducir `miembro_id` colgaban TODAS
del titular, sin importar de quién fueran de verdad (el bug). Este comando las MUEVE a la
`Persona` que les corresponde — no las borra y reimporta: las dos opciones dan el mismo
resultado final, medido en la ficha, y "borrar y reimportar" pierde el `id`/`created_at`
original sin ganar nada a cambio. Se ejecuta DESPUÉS de que el arreglo de la decisión 1 esté
mergeado, nunca antes (medido en la misma sección: reejecutar el comando VIEJO tras mover
duplica, porque su idempotencia miraba `persona=persona` sin saber de miembros).

## Por qué es un comando, con su --dry-run y su test — y no un UPDATE tecleado a mano

La medición que decidió esta corrección fue, literalmente, dos sentencias de `psql` contra una
copia. Tal cual, contra la base real (la única vez que este movimiento se ejecuta de verdad) es
un cambio sin ensayo, sin test que lo contrapruebe y sin nada que lo repita si algo sale mal a
medio camino. Choca además con la doctrina que la propia 022 se puso: pasar por mecanismos
verificables, no por `create()`/`UPDATE` sueltos. Un comando de gestión, con `--dry-run` y su
propia suite, cuesta poco más que el `UPDATE` y lo vuelve repetible, ensayable y verificable —
exactamente lo que una corrección que se ejecuta UNA sola vez, contra datos reales, más falta
le hace.

## Cómo identifica qué mover — la MISMA clave que ya usa la importación, nunca `id` a pelo

Para cada fila de Node con un `miembro_id` mapeado (no `NULL`), calcula su tupla de identidad —
la misma que `importar_datos_node` ya usa para reconocer una fila: `mapeo.clave_entreno` para
entrenos (fecha, deporte, intensidad, minutos, calorías); fecha+peso_kg+grasa_pct+cintura_cm
para pesadas (el índice único de Node es por fecha, pero se compara la fila COMPLETA: una
coincidencia de fecha con datos distintos no es la misma fila, es una pesada de verdad del
titular ese mismo día que no hay que tocar) — y busca, bajo el TITULAR, una fila Django con esa
tupla exacta. Nunca por `id` de Django: un `id` no significa nada en Node, y guiarse por él
sería inventar una correspondencia que nadie declaró.

## No inventa: idempotente, y para en vez de aproximar

Antes de mover cada fila, mira DOS sitios: bajo el titular (de donde tendría que desaparecer) y
bajo la persona de destino (donde tendría que estar). Solo hay dos estados sanos:

- **1 bajo el titular, 0 bajo el destino** → todavía no se movió: la mueve (o dice que la
  movería, en `--dry-run`).
- **0 bajo el titular, 1 bajo el destino** → ya se movió en una pasada anterior: no hace nada.
  Es lo que hace que la SEGUNDA pasada no mueva nada (idempotente, como pide el contrato).

Cualquier otra combinación (0 y 0: la fila no está en ningún sitio; 1 y 1: está duplicada —
exactamente el riesgo medido de reejecutar el comando viejo tras mover; o más de una en
cualquiera de los dos lados) es una anomalía que el comando NO intenta adivinar cómo resolver:
para con un `CommandError` que dice cuál fila y qué encontró, y no mueve NADA de esta pasada
(la `transaction.atomic()` deshace lo que ya se hubiera movido en las filas anteriores de la
misma ejecución) — "no inventa" también significa no dejar una corrección a medias.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from entrenos.models import Entreno
from hogares.models import persona_de
from perfiles.models import MedicionPeso

from ... import mapeo, miembros, origen

Usuario = get_user_model()

_CAMPOS_CLAVE_ENTRENO = ("fecha", "deporte", "intensidad", "minutos", "calorias")


class _CanceladoPorDryRun(Exception):
    """Misma señal y mismo motivo que en `importar_datos_node.py`: `--dry-run` hace el trabajo
    de verdad (para que el resumen sea el resumen real) y fuerza el deshacer al final."""

    def __init__(self, resumen):
        super().__init__("dry-run: deshaciendo la transacción a propósito")
        self.resumen = resumen


class Command(BaseCommand):
    help = (
        "Bug 033 — mueve los entrenos y las pesadas que se importaron mal (colgados del "
        "titular) a la Persona a la que de verdad pertenecen. Repetible: la segunda vez no "
        "mueve nada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "ruta_db",
            help="Ruta a la SQLite de Node — la MISMA que se usó para importar estas filas.",
        )
        parser.add_argument(
            "--cuenta",
            required=True,
            metavar="CORREO",
            help="Correo de la cuenta titular: de la que las filas cuelgan hoy, mal.",
        )
        parser.add_argument(
            "--miembro-node",
            action="append",
            default=[],
            metavar="ID:CORREO-O-ID-DE-PERSONA",
            help=(
                "Igual formato que en importar_datos_node: '<id-de-node>:<correo>' o "
                "'<id-de-node>:<id-de-persona>'. Repetible, uno por cada miembro cuyas filas "
                "hay que mover. Obligatorio al menos uno: sin ninguno no hay nada que mover."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Enseña qué movería, fila a fila resumida por tabla, sin mover nada.",
        )

    def handle(self, *args, **options):
        ruta_db = options["ruta_db"]
        correo = options["cuenta"]
        dry_run = options["dry_run"]

        try:
            conexion = origen.abrir(ruta_db)
        except origen.OrigenNodeInvalido as exc:
            raise CommandError(str(exc)) from exc

        try:
            usuario = Usuario.objects.filter(email__iexact=correo).first()
            if usuario is None:
                raise CommandError(
                    f"No existe ninguna cuenta con el correo '{correo}'. No se ha tocado nada."
                )
            persona_titular = persona_de(usuario)
            hogar = persona_titular.hogar if persona_titular is not None else None
            if hogar is None:
                raise CommandError(
                    f"La cuenta '{correo}' todavía no tiene hogar. No se ha tocado nada."
                )

            mapa_miembros = miembros.resolver_mapa_miembros(options["miembro_node"], hogar)
            if not mapa_miembros:
                raise CommandError(
                    "No se ha declarado ningún --miembro-node: no hay nada que mover. "
                    "No se ha tocado nada."
                )
            faltan = miembros.miembros_sin_mapear(conexion, mapa_miembros)
            if faltan:
                lista = ", ".join(str(m) for m in faltan)
                plural = "s" if len(faltan) > 1 else ""
                raise CommandError(
                    f"La base de Node trae fila{plural} con miembro_id {lista} sin "
                    "correspondencia declarada. No se ha tocado nada. Añade "
                    "--miembro-node <id-de-node>:<correo-o-id-de-persona> por cada uno."
                )

            try:
                with transaction.atomic():
                    resumen = _mover_todo(conexion, persona_titular, mapa_miembros)
                    if dry_run:
                        raise _CanceladoPorDryRun(resumen)
            except _CanceladoPorDryRun as cancelado:
                resumen = cancelado.resumen
        finally:
            conexion.close()

        _imprimir_resumen(self.stdout, resumen, dry_run)


def _mover_todo(conexion, persona_titular, mapa_miembros):
    return {
        "entrenos": _mover_entrenos(conexion, persona_titular, mapa_miembros),
        "pesadas": _mover_pesadas(conexion, persona_titular, mapa_miembros),
    }


def _decidir(en_origen, en_destino):
    """Ver el docstring del módulo, 'No inventa'. Solo dos combinaciones son sanas; cualquier
    otra es una anomalía que quien llama tiene que parar a reportar, nunca resolver a ciegas."""
    if en_origen == 1 and en_destino == 0:
        return "mover"
    if en_origen == 0 and en_destino == 1:
        return "ya_movida"
    return "anomalia"


def _mover_entrenos(conexion, persona_titular, mapa_miembros):
    movidas = 0
    ya_movidas = 0
    for fila in origen.entrenos(conexion):
        miembro_id = fila["miembro_id"]
        if miembro_id is None:
            continue  # es del titular: nunca hubo nada mal colgado que mover
        persona_destino = mapa_miembros[miembro_id]
        datos = mapeo.datos_entreno(fila)
        clave = dict(zip(_CAMPOS_CLAVE_ENTRENO, mapeo.clave_entreno(datos)))

        en_origen = Entreno.objects.filter(persona=persona_titular, **clave).count()
        en_destino = Entreno.objects.filter(persona=persona_destino, **clave).count()
        decision = _decidir(en_origen, en_destino)
        if decision == "mover":
            Entreno.objects.filter(persona=persona_titular, **clave).update(persona=persona_destino)
            movidas += 1
        elif decision == "ya_movida":
            ya_movidas += 1
        else:
            raise CommandError(
                f"Un entreno de Node (miembro_id={miembro_id}, {clave}) no está donde se "
                f"esperaba: {en_origen} bajo el titular y {en_destino} bajo el destino (se "
                "esperaba 1 y 0, o 0 y 1). No se ha movido nada de esta pasada."
            )
    return {"movidas": movidas, "ya_movidas": ya_movidas}


def _mover_pesadas(conexion, persona_titular, mapa_miembros):
    movidas = 0
    ya_movidas = 0
    for fila in origen.pesadas(conexion):
        miembro_id = fila["miembro_id"]
        if miembro_id is None:
            continue
        persona_destino = mapa_miembros[miembro_id]
        datos = mapeo.datos_pesada(fila)
        clave = {
            "fecha": datos["fecha"],
            "peso_kg": datos["peso_kg"],
            "grasa_pct": datos["grasa_pct"],
            "cintura_cm": datos["cintura_cm"],
        }

        en_origen = MedicionPeso.objects.filter(persona=persona_titular, **clave).count()
        en_destino = MedicionPeso.objects.filter(persona=persona_destino, **clave).count()
        decision = _decidir(en_origen, en_destino)
        if decision == "mover":
            MedicionPeso.objects.filter(persona=persona_titular, **clave).update(persona=persona_destino)
            movidas += 1
        elif decision == "ya_movida":
            ya_movidas += 1
        else:
            raise CommandError(
                f"Una pesada de Node (miembro_id={miembro_id}, {clave}) no está donde se "
                f"esperaba: {en_origen} bajo el titular y {en_destino} bajo el destino (se "
                "esperaba 1 y 0, o 0 y 1). No se ha movido nada de esta pasada."
            )
    return {"movidas": movidas, "ya_movidas": ya_movidas}


def _imprimir_resumen(stdout, resumen, dry_run):
    if dry_run:
        stdout.write("[DRY-RUN] Nada de lo siguiente se ha movido de verdad:")
    for clave, etiqueta in (("entrenos", "Entrenos"), ("pesadas", "Pesadas")):
        datos = resumen[clave]
        stdout.write(
            f"{etiqueta}: {datos['movidas']} movida(s), {datos['ya_movidas']} ya estaba(n) "
            "movida(s)."
        )
    if dry_run:
        stdout.write("[DRY-RUN] Fin. No se ha movido ni una fila.")
