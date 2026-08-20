r"""
El check permanente de la unidad 035: la red del `follow=True` que no puede fallar.

Tres unidades (027, 032, 034) cazaron a mano la misma forma de test que PARECE protección y no
lo es: `self.client.post(..., follow=True)` seguido de `self.assertEqual(respuesta.status_code,
200)`. Con `follow=True`, el formulario VÁLIDO redirige y el cliente sigue la redirección hasta
la pantalla de destino (200); el formulario INVÁLIDO repinta la misma pantalla con errores (200
también). **Las dos ramas terminan en 200 por construcción**: ese assert no puede fallar por el
motivo que dice proteger (22ª cara de `docs/conocimiento/tests-que-no-fallan-cuando-deben.md`).

Este fichero es el hermano de `kcalibra/tests_estilos.py` (015) y `kcalibra/tests_aislamiento.py`
(020): un check que vigila al EQUIPO, no al código de producción de hoy. Porta el escáner AST de
dos fases de la unidad 034 (FASE 1: descubre por comportamiento los "helpers" que esconden un
`follow=True` detrás de un nombre que no lo delata; FASE 2: con esos helpers, encuentra los
`assertEqual(<var>.status_code, 200)` que dependen de uno) y lo deja corriendo con la suite, con
una LÍNEA BASE cerrada de los 23 sitios que existen hoy, cada uno con el veredicto que la 034 le
dio por mutación (CUBIERTO: un assert vecino SÍ atrapa el fallo real; SANO: este mismo assert
cae en su propia línea). El check falla si el escaneo de hoy y esa lista dejan de coincidir EN
CUALQUIER SENTIDO: sitio nuevo sin medir, o entrada de la lista que ya no existe en el código.

Trampas ya pisadas al escribir esto (para quien lo toque después):

- **El escáner busca helpers por COMPORTAMIENTO, no por nombre.** La primera versión de la 034
  buscaba funciones con un patrón de nombre ("método `_algo`") y perdió un helper real,
  `planes/tests.py:apuntar`, que no lleva guion bajo (21ª cara: "la lista que TÚ MISMO
  regeneras también trae falsos negativos"). Este escáner define un helper como CUALQUIER
  función no-test que hace una llamada de cliente con `follow=True` y DEVUELVE el resultado
  (directo o vía variable) — sin mirar el nombre.
- **El arreglo de R4, en el sitio exacto donde la 034 dejó el límite escrito.** La FASE 2 de la
  034 solo reconocía `algo.helper(...)` (un `ast.Attribute`: `self.registrar(...)`), así que un
  helper de nivel de MÓDULO (`from ayuda_pruebas import algo` y `algo(...)` a secas, un
  `ast.Name`) lo descubría la FASE 1 y lo perdía la FASE 2 — el mismo falso negativo, un nivel
  más abajo, dentro de la propia herramienta. Aquí `_variables_con_follow_true` acepta las dos
  formas (`ast.Attribute` y `ast.Name`).
- **La clave de la línea base es `(fichero, test, variable)`, SIN línea.** Una clave por
  `fichero:línea` se rompería con cualquier edición de arriba del fichero y enseñaría a
  actualizar la lista sin leerla, que es como muere un guardián. El precio es que hay que
  comparar como MULTICONJUNTO (`collections.Counter`), no como conjunto: así, si alguien añade
  un SEGUNDO `assertEqual(<misma var>.status_code, 200)` dentro del mismo test, cuenta como
  sitio nuevo en vez de esconderse detrás de la entrada que ya cubre esa clave.
- **Este assert, con `follow=True` puesto, JAMÁS cubre por sí solo un resultado incorrecto —
  solo un crash (22ª cara).** El cliente de pruebas de Django comprueba si hubo una excepción
  señalada DESPUÉS de cada salto de la redirección, dentro de la propia llamada `.post()`/
  `.get()`: si hubo un 500, el test ya revienta como ERROR antes de llegar al `assertEqual`. Por
  eso un sitio puede estar "no desprotegido" sin que este assert sea quien lo cubre — el
  mensaje de fallo de este check explica esa diferencia y nunca declara un sitio nuevo cubierto
  solo por tener un `follow=True` detrás: pide medirlo por mutación.
- **No se persigue la familia hermana.** `assertContains` flojos, POST sin afirmar nada, guardas
  de carga sin red: son otras caras del mismo documento, con otro oráculo. Este fichero vigila
  EXACTAMENTE la forma `follow=True` + `assertEqual(status_code, 200)`.
"""

