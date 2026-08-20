r"""
El check permanente de la unidad 020: la puerta del hogar deja de ser opcional.

Desde la unidad 003 esta casa promete que **los datos de un hogar no se ven desde otro**: todo
lo que sea de un hogar se pide por la puerta única (`hogares/acceso.py`), que responde 404 —
nunca 403 — cuando lo que pides no es tuyo (R9, R14, Q-11, Q-20). Hasta hoy esa promesa
dependía de que cada persona se acordara de usar la puerta: nada impedía escribir
`ProductoDespensa.objects.get(pk=...)` en una vista nueva y servir la despensa de otra casa sin
enterarse.

Este fichero es el hermano de `kcalibra/tests_estilos.py` (unidad 015): un check que **vigila al
equipo, no al código**. Recorre los `.py` del repositorio, encuentra las consultas que arrancan
en `<ModeloDelHogar>.objects` y falla nombrando las que no dicen **de qué hogar** son.

## Qué cuenta como "decir de qué hogar"

Una consulta está acotada si alguna de sus llamadas de estrechamiento (`filter`, `get`,
`get_or_create`, `update_or_create`, `create`, `del_hogar`) pasa un campo que **lleva a un
hogar**:

- el propio `hogar` del modelo, o
- una clave ajena del modelo cuyo destino tenga a su vez un `hogar` (hoy: `persona`, porque
  `hogares.Persona.hogar` existe — ver `_lleva_a_un_hogar()` y `modelos_del_hogar()`).

Ese segundo caso NO es un apaño para callar avisos: es el patrón real de `planes/logica.py`,
donde el plan se pide por la persona (`filter(persona=persona, fecha=fecha)`) y esa persona ya
vino validada por la puerta (`hogares.acceso.persona_del_hogar_o_404`). Acotar por una persona
del hogar es MÁS estrecho que acotar por el hogar entero, no más ancho. La lista no se escribe a
mano: se deduce de las claves ajenas de cada modelo, así que el día que llegue un modelo nuevo
sus caminos al hogar se descubren solos, igual que el modelo (R3).

**Lo que este check comprueba es estructural, no semántico:** que la consulta DIGA a quién
pertenece lo que pide, no que ese "a quién" sea el correcto. `filter(hogar=hogar_de_otro)`
pasaría. Quien decide que el hogar es el bueno es la puerta, y por eso el mensaje de fallo manda
a la puerta en vez de sugerir un `filter` a mano.

**Y admitir `persona` ENSANCHA ese hueco, no lo deja igual.** Conviene saberlo con nombres y
apellidos, porque en abstracto no avisa a nadie: en este repositorio un `hogar` sale casi
siempre de `hogares.acceso.hogar_actual(request)` (lo pone el servidor, a partir de la
`Persona` de quien hizo login), mientras que un `persona_id` sale rutinariamente **de la
URL** (lo pone quien llama). Unidad 023 — antes de ella este ejemplo se contaba con
`request.user.hogar` y `usuario_id`: el desfase Persona/Usuario de esa unidad borró
`Usuario.hogar` (vive en `hogares.Persona.hogar` desde entonces) y renombró la puerta
(`usuario_del_hogar_o_404` pasó a `persona_del_hogar_o_404`) — cambió QUIÉN es el vector, no
si lo hay. Una vista que copiara `planes/views.py:apuntar_plan` y se saltara
`persona_del_hogar_o_404` —

    def ver_plan(request, persona_id):
        plan = PlanDeDia.objects.filter(persona_id=persona_id, fecha=hoy).first()

— **pasa este check en VERDE** y sirve el plan de cualquier persona de cualquier hogar a quien
pruebe ids. Es una fuga real, comprobada primero en la revisión de la 020 (entonces con la
forma de antes de la 023, `usuario_id`) y **re-verificada por la unidad 034 con la forma que
tiene HOY** — la misma vista de sonda de arriba, pasada por `consultas_sin_acotar()`, sigue
devolviendo `[]` (ninguna infracción) — y **no es cazable estáticamente**: `persona_id=
persona_id` es indistinguible de la versión legítima (la que usa
`planes/logica.py:obtener_plan_de`, con una `persona` que YA pasó por la puerta). Lo único
que la impide sigue siendo la puerta. Si algún día se busca red para esto, la forma que puede
funcionar no es mirar el `filter`, es exigir que toda vista con un `persona_id` en su firma
llame a una puerta (`persona_del_hogar_o_404` u otra de `hogares.acceso`) — otro check, y
otra unidad.

## Excepciones (R4): declaradas una a una, con su motivo, en `EXCEPCIONES`

Nunca en bloque. Y para que ampliar una excepción no pueda dejar el check verde por vacío, hay
un segundo test (`test_las_excepciones_no_se_comen_el_repositorio`) que exige que los ficheros
de lógica vivos SIGAN mirándose. Una excepción sin motivo escrito es un agujero con permiso; una
excepción que nadie vigila es el mismo agujero, más grande.

## Hasta dónde llega y hasta dónde NO (la asimetría, escrita a propósito)

El análisis es **estático y por nombre**: ve `PlanDeDia.objects...` porque el texto dice
`PlanDeDia`. Por tanto **NO** ve:

- un import con alias (`from planes.models import PlanDeDia as P`; `P.objects.all()`),
- un acceso indirecto (`getattr(modelo, "objects")`, `apps.get_model(...).objects`),
- los managers inversos (`hogar.productodespensa_set`, `plan.comidas`), que ya salen acotados
  por el objeto del que cuelgan,
- una variable que se reasigna a OTRA cosa ya acotada dentro del mismo ámbito
  (`qs = ProductoDespensa.objects.all()` y tres líneas después `qs = otra.filter(hogar=h)`):
  el seguimiento de variables es por nombre, no por flujo de datos,
- **un `persona_id` que viene de la URL en vez de la puerta** (el caso de arriba,
  `filter(persona_id=persona_id)`): estructuralmente idéntico al legítimo,
- lo que ocurra dentro de una librería.

Ninguno de esos huecos existe hoy en el repositorio (medido: ver `hallazgos.md` de la unidad
020, y re-medido por la 034 — las dieciséis vistas que hoy reciben un `persona_id` por la URL
[`planes/views.py:apuntar_plan`; `cierres/views.py:responder/saltar/cerrar`;
`progreso/views.py:ver_progreso`; `hogares/views.py:pasar_responsable/borrar_persona_a_cargo`;
`perfiles/views.py:ver_perfil/actualizar_perfil/ver_peso/apuntar_peso/borrar_peso`;
`entrenos/views.py:ver_entrenos/apuntar/corregir/borrar`] pasan TODAS por una puerta —
`persona_del_hogar_o_404`, `persona_editable_o_404`, `persona_propia_o_404`,
`persona_visible_o_404`, `perfil_editable_o_404`, `perfil_visible_o_404` o
`persona_a_cargo_o_404` — antes de tocar el `persona_id` crudo). Se dejan escritos porque un
check cuyo perímetro no está escrito acaba creyéndose más grande de lo que es, que es justo lo
que el bug 019 enseñó a temer: una red que caza la mitad de los peces **parece** una red.

## Trampas ya pisadas al escribir esto (para quien lo toque después)

- `exclude()` **no** acota: `exclude(hogar=h)` devuelve todo lo que NO es de ese hogar, o sea
  lo contrario. Solo cuentan las llamadas de `_METODOS_QUE_ACOTAN`.
- El `defaults={...}` de `get_or_create` **tampoco** acota: son los valores con los que se CREA
  si no había nada, no la búsqueda. `planes/logica.py:97` pasa por su `usuario=`, no por su
  `defaults={"hogar": ...}` — y así debe ser.
- Un campo que acota **con valor `None`** no acota nada: `filter(resuelta_por=None)` no dice de
  qué hogar es, dice "sin resolver". Se descarta explícitamente (`_valor_es_none`).
- La consulta se guarda en una variable y se filtra tres líneas después
  (`hogares/logica.py:63-67` lo hace). Si el check mirase solo la expresión, eso sería un falso
  positivo, así que sigue las asignaciones locales dentro de su ámbito (`_acotaciones_por_variable`).
- La cadena hay que cogerla ENTERA: en `filter(hogar=h).exclude(pk=...)` el `hogar=` está en el
  primer eslabón, y en `.filter(...).select_related(...).first()` el último nodo del árbol es
  `first`. Por eso se busca la expresión más larga que nace en cada `<Modelo>.objects`.
"""

