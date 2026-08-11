"""
`python manage.py importar_datos_node <ruta-a-la-sqlite-de-node> --cuenta <correo> [--dry-run]`

Trae la despensa, los entrenos, las recetas y las pesadas DE VERDAD de la app Node que sigue en
uso, y los cuelga de una cuenta que YA EXISTE en la app nueva (unidad 022, "Qué" de la
especificación). Repetible sin estropear nada (R2) y capaz de enseñar lo que haría antes de
tocar la base (R3, `--dry-run`).

## Por qué pasa por las puertas que ya existen, y no por un `create()` a pelo

- **Despensa** (`despensa.logica.anadir_producto`): es la pieza que convierte "1 kg" a 1000 g y
  funde dos líneas del mismo producto (R1) — reimplementar esa conversión aquí resucitaría el
  problema que cerró la unidad 017 (ver `despensa/logica.py`, encabezado del módulo).
- **Entrenos** (`entrenos.logica.apuntar_entreno`): decide si las calorías se toman tal cual o
  se estiman (G-70). Como Node siempre trae `calorias` (columna `NOT NULL`), esta puerta nunca
  entra en su rama de estimación: los valores llegan intactos (R4), sin repetir la fórmula.
  `origen` queda en su valor de fábrica, `"mano"` — la puerta no expone ese parámetro, y no hay
  ningún R* de esta unidad que pida preservarlo (ver hallazgos.md).
- **Recetas** (`recetas.logica.crear_receta`): crea la receta y sus ingredientes en una sola
  transacción (R5).
- **Pesadas** — la ÚNICA excepción, y está declarada: `perfiles.logica.apuntar_medicion` hace
  `update_or_create` por (usuario, fecha), pensada para que una persona CORRIJA su propia pesada
  del día. Usarla aquí sobrescribiría en silencio una medición que ya existiera en Django con la
  que trae Node, en vez de reconocer la colisión y saltarse la fila (R4). El comando comprueba
  la colisión primero y solo entonces crea directamente (ver `importacion/mapeo.py`, docstring
  de `datos_pesada`, y hallazgos.md).

## Todo o nada (R7, generalizado)

Todo el trabajo de escritura vive dentro de UNA `transaction.atomic()`. Cualquier fila que no se
sepa traducir (`importacion.mapeo.DatosNodeInvalidos`) o cualquier problema con el origen
(`importacion.origen.OrigenNodeInvalido`) deshace todo lo escrito hasta ese punto: nunca se deja
la base a medias. `--dry-run` usa el MISMO mecanismo desde dentro: hace todo el trabajo de
verdad (para que los recuentos que informa sean los recuentos reales) y fuerza el deshacer al
final con `_CanceladoPorDryRun`, en vez de simular en un camino de código aparte que podría
desviarse silenciosamente de lo que el comando hace de verdad.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from despensa.logica import anadir_producto
from despensa.models import ProductoDespensa
from entrenos.logica import apuntar_entreno
from entrenos.models import Entreno
from perfiles.models import MedicionPeso
from recetas.logica import crear_receta
from recetas.models import Receta

from ... import mapeo, origen

Usuario = get_user_model()


class _CanceladoPorDryRun(Exception):
    """Señal interna para deshacer la transacción en `--dry-run`. Django solo revierte una
    `atomic()` cuando sale una excepción por su bloque; esta lleva el resumen ya calculado a
    cuestas para que el `handle()` pueda seguir imprimiéndolo fuera, con la transacción ya
    deshecha."""

    def __init__(self, resumen):
        super().__init__("dry-run: deshaciendo la transacción a propósito")
        self.resumen = resumen


class Command(BaseCommand):
    help = (
        "Trae la despensa, los entrenos, las recetas y las pesadas de la app Node a una cuenta "
        "que ya existe en KCalibra. Repetible: la segunda vez no duplica nada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "ruta_db",
            help="Ruta a la SQLite de la app Node (kcalibra.db). Nunca se escribe en el código.",
        )
        parser.add_argument(
            "--cuenta",
            required=True,
            metavar="CORREO",
            help="Correo de la cuenta de KCalibra (Django) ya existente a la que cuelga todo lo importado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Enseña lo que haría, tabla a tabla, sin escribir nada.",
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
            hogar = usuario.hogar
            if hogar is None:
                raise CommandError(
                    f"La cuenta '{correo}' todavía no tiene hogar (está esperando a que la "
                    "acepten en uno): no hay dónde colgar la despensa ni las recetas. No se ha "
                    "tocado nada."
                )

            try:
                with transaction.atomic():
                    resumen = _importar_todo(conexion, usuario, hogar)
                    if dry_run:
                        raise _CanceladoPorDryRun(resumen)
            except _CanceladoPorDryRun as cancelado:
                resumen = cancelado.resumen
            except mapeo.DatosNodeInvalidos as exc:
                raise CommandError(
                    f"La base de Node trae un dato que no se sabe traducir: {exc} "
                    "No se ha escrito nada (se deshizo todo)."
                ) from exc
        finally:
            conexion.close()

        _imprimir_resumen(self.stdout, resumen, dry_run)


def _importar_todo(conexion, usuario, hogar):
    """Hace el trabajo real (dentro de la `atomic()` de `handle`) y devuelve el resumen, tabla
    a tabla. El orden (despensa, entrenos, pesadas, recetas) no importa para el resultado: las
    cuatro son independientes entre sí."""
    return {
        "despensa": _importar_despensa(conexion, hogar),
        "entrenos": _importar_entrenos(conexion, usuario),
        "pesadas": _importar_pesadas(conexion, usuario),
        "recetas": _importar_recetas(conexion, hogar),
    }


def _importar_despensa(conexion, hogar):
    """
    R1/R2 — reutiliza `despensa.logica.anadir_producto`, que ya hace la conversión a unidad
    canónica y la fusión (R1) CADA VEZ que se llama. La idempotencia entre pasadas (R2) se
    resuelve mirando, para cada línea de Node, si YA existía un producto con su misma clave
    canónica (`mapeo.clave_producto`) ANTES de que esta pasada tocara nada — el snapshot
    `existentes_al_empezar` se toma una sola vez, al principio, precisamente para no confundir
    "ya estaba antes de esta pasada" con "lo acabo de crear yo mismo hace dos líneas" (que es
    exactamente el caso de "1 kg" + "500 g" del mismo producto: la segunda línea SÍ tiene que
    fundirse con la primera DENTRO de esta misma pasada, R1; solo la comparación contra el
    snapshot inicial decide qué es "ya estaba" de verdad, R2).
    """
    existentes_al_empezar = {
        (nombre_normalizado, unidad)
        for nombre_normalizado, unidad in ProductoDespensa.objects.filter(hogar=hogar).values_list(
            "nombre_normalizado", "unidad"
        )
    }

    nuevos = 0
    ya_estaban = 0
    for fila in origen.productos_despensa(conexion):
        datos = mapeo.datos_producto_despensa(fila)
        clave = mapeo.clave_producto(datos["nombre"], datos["unidad"])
        if clave in existentes_al_empezar:
            ya_estaban += 1
            continue
        anadir_producto(hogar, datos)
        nuevos += 1

    return {"origen": nuevos + ya_estaban, "nuevos": nuevos, "ya_estaban": ya_estaban}


def _importar_entrenos(conexion, usuario):
    """R2/R4 — clave de idempotencia: la tupla completa (ver el porqué en `mapeo.py`). Snapshot
    tomado al empezar, mismo motivo que en la despensa (aunque aquí no hay fusión posible: cada
    fila de Node es siempre UN entreno nuevo si su clave no estaba, nunca se combina con otro)."""
    existentes_al_empezar = {
        (fecha, deporte, intensidad, minutos, calorias)
        for fecha, deporte, intensidad, minutos, calorias in Entreno.objects.filter(
            usuario=usuario
        ).values_list("fecha", "deporte", "intensidad", "minutos", "calorias")
    }

    nuevos = 0
    ya_estaban = 0
    for fila in origen.entrenos(conexion):
        datos = mapeo.datos_entreno(fila)
        clave = mapeo.clave_entreno(datos)
        if clave in existentes_al_empezar:
            ya_estaban += 1
            continue
        apuntar_entreno(usuario, datos)
        nuevos += 1

    return {"origen": nuevos + ya_estaban, "nuevos": nuevos, "ya_estaban": ya_estaban}


def _importar_pesadas(conexion, usuario):
    """
    R2/R4 — la clave (usuario, fecha) es LA restricción `una_medicion_por_persona_y_dia` de la
    unidad 006. Si ya hay una medición ese día (importada antes, o apuntada a mano por la
    persona en la app), la fila de Node se SALTA sin tocar la que ya hay — nunca se sobrescribe
    (ver el porqué de no usar `perfiles.logica.apuntar_medicion` en el docstring de `mapeo.
    datos_pesada`). Por eso se crea con `MedicionPeso.objects.create(...)` directamente: es la
    misma llamada que hace `apuntar_medicion` en su rama de "no había nada", sin su rama de
    `update_or_create` que aquí sería peligrosa.

    A DIFERENCIA de las otras tres tablas, aquí la comprobación es VIVA, no solo un snapshot
    tomado al empezar (ronda 1 de revisión, H1). El índice único de Node es
    `(usuario_id, COALESCE(miembro_id, 0), fecha)`: permite DOS pesadas el mismo día si son de
    personas distintas de la misma casa (`miembro_id` no se lee, "Fuera de alcance" — cuelga
    todo del único `usuario` de Django). Con un snapshot congelado, la SEGUNDA fila de Node de
    ese día no está en `existentes_al_empezar` (la primera solo se guarda en Django DURANTE
    esta misma pasada) y llegaría desnuda a `MedicionPeso.objects.create()`, que revienta con
    `IntegrityError` contra `una_medicion_por_persona_y_dia` — justo lo que R4 prohíbe ("no
    revienta: se salta y lo dice") y con una traza cruda de Python en vez de un aviso (R7). Por
    eso, además de `existentes_al_empezar` (lo que YA había en Django antes de esta pasada, para
    R2), se lleva `vistas_en_esta_pasada`: un segundo set que SÍ se actualiza fila a fila.

    Nótese que esto NO se aplica a despensa/entrenos/recetas: en despensa el snapshot congelado
    es CORRECTO a propósito (es lo que deja que `anadir_producto` funda "1 kg" + "500 g" del
    mismo producto DENTRO de la misma pasada, R1 — actualizar la foto ahí rompería la fusión);
    en entrenos, la clave es la tupla completa de valores, así que dos entrenos "iguales" de
    verdad SON el mismo entreno repetido y fundirse es lo correcto. Pesadas es la única de las
    cuatro donde dos filas de Node distintas (persona distinta, mismo día) comparten la MISMA
    clave de idempotencia sin ser la misma fila — de ahí que necesite su propia comprobación,
    y solo ella.

    Una colisión ENTRE DOS FILAS DE NODE (mismo día, ninguna de las dos existía ya en Django) se
    cuenta aparte, en `colisiones`, y NO se suma a `ya_estaban`: "ya estaba" es honesto para "esa
    fecha ya tenía una medición en Django antes de esta pasada", no para "otra fila de Node de
    esta misma pasada se adelantó". `_imprimir_resumen` lo dice con su propia frase (R4: "se
    salta y lo dice").
    """
    existentes_al_empezar = set(
        MedicionPeso.objects.filter(usuario=usuario).values_list("fecha", flat=True)
    )
    vistas_en_esta_pasada = set()

    nuevos = 0
    ya_estaban = 0
    colisiones = 0
    for fila in origen.pesadas(conexion):
        datos = mapeo.datos_pesada(fila)
        fecha = datos["fecha"]
        if fecha in existentes_al_empezar:
            ya_estaban += 1
            continue
        if fecha in vistas_en_esta_pasada:
            colisiones += 1
            continue
        MedicionPeso.objects.create(usuario=usuario, **datos)
        vistas_en_esta_pasada.add(fecha)
        nuevos += 1

    return {
        "origen": nuevos + ya_estaban + colisiones,
        "nuevos": nuevos,
        "ya_estaban": ya_estaban,
        "colisiones": colisiones,
    }


def _importar_recetas(conexion, hogar):
    """R2/R5 — clave de idempotencia: el nombre normalizado (`mapeo.nombre_normalizado`), por
    hogar. `Receta` no tiene ninguna restricción de unicidad (unidad 021: no la necesitaba), así
    que el snapshot se calcula en Python, no en la base de datos."""
    existentes_al_empezar = {
        mapeo.nombre_normalizado(nombre)
        for nombre in Receta.objects.filter(hogar=hogar).values_list("nombre", flat=True)
    }

    nuevos = 0
    ya_estaban = 0
    for fila in origen.recetas(conexion):
        datos, ingredientes = mapeo.datos_receta(fila)
        clave = mapeo.nombre_normalizado(datos["nombre"])
        if clave in existentes_al_empezar:
            ya_estaban += 1
            continue
        crear_receta(hogar, datos, ingredientes)
        nuevos += 1

    return {"origen": nuevos + ya_estaban, "nuevos": nuevos, "ya_estaban": ya_estaban}


_ETIQUETAS = {
    "despensa": "Despensa",
    "entrenos": "Entrenos",
    "pesadas": "Pesadas",
    "recetas": "Recetas",
}


def _imprimir_resumen(stdout, resumen, dry_run):
    if dry_run:
        stdout.write("[DRY-RUN] Nada de lo siguiente se ha escrito de verdad:")
    for clave, etiqueta in _ETIQUETAS.items():
        datos = resumen[clave]
        stdout.write(
            f"{etiqueta}: {datos['origen']} en Node -> {datos['nuevos']} nuevos, "
            f"{datos['ya_estaban']} ya estaban."
        )
        # Solo pesadas puede traer `colisiones` (H1, ronda 1): dos filas de Node del mismo día
        # que Django no puede guardar las dos porque cuelgan del mismo `usuario`. Se dice aparte
        # de "ya estaban" a propósito: no es que esa fecha ya existiera en Django, es que otra
        # fila de Node de ESTA MISMA pasada se adelantó (R4: "se salta y lo dice").
        colisiones = datos.get("colisiones", 0)
        if colisiones:
            verbo = "se ha saltado" if colisiones == 1 else "se han saltado"
            stdout.write(
                f"{etiqueta}: {colisiones} más {verbo} por chocar en fecha con otra fila de "
                "Node de esta misma pasada (una persona no puede tener dos pesadas el mismo "
                "día)."
            )
    if dry_run:
        stdout.write("[DRY-RUN] Fin. No se ha escrito ni una fila.")