import ast
import os
from collections import Counter

from django.conf import settings
from django.test import SimpleTestCase

_CARPETAS_IGNORADAS = frozenset({".git", "__pycache__", ".venv", "venv", "node_modules", "staticfiles"})

# Los tres helpers que hoy esconden un follow=True: solo por NOMBRE, para el meta-check de R6.
# Sirve para saber que la FASE 1 sigue viva, no para sustituir el descubrimiento de la FASE 1.
HELPERS_CONOCIDOS = frozenset({"apuntar", "registrar", "registrar_y_verificar"})

# Ficheros de test que hoy tienen sitios de la familia: el barrido tiene que seguir viéndolos.
FICHEROS_DE_TEST_CONOCIDOS = frozenset(
    {
        os.path.join("cuentas", "tests.py"),
        os.path.join("cuentas", "ayuda_pruebas.py"),
        os.path.join("hogares", "tests_la_salida_del_borrado.py"),
        os.path.join("hogares", "tests_personas_de_la_casa.py"),
        os.path.join("planes", "tests.py"),
    }
)


def _ficheros_py(base):
    salida = []
    for carpeta, subcarpetas, nombres in os.walk(base):
        subcarpetas[:] = [
            s for s in subcarpetas if s not in _CARPETAS_IGNORADAS and not s.startswith(".")
        ]
        for nombre in nombres:
            if nombre.endswith(".py"):
                salida.append(os.path.relpath(os.path.join(carpeta, nombre), base))
    return sorted(salida)


def _tiene_follow_true(llamada):
    return any(
        kw.arg == "follow" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in llamada.keywords
    )


def _es_llamada_de_cliente(nodo):
    """¿Es esto una llamada tipo `self.client.get(...)`/`self.client.post(...)`/
    `cliente.get(...)`? No exige el nombre exacto `client`: basta con que sea un `Call` cuyo
    `func` es un `Attribute` con nombre de método HTTP habitual."""
    return (
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr in {"get", "post", "put", "patch", "delete"}
    )


def _arbol_de(rel, raiz):
    with open(os.path.join(raiz, rel), encoding="utf-8") as f:
        fuente = f.read()
    return ast.parse(fuente, filename=rel)


def descubrir_helpers(raiz):
    """FASE 1 — enumeración EXHAUSTIVA de "helpers": toda función NO-test (su nombre no empieza
    por `test_`, y no es `setUp`/`setUpClass`/`setUpTestData` — esos no DEVUELVEN nada, no
    pueden alimentar un assert) que hace una llamada tipo `self.client.<verbo>(..., follow=True)`
    o `self.<algo>.<verbo>(..., follow=True)` Y la DEVUELVE (`return <esa llamada>` o
    `return <variable asignada desde ella>`). Por COMPORTAMIENTO, no por el nombre de la
    función: así un cuarto helper que aparezca mañana no se pierde por no coincidir con un
    patrón de nombre escrito de memoria (21ª cara)."""
    helpers = {}
    for rel in _ficheros_py(raiz):
        try:
            arbol = _arbol_de(rel, raiz)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for func in ast.walk(arbol):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if func.name.startswith("test_") or func.name in ("setUp", "setUpClass", "setUpTestData"):
                continue

            variables_follow = set()
            llamadas_directas_follow = []
            for nodo in ast.walk(func):
                if (
                    isinstance(nodo, ast.Assign)
                    and len(nodo.targets) == 1
                    and isinstance(nodo.targets[0], ast.Name)
                ):
                    if _es_llamada_de_cliente(nodo.value) and _tiene_follow_true(nodo.value):
                        variables_follow.add(nodo.targets[0].id)
                if _es_llamada_de_cliente(nodo) and _tiene_follow_true(nodo):
                    llamadas_directas_follow.append(nodo)
            if not variables_follow and not llamadas_directas_follow:
                continue

            devuelve = False
            for nodo in ast.walk(func):
                if not isinstance(nodo, ast.Return) or nodo.value is None:
                    continue
                if isinstance(nodo.value, ast.Name) and nodo.value.id in variables_follow:
                    devuelve = True
                if _es_llamada_de_cliente(nodo.value) and _tiene_follow_true(nodo.value):
                    devuelve = True

            if devuelve:
                helpers.setdefault(func.name, []).append(f"{rel}:{func.lineno}")
    return helpers