import ast
import os

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

from hogares.models import Hogar, ModeloDeHogar

PUERTA = "hogares/acceso.py"

# Las llamadas que ESTRECHAN el conjunto de filas. `exclude` no está (hace lo contrario), ni
# `order_by`/`select_related`/`values` (no cambian qué filas salen).
_METODOS_QUE_ACOTAN = frozenset(
    {"filter", "get", "get_or_create", "update_or_create", "create", "del_hogar"}
)

# Carpetas que no son código de este proyecto y que no se recorren nunca.
_CARPETAS_IGNORADAS = frozenset({".git", "__pycache__", ".venv", "venv", "node_modules", "staticfiles"})


def _es_migracion(rel):
    return "migrations" in rel.split(os.sep)


def _es_admin(rel):
    return os.path.basename(rel) == "admin.py"


def _es_de_hogares(rel):
    return rel.split(os.sep)[0] == "hogares"


def _es_test(rel):
    base = os.path.basename(rel)
    return base == "tests.py" or base.startswith("tests_") or base.startswith("test_") or "tests" in rel.split(os.sep)[:-1]


# R4 — cada excepción, por su nombre y con su motivo escrito al lado. Nunca en bloque.
EXCEPCIONES = (
    (
        _es_migracion,
        "migraciones: corren sin ninguna petición detrás (no hay 'quién pregunta') y operan "
        "sobre toda la tabla A PROPÓSITO — `despensa/migrations/0002_funde_pesos_y_liquidos_"
        "en_su_unidad_pequena.py` recorre la despensa de TODOS los hogares para convertir "
        "unidades, y tiene que hacerlo",
    ),
    (
        _es_admin,
        "admin de Django: es la consola de quien administra el sistema, no una pantalla del "
        "hogar. Ve todas las filas por definición y enseña la columna `hogar` para "
        "distinguirlas (`despensa/admin.py`). Que el admin no pase por la unidad canónica de "
        "la despensa es deuda conocida de la unidad 017, y es otro problema",
    ),
    (
        _es_de_hogares,
        "hogares/: es quien IMPLEMENTA la puerta. `hogares/acceso.py` no puede salir por sí "
        "mismo, y `hogares/logica.py:resolver_solicitudes_caducadas` necesita a propósito "
        "poder correr sin acotar (mantenimiento). Pedirle a la puerta que use la puerta es "
        "circular",
    ),
    (
        _es_test,
        "tests: montan varios hogares a la vez a propósito para comprobar que el aislamiento "
        "funciona, y comprueban el resultado mirando la tabla entera "
        "(`ProductoDespensa.objects.filter(id=...).exists()`). Obligarles a salir por la "
        "puerta les quitaría el único punto de vista desde el que se puede ver si la puerta "
        "cierra",
    ),
)

