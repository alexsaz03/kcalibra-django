"""
`python manage.py importar_datos_node <ruta-a-la-sqlite-de-node> --cuenta <correo>
[--miembro-node <id-de-node>:<correo> ...] [--dry-run]`

Trae la despensa, los entrenos, las recetas y las pesadas DE VERDAD de la app Node que sigue en
uso, y los cuelga de una cuenta que YA EXISTE en la app nueva (unidad 022, "Qué" de la
especificación). Repetible sin estropear nada (R2) y capaz de enseñar lo que haría antes de
tocar la base (R3, `--dry-run`).

## Bug 033 — entrenos y pesadas ya no cuelgan TODOS del titular

`entrenos`/`pesos` traen `miembro_id` en Node (`NULL` = titular, un id = otro miembro de la
casa). Antes de esta unidad esa columna no se leía y todo colgaba de la única `persona` de
`--cuenta` — el bug 033. Ahora cada fila cuelga de quien le corresponde: la del titular sigue
resolviéndose con `--cuenta`; la de cualquier otro miembro necesita su propia correspondencia,
declarada A MANO con `--miembro-node <id-de-node>:<correo>` (repetible). La traducción completa
—por qué es un parámetro explícito y no un emparejamiento por nombre, y qué pasa si falta
alguno— vive en `importacion/miembros.py`. Despensa y recetas no tienen `miembro_id`: siguen
colgando del `hogar`, sin cambios.

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
  `update_or_create` por (persona, fecha), pensada para que una persona CORRIJA su propia pesada
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
from hogares.models import persona_de
from perfiles.models import MedicionPeso
from recetas.logica import crear_receta
from recetas.models import Receta

from ... import mapeo, miembros, origen

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
            "--miembro-node",
            action="append",
            default=[],
            metavar="ID:CORREO-O-ID-DE-PERSONA",
            help=(
                "Bug 033 — correspondencia de un miembro_id de Node (columna de `entrenos`/"
                "`pesos`) con la persona de KCalibra a la que cuelgan sus filas: "
                "'<id-de-node>:<correo>' si esa persona tiene cuenta propia, o "
                "'<id-de-node>:<id-de-persona>' si no la tiene (unidad 024). Repetible, uno "
                "por cada miembro de la casa que Node distingue del titular. Una fila con un "
                "miembro_id sin declarar aquí hace fallar el comando ANTES de escribir nada "
                "(nunca cuelga del titular por defecto, nunca se descarta callada) — ver "
                "importacion/miembros.py."
            ),
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
            # Unidad 023 — el hogar (y todo lo personal) cuelga de la PERSONA, no de la
            # cuenta. `--cuenta` sigue recibiendo un correo porque es lo que una persona sabe
            # teclear; de ahí se saca su persona.
            persona = persona_de(usuario)
            hogar = persona.hogar if persona is not None else None
            if hogar is None:
                raise CommandError(
                    f"La cuenta '{correo}' todavía no tiene hogar (está esperando a que la "
                    "acepten en uno): no hay dónde colgar la despensa ni las recetas. No se ha "
                    "tocado nada."
                )

            # Bug 033 — la correspondencia miembro_id -> Persona se resuelve y se valida ANTES
            # de abrir la transacción de escritura: si algo no cuadra (formato, cuenta que no
            # existe, persona de otra casa, o una fila de Node con un miembro_id que nadie
            # declaró), el comando revienta aquí, sin haber tocado la base todavía.
            mapa_miembros = miembros.resolver_mapa_miembros(options["miembro_node"], hogar)
            faltan = miembros.miembros_sin_mapear(conexion, mapa_miembros)
            if faltan:
                lista = ", ".join(str(m) for m in faltan)
                plural = "s" if len(faltan) > 1 else ""
                raise CommandError(
                    f"La base de Node trae fila{plural} con miembro_id {lista} sin "
                    "correspondencia declarada. No se ha escrito nada. Añade "
                    "--miembro-node <id-de-node>:<correo> por cada uno."
                )

            # R2 de la revisión (ronda 2): PRECONDICIÓN de la pasada entera, no un salto por
            # fila. Un salto por fila (la versión de la ronda 1) cambiaba una duplicación por
            # una omisión silenciosa — el mismo error de fondo que H1 en el mover, con la
            # tupla haciendo de identidad cuando no lo es. Si hay señales de una importación
            # anterior sin mover, el comando se NIEGA ENTERO (ni siquiera importa lo que sí
            # estaría limpio) y manda a `mover_filas_de_miembro` primero; si no hay ninguna,
            # importa TODAS las filas sin saltarse ninguna — nunca un resultado a medias.
            senales = _filas_pendientes_de_mover(conexion, persona, mapa_miembros, hogar)
            if senales:
                detalle = "; ".join(senales)
                raise CommandError(
                    "La base de Node trae filas que ya existen, idénticas, bajo OTRA persona "
                    "de esta misma casa — probablemente una importación anterior (con el "
                    f"comando de antes de esta unidad) todavía sin mover: {detalle}. Ejecuta "
                    "'mover_filas_de_miembro' antes de repetir esta importación. No se ha "
                    "escrito nada."
                )

            try:
                with transaction.atomic():
                    resumen = _importar_todo(conexion, persona, hogar, mapa_miembros)
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


def _importar_todo(conexion, persona, hogar, mapa_miembros):
    """Hace el trabajo real (dentro de la `atomic()` de `handle`) y devuelve el resumen, tabla
    a tabla. El orden (despensa, entrenos, pesadas, recetas) no importa para el resultado: las
    cuatro son independientes entre sí."""
    return {
        "despensa": _importar_despensa(conexion, hogar),
        "entrenos": _importar_entrenos(conexion, persona, mapa_miembros, hogar),
        "pesadas": _importar_pesadas(conexion, persona, mapa_miembros, hogar),
        "recetas": _importar_recetas(conexion, hogar),
    }


def _personas_involucradas(persona, mapa_miembros):
    """El titular más cada `Persona` que `--miembro-node` declaró, sin repetidos (por si el
    mismo correo se declarara para dos `miembro_id` distintos): `{persona.id: persona}`, para
    poder construir un snapshot de idempotencia POR PERSONA (033) en vez de uno solo."""
    personas = {persona.id: persona}
    personas.update({p.id: p for p in mapa_miembros.values()})
    return personas


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


def _existentes_del_hogar_entrenos(hogar):
    """H3 de la revisión (033): TODOS los entrenos de TODO el hogar (no solo de las personas
    involucradas en esta pasada), agrupados por su tupla de identidad, con el conjunto de
    `persona_id` que YA tiene cada una. Una sola consulta, barata (un hogar de verdad no tiene
    miles de entrenos), para poder preguntar 'esta fila que voy a crear para X ¿ya existe,
    idéntica, colgada de otra persona de la MISMA casa?' sin una query por fila."""
    mapa = {}
    filas = Entreno.objects.filter(persona__hogar=hogar).values_list(
        "persona_id", "fecha", "deporte", "intensidad", "minutos", "calorias"
    )
    for persona_id, fecha, deporte, intensidad, minutos, calorias in filas:
        clave = (fecha, deporte, intensidad, minutos, calorias)
        mapa.setdefault(clave, set()).add(persona_id)
    return mapa