def _variables_con_follow_true(func_node, nombres_helper):
    """Las variables de `func_node` que vienen de una llamada directa con `follow=True` o de uno
    de los helpers descubiertos en la FASE 1.

    ARREGLO DE R4: un helper se puede llamar como `self.helper(...)` (`valor.func` es un
    `ast.Attribute`, la única forma que reconocía la 034) o como `helper(...)` a secas —un
    helper de nivel de MÓDULO importado (`valor.func` es un `ast.Name`)—. La 034 solo miraba la
    primera forma y perdía el segundo caso, aunque la FASE 1 ya lo hubiera descubierto: el mismo
    falso negativo que motivó toda la unidad, un nivel más abajo dentro de la propia
    herramienta. Aquí se aceptan las dos."""
    variables = set()
    for nodo in ast.walk(func_node):
        if (
            isinstance(nodo, ast.Assign)
            and len(nodo.targets) == 1
            and isinstance(nodo.targets[0], ast.Name)
        ):
            valor = nodo.value
            if _es_llamada_de_cliente(valor) and _tiene_follow_true(valor):
                variables.add(nodo.targets[0].id)
            elif isinstance(valor, ast.Call) and (
                (isinstance(valor.func, ast.Attribute) and valor.func.attr in nombres_helper)
                or (isinstance(valor.func, ast.Name) and valor.func.id in nombres_helper)
            ):
                variables.add(nodo.targets[0].id)
    return variables


def _es_status_code_200(nodo_assert):
    if not isinstance(nodo_assert, ast.Call):
        return None
    if not isinstance(nodo_assert.func, ast.Attribute) or nodo_assert.func.attr != "assertEqual":
        return None
    args = nodo_assert.args
    if len(args) < 2:
        return None
    a, b = args[0], args[1]

    def es_status_code_attr(x):
        return isinstance(x, ast.Attribute) and x.attr == "status_code"

    def es_200(x):
        return isinstance(x, ast.Constant) and x.value == 200

    var = None
    if es_status_code_attr(a) and es_200(b):
        var = a.value
    elif es_status_code_attr(b) and es_200(a):
        var = b.value
    else:
        return None
    return var.id if isinstance(var, ast.Name) else "<expresion-no-variable>"


def sitios_de_hoy(raiz):
    """FASE 2 — con los helpers de la FASE 1, recorre cada método de test y devuelve una lista
    de tuplas `(fichero, línea, test, variable)`: los sitios `follow=True` +
    `assertEqual(<var>.status_code, 200)` que existen HOY en el repo."""
    helpers = descubrir_helpers(raiz)
    resultados = []
    for rel in _ficheros_py(raiz):
        try:
            arbol = _arbol_de(rel, raiz)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for func in ast.walk(arbol):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            variables_follow = _variables_con_follow_true(func, helpers.keys())
            if not variables_follow:
                continue
            for nodo in ast.walk(func):
                if (
                    isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Attribute)
                    and nodo.func.attr == "assertEqual"
                ):
                    var = _es_status_code_200(nodo)
                    if var is not None and var in variables_follow:
                        resultados.append((rel, nodo.lineno, func.name, var))
    return sorted(resultados)


