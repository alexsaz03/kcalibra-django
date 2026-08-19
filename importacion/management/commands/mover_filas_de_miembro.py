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

## Por qué NO decide fila a fila, ni siquiera por lote (rondas 1 y 2 de revisión)

**Ronda 1 (H1):** la primera versión decidía cada fila de Node por su cuenta: "¿hay exactamente
1 bajo el titular y 0 bajo el destino? la muevo". El revisor lo reventó así: mover 8 filas de
verdad, borrar UNA desde la app (acción normal), apuntar OTRA fila nueva con la misma tupla
exacta — y la segunda pasada "reconocía" la fila nueva como si fuera la vieja mal colgada y la
movía. Se corrigió agrupando por miembro y tabla: solo actuaba si el LOTE COMPLETO (todas las
filas de ESE miembro en ESA tabla) estaba uniformemente íntegro o uniformemente ya movido.

**Ronda 2 (R1): un lote de UNA fila degenera EXACTAMENTE en la regla vieja.** Y no es teórico:
la pesada del `miembro_id` real en la Node de verdad es, precisamente, un lote de una fila. El
revisor reprodujo el mismo ataque de la ronda 1 pero sobre la pesada (que vive sola en su
lote) y volvió a colarse. La propiedad "todo el lote en el mismo estado" es correcta, pero
"lote" estaba mal recortado: un miembro con datos en dos tablas (8 entrenos + 1 pesada, el caso
real) tiene DOS lotes independientes, y decidir cada tabla por separado deja que la pesada
(el lote débil) decida sola, sin que los 8 entrenos (el lote fuerte, ya migrado) puedan avisar
de que algo no cuadra.

**La propiedad ahora es de TODA LA OPERACIÓN, no del lote:** se juntan las filas candidatas de
TODAS las tablas y TODOS los miembros de esta pasada en una sola lista, y se decide UNA vez:
íntegra (cada candidata, 1 bajo el titular y 0 bajo el destino: se mueven TODAS), ya movida
(cada candidata, 0 y 1: no-op), o mezclada (cualquier otra cosa: para, sin mover nada de nada).
Con esto, el ataque de la ronda 2 SÍ se detecta: los 8 entrenos ya están en "0 y 1" (ya
movidos) mientras la pesada manipulada aparece en "1 y 0" (parece íntegra) — la operación
completa es una MEZCLA de los dos estados, así que para entera, sin mover ni la pesada.

**El límite honesto, no fingido: una operación de UNA sola fila total no gana nada con este
diseño** — con un solo dato no hay con qué corroborar nada, y "toda la operación en el mismo
estado" se reduce, otra vez, a la regla vieja fila a fila. En vez de fingir que la comprobación
protege igual, el comando lo dice: si la operación completa tiene una única fila candidata Y
esa fila resultaría "íntegra" (se movería), el comando SE NIEGA explícitamente en vez de mover
a ciegas (ver el bloque final de `_mover_todo`). Esto es una limitación conocida, no resuelta del
todo por este diseño — cerrarla de verdad necesitaría que una fila importada llevara marcada su
procedencia (una columna, no una tupla de valores), y eso es un cambio de contrato que le toca
decidir al usuario, no a este comando.

## H2 de la ronda 1 — el choque de `(persona, fecha)` en pesadas, detectado, no crudo

`MedicionPeso` tiene una restricción real en la base, `una_medicion_por_persona_y_dia`
`(persona, fecha)` — más corta que la tupla completa que este comando usa para identificar una
fila. Si la persona de destino YA tiene una pesada esa fecha (con otros valores: la suya
propia, apuntada a mano), mover esa fila violaría esa restricción y saldría como un
`IntegrityError` crudo, no como el `CommandError` en cristiano que el resto del comando
promete. Por eso, para cada candidata de pesada que fuera a moverse, se comprueba también si el
destino ya tiene ALGO esa fecha (choque de `(persona, fecha)`, no de la tupla completa) — si lo
tiene, la operación entera se trata como mezclada: no se intenta el `UPDATE` que iba a reventar.

## H4/PII de la ronda 1 — qué se imprime de una pesada

Los mensajes de error de pesadas nunca imprimen `peso_kg`/`grasa_pct`/`cintura_cm` (datos de
salud de una persona real) — solo la fecha, que basta para que quien lee el aviso localice la
fila en la app. Los de entrenos sí llevan la tupla completa: no son datos de salud y localizar
la fila exacta (puede haber varias el mismo día) lo necesita.

## Cómo identifica qué mover — la MISMA clave que ya usa la importación, nunca `id` a pelo