def _importar_entrenos(conexion, persona, mapa_miembros, hogar):
    """R2/R4 — clave de idempotencia: la tupla completa (ver el porqué en `mapeo.py`). Snapshot
    tomado al empezar, mismo motivo que en la despensa (aunque aquí no hay fusión posible: cada
    fila de Node es siempre UN entreno nuevo si su clave no estaba, nunca se combina con otro).

    Bug 033 — el snapshot es POR PERSONA, no uno solo: dos entrenos con la misma tupla
    (fecha/deporte/intensidad/minutos/calorías) son "el mismo, repetido" solo si son de la
    MISMA persona. Un entreno del titular y uno de un miembro de la casa que por casualidad
    coincidieran en todo menos en quién lo hizo tienen que colgar los DOS, no fundirse en uno.
    Confirmado correcto por la revisión (ronda 2): esto es lo que hace que dos filas con la
    misma tupla DENTRO del propio Node (una del titular, otra del miembro) pasen las dos, y que
    la segunda pasada siga siendo idempotente. No se toca.

    H3 (ronda 1) vivía aquí como un salto por fila; la revisión (ronda 2, R2) lo movió a una
    PRECONDICIÓN de toda la pasada (`_filas_pendientes_de_mover`, llamada en `handle()` antes
    de abrir la transacción): un salto por fila cambiaba una duplicación por una omisión
    silenciosa (Euridice acababa con 7 entrenos, no con los 8 que exige el contrato) — el mismo
    error de fondo que H1 tenía en el mover, con la tupla haciendo de identidad cuando no lo
    es. Con la precondición ya resuelta ANTES de llegar aquí, esta función vuelve a poder
    asumir que ninguna fila choca con otra persona del hogar: si `handle()` llegó hasta
    llamarla, es porque no hay ninguna señal pendiente, y puede crear TODAS las filas que le
    toquen sin saltarse ninguna.
    """
    existentes_por_persona = {
        id_persona: {
            (fecha, deporte, intensidad, minutos, calorias)
            for fecha, deporte, intensidad, minutos, calorias in Entreno.objects.filter(
                persona_id=id_persona
            ).values_list("fecha", "deporte", "intensidad", "minutos", "calorias")
        }
        for id_persona in _personas_involucradas(persona, mapa_miembros)
    }

    nuevos = 0
    ya_estaban = 0
    for fila in origen.entrenos(conexion):
        datos = mapeo.datos_entreno(fila)
        persona_fila = miembros.persona_de_fila(fila, persona, mapa_miembros)
        clave = mapeo.clave_entreno(datos)
        if clave in existentes_por_persona[persona_fila.id]:
            ya_estaban += 1
            continue
        apuntar_entreno(persona_fila, datos)
        nuevos += 1

    return {"origen": nuevos + ya_estaban, "nuevos": nuevos, "ya_estaban": ya_estaban}