# LÍNEA BASE — los 23 sitios medidos por la unidad 034 contra `main` en `d43f664`, cada uno con
# su veredicto por MUTACIÓN (nunca por lectura): CUBIERTO = un assert vecino (u otra excepción
# que sube antes de llegar al assertEqual) es quien de verdad atrapa el fallo; SANO = este mismo
# assertEqual cae en SU PROPIA línea. Clave `(fichero, test, variable)`, sin línea (R2): una
# edición de arriba del fichero no debe forzar tocar esta lista. Fuente: hallazgos.md de la
# unidad 034 (docs/05-trabajo/archivo/034-.../hallazgos.md), tabla R2/R3.
LINEA_BASE = (
    (os.path.join("cuentas", "tests.py"), "test_con_registro_cerrado_no_se_crea_ninguna_cuenta", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_cambiar_la_contrasena_cierra_las_demas_sesiones", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_fallo_al_dar_de_alta_no_deja_una_cuenta_atrapada", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_fallo_al_dar_de_alta_no_deja_una_cuenta_atrapada", "respuesta_reenvio", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_fallo_al_dar_de_alta_no_deja_una_cuenta_atrapada", "respuesta_reenvio_bueno", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_fallo_de_red_generico_tampoco_tumba_el_alta", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_fallo_al_reenviar_no_da_un_500", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_fallo_al_corregir_no_da_un_500", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_pedir_recuperacion_y_usarla_deja_entrar_con_la_nueva", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_pedir_recuperacion_y_usarla_deja_entrar_con_la_nueva", "respuesta_cambio", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_tras_pasarla_ya_se_puede_borrar_la_cuenta", "respuesta", "CUBIERTO"),
    (os.path.join("cuentas", "tests.py"), "test_tras_borrarla_ya_se_puede_borrar_la_cuenta", "respuesta", "CUBIERTO"),
    (os.path.join("hogares", "tests_la_salida_del_borrado.py"), "test_marta_conserva_su_ficha_y_todo_su_historico", "respuesta", "CUBIERTO"),
    (os.path.join("hogares", "tests_la_salida_del_borrado.py"), "test_borrarla_se_lleva_la_ficha_y_todo_su_historico", "respuesta", "CUBIERTO"),
    (os.path.join("hogares", "tests_la_salida_del_borrado.py"), "test_a_otra_persona_a_cargo_se_rechaza", "respuesta", "SANO"),
    (os.path.join("hogares", "tests_la_salida_del_borrado.py"), "test_a_si_mismo_tambien_se_rechaza", "respuesta", "SANO"),
    (os.path.join("hogares", "tests_la_salida_del_borrado.py"), "test_no_revienta_y_da_un_mensaje_en_cristiano", "respuesta", "CUBIERTO"),
    (os.path.join("hogares", "tests_personas_de_la_casa.py"), "test_no_se_borra_la_cuenta_ni_se_pierde_nada_de_euridice", "respuesta", "CUBIERTO"),
    (os.path.join("hogares", "tests_personas_de_la_casa.py"), "test_sin_nadie_a_cargo_se_borra_sin_mas_preguntas", "respuesta", "CUBIERTO"),
    (os.path.join("planes", "tests.py"), "test_alejandro_le_apunta_la_cena_a_euridice", "respuesta", "SANO"),
    (os.path.join("planes", "tests.py"), "test_calorias_negativas_se_rechazan", "respuesta", "CUBIERTO"),
    (os.path.join("planes", "tests.py"), "test_macro_negativo_se_rechaza", "respuesta", "CUBIERTO"),
    (os.path.join("planes", "tests.py"), "test_una_comida_sin_nombre_se_rechaza", "respuesta", "CUBIERTO"),
)