# Oráculo de la propia comprobación (ver `test_las_excepciones_no_se_comen_el_repositorio`):
# ficheros de lógica vivos que HOY tienen consultas a un modelo del hogar y que el check tiene
# que seguir mirando pase lo que pase. No es un suelo cerrado: pueden aparecer más.
FICHEROS_QUE_EL_CHECK_TIENE_QUE_MIRAR = frozenset(
    {
        os.path.join("planes", "logica.py"),
        os.path.join("despensa", "logica.py"),
    }
)


def motivo_de_la_excepcion(rel):
    """El motivo escrito por el que `rel` no se mira, o `None` si sí se mira."""
    for predicado, motivo in EXCEPCIONES:
        if predicado(rel):
            return motivo
    return None


def _lleva_a_un_hogar(modelo):
    """`modelo` es un hogar, o tiene una clave ajena a uno. Es lo que convierte a un campo en
    un camino válido para acotar."""
    if modelo is Hogar:
        return True
    return any(
        campo.many_to_one and campo.related_model is Hogar
        for campo in modelo._meta.get_fields()
        if hasattr(campo, "many_to_one")
    )


def modelos_del_hogar():
    """Los modelos del hogar, DESCUBIERTOS en tiempo de ejecución (R3), con los campos por los
    que se les puede acotar. Nada de listas escritas a mano: el día que las recetas hereden de
    `ModeloDeHogar` quedan vigiladas sin tocar este fichero."""
    encontrados = {}
    for modelo in apps.get_models():
        if not issubclass(modelo, ModeloDeHogar):
            continue
        campos = {
            campo.name
            for campo in modelo._meta.get_fields()
            if getattr(campo, "many_to_one", False) and _lleva_a_un_hogar(campo.related_model)
        }
        encontrados[modelo.__name__] = frozenset(campos)
    return encontrados