def _existentes_del_hogar_pesadas(hogar):
    """H3 de la revisión (033), misma idea que `_existentes_del_hogar_entrenos`: TODAS las
    pesadas del hogar, agrupadas por su tupla COMPLETA (fecha, peso, grasa, cintura — NUNCA
    solo `fecha`: dos personas de la misma casa pueden, legítimamente, tener CADA UNA su propia
    pesada el mismo día, eso no es un duplicado). Solo una coincidencia de los CUATRO valores a
    la vez es sospechosa de ser la misma fila mal colgada, todavía no movida."""
    mapa = {}
    filas = MedicionPeso.objects.filter(persona__hogar=hogar).values_list(
        "persona_id", "fecha", "peso_kg", "grasa_pct", "cintura_cm"
    )
    for persona_id, fecha, peso_kg, grasa_pct, cintura_cm in filas:
        clave = (fecha, peso_kg, grasa_pct, cintura_cm)
        mapa.setdefault(clave, set()).add(persona_id)
    return mapa


def _filas_pendientes_de_mover(conexion, persona, mapa_miembros, hogar):
    """R2 de la revisión (ronda 2): PRECONDICIÓN de la pasada ENTERA, llamada en `handle()`
    ANTES de abrir la `transaction.atomic()` — nunca escribe nada, solo mira. La versión
    anterior (H3, ronda 1) saltaba fila a fila la que ya existiera, idéntica, bajo otra persona
    del hogar; el revisor midió que eso cambiaba una duplicación (el bug original) por una
    OMISIÓN silenciosa (Euridice acababa con 7 entrenos, no 8: el contrato roto por el lado
    contrario). Es el mismo error de fondo que H1 tenía en `mover_filas_de_miembro`: una tupla
    de valores no es una identidad, y decidir fila a fila con ella termina adivinando.

    Por eso esto ya NO decide qué fila crear o saltar: recorre TODAS las filas de `entrenos` y
    `pesos` que le tocarían a un miembro (nunca al titular: sus filas nunca chocaban con nadie,
    ver la sección 1 de la ficha) y, para cada una que todavía NO esté en su sitio correcto,
    comprueba si ya existe, idéntica, bajo OTRA persona del hogar. Si encuentra AUNQUE SEA UNA,
    devuelve la lista de señales — quien llama se niega ENTERO (ni una fila de esta pasada se
    escribe, ni siquiera las que estarían limpias) y manda a `mover_filas_de_miembro` primero.
    Lista vacía: nada pendiente, la pasada puede crear TODAS sus filas sin saltar ninguna."""
    existentes_del_hogar_entrenos = _existentes_del_hogar_entrenos(hogar)
    existentes_del_hogar_pesadas = _existentes_del_hogar_pesadas(hogar)
    personas = _personas_involucradas(persona, mapa_miembros)
    existentes_por_persona_entrenos = {
        id_persona: {
            (fecha, deporte, intensidad, minutos, calorias)
            for fecha, deporte, intensidad, minutos, calorias in Entreno.objects.filter(
                persona_id=id_persona
            ).values_list("fecha", "deporte", "intensidad", "minutos", "calorias")
        }
        for id_persona in personas
    }
    existentes_por_persona_pesadas = {
        id_persona: set(
            MedicionPeso.objects.filter(persona_id=id_persona).values_list("fecha", flat=True)
        )
        for id_persona in personas
    }

    senales = []
    for fila in origen.entrenos(conexion):
        if fila["miembro_id"] is None:
            continue
        datos = mapeo.datos_entreno(fila)
        persona_fila = miembros.persona_de_fila(fila, persona, mapa_miembros)
        clave = mapeo.clave_entreno(datos)
        if clave in existentes_por_persona_entrenos[persona_fila.id]:
            continue  # ya está en su sitio correcto: idempotencia normal, no es una señal
        if existentes_del_hogar_entrenos.get(clave, set()) - {persona_fila.id}:
            senales.append(f"entreno {clave} (miembro_id={fila['miembro_id']})")

    for fila in origen.pesadas(conexion):
        if fila["miembro_id"] is None:
            continue
        datos = mapeo.datos_pesada(fila)
        persona_fila = miembros.persona_de_fila(fila, persona, mapa_miembros)
        fecha = datos["fecha"]
        if fecha in existentes_por_persona_pesadas[persona_fila.id]:
            continue
        clave_completa = (fecha, datos["peso_kg"], datos["grasa_pct"], datos["cintura_cm"])
        if existentes_del_hogar_pesadas.get(clave_completa, set()) - {persona_fila.id}:
            senales.append(f"pesada {fecha} (miembro_id={fila['miembro_id']})")

    return senales