class NingunAssertQueNoPuedeFallarSeCuelaSinMedirTests(SimpleTestCase):
    """El check de la unidad 035: ningún sitio nuevo de la familia `follow=True` +
    `assertEqual(status_code, 200)` puede colarse sin que alguien lo mida y lo dé de alta con su
    veredicto. No toca la base de datos (`SimpleTestCase`): lee los `.py` del repo, igual que
    `tests_estilos.py` lee las plantillas y `tests_aislamiento.py` lee los modelos."""

    databases = set()

    def test_no_desaparecen_los_helpers_ni_los_ficheros_conocidos(self):
        """Comprobación de la propia comprobación (R6, patrón de `tests_estilos.py`): si el
        descubrimiento de helpers (FASE 1) o el barrido de ficheros se rompiera, "no encuentro
        nada" sería indistinguible de "todo correcto" -- el fallo de la 015, ya pagado. NO fija
        un suelo cerrado (prohibir que aparezcan MÁS helpers o ficheros pondría la suite en rojo
        el día que llegue un cuarto helper legítimo): exige que los tres helpers y los cinco
        ficheros conocidos de HOY sigan encontrándose SIEMPRE, sin prohibir que aparezcan más."""
        helpers = descubrir_helpers(str(settings.BASE_DIR))
        faltantes_helpers = HELPERS_CONOCIDOS - set(helpers)
        self.assertLessEqual(
            HELPERS_CONOCIDOS,
            set(helpers),
            "la FASE 1 (descubrir_helpers) ha dejado de encontrar helpers que sí debería "
            f"(desaparecidos: {sorted(faltantes_helpers)}) -- si esto falla, el test de la "
            "lista exacta podría estar pasando en falso: un helper perdido esconde todos los "
            "sitios que cuelgan de él",
        )

        ficheros = set(_ficheros_py(str(settings.BASE_DIR)))
        faltantes_ficheros = FICHEROS_DE_TEST_CONOCIDOS - ficheros
        self.assertLessEqual(
            FICHEROS_DE_TEST_CONOCIDOS,
            ficheros,
            "el barrido de ficheros .py ha dejado de encontrar ficheros de test que sí debería "
            f"(desaparecidos: {sorted(faltantes_ficheros)}) -- 'no encuentro nada' es "
            "indistinguible de 'todo correcto'",
        )

    def test_la_lista_de_hoy_coincide_exactamente_con_lo_escaneado(self):
        encontrados = sitios_de_hoy(str(settings.BASE_DIR))
        lineas_por_clave = {}
        for fichero, linea, test, variable in encontrados:
            lineas_por_clave.setdefault((fichero, test, variable), []).append(linea)

        conteo_encontrados = Counter((fichero, test, variable) for fichero, _, test, variable in encontrados)
        conteo_base = Counter((fichero, test, variable) for fichero, test, variable, _ in LINEA_BASE)

        nuevos = conteo_encontrados - conteo_base
        if nuevos:
            detalle = "\n".join(
                f"  - {fichero}:{','.join(str(l) for l in lineas_por_clave[(fichero, test, variable)])} "
                f"en {test}(), variable `{variable}`"
                for fichero, test, variable in sorted(nuevos.elements())
            )
            self.fail(
                "Hay sitio(s) NUEVOS de la familia follow=True + assertEqual(<var>.status_code, "
                "200) que nadie ha medido todavía:\n" + detalle + "\n\n"
                "Con follow=True, el formulario VÁLIDO redirige y termina en 200; el INVÁLIDO "
                "repinta la pantalla con errores y también da 200: las dos ramas terminan en "
                "200 por construcción, así que este assert no puede fallar por el motivo que "
                "dice proteger. Y si lo que temes es un 500: ese crash ya revienta como ERROR "
                "dentro de la propia llamada .post()/.get(), antes de llegar a este "
                "assertEqual -- así que el assert tampoco es quien lo cazaría.\n\n"
                "Dos salidas legítimas:\n"
                "  (a) cambia el assert por uno que afirme la CONSECUENCIA -- que el dato "
                "exista, que la página lleve lo suyo -- la cura que ya aplicaron la 030 y la "
                "032; o\n"
                "  (b) si de verdad este sitio atrapa algo, mídelo por MUTACIÓN (rompe lo que "
                "el test dice proteger y comprueba EN QUÉ LÍNEA cae la suite) y date de alta en "
                "LINEA_BASE de este fichero con tu veredicto: CUBIERTO si cae en otra línea, "
                "SANO si cae en esta misma. Nunca lo declares CUBIERTO solo porque hay un "
                "follow=True detrás -- eso, como mucho, explica por qué no está desprotegido, "
                "nunca prueba que lo esté."
            )

        desaparecidos = conteo_base - conteo_encontrados
        if desaparecidos:
            detalle = "\n".join(
                f"  - {fichero} / {test}() / variable `{variable}`"
                for fichero, test, variable in sorted(desaparecidos.elements())
            )
            self.fail(
                "Hay entrada(s) en LINEA_BASE de este fichero que el escaneo de hoy ya NO "
                "encuentra en el código:\n" + detalle + "\n\n"
                "La lista dejó de decir la verdad: pódala. Borra la(s) entrada(s) de "
                "LINEA_BASE. Si el sitio se movió de test o cambió de nombre de variable, es "
                "una poda más un alta -- la clave (fichero, test, variable) es otra."
            )