def _ficheros_py():
    base = str(settings.BASE_DIR)
    salida = []
    for carpeta, subcarpetas, nombres in os.walk(base):
        subcarpetas[:] = [
            s for s in subcarpetas if s not in _CARPETAS_IGNORADAS and not s.startswith(".")
        ]
        for nombre in nombres:
            if nombre.endswith(".py"):
                salida.append(os.path.relpath(os.path.join(carpeta, nombre), base))
    return sorted(salida)


def _valor_es_none(nodo):
    return isinstance(nodo, ast.Constant) and nodo.value is None


def _kwargs_que_acotan(llamada):
    """Los nombres de campo por los que ESTA llamada estrecha, incluidos los que vengan dentro
    de un `Q(...)`. Descarta los que valen `None` (no dicen de quién es nada)."""
    nombres = set()
    for kw in llamada.keywords:
        if kw.arg and not _valor_es_none(kw.value):
            nombres.add(kw.arg)
    for arg in llamada.args:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "Q":
                for kw in sub.keywords:
                    if kw.arg and not _valor_es_none(kw.value):
                        nombres.add(kw.arg)
    return nombres


# Las formas con que se puede IDENTIFICAR a quién pertenece lo que se pide. Es una lista
# blanca a propósito, y la primera versión de esta unidad se equivocó aquí: aceptaba cualquier
# `campo__<loquesea>` con un `startswith`, y eso deja pasar consultas que devuelven filas de
# TODOS los hogares porque el lookup no identifica a nadie. Los tres casos que lo destaparon
# (revisión de la 020, los tres salían VERDE y las tres devuelven todas las casas):
#
#   PlanDeDia.objects.filter(usuario__is_active=True, …)     ← "las personas activas"
#   ProductoDespensa.objects.filter(hogar__isnull=False)     ← "los que tienen hogar"
#   SolicitudEntrada.objects.filter(resuelta_por__isnull=True)  ← "las que nadie ha resuelto"
#
# El tercero es el que más asusta: "las solicitudes sin resolver" es un concepto del dominio
# que cualquiera escribe sin pensar. Un `__isnull`, un `__gte` o un `__contains` acotan por una
# PROPIEDAD, no por una identidad; solo lo segundo dice de quién es lo que estás pidiendo.
_SUFIJOS_DE_IDENTIDAD = ("", "_id", "__id", "__pk", "__codigo", "__in")


