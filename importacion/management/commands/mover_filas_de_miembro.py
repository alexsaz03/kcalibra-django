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

## H1 de la revisión (ronda 1) — por qué NO decide fila a fila

La primera versión de este comando decidía cada fila de Node por su cuenta: "¿hay exactamente
1 bajo el titular y 0 bajo el destino? la muevo". El revisor lo reventó así: mover 8 filas de
verdad, borrar UNA desde la app (acción normal de la persona), apuntar OTRA fila nueva con la
misma tupla exacta (fecha/deporte/intensidad/minutos/calorías) — y la segunda pasada del comando
"reconocía" esa fila nueva como si fuera la vieja mal colgada y la movía. Los números seguían
cuadrando (7 ya movidas + 1 "recién encontrada" = 8) y aun así la fila movida era otra: el mismo
síntoma que esta unidad existe para arreglar, reintroducido por el lado del propio comando.

La causa es que la tupla de datos NO es un identificador — es una coincidencia de valores, y dos
filas de Node distintas (o una vieja y una nueva de la persona) pueden compartirla sin ser la
misma. Fila a fila no hay forma de distinguirlas.

**La propiedad que sí lo evita:** el comando nunca decide mirando una fila sola. Para cada
miembro y cada tabla, mira el LOTE COMPLETO de filas que le corresponden y solo actúa si el
lote entero está en uno de los dos únicos estados que puede explicar:

- **íntegro:** TODAS sus filas están, cada una, con exactamente 1 copia bajo el titular y 0
  bajo el destino — el lote entero sigue tal cual lo dejó el bug. Se mueve TODO el lote.
- **ya movido:** TODAS sus filas están, cada una, con exactamente 0 copias bajo el titular y 1
  bajo el destino — el lote entero ya se corrigió en una pasada anterior. No-op (idempotencia).

Cualquier otra combinación —una sola fila que no encaje, sea porque falta, porque aparece en
los dos sitios, o porque aparece donde no tocaba (el escenario del revisor)— es un lote
**mezclado**: la prueba de que pasó algo que el comando no puede razonar. Ninguna fila del lote
se toca, ni siquiera las que sí encajarían solas — porque si una fila del lote es sospechosa,
la "identidad" de las demás (la misma tupla, la misma lógica) deja de ser de fiar.

## H2 de la revisión — el choque de `(persona, fecha)` en pesadas, detectado, no crudo

`MedicionPeso` tiene una restricción real en la base, `una_medicion_por_persona_y_dia`
`(persona, fecha)` — más corta que la tupla completa que este comando usa para identificar una
fila. Si la persona de destino YA tiene una pesada esa fecha (con otros valores: la suya
propia, apuntada a mano), mover una fila "íntegra" hacia ella violaría esa restricción y saldría
como un `IntegrityError` crudo de Django, no como el `CommandError` en cristiano que el resto
del comando promete. Por eso, SOLO para pesadas, antes de dar un lote por "íntegro" se comprueba
también si el destino ya tiene ALGO esa fecha (choque de `(persona, fecha)`, no de la tupla
completa) — si lo tiene, el lote se trata como mezclado: no se intenta el `UPDATE` que iba a
reventar.

## H4/PII de la revisión — qué se imprime de una pesada

Los mensajes de error de pesadas nunca imprimen `peso_kg`/`grasa_pct`/`cintura_cm` (datos de
salud de una persona real) — solo la fecha, que basta para que quien lee el aviso localice la
fila en la app. Los de entrenos sí llevan la tupla completa: no son datos de salud y localizar
la fila exacta (puede haber varias el mismo día) lo necesita.

## Cómo identifica qué mover — la MISMA clave que ya usa la importación, nunca `id` a pelo

Para cada fila de Node con un `miembro_id` mapeado (no `NULL`), calcula su tupla de identidad —
la misma que `importar_datos_node` ya usa para reconocer una fila: `mapeo.clave_entreno` para
entrenos; fecha+peso_kg+grasa_pct+cintura_cm para pesadas — y busca, bajo el TITULAR y bajo el
DESTINO, cuántas filas Django tienen esa tupla exacta. Nunca por `id` de Django.

## Todo o nada (H3 de la revisión, generalizado): sin `--dry-run` real no hay ensayo posible

Todo el trabajo vive en UNA `transaction.atomic()`, igual que en `importar_datos_node.py`.
Cualquier lote mezclado revienta con `CommandError` y deshace TODO lo que esta pasada ya
hubiera movido de otros lotes/tablas — nunca deja una corrección a medias.
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
        "titular) a la Persona a la que de verdad pertenecen. Solo actúa cuando el lote "
        "completo de un miembro está íntegro (todo mal) o ya corregido (todo bien); ante "
        "cualquier mezcla, para y no toca nada. Repetible: la segunda vez no mueve nada."
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


def _mover_todo(conexion, persona_titular, mapa_miembros):
    return {
        "entrenos": _mover_entrenos(conexion, persona_titular, mapa_miembros),
        "pesadas": _mover_pesadas(conexion, persona_titular, mapa_miembros),
    }


def _agrupar_por_miembro(filas):
    """Filas de origen (con `miembro_id`), agrupadas por `miembro_id`, EXCLUYENDO las del
    titular (`miembro_id is None`: nunca hay nada que mover para esas)."""
    agrupadas = {}
    for fila in filas:
        miembro_id = fila["miembro_id"]
        if miembro_id is None:
            continue
        agrupadas.setdefault(miembro_id, []).append(fila)
    return agrupadas