def _importar_pesadas(conexion, persona, mapa_miembros, hogar):
    """
    R2/R4 — la clave (persona, fecha) es LA restricción `una_medicion_por_persona_y_dia` de la
    unidad 006. Si ya hay una medición ese día (importada antes, o apuntada a mano por la
    persona en la app), la fila de Node se SALTA sin tocar la que ya hay — nunca se sobrescribe
    (ver el porqué de no usar `perfiles.logica.apuntar_medicion` en el docstring de `mapeo.
    datos_pesada`). Por eso se crea con `MedicionPeso.objects.create(...)` directamente: es la
    misma llamada que hace `apuntar_medicion` en su rama de "no había nada", sin su rama de
    `update_or_create` que aquí sería peligrosa.

    H3 (ronda 1) vivía aquí como un salto por fila; la revisión (ronda 2, R2) lo movió a una
    PRECONDICIÓN de toda la pasada (`_filas_pendientes_de_mover`, en `handle()`, antes de abrir
    la transacción) — un salto por fila cambiaba una duplicación por una omisión silenciosa, y
    rompía el criterio de aceptación del contrato. Con la precondición ya resuelta antes de
    llegar aquí, esta función asume que ninguna fila choca con otra persona del hogar.

    A DIFERENCIA de las otras tres tablas, aquí la comprobación es VIVA, no solo un snapshot
    tomado al empezar (ronda 1 de revisión, H1). El índice único de Node es
    `(usuario_id, COALESCE(miembro_id, 0), fecha)`: permite DOS pesadas el mismo día si son de
    personas distintas de la misma casa. Con un snapshot congelado, la SEGUNDA fila de Node de
    ese día no está en `existentes_al_empezar` (la primera solo se guarda en Django DURANTE
    esta misma pasada) y llegaría desnuda a `MedicionPeso.objects.create()`, que revienta con
    `IntegrityError` contra `una_medicion_por_persona_y_dia` — justo lo que R4 prohíbe ("no
    revienta: se salta y lo dice") y con una traza cruda de Python en vez de un aviso (R7). Por
    eso, además de `existentes_al_empezar` (lo que YA había en Django antes de esta pasada, para
    R2), se lleva `vistas_en_esta_pasada`: un segundo set que SÍ se actualiza fila a fila.

    Bug 033 — las dos, `existentes_al_empezar` y `vistas_en_esta_pasada`, son ahora POR
    PERSONA (un dict de sets, uno por persona involucrada), no una sola pareja compartida.
    Es la parte que de verdad importa aquí: el titular y un miembro de la casa pueden tener
    CADA UNO su propia pesada el mismo día (el índice único de Node ya lo permitía, `COALESCE
    (miembro_id, 0)`) y con un único par de sets compartido entre las dos personas, la segunda
    fila del día (la del miembro) se habría marcado como "colisión" contra la del titular sin
    serlo — exactamente el fallo que la unidad 006 y este índice existen para evitar, solo que
    ahora entre dos personas en vez de dentro de una.

    Nótese que esto NO se aplica a despensa/entrenos/recetas: en despensa el snapshot congelado
    es CORRECTO a propósito (es lo que deja que `anadir_producto` funda "1 kg" + "500 g" del
    mismo producto DENTRO de la misma pasada, R1 — actualizar la foto ahí rompería la fusión);
    en entrenos, la clave es la tupla completa de valores, así que dos entrenos "iguales" de
    verdad SON el mismo entreno repetido y fundirse es lo correcto. Pesadas es la única de las
    cuatro donde dos filas de Node distintas (persona distinta, mismo día) comparten la MISMA
    clave de idempotencia sin ser la misma fila — de ahí que necesite su propia comprobación,
    y solo ella.

    Una colisión ENTRE DOS FILAS DE NODE DE LA MISMA PERSONA (mismo día, ninguna de las dos
    existía ya en Django) se cuenta aparte, en `colisiones`, y NO se suma a `ya_estaban`: "ya
    estaba" es honesto para "esa fecha ya tenía una medición en Django antes de esta pasada",
    no para "otra fila de Node de esta misma pasada se adelantó". `_imprimir_resumen` lo dice
    con su propia frase (R4: "se salta y lo dice").
    """
    personas = _personas_involucradas(persona, mapa_miembros)
    existentes_por_persona = {
        id_persona: set(
            MedicionPeso.objects.filter(persona_id=id_persona).values_list("fecha", flat=True)
        )
        for id_persona in personas
    }
    vistas_por_persona = {id_persona: set() for id_persona in personas}

    nuevos = 0
    ya_estaban = 0
    colisiones = 0
    for fila in origen.pesadas(conexion):
        datos = mapeo.datos_pesada(fila)
        persona_fila = miembros.persona_de_fila(fila, persona, mapa_miembros)
        fecha = datos["fecha"]
        if fecha in existentes_por_persona[persona_fila.id]:
            ya_estaban += 1
            continue
        if fecha in vistas_por_persona[persona_fila.id]:
            colisiones += 1
            continue
        MedicionPeso.objects.create(persona=persona_fila, **datos)
        vistas_por_persona[persona_fila.id].add(fecha)
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
        # que Django no puede guardar las dos porque cuelgan de la misma `persona`. Se dice aparte
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