def _acota(nombres, campos):
    """`nombres` (los kwargs vistos) identifica al dueño de lo que se pide.

    Cada campo que lleva al hogar se admite solo en las formas de `_SUFIJOS_DE_IDENTIDAD`:
    `hogar`, `hogar_id`, `hogar__id`, `hogar__pk`, `hogar__codigo` y `hogar__in`. Cualquier
    otro lookup (`hogar__isnull`, `usuario__is_active`…) NO acota: filtra por una propiedad y
    devuelve filas de todos los hogares."""
    admitidos = {campo + sufijo for campo in campos for sufijo in _SUFIJOS_DE_IDENTIDAD}
    return any(nombre in admitidos for nombre in nombres)


def _baja_un_eslabon(nodo):
    if isinstance(nodo, ast.Attribute):
        return nodo.value
    if isinstance(nodo, ast.Call):
        return nodo.func
    if isinstance(nodo, ast.Subscript):
        return nodo.value
    return None


def _nace_en(nodo, arranques):
    """El nodo `<Modelo>.objects` en el que nace la cadena de `nodo`, o `None`."""
    actual = nodo
    while actual is not None:
        if id(actual) in arranques:
            return actual
        actual = _baja_un_eslabon(actual)
    return None


def _kwargs_de_la_cadena(nodo):
    """Todos los kwargs de estrechamiento de la cadena entera, recorrida de la punta a la raíz.

    El nombre del método se lee EN el propio nodo `Call` (`llamada.func.attr`), no en el
    eslabón siguiente: al bajar, un `Call` aparece ANTES que el `Attribute` que lo nombra, así
    que mirar "el último atributo visto" leería el método del eslabón equivocado (y con
    `.filter(hogar=h).first()` se quedaría sin ver el `hogar=`)."""
    nombres = set()
    actual = nodo
    while actual is not None:
        if isinstance(actual, ast.Call) and isinstance(actual.func, ast.Attribute):
            if actual.func.attr in _METODOS_QUE_ACOTAN:
                nombres |= _kwargs_que_acotan(actual)
        actual = _baja_un_eslabon(actual)
    return nombres


def _metodos_de_la_cadena(nodo):
    """Los métodos encadenados, en el orden en que se leen: `filter`, `first`… Sirve para que
    el mensaje de fallo enseñe la consulta y no un `objects(...)` genérico."""
    metodos = []
    actual = nodo
    while actual is not None:
        if isinstance(actual, ast.Attribute) and actual.attr != "objects":
            metodos.append(actual.attr)
        actual = _baja_un_eslabon(actual)
    return list(reversed(metodos))


def _ambito_mas_cercano(arbol, cadena):
    """La función (o el módulo, si la cadena está suelta) MÁS INTERIOR que contiene a `cadena`.

    Tiene que ser la más interior, no cualquiera que la contenga: si se mirara también el
    módulo entero, un `qs` sin acotar en una vista se daría por acotado porque OTRA función del
    mismo fichero tiene su propio `qs` y sí lo filtra por hogar. `qs`, `productos` y `plan` son
    nombres demasiado comunes para permitirse esa confusión."""
    mejor = arbol
    mejor_tamano = None
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        subarbol = list(ast.walk(nodo))
        if not any(sub is cadena for sub in subarbol):
            continue
        if mejor_tamano is None or len(subarbol) < mejor_tamano:
            mejor, mejor_tamano = nodo, len(subarbol)
    return mejor


def _acotaciones_por_variable(ambito):
    """Para cada variable del ámbito, los kwargs de estrechamiento que se le aplican en algún
    momento: `qs = X.objects.filter(...)` ... `qs = qs.filter(hogar=hogar)`. Sin esto, el
    patrón de `hogares/logica.py:63-67` sería un falso positivo."""
    por_variable = {}
    for nodo in ast.walk(ambito):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Attribute):
            continue
        if nodo.func.attr not in _METODOS_QUE_ACOTAN:
            continue
        raiz = nodo.func.value
        while isinstance(raiz, (ast.Attribute, ast.Call, ast.Subscript)):
            raiz = _baja_un_eslabon(raiz)
        if isinstance(raiz, ast.Name):
            por_variable.setdefault(raiz.id, set()).update(_kwargs_que_acotan(nodo))
    return por_variable