def _estado_lote(triples):
    """`triples`: una `(en_origen, en_destino, colision)` por fila del lote (mismo miembro,
    misma tabla). Ver el docstring del módulo, 'H1'. Devuelve 'integro', 'ya_movido' o
    'mezclado' — NUNCA decide fila a fila."""
    if any(colision for _, _, colision in triples):
        return "mezclado"
    if all(en_origen == 1 and en_destino == 0 for en_origen, en_destino, _ in triples):
        return "integro"
    if all(en_origen == 0 and en_destino == 1 for en_origen, en_destino, _ in triples):
        return "ya_movido"
    return "mezclado"


def _mover_lote(
    *, filas, mapa_miembros, persona_titular, modelo, calcular_clave, etiqueta,
    describir_clave, hay_colision=None,
):
    """Genérico para `entrenos`/`pesadas`: agrupa por miembro, decide el lote COMPLETO de cada
    uno (H1) y, si está íntegro, mueve TODAS sus filas de una vez; si ya está movido, no hace
    nada; si está mezclado, para con un `CommandError` — sin mover NADA de ese lote."""
    movidas = 0
    ya_movidas = 0
    for miembro_id, filas_miembro in _agrupar_por_miembro(filas).items():
        persona_destino = mapa_miembros[miembro_id]
        claves = [calcular_clave(fila) for fila in filas_miembro]
        triples = []
        for clave in claves:
            en_origen = modelo.objects.filter(persona=persona_titular, **clave).count()
            en_destino = modelo.objects.filter(persona=persona_destino, **clave).count()
            # H2 solo tiene sentido como candidata a moverse (en_destino == 0): si en_destino
            # ya es >= 1, lo que `hay_colision` encontraría es la MISMA fila que constituye el
            # estado "ya_movido" (o una anomalía que las otras dos cuentas ya van a marcar como
            # mezclada) — comprobarlo ahí sería un falso positivo contra la propia idempotencia.
            colision = bool(
                hay_colision and en_destino == 0 and hay_colision(clave, persona_destino)
            )
            triples.append((en_origen, en_destino, colision))

        estado = _estado_lote(triples)
        if estado == "ya_movido":
            ya_movidas += len(claves)
            continue
        if estado == "integro":
            for clave in claves:
                modelo.objects.filter(persona=persona_titular, **clave).update(persona=persona_destino)
            movidas += len(claves)
            continue

        # mezclado — PARA, sin mover NADA de este lote (la transacción deshace además
        # cualquier otro lote/miembro/tabla ya movido en esta misma pasada).
        detalle = "; ".join(
            f"{describir_clave(clave)} -> {en_origen} bajo el titular, {en_destino} bajo el "
            f"destino{' (y ya hay una medición de esa fecha con otro valor)' if colision else ''}"
            for clave, (en_origen, en_destino, colision) in zip(claves, triples)
        )
        raise CommandError(
            f"Las {etiqueta} del miembro_id={miembro_id} no están en un estado que el comando "
            "pueda explicar (se esperaba que TODAS estuvieran bajo el titular, o que TODAS ya "
            f"estuvieran bajo el destino — nunca una mezcla): {detalle}. No se ha movido nada "
            "de esta pasada."
        )
    return {"movidas": movidas, "ya_movidas": ya_movidas}


def _clave_entreno(fila):
    datos = mapeo.datos_entreno(fila)
    return dict(zip(_CAMPOS_CLAVE_ENTRENO, mapeo.clave_entreno(datos)))


def _describir_clave_entreno(clave):
    return (
        f"{clave['fecha']} {clave['deporte']}/{clave['intensidad']}/{clave['minutos']}min/"
        f"{clave['calorias']}kcal"
    )


def _mover_entrenos(conexion, persona_titular, mapa_miembros):
    return _mover_lote(
        filas=origen.entrenos(conexion),
        mapa_miembros=mapa_miembros,
        persona_titular=persona_titular,
        modelo=Entreno,
        calcular_clave=_clave_entreno,
        etiqueta="entrenos",
        describir_clave=_describir_clave_entreno,
        # Entreno no tiene ninguna restricción de unicidad en la base (solo un índice, ver
        # entrenos/models.py): no hace falta la comprobación de H2, que es específica de
        # `una_medicion_por_persona_y_dia`.
        hay_colision=None,
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
    # H4/PII de la revisión: NUNCA el peso, la grasa ni la cintura — solo la fecha, que basta
    # para localizar la fila en la app.
    return str(clave["fecha"])


def _hay_colision_pesada(clave, persona_destino):
    """H2 de la revisión: `MedicionPeso` exige `(persona, fecha)` único en la base — más corto
    que la tupla completa que usa este comando para identificar una fila. Si el destino YA
    tiene una medición esa fecha (con OTROS valores: la suya propia), moverla revienta con
    `IntegrityError`. Se comprueba ANTES de intentarlo, por `(persona, fecha)` sin más — la
    misma restricción que la base va a hacer cumplir de todas formas."""
    return MedicionPeso.objects.filter(persona=persona_destino, fecha=clave["fecha"]).exists()


def _mover_pesadas(conexion, persona_titular, mapa_miembros):
    return _mover_lote(
        filas=origen.pesadas(conexion),
        mapa_miembros=mapa_miembros,
        persona_titular=persona_titular,
        modelo=MedicionPeso,
        calcular_clave=_clave_pesada,
        etiqueta="pesadas",
        describir_clave=_describir_clave_pesada,
        hay_colision=_hay_colision_pesada,
    )


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