Para cada fila de Node con un `miembro_id` mapeado (no `NULL`), calcula su tupla de identidad —
la misma que `importar_datos_node` ya usa para reconocer una fila: `mapeo.clave_entreno` para
entrenos; fecha+peso_kg+grasa_pct+cintura_cm para pesadas — y busca, bajo el TITULAR y bajo el
DESTINO, cuántas filas Django tienen esa tupla exacta. Nunca por `id` de Django.

## Todo o nada: sin `--dry-run` real no hay ensayo posible

Todo el trabajo vive en UNA `transaction.atomic()`, igual que en `importar_datos_node.py`.
Cualquier mezcla revienta con `CommandError` y deshace TODO lo que esta pasada ya hubiera
movido — nunca deja una corrección a medias.
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
        "titular) a la Persona a la que de verdad pertenecen. Solo actúa cuando TODA la "
        "pasada (todas las tablas, todos los miembros) está íntegra (todo mal) o ya "
        "corregida (todo bien); ante cualquier mezcla, para y no toca nada. Repetible: la "
        "segunda vez no mueve nada."
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
            help="Enseña qué movería, resumido por tabla, sin mover nada.",
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


def _agrupar_por_miembro(filas):
    """Filas de origen (con `miembro_id`), agrupadas por `miembro_id`, EXCLUYENDO las del
    titular (`miembro_id is None`: nunca hay nada que mover para esas). R3 de la revisión
    (ronda 2): esta línea es la que hace que las filas del titular NUNCA lleguen a
    `mapa_miembros[miembro_id]` con `miembro_id=None` (que reventaría con `KeyError`, crudo,
    sobre la Node real — que SIEMPRE mezcla filas del titular y de miembros en la misma tabla).
    Tiene su propia red (`test_R3_...`), contraprobada con esta misma mutación."""
    agrupadas = {}
    for fila in filas:
        miembro_id = fila["miembro_id"]
        if miembro_id is None:
            continue
        agrupadas.setdefault(miembro_id, []).append(fila)
    return agrupadas


def _clave_entreno(fila):
    datos = mapeo.datos_entreno(fila)
    return dict(zip(_CAMPOS_CLAVE_ENTRENO, mapeo.clave_entreno(datos)))


def _describir_clave_entreno(clave):
    return (
        f"{clave['fecha']} {clave['deporte']}/{clave['intensidad']}/{clave['minutos']}min/"
        f"{clave['calorias']}kcal"
    )


def _clave_pesada(fila):
    datos = mapeo.datos_pesada(fila)
    return {
        "fecha": datos["fecha"],
        "peso_kg": datos["peso_kg"],
        "grasa_pct": datos["grasa_pct"],
        "cintura_cm": datos["cintura_cm"],
    }


def _describir_clave_pesada(clave):
    # H4/PII de la revisión (ronda 1): NUNCA el peso, la grasa ni la cintura — solo la fecha,
    # que basta para localizar la fila en la app.
    return str(clave["fecha"])


def _hay_colision_pesada(clave, persona_destino):
    """H2 de la revisión (ronda 1): `MedicionPeso` exige `(persona, fecha)` único en la base —
    más corto que la tupla completa que usa este comando para identificar una fila. Si el
    destino YA tiene una medición esa fecha (con OTROS valores: la suya propia), moverla
    revienta con `IntegrityError`. Se comprueba ANTES de intentarlo, por `(persona, fecha)` sin
    más — la misma restricción que la base va a hacer cumplir de todas formas."""
    return MedicionPeso.objects.filter(persona=persona_destino, fecha=clave["fecha"]).exists()


def _candidatas(*, filas, mapa_miembros, persona_titular, modelo, calcular_clave, etiqueta,
                 describir_clave, hay_colision=None):
    """Recorre las filas de UNA tabla (agrupadas por miembro) y, para cada una, calcula su
    clave y sus recuentos (bajo el titular, bajo el destino) — sin decidir nada todavía: R1 de
    la revisión (ronda 2) exige que la decisión sea de TODA la operación, no de esta tabla ni
    de este miembro por separado, así que aquí solo se reúnen los datos."""
    candidatas = []
    for miembro_id, filas_miembro in _agrupar_por_miembro(filas).items():
        persona_destino = mapa_miembros[miembro_id]
        for fila in filas_miembro:
            clave = calcular_clave(fila)
            en_origen = modelo.objects.filter(persona=persona_titular, **clave).count()
            en_destino = modelo.objects.filter(persona=persona_destino, **clave).count()
            # H2: solo tiene sentido como candidata a moverse (en_destino == 0); si ya es
            # >= 1, lo que `hay_colision` encontraría es la MISMA fila del estado "ya movido"
            # — comprobarlo ahí sería un falso positivo contra la propia idempotencia.
            colision = bool(
                hay_colision and en_destino == 0 and hay_colision(clave, persona_destino)
            )
            candidatas.append({
                "modelo": modelo,
                "clave": clave,
                "persona_destino": persona_destino,
                "miembro_id": miembro_id,
                "etiqueta": etiqueta,
                "descripcion": describir_clave(clave),
                "triple": (en_origen, en_destino, colision),
            })
    return candidatas