def _variable_de_la_asignacion(ambito, cadena):
    """Si `cadena` es lo que se asigna a una variable simple, su nombre."""
    for nodo in ast.walk(ambito):
        if isinstance(nodo, ast.Assign) and nodo.value is cadena:
            for destino in nodo.targets:
                if isinstance(destino, ast.Name):
                    return destino.id
        if isinstance(nodo, ast.AnnAssign) and nodo.value is cadena:
            if isinstance(nodo.target, ast.Name):
                return nodo.target.id
    return None


def consultas_sin_acotar(rel, fuente, modelos):
    """Las consultas de `fuente` que arrancan en un modelo del hogar y no dicen de qué hogar
    son. Devuelve tuplas `(linea, modelo, campos_que_habrian_valido)`."""
    arbol = ast.parse(fuente, filename=rel)

    arranques = {}
    for nodo in ast.walk(arbol):
        if (
            isinstance(nodo, ast.Attribute)
            and nodo.attr == "objects"
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id in modelos
        ):
            arranques[id(nodo)] = nodo.value.id
    if not arranques:
        return []

    # La expresión MÁS LARGA que nace en cada arranque: la cadena entera, no un trozo.
    cadenas = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Call, ast.Attribute, ast.Subscript)):
            continue
        base = _nace_en(nodo, arranques)
        if base is None:
            continue
        anterior = cadenas.get(id(base))
        if anterior is None or len(list(ast.walk(nodo))) > len(list(ast.walk(anterior[0]))):
            cadenas[id(base)] = (nodo, base)

    hallazgos = []
    for cadena, base in cadenas.values():
        modelo = arranques[id(base)]
        campos = modelos[modelo]
        nombres = _kwargs_de_la_cadena(cadena)

        # …y lo que se le aplique después a la variable donde se guardó, dentro de SU ámbito.
        ambito = _ambito_mas_cercano(arbol, cadena)
        variable = _variable_de_la_asignacion(ambito, cadena)
        if variable is not None:
            nombres |= _acotaciones_por_variable(ambito).get(variable, set())

        if not _acota(nombres, campos):
            consulta = ".".join([modelo, "objects"] + _metodos_de_la_cadena(cadena))
            hallazgos.append((base.lineno, modelo, consulta, sorted(campos)))
    return sorted(hallazgos)


def analizar_repositorio():
    """Recorre el repositorio entero y devuelve `(infracciones, ficheros_mirados)`."""
    modelos = modelos_del_hogar()
    base = str(settings.BASE_DIR)
    infracciones = []
    mirados = []
    for rel in _ficheros_py():
        if motivo_de_la_excepcion(rel) is not None:
            continue
        mirados.append(rel)
        with open(os.path.join(base, rel), encoding="utf-8") as f:
            fuente = f.read()
        for linea, modelo, consulta, campos in consultas_sin_acotar(rel, fuente, modelos):
            infracciones.append((rel, linea, modelo, consulta, campos))
    return sorted(infracciones), mirados


class LaPuertaDelHogarNoSeRodeaTests(SimpleTestCase):
    """El check de la unidad 020: ninguna consulta a un modelo del hogar puede pedir datos sin
    decir de qué hogar son. No toca la base de datos (`SimpleTestCase`): lee los `.py` del repo
    y el registro de modelos, que es metadatos."""

    databases = set()

    def test_los_modelos_del_hogar_se_descubren_solos(self):
        """Comprobación de la propia comprobación. Si el descubrimiento se rompiera, el test de
        abajo pasaría en falso: "ningún modelo que vigilar" es indistinguible de "todo
        correcto". NO fija un suelo cerrado (un `assertEqual` contra los tres de hoy pondría la
        suite en rojo el día que lleguen las recetas, diciendo lo contrario de lo ocurrido):
        exige que los tres conocidos sigan apareciendo, sin prohibir que aparezcan más.

        Y comprueba lo que el descubrimiento NO debe traer: `Entreno` aísla por usuario, no por
        hogar (su propio docstring avisa de que un comentario antiguo dice lo contrario), y
        `Hogar` no pertenece a ningún hogar."""
        descubiertos = modelos_del_hogar()
        self.assertLessEqual(
            {"SolicitudEntrada", "PlanDeDia", "ProductoDespensa"},
            set(descubiertos),
            "el descubrimiento de modelos del hogar ha dejado de encontrar modelos que sí "
            f"debería (encontrados: {sorted(descubiertos)}) -- si esto falla, el test de "
            "abajo podría estar pasando en falso por no vigilar nada",
        )
        self.assertNotIn(
            "Entreno",
            descubiertos,
            "`Entreno` NO es un modelo del hogar: aísla por usuario (ver el docstring de "
            "`entrenos/models.py`, que avisa del comentario antiguo que dice lo contrario)",
        )
        self.assertNotIn("Hogar", descubiertos, "un hogar no pertenece a un hogar")
        for modelo, campos in descubiertos.items():
            self.assertIn(
                "hogar",
                campos,
                f"{modelo} hereda de ModeloDeHogar pero no se le ve el campo `hogar`: el "
                "check no sabría por dónde acotarlo",
            )

    def test_las_excepciones_no_se_comen_el_repositorio(self):
        """La otra mitad de la comprobación de la comprobación, y la que hace que R4 sea algo
        más que una promesa: si alguien amplía una excepción hasta tapar la lógica viva, el
        test de abajo se quedaría verde por vacío. Aquí se exige que los ficheros que HOY
        tienen consultas a un modelo del hogar sigan mirándose."""
        _, mirados = analizar_repositorio()
        no_mirados = FICHEROS_QUE_EL_CHECK_TIENE_QUE_MIRAR - set(mirados)
        self.assertEqual(
            set(),
            no_mirados,
            "las excepciones de EXCEPCIONES han dejado de mirar ficheros de lógica viva "
            f"({sorted(no_mirados)}): el check de abajo estaría pasando por no mirar, no por "
            "estar todo bien. Una excepción sin vigilancia es un agujero con permiso (R4)",
        )
        for rel in _ficheros_py():
            motivo = motivo_de_la_excepcion(rel)
            if motivo is not None:
                self.assertTrue(
                    motivo.strip(),
                    f"{rel} está excluido sin motivo escrito: R4 lo prohíbe expresamente",
                )

    def test_ninguna_consulta_rodea_la_puerta_del_hogar(self):
        infracciones, _ = analizar_repositorio()
        if infracciones:
            detalle = "\n".join(
                f"  - {rel}:{linea}: `{consulta}(...)` sobre el modelo del hogar {modelo}, "
                f"sin acotar por ninguno de {campos}"
                for rel, linea, modelo, consulta, campos in infracciones
            )
            self.fail(
                "Hay consultas a un modelo del hogar que NO dicen de qué hogar son: rodean la "
                f"puerta única ({PUERTA}) y pueden servir los datos de otra casa sin que nadie "
                f"se entere (R9, R14, Q-11, Q-20).\n{detalle}\n"
                "Sal por la puerta: `hogares.acceso.obtener_de_mi_hogar_o_404(request, "
                "<Modelo>, pk=...)` para UN objeto, o `<Modelo>.del_hogar(hogar)` para una "
                "lista. Si de verdad tienes que consultar sin acotar (una migración, un "
                "comando de mantenimiento), declara la excepción con su motivo en "
                "`EXCEPCIONES` de kcalibra/tests_aislamiento.py -- nunca en bloque."
            )