def _estado_operacion(triples):
    """`triples`: una `(en_origen, en_destino, colision)` por CADA candidata de TODA la
    operación (todas las tablas, todos los miembros de esta pasada) — R1 de la revisión (ronda
    2: "sube el todo o nada de lote a operación"). Devuelve 'integra', 'ya_movida' o
    'mezclada'. Con una lista vacía (no hay ningún `--miembro-node` con filas en Node) no hay
    nada que decidir; quien llama no debería invocar esto en ese caso."""
    if any(colision for _, _, colision in triples):
        return "mezclada"
    if all(en_origen == 1 and en_destino == 0 for en_origen, en_destino, _ in triples):
        return "integra"
    if all(en_origen == 0 and en_destino == 1 for en_origen, en_destino, _ in triples):
        return "ya_movida"
    return "mezclada"


def _mover_todo(conexion, persona_titular, mapa_miembros):
    candidatas_entrenos = _candidatas(
        filas=origen.entrenos(conexion), mapa_miembros=mapa_miembros,
        persona_titular=persona_titular, modelo=Entreno, calcular_clave=_clave_entreno,
        etiqueta="entrenos", describir_clave=_describir_clave_entreno,
        # Entreno no tiene ninguna restricción de unicidad en la base (solo un índice, ver
        # entrenos/models.py): no hace falta H2, que es específica de
        # `una_medicion_por_persona_y_dia`.
        hay_colision=None,
    )
    candidatas_pesadas = _candidatas(
        filas=origen.pesadas(conexion), mapa_miembros=mapa_miembros,
        persona_titular=persona_titular, modelo=MedicionPeso, calcular_clave=_clave_pesada,
        etiqueta="pesadas", describir_clave=_describir_clave_pesada,
        hay_colision=_hay_colision_pesada,
    )
    todas = candidatas_entrenos + candidatas_pesadas

    resumen_vacio = {"entrenos": {"movidas": 0, "ya_movidas": 0}, "pesadas": {"movidas": 0, "ya_movidas": 0}}
    if not todas:
        return resumen_vacio

    estado = _estado_operacion([c["triple"] for c in todas])

    if estado == "mezclada":
        detalle = "; ".join(
            f"{c['etiqueta']} {c['descripcion']} (miembro_id={c['miembro_id']}) -> "
            f"{c['triple'][0]} bajo el titular, {c['triple'][1]} bajo el destino"
            + (" (y ya hay una medición de esa fecha con otro valor)" if c["triple"][2] else "")
            for c in todas
        )
        raise CommandError(
            "Las filas de esta pasada no están en un estado que el comando pueda explicar (se "
            "esperaba que TODA la operación — todas las tablas, todos los miembros — estuviera "
            "íntegra bajo el titular, o que TODA ya estuviera bajo su destino — nunca una "
            f"mezcla): {detalle}. No se ha movido nada."
        )

    if estado == "ya_movida":
        return {
            "entrenos": {"movidas": 0, "ya_movidas": len(candidatas_entrenos)},
            "pesadas": {"movidas": 0, "ya_movidas": len(candidatas_pesadas)},
        }

    # integra — pero antes de mover, el límite honesto de la ronda 2: con una sola fila en
    # TODA la operación no hay con qué corroborar que de verdad es la del bug y no una
    # coincidencia (ver el docstring del módulo, "El límite honesto"). El comando no finge.
    if len(todas) == 1:
        c = todas[0]
        raise CommandError(
            f"Solo hay UNA fila que mover en toda esta pasada ({c['etiqueta']} "
            f"{c['descripcion']}, miembro_id={c['miembro_id']}): con un único dato no hay con "
            "qué corroborar que de verdad es la fila que dejó mal colgada el bug y no una "
            "coincidencia — el comando no la mueve a ciegas. Revísala a mano, o declara más "
            "--miembro-node si hay más filas que mover en la misma pasada. No se ha movido nada."
        )

    for c in candidatas_entrenos:
        c["modelo"].objects.filter(persona=persona_titular, **c["clave"]).update(persona=c["persona_destino"])
    for c in candidatas_pesadas:
        c["modelo"].objects.filter(persona=persona_titular, **c["clave"]).update(persona=c["persona_destino"])

    return {
        "entrenos": {"movidas": len(candidatas_entrenos), "ya_movidas": 0},
        "pesadas": {"movidas": len(candidatas_pesadas), "ya_movidas": 0},
    }


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
