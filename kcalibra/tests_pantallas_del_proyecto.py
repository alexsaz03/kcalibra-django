r"""
La red PERMANENTE de la unidad 059 (la-red-que-vigila-todas-las-pantallas.md): la única red que
recorre el PROYECTO ENTERO, no una unidad. Antes de esta unidad, cada peldaño de la escalera
visual (050 → 053 → 057 → 054) derivó sus propias reglas sobre su propia lista de pantallas
escrita a mano — y una plantilla que nace fuera de esas listas no la vigila nadie (medido sobre
`48c939d`: el `<p>` de ayuda sin `id` seguía vivo en cuatro plantillas que la 054 acababa de
reescribir).

**La definición de caso sale del árbol, no de una lista** (R1): una pantalla es cualquier
plantilla que hace `{% extends "base.html" %}`, hallada recorriendo los directorios que LOS
CARGADORES de Django buscan de verdad (`engine.dirs` + `get_app_template_dirs("templates")` —
el mismo mecanismo que usa el loader de `app_directories`), no un `os.walk` a mano sobre el
repositorio ni, mucho menos, una lista de 25 rutas escritas aquí. Nadie tiene que apuntar una
pantalla nueva en ningún sitio (26ª cara,
docs/conocimiento/tests-que-no-fallan-cuando-deben.md): lo único que se declara, uno por uno y
por escrito, es el INCUMPLIMIENTO — `EXCEPCIONES`, más abajo, la lista que solo puede encoger
(R8, el trinquete).

Los ayudantes pesados (el parser de ramas de `{% block titulo_grande %}`, el detector de copia
de piezas de `_ui.html`, el barrido de `.cifra` sobre HTML renderizado, la alcanzabilidad) se
IMPORTAN de `kcalibra.tests_pantallas`/`kcalibra.tests_pantallas_de_la_casa`/
`kcalibra.ayuda_de_alcanzabilidad`/`kcalibra.tests_nada_escondido`, nunca se copian: son la
misma máquina que ya se endureció contra los mismos agujeros vuelta a vuelta, y copiarla a mano
es exactamente el error que costó siete agujeros a la 053 con la de alcanzabilidad (27ª cara).

R9 manda en esta unidad: cada criterio de R2 a R7 se prueba por MUTACIÓN, y la mutación va
pegada junto a su salida roja en `hallazgos.md` — un criterio sin su rojo demostrado no cuenta
como hecho. Varios de los criterios de abajo llevan, además, su propia mutación EN CÓDIGO (sobre
una plantilla de usar y tirar, nunca sobre un fichero real del repositorio): así el rojo queda
demostrado en cada corrida futura de la suite, no solo en la evidencia pegada de hoy.
"""

import re
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.template import engines
from django.template.utils import get_app_template_dirs
from django.test import Client, SimpleTestCase

from cuentas.ayuda_pruebas import PruebaConRegistroAbierto
from despensa.logica import _PALABRA_DE_UNIDAD, _PLURAL_SI_NO_ES_UNA
from despensa.models import UNIDADES
from hogares.models import Persona, SolicitudEntrada
from recetas.models import Receta

import kcalibra.tests_pantallas as _tests_pantallas
import kcalibra.tests_pantallas_de_la_casa as _tests_pantallas_de_la_casa
from kcalibra.ayuda_de_alcanzabilidad import atributos
from kcalibra.tests_nada_escondido import _rutas_enlazadas
from kcalibra.tests_pantallas import (
    _CLASE_CON_ETIQUETA_RE,
    _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE,
    _PALETA_VIEJA_RE,
    _VARIABLE_DE_DJANGO_RE,
    _NumerosDeDatoEnElTexto,
    _algun_elemento_de_la_cadena_lleva_cifra,
    _con_procedencia_marcada,
    _texto,
)
from kcalibra.tests_pantallas_de_la_casa import (
    _BLOQUE_TITULO_GRANDE_RE,
    _todo_lo_que_titulo_grande_puede_pintar_lleva_un_h1,
)

# Dos piezas que solo viven como atributos de CLASE en otros ficheros de test, leídas a través
# del MÓDULO (`import kcalibra.tests_pantallas as _tests_pantallas`, arriba) y no con
# `from … import NombreDeLaClase`: importar la clase por su nombre la deja como atributo de
# ESTE módulo, y `manage.py test` la volvería a descubrir y a CORRER aquí también — un duplicado
# silencioso de toda su suite. Solo se importa lo que hace falta (el dict/la función), nunca la
# clase entera.
#
# `_FIRMAS_DE_CLASE_POR_PIEZA`/`_copia_el_marcado_de_la_pieza` — la misma firma que ya vigila
# `kcalibra/tests_pantallas.py`, con las tres piezas que el paso 8 de esta unidad añadió (`chip`,
# `fila_lista_abre`, `boton_enlace`).
_FIRMAS_DE_CLASE_POR_PIEZA = _tests_pantallas.R7_PiezasCompartidasUnaSolaVezTests._FIRMAS_DE_CLASE_POR_PIEZA
_copia_el_marcado_de_la_pieza = _tests_pantallas.R7_PiezasCompartidasUnaSolaVezTests._copia_el_marcado_de_la_pieza

# `perfiles/ver.html` imprime "Proteína: <strong>N g</strong>" (y Grasa/Carbohidratos) SIN
# `.cifra` en el `<strong>`, a propósito — `perfiles/tests.py` (unidad 004, fuera de `ficheros:`
# de esta unidad) exige el literal EXACTO `<strong>136 g</strong>`, así que un `class="cifra"`
# ahí rompería ese assert. La 054 ya midió y firmó esta excepción (hallazgos.md); se importa su
# comprobación, no se re-deduce.
_es_la_excepcion_de_perfiles_sobre_r6 = (
    _tests_pantallas_de_la_casa.R6_CifraEnLosNumerosDeDatoTests._es_la_excepcion_de_r3_sobre_r6
)

BASE_DIR = Path(settings.BASE_DIR)


# ------------------------------------------------------------------------------------------ #
# R1 — la definición de caso: pantalla = plantilla que Django ve Y que extiende `base.html`.
# ------------------------------------------------------------------------------------------ #


def _directorios_que_django_ve():
    """Los directorios donde Django busca una plantilla de verdad: el `DIRS` del motor (aquí,
    `templates/` en la raíz) más el `templates/` de cada app instalada — este segundo grupo es
    LITERALMENTE lo que consulta el loader de `django.template.loaders.app_directories`
    (`get_app_template_dirs`, la misma función que usa por dentro), no una réplica a mano de su
    lógica. No hay un tercer sitio: cualquier plantilla que Django pueda cargar por nombre vive
    en uno de estos dos grupos."""
    motor = engines["django"].engine
    return [Path(d) for d in motor.dirs] + [Path(d) for d in get_app_template_dirs("templates")]


def _todas_las_plantillas_html(directorios=None):
    """Todo fichero `.html` bajo los directorios que Django ve — se recorre DENTRO de esos
    directorios (nunca el repositorio entero a ciegas: eso tragaría `static/`, `.venv/`,
    migraciones…), y el conjunto de directorios no lo elige esta función, lo elige Django."""
    vistas = {}
    for directorio in (directorios if directorios is not None else _directorios_que_django_ve()):
        directorio = Path(directorio)
        if not directorio.is_dir():
            continue
        for ruta in directorio.rglob("*.html"):
            vistas[ruta.resolve()] = ruta
    return sorted(vistas.values())


_EXTENDS_BASE_RE = re.compile(r'\{%\s*extends\s+["\']base\.html["\']\s*%\}')


def _es_pantalla(ruta):
    """Una PANTALLA es una plantilla que hace `{% extends "base.html" %}` — la propia
    convención del proyecto (verificado: las 25 de hoy lo escriben así, literal, en su primera
    línea). Los seis trozos sueltos (`_ui.html`, `_iconos.html`, `_grafica.html`,
    `_fila_ingrediente.html`, `_pregunta_pendiente.html`, `password_reset_help_text.html`) y
    `base.html` mismo no extienden nada y caen fuera solos, sin excluirlos a mano."""
    return bool(_EXTENDS_BASE_RE.search(_texto(ruta)))


def pantallas_vigiladas(directorios=None):
    """Las pantallas de HOY — recalculado en cada corrida, nunca cacheado en una lista. Una
    plantilla nueva que extienda `base.html` entra sola; una que se borre sale sola."""
    return [r for r in _todas_las_plantillas_html(directorios) if _es_pantalla(r)]


def _nombre_de_plantilla(ruta):
    """El nombre con el que DJANGO conoce esta plantilla (`"paginas/inicio.html"`, el que
    aparece en `{% extends %}`/`response.templates`) — la ruta relativa al directorio de
    búsqueda que la contiene, no la ruta relativa al repositorio (que además incluye
    `.../templates/...` por el medio)."""
    for directorio in _directorios_que_django_ve():
        directorio = Path(directorio)
        try:
            return str(ruta.relative_to(directorio)).replace("\\", "/")
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------------------------------ #
# R8 (el trinquete) — la lista de excepciones: EXACTA, no generosa, y solo puede encoger.
# ------------------------------------------------------------------------------------------ #

# Las diez pantallas que la 055 va a migrar (medido sobre `48c939d`, "Contexto para el
# constructor" de la especificación de esta unidad): las nueve de `templates/account/`
# (allauth) más `cuentas/esperando_verificacion.html` — la propia pantalla de la app que
# también arrastra la paleta vieja porque nace desde el mismo flujo de alta. NINGUNA MÁS: R8
# vigila, una a una, que las diez SIGAN incumpliendo — el día que la 055 cure alguna, sacarla de
# aquí es parte de cerrar esa unidad, no de esta.
EXCEPCIONES = frozenset({
    # --- Las nueve de allauth (unidad 055) ---
    "templates/account/login.html",
    "templates/account/logout.html",
    "templates/account/password_change.html",
    "templates/account/password_reset.html",
    "templates/account/password_reset_done.html",
    "templates/account/password_reset_from_key.html",
    "templates/account/password_reset_from_key_done.html",
    "templates/account/signup.html",
    "templates/account/email_confirm.html",
    # --- La propia de cuentas, migra junto a las de allauth (misma unidad 055) ---
    "cuentas/templates/cuentas/esperando_verificacion.html",
})


def _pantallas_reales_hoy():
    """Las vigiladas de HOY menos las `EXCEPCIONES` declaradas — sobre estas quince (hoy) corre
    el barrido POSITIVO de R2/R3/R4 más abajo; las excepciones se vigilan al revés, en R8."""
    excepciones_absolutas = {(BASE_DIR / e).resolve() for e in EXCEPCIONES}
    return [p for p in pantallas_vigiladas() if p not in excepciones_absolutas]


# ------------------------------------------------------------------------------------------ #
# Los tres chequeos ESTÁTICOS (sobre el fichero fuente, sin renderizar nada) que R2/R3/R4
# comparten con R8: una pantalla "incumple" si cualquiera de los tres dice que sí.
# ------------------------------------------------------------------------------------------ #


def _incumple_r2(ruta):
    """R2 — `{% block titulo_grande %}` sin llenar, o alguna de sus ramas sin `<h1>` de
    verdad. Reutiliza el parser de ramas que la 054 escribió para cerrar su hueco H3 (importado,
    no copiado): recorre el cuerpo del bloque tramo a tramo por profundidad de `{% if %}`, no
    con una búsqueda de subcadena sobre el bloque entero — así una rama `{% else %}` sin su
    propio `<h1>` no se esconde detrás del `<h1>` que sí trae la rama `{% if %}`."""
    coincidencia = _BLOQUE_TITULO_GRANDE_RE.search(_texto(ruta))
    if coincidencia is None:
        return True
    return not _todo_lo_que_titulo_grande_puede_pintar_lleva_un_h1(coincidencia.group("cuerpo"))


def _incumple_r3(ruta):
    """R3 — queda algún `emerald-*`/`slate-*` en el fichero fuente."""
    return bool(_PALETA_VIEJA_RE.search(_texto(ruta)))


def _piezas_copiadas(ruta):
    """Las piezas de `_ui.html` cuyo marcado aparece PEGADO A MANO en `ruta`, detectadas con la
    MISMA máquina que ya vigila `kcalibra/tests_pantallas.py` (importada: `_CLASE_CON_ETIQUETA_RE`
    normaliza `{% %}`/`{# #}` antes de leer cada `class="…"`, cuenta los `{{ … }}` que queden
    como comodines, y compara por FIRMA de tokens — nunca por subcadena fija)."""
    contenido = _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE.sub("", _texto(ruta))
    encontradas = set()
    for coincidencia in _CLASE_CON_ETIQUETA_RE.finditer(contenido):
        etiqueta = coincidencia.group("etiqueta").lower()
        clases_crudas = coincidencia.group("clases")
        comodines = len(_VARIABLE_DE_DJANGO_RE.findall(clases_crudas))
        clases = set(_VARIABLE_DE_DJANGO_RE.sub(" ", clases_crudas).split())
        for pieza, candidatas in _FIRMAS_DE_CLASE_POR_PIEZA.items():
            if _copia_el_marcado_de_la_pieza(etiqueta, clases, candidatas, comodines):
                encontradas.add(pieza)
    return encontradas


def _incumple_r4(ruta):
    return bool(_piezas_copiadas(ruta))


def _incumple_algo_estatico(ruta):
    return _incumple_r2(ruta) or _incumple_r3(ruta) or _incumple_r4(ruta)


# ------------------------------------------------------------------------------------------ #
# R1 — la lista sale del árbol: se demuestra creando una pantalla nueva (sin apuntarla en
# ningún sitio) y, al revés, borrando una existente.
# ------------------------------------------------------------------------------------------ #


class R1_LaListaDePantallasSaleDelArbolTests(SimpleTestCase):
    databases = set()

    def test_hoy_hay_veinticinco_pantallas_y_las_diez_excepciones_siguen_siendolo(self):
        """Número de control (evidencia de que el barrido corre, no una lista que sustituya al
        árbol) — y la mitad que de verdad importa para R8: cada excepción declarada tiene que
        SER una pantalla real hoy. Si una dejara de existir (o de extender `base.html`), la
        excepción sería papel muerto y R8 no podría ni comprobarla: sácala de la lista, no la
        dejes envejecer."""
        pantallas = pantallas_vigiladas()
        nombres = {str(p.relative_to(BASE_DIR)) for p in pantallas}
        self.assertEqual(len(pantallas), len(nombres), "hay una plantilla contada dos veces")
        self.assertEqual(len(pantallas), 25, f"se esperaban 25 pantallas hoy, salieron: {sorted(nombres)}")
        for excepcion in EXCEPCIONES:
            self.assertIn(excepcion, nombres, f"la excepción «{excepcion}» ya no es una pantalla real: sácala de EXCEPCIONES")

    def test_una_plantilla_nueva_que_incumple_pone_la_suite_roja_sin_apuntarla_en_ningun_sitio(self):
        """R1, el que resuelve el encargo entero: una plantilla de usar y tirar, creada DENTRO
        del test — nunca en el repositorio de verdad — entra al barrido sola, sin que nadie la
        haya escrito en `EXCEPCIONES` ni en ninguna lista, y R2 la caza."""
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp) / "paginas" / "templates" / "paginas"
            directorio.mkdir(parents=True)
            plantilla_rota = directorio / "prueba_de_usar_y_tirar_059.html"
            plantilla_rota.write_text(
                '{% extends "base.html" %}\n'
                '{% block titulo_grande %}<div>Sin h1 de verdad</div>{% endblock %}\n'
            )
            pantallas = pantallas_vigiladas([Path(tmp)])
            self.assertEqual(
                [p.name for p in pantallas], [plantilla_rota.name],
                "la plantilla nueva no entró al barrido: la definición de caso no sale del árbol",
            )
            self.assertTrue(
                _incumple_r2(plantilla_rota),
                "la plantilla rota (su <h1> mudado a <div>) debía incumplir R2 y no lo hizo: "
                "la red no la está vigilando de verdad, solo la está contando",
            )

    def test_borrar_una_pantalla_existente_la_saca_del_barrido_sola(self):
        """R1 al revés: nadie mantiene una lista de la que haya que TACHAR una pantalla borrada
        — desaparece del barrido sin tocar ningún código, porque el barrido nunca la memorizó."""
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp) / "paginas" / "templates" / "paginas"
            directorio.mkdir(parents=True)
            a = directorio / "pantalla_a.html"
            b = directorio / "pantalla_b.html"
            for plantilla in (a, b):
                plantilla.write_text(
                    '{% extends "base.html" %}\n{% block titulo_grande %}<h1>Hola</h1>{% endblock %}\n'
                )
            antes = {p.name for p in pantallas_vigiladas([Path(tmp)])}
            self.assertEqual(antes, {"pantalla_a.html", "pantalla_b.html"})
            b.unlink()
            despues = {p.name for p in pantallas_vigiladas([Path(tmp)])}
            self.assertEqual(
                despues, {"pantalla_a.html"},
                "borrar un fichero debía encoger el barrido solo, sin editar ninguna lista",
            )


# ------------------------------------------------------------------------------------------ #
# R8 — el trinquete: cada excepción listada tiene que SEGUIR incumpliendo algo. Si una ya
# cumple y sigue en la lista, la suite se pone roja — así arreglar una pantalla obliga a
# sacarla de aquí, y la lista solo puede encoger.
# ------------------------------------------------------------------------------------------ #


class R8_LaListaDeExcepcionesSoloPuedeEncogerTests(SimpleTestCase):
    databases = set()

    def test_cada_excepcion_sigue_incumpliendo_algo(self):
        cumplen_ya = []
        for relativa in sorted(EXCEPCIONES):
            ruta = BASE_DIR / relativa
            if not _incumple_algo_estatico(ruta):
                cumplen_ya.append(relativa)
        self.assertEqual(
            cumplen_ya, [],
            f"estas excepciones ya NO incumplen nada y siguen en la lista — sácalas de "
            f"EXCEPCIONES, dejarlas es el fraude que R8 existe para impedir: {cumplen_ya}",
        )

    def test_una_excepcion_que_deja_de_incumplir_pone_la_suite_roja(self):
        """El trinquete demostrado con una mutación EN CÓDIGO, no solo con la observación de
        arriba: una copia de `login.html` con la paleta vieja QUITADA (sin `<h1>` de verdad
        tampoco haría falta, basta con curar UN criterio) simula la pantalla ya migrada — y
        si, a pesar de estar arreglada, siguiera figurando en `EXCEPCIONES`, `_incumple_algo_estatico`
        tiene que decir `False` para que el test de arriba la cace."""
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp) / "cuentas" / "templates" / "cuentas"
            directorio.mkdir(parents=True)
            plantilla_migrada = directorio / "ya_no_incumple.html"
            plantilla_migrada.write_text(
                '{% extends "base.html" %}\n'
                '{% block titulo_grande %}<h1>Ya migrada</h1>{% endblock %}\n'
                '{% block content %}<p class="text-tinta">sin paleta vieja, sin piezas copiadas</p>{% endblock %}\n'
            )
            self.assertFalse(
                _incumple_algo_estatico(plantilla_migrada),
                "la plantilla del control debía cumplir TODO para que la mutación signifique algo",
            )
            # Si esta pantalla, ya arreglada, estuviera en EXCEPCIONES, el bucle de
            # `test_cada_excepcion_sigue_incumpliendo_algo` la habría añadido a `cumplen_ya` —
            # se reproduce aquí la misma comprobación, sin depender de editar la constante real.
            cumplen_ya = [] if _incumple_algo_estatico(plantilla_migrada) else ["ya_no_incumple.html"]
            self.assertEqual(
                cumplen_ya, ["ya_no_incumple.html"],
                "una excepción arreglada tiene que aparecer como 'ya no incumple': si no, el "
                "trinquete no la habría cazado",
            )


# ------------------------------------------------------------------------------------------ #
# R2, R3, R4 — el barrido positivo sobre las quince pantallas reales de hoy.
# ------------------------------------------------------------------------------------------ #


class R2_TituloGrandeConHEnCualquierRamaTests(SimpleTestCase):
    databases = set()

    def test_ninguna_pantalla_real_incumple_r2(self):
        incumplen = [str(r.relative_to(BASE_DIR)) for r in _pantallas_reales_hoy() if _incumple_r2(r)]
        self.assertEqual(incumplen, [], f"sin <h1> de verdad en alguna rama de titulo_grande: {incumplen}")

    def test_mutacion_una_rama_sin_h1_se_pone_roja(self):
        """R9 en código: el MISMO parser de ramas que vigila las 15 reales, puesto a prueba
        contra una plantilla sintética con dos ramas donde solo UNA trae su `<h1>` — tiene que
        decir que SÍ incumple (26ª/27ª cara: una firma o un parser que nunca se ha visto fallar
        es decoración)."""
        cuerpo_con_una_rama_sin_h1 = (
            '{% if algo %}<h1>Con título</h1>{% else %}<div>Sin título de verdad</div>{% endif %}'
        )
        self.assertFalse(_todo_lo_que_titulo_grande_puede_pintar_lleva_un_h1(cuerpo_con_una_rama_sin_h1))
        cuerpo_con_las_dos_ramas = (
            '{% if algo %}<h1>Con título</h1>{% else %}<h1>También con título</h1>{% endif %}'
        )
        self.assertTrue(_todo_lo_que_titulo_grande_puede_pintar_lleva_un_h1(cuerpo_con_las_dos_ramas))


class R3_SinPaletaViejaTests(SimpleTestCase):
    databases = set()

    def test_ninguna_pantalla_real_conserva_emerald_ni_slate(self):
        con_paleta_vieja = {}
        for ruta in _pantallas_reales_hoy():
            hallazgos = _PALETA_VIEJA_RE.findall(_texto(ruta))
            if hallazgos:
                con_paleta_vieja[str(ruta.relative_to(BASE_DIR))] = hallazgos
        self.assertEqual(con_paleta_vieja, {}, f"quedan clases de la paleta vieja: {con_paleta_vieja}")

    def test_mutacion_reintroducir_un_token_viejo_se_pone_rojo(self):
        self.assertFalse(_PALETA_VIEJA_RE.search('<p class="text-tinta-media">bien</p>'))
        self.assertTrue(_PALETA_VIEJA_RE.search('<p class="text-slate-500">reintroducido</p>'))
        self.assertTrue(_PALETA_VIEJA_RE.search('<div class="bg-emerald-50">reintroducido</div>'))


class R4_NingunaPiezaCopiadaAManoTests(SimpleTestCase):
    databases = set()

    def test_ninguna_pantalla_real_copia_el_marcado_de_ninguna_pieza(self):
        con_copias = {}
        for ruta in _pantallas_reales_hoy():
            piezas = _piezas_copiadas(ruta)
            if piezas:
                con_copias[str(ruta.relative_to(BASE_DIR))] = sorted(piezas)
        self.assertEqual(con_copias, {}, f"pantallas que copian una pieza en vez de incluirla: {con_copias}")

    def test_mutacion_pegar_una_copia_real_de_chip_dispara_la_firma(self):
        """27ª cara: la firma se prueba PEGANDO una copia de verdad, nunca leyéndola. Se pega el
        marcado REAL de `chip` (`templates/_ui.html`) tal cual sale hoy, sobre un `<label>`
        suelto que no incluye la pieza — exactamente el defecto que R4 prohíbe."""
        copia_real_de_chip = (
            '<label class="inline-flex cursor-pointer items-center gap-1.5 rounded-pastilla '
            'bg-lienzo px-4 py-2 text-[14px] font-semibold text-tinta-media transition-colors '
            'has-[:checked]:bg-tinta has-[:checked]:text-white">'
            '<input type="checkbox">comida</label>'
        )
        for coincidencia in _CLASE_CON_ETIQUETA_RE.finditer(copia_real_de_chip):
            etiqueta = coincidencia.group("etiqueta").lower()
            clases = set(coincidencia.group("clases").split())
            self.assertTrue(
                _copia_el_marcado_de_la_pieza(etiqueta, clases, _FIRMAS_DE_CLASE_POR_PIEZA["chip"]),
                "la firma de «chip» no se disparó sobre una copia REAL de su propio marcado",
            )
            return
        self.fail("el regex no encontró ningún class= en la copia de prueba")

    def test_mutacion_pegar_una_copia_real_de_boton_enlace_dispara_la_firma(self):
        copia_real = (
            '<a href="/algo/" class="w-full inline-block text-center rounded-pastilla px-6 '
            'py-3.5 text-[15px] font-semibold transition-opacity active:opacity-80 bg-tinta '
            'text-white">Ir</a>'
        )
        for coincidencia in _CLASE_CON_ETIQUETA_RE.finditer(copia_real):
            etiqueta = coincidencia.group("etiqueta").lower()
            clases = set(coincidencia.group("clases").split())
            self.assertTrue(
                _copia_el_marcado_de_la_pieza(etiqueta, clases, _FIRMAS_DE_CLASE_POR_PIEZA["boton_enlace"]),
                "la firma de «boton_enlace» no se disparó sobre una copia REAL de su propio marcado",
            )
            return
        self.fail("el regex no encontró ningún class= en la copia de prueba")


# ------------------------------------------------------------------------------------------ #
# Fixture de integración (R5, R6): una casa completa, con datos en despensa, receta, plan,
# entreno y peso — así el recorrido real de la app alcanza las quince pantallas con algo que
# enseñar en cada una. Alejandro es quien manda el hogar; Euridice está a su cargo; Berta tiene
# cuenta propia en el mismo hogar; Carlos pide entrar y se queda ESPERANDO (sin aceptar), la
# única forma de alcanzar `hogares/esperando_aceptacion.html`.
# ------------------------------------------------------------------------------------------ #


class _ConLaAppEnteraYSusDatos(PruebaConRegistroAbierto):
    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        respuesta_alta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/",
            {
                "nombre": "Euridice", "sexo": "mujer", "fecha_nacimiento": "1997-06-29",
                "altura_cm": "167", "peso_kg": "62", "actividad": "moderado",
                "objetivo": "perder_grasa", "ajuste_pct": "", "dieta": "", "alergias": "",
                "intolerancias": "", "no_le_gusta": "",
            },
            follow=True,
        )
        assert respuesta_alta.status_code == 200
        self.euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)

        codigo = self.alejandro.hogar.codigo
        self.client.logout()
        self.registrar_y_verificar("berta@example.com", codigo_hogar=codigo, sexo="mujer")
        self.berta = Persona.objects.get(usuario__email="berta@example.com")

        self.client.logout()
        self.registrar_y_verificar("carlos@example.com", codigo_hogar=codigo, sexo="hombre")
        assert SolicitudEntrada.objects.filter(
            usuario__email="carlos@example.com", estado=SolicitudEntrada.PENDIENTE
        ).exists()  # control: Carlos se queda pendiente, nadie lo aceptó todavía
        # Un segundo cliente para Carlos: su sesión SIGUE en el navegador de arriba, así que
        # antes de recuperarla para Alejandro se aísla en su propio `Client()` — dos sesiones a
        # la vez, cada una con su propia cookie.
        self.client_carlos = Client()
        self.client_carlos.login(username="carlos@example.com", password="una-clave-de-verdad-2026")

        self.client.logout()
        self.client.login(username="alejandro@example.com", password="una-clave-de-verdad-2026")
        solicitud_de_berta = SolicitudEntrada.objects.get(
            usuario__email="berta@example.com", estado=SolicitudEntrada.PENDIENTE
        )
        respuesta_aceptar = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{solicitud_de_berta.pk}/aceptar/", follow=True
        )
        assert respuesta_aceptar.status_code == 200
        self.berta.refresh_from_db()
        assert self.berta.hogar_id == self.alejandro.hogar_id  # control: se aceptó de verdad

        respuesta_stock = self.client.post(
            "/despensa/anadir/",
            {"nombre": "Tomate", "cantidad": "2", "unidad": "lata", "categoria": "verdura"},
        )
        assert respuesta_stock.status_code == 200

        respuesta_receta = self.client.post(
            "/recetas/nueva/",
            {
                "nombre": "Crema de champiñones", "raciones": "4", "comidas": ["comida"],
                "preparacion": "Se pochan y se trituran.",
                "ingrediente_nombre": ["Champiñones", "Nata"],
                "ingrediente_cantidad": ["300", "100"],
                "ingrediente_unidad": ["g", "ml"],
            },
            follow=True,
        )
        assert respuesta_receta.status_code == 200
        self.receta = Receta.objects.get(nombre="Crema de champiñones")

        from django.utils import timezone

        hoy = timezone.localdate().isoformat()
        respuesta_plan = self.client.post(
            f"/planes/{self.alejandro.id}/apuntar/",
            {
                "nombre": "Tortilla de claras", "momento_del_dia": "desayuno", "calorias": "500",
                "proteina_g": "40", "grasa_g": "15", "carbos_g": "35",
            },
        )
        assert respuesta_plan.status_code == 200

        respuesta_entreno = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": hoy, "deporte": "correr", "intensidad": "media", "minutos": "30", "calorias": "300"},
        )
        assert respuesta_entreno.status_code == 200
        from entrenos.models import Entreno

        self.entreno = Entreno.objects.get(persona=self.alejandro)

        respuesta_peso = self.client.post(
            f"/perfiles/{self.alejandro.id}/peso/apuntar/",
            {"fecha": hoy, "peso_kg": "80", "grasa_pct": "", "cintura_cm": ""},
        )
        assert respuesta_peso.status_code == 200


def _paginas_de_pantallas_reales(cliente, nombres_de_pantallas, arranque):
    """BFS con el cliente de test desde `arranque` (mismo mecanismo que `_recorrer_la_app` de
    `kcalibra.tests_nada_escondido`, adaptado para devolver el HTML de cada página que renderiza
    alguna pantalla REAL — `_rutas_enlazadas`, importada de allí, sigue cada `href`/`hx-get`, no
    una lista de rutas escrita a mano)."""
    encontradas = []
    por_visitar = [arranque]
    visitadas = set()
    while por_visitar:
        ruta = por_visitar.pop(0)
        if ruta in visitadas:
            continue
        visitadas.add(ruta)
        respuesta = cliente.get(ruta)
        if respuesta.status_code != 200:
            continue
        usadas = {plantilla.name for plantilla in (respuesta.templates or []) if plantilla.name}
        contenido = respuesta.content.decode()
        if usadas & nombres_de_pantallas:
            encontradas.append((ruta, contenido))
        for destino in _rutas_enlazadas(contenido):
            if destino not in visitadas:
                por_visitar.append(destino)
    return encontradas


def _nombres_de_pantallas_reales_hoy():
    return {_nombre_de_plantilla(r) for r in _pantallas_reales_hoy()}


# ------------------------------------------------------------------------------------------ #
# R5 — los números de dato llevan `.cifra`, y el vocabulario de unidades sale de las `choices`
# reales de `despensa`/`recetas` — no de una lista escrita a mano.
# ------------------------------------------------------------------------------------------ #


def _vocabulario_de_unidades_de_despensa_y_recetas():
    """(a) VOCABULARIO — de una ESTRUCTURA que ya existe: `despensa.models.UNIDADES` (que
    `recetas.models` reutiliza tal cual) es la fuente de lo que `get_unidad_display` imprime
    ("Gramos", "Mililitros"…); `despensa.logica._PALABRA_DE_UNIDAD`/`_PLURAL_SI_NO_ES_UNA` son
    la fuente de lo que `cantidad_mostrada` imprime ("lata"/"latas"). Ninguna de las dos se
    copia a mano: se recorren."""
    palabras = set()
    for _codigo, etiqueta in UNIDADES:
        palabras.add(etiqueta)
    for codigo, palabra in _PALABRA_DE_UNIDAD.items():
        palabras.add(palabra)
        if codigo in _PLURAL_SI_NO_ES_UNA:
            palabras.add(palabra + "s")
    return palabras


# `cm` (altura) y `ración`/`raciones` no salen de ninguna `choices`: no son la unidad de un
# campo con opciones, son la palabra fija que la propia plantilla pone junto al número — las dos
# únicas piezas de este vocabulario que se escriben literalmente, igual que `kcal`/`min`/`%`
# (unidades físicas ya aceptadas desde la 053, que esta unidad no afloja).
_PALABRAS_SIN_CHOICES = {"ración", "raciones", "cm"}
_VOCABULARIO = sorted(
    {re.escape(p) for p in _vocabulario_de_unidades_de_despensa_y_recetas()}
    | {re.escape(p) for p in _PALABRAS_SIN_CHOICES}
    | {"kcal", "kg", "g", "min", "%"}
)
_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE = re.compile(
    r"\d[\d.,]*\s*(?:" + "|".join(_VOCABULARIO) + r")(?!\w)", re.I
)


class R5_VocabularioDeUnidadesYCifraTests(_ConLaAppEnteraYSusDatos):
    def test_ningun_numero_de_dato_escrito_en_linea_se_queda_sin_cifra(self):
        """El barrido universal (H2 de la revisión de la 054, hallazgos.md: "el código de hoy
        SÍ cumple R6; lo que miente es la red" — la deuda que esta unidad cierra de una vez para
        las QUINCE pantallas reales, no solo para las nueve de una unidad). Vocabulario ancho
        (arriba) + rutas de un recorrido real (nunca una lista de rutas a mano) con DOS sesiones
        —Alejandro y Carlos (pendiente)— para alcanzar también `esperando_aceptacion.html`.

        Cada ruta se guarda ATADA al cliente que la alcanzó (`objetivos`, abajo): la misma URL
        `/hogares/mi-hogar/` pinta una plantilla distinta según quién la pida (Alejandro ve
        `mi_hogar.html`; Carlos, pendiente, ve `esperando_aceptacion.html`), así que volver a
        pedirla con el cliente equivocado repintaría la pantalla equivocada."""
        nombres = _nombres_de_pantallas_reales_hoy()
        objetivos = [
            (self.client, ruta) for ruta, _ in _paginas_de_pantallas_reales(self.client, nombres, "/")
        ] + [
            (self.client_carlos, ruta)
            for ruta, _ in _paginas_de_pantallas_reales(self.client_carlos, nombres, "/hogares/mi-hogar/")
        ]
        # Guarda de rojo mudo (misma familia que `kcalibra.tests_nada_escondido`): si el
        # recorrido se rompiera y no alcanzara nada, el barrido de abajo compararía una lista
        # vacía contra sí misma y colaría en verde sin haber mirado ni una pantalla.
        self.assertGreaterEqual(
            len(objetivos), 10, f"el recorrido apenas alcanzó pantallas reales: {objetivos}"
        )
        sin_cifra = []
        with _con_procedencia_marcada(), self._vocabulario_ancho():
            for cliente, ruta in objetivos:
                # Se vuelve a pedir la página DENTRO de los dos `with`: `_con_procedencia_marcada`
                # parchea el motor de plantillas, así que hace falta renderizar DE NUEVO bajo el
                # parche para que el centinela de procedencia quede escrito en el HTML.
                respuesta = cliente.get(ruta)
                self.assertEqual(respuesta.status_code, 200, ruta)
                lector = _NumerosDeDatoEnElTexto()
                lector.feed(respuesta.content.decode())
                for numero, cadena, de_variable in lector.hallazgos:
                    if not de_variable:
                        continue
                    if _algun_elemento_de_la_cadena_lleva_cifra(cadena):
                        continue
                    if _es_la_excepcion_de_perfiles_sobre_r6(ruta, cadena):
                        continue
                    sin_cifra.append(f"{ruta}: «{numero}» dentro de {[e for e, _ in cadena]}")
        self.assertEqual(
            sin_cifra, [], f"números de dato sin `.cifra`, ni propio ni heredado: {sin_cifra}"
        )

    @staticmethod
    @contextmanager
    def _vocabulario_ancho():
        """`_NumerosDeDatoEnElTexto.hallazgos` (importada de `kcalibra.tests_pantallas`)
        consulta `_NUMERO_CON_UNIDAD_RE` como global DE SU PROPIO MÓDULO — el mismo mecanismo de
        sustitución temporal que ya usa `kcalibra.tests_pantallas_de_la_casa._con_vocabulario_ampliado`,
        aplicado aquí para que el barrido universal use el vocabulario ANCHO de este fichero sin
        tocar `kcalibra/tests_pantallas.py` con un vocabulario que solo tiene sentido aquí."""
        import kcalibra.tests_pantallas as _tests_pantallas

        original = _tests_pantallas._NUMERO_CON_UNIDAD_RE
        _tests_pantallas._NUMERO_CON_UNIDAD_RE = _NUMERO_CON_UNIDAD_DEL_PROYECTO_RE
        try:
            yield
        finally:
            _tests_pantallas._NUMERO_CON_UNIDAD_RE = original

    def test_mutacion_vocabulario_reconoce_gramos_mililitros_y_raciones(self):
        """R9 en código: el vocabulario ancho tiene que casar justo las palabras que el
        vocabulario ESTRECHO de la 053 (`kcal|kg|g|min|%`) dejaba escapar — medido en vivo por
        la revisión de la 054 (hueco H2): "raciones", "cm", "Gramos", "Mililitros", "2 latas"."""
        for texto, debe_casar in [
            ("4 raciones", True), ("1 ración", True), ("167 cm", True),
            ("300,00 Gramos", True), ("100,00 Mililitros", True), ("2 latas", True),
            ("3 Kilos", True), ("6 Litros", True), ("1 Unidades", True),
            ("hola mundo", False),
        ]:
            with self.subTest(texto=texto):
                encontrado = bool(_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE.search(texto))
                self.assertEqual(encontrado, debe_casar, texto)


# ------------------------------------------------------------------------------------------ #
# R6 — el texto de ayuda queda asociado a su campo: en toda pantalla vigilada, todo
# `aria-describedby="…"` apunta a un `id` que existe DE VERDAD en la misma página.
# ------------------------------------------------------------------------------------------ #


class _IdsYAriaDescribedby(HTMLParser):
    """Todos los `id` que declara la página, y todos los `aria-describedby` que la página pide
    — generalizable a CUALQUIER campo futuro con `help_text`, sin nombrar ni una pantalla ni un
    `id` concreto: Django (`BoundField.aria_describedby`, `django/forms/boundfield.py`) siempre
    escribe `f"{auto_id}_helptext"`, así que basta con comprobar que ESE id existe."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.referencias = []  # (id_referenciado, atributo_que_lo_pidio)

    def handle_starttag(self, etiqueta, atributos_crudos):
        attrs = atributos(atributos_crudos)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for referenciado in (attrs.get("aria-describedby") or "").split():
            self.referencias.append(referenciado)


# Hueco MEDIDO durante esta unidad, fuera de `ficheros:` (no se puede tocar aquí — "Reglas del
# constructor": lo que no está en `ficheros:` no se edita aunque el cambio se necesite; se
# propone en hallazgos.md y lo aplica el padre): `entrenos/templates/entrenos/corregir.html:35`
# tiene EXACTAMENTE el mismo defecto que las cuatro plantillas que esta unidad SÍ cura (el `<p>`
# de `field.help_text` sin su `id`) — el campo `calorias` de `EntrenoForm` (`entrenos/forms.py`)
# trae `help_text`. La especificación midió el defecto "vivo" en cuatro sitios sobre `48c939d`;
# el barrido universal de esta unidad, al cubrir las QUINCE pantallas reales y no solo las
# cuatro nombradas, encontró esta quinta — apretar la red la hizo visible, no crearla: el
# defecto ya estaba en `48c939d`. Se declara aparte de `EXCEPCIONES` (que es, letra a letra, la
# lista de R8 — las diez que migra la 055) porque es un contrato distinto: no es que la 055 vaya
# a rehacer esta pantalla, es que el fichero no lo puede tocar ESTA unidad. El día que el padre
# aplique el cambio propuesto en hallazgos.md, esta exención deja de encontrar nada que eximir
# y puede borrarse (no hay id fijo que nombrar: `/entrenos/<persona>/<entreno>/corregir/` lleva
# los dos ids de la fixture, así que se reconoce por FORMA de ruta, no por valor).
def _es_el_hueco_r6_fuera_de_ficheros(ruta):
    return ruta.startswith("/entrenos/") and ruta.endswith("/corregir/")


class R6_AyudaAsociadaASuCampoTests(_ConLaAppEnteraYSusDatos):
    def test_todo_aria_describedby_apunta_a_un_id_que_existe(self):
        nombres = _nombres_de_pantallas_reales_hoy()
        paginas = _paginas_de_pantallas_reales(self.client, nombres, "/")
        paginas += _paginas_de_pantallas_reales(self.client_carlos, nombres, "/hogares/mi-hogar/")
        self.assertGreaterEqual(len(paginas), 10, "el recorrido apenas alcanzó pantallas reales")
        huerfanos = []
        total_referencias = 0
        for ruta, contenido in paginas:
            lector = _IdsYAriaDescribedby()
            lector.feed(contenido)
            for referenciado in lector.referencias:
                total_referencias += 1
                if referenciado not in lector.ids:
                    if _es_el_hueco_r6_fuera_de_ficheros(ruta):
                        continue  # ver el comentario de arriba: hueco fuera de `ficheros:`
                    huerfanos.append(f"{ruta}: aria-describedby='{referenciado}' sin ningún id igual")
        self.assertGreater(
            total_referencias, 0,
            "ninguna página trajo ni un aria-describedby: la fixture no está ejercitando "
            "ningún help_text — el test no probaría nada",
        )
        self.assertEqual(huerfanos, [], f"aria-describedby huérfanos: {huerfanos}")

    def test_mutacion_un_id_que_no_coincide_se_pone_rojo(self):
        lector = _IdsYAriaDescribedby()
        lector.feed(
            '<input aria-describedby="id_nombre_helptext"><p id="id_nombre_help_text">ayuda</p>'
        )
        self.assertNotIn(
            "id_nombre_helptext", lector.ids,
            "el control: un id que no coincide EXACTAMENTE (por un guion bajo de más) no debía "
            "colar como si existiera",
        )
        self.assertIn("id_nombre_helptext", lector.referencias)


# ------------------------------------------------------------------------------------------ #
# R7 — los controles que abren algo se comprueban importando `kcalibra.ayuda_de_alcanzabilidad`,
# nunca copiándola. Guarda ESTRUCTURAL: ningún fichero de tests redefine las piezas del módulo
# compartido — si alguien las copiara a mano (el error que abrió siete agujeros en la 053), este
# barrido lo cazaría por la FORMA del fichero, no leyendo el diff.
# ------------------------------------------------------------------------------------------ #

_NOMBRES_DE_LAS_OCHO_PIEZAS = (
    "TAPADERAS_DE_CLASE", "TAPADERAS_DE_ESTILO", "CadenaDeAncestros", "cadena_unica",
    "claves_de_primer_nivel", "nada_lo_tapa", "el_estado_es_compartido", "re_de_atributo",
)


class R7_LaAlcanzabilidadSeImportaNuncaSeCopiaTests(SimpleTestCase):
    databases = set()

    def test_ningun_fichero_de_tests_redefine_las_piezas_de_alcanzabilidad(self):
        """El barrido recorre TODO fichero `tests*.py`/`test_*.py` del árbol (salvo el propio
        módulo compartido) buscando una definición PROPIA (`def nombre(` / `class nombre` /
        `nombre =`) de cualquiera de las ocho piezas — no una lista de ficheros de test escrita
        a mano: un fichero de test nuevo que copiara el patrón entraría solo en este barrido."""
        modulo_compartido = BASE_DIR / "kcalibra" / "ayuda_de_alcanzabilidad.py"
        con_copia = {}
        for ruta in sorted(BASE_DIR.glob("*/tests*.py")):
            if ruta.resolve() == modulo_compartido.resolve():
                continue
            if ".venv" in ruta.parts:
                continue
            texto = _texto(ruta)
            redefinidas = [
                nombre for nombre in _NOMBRES_DE_LAS_OCHO_PIEZAS
                if re.search(rf"^(def|class)\s+{nombre}\b|^{nombre}\s*=", texto, re.M)
            ]
            if redefinidas:
                con_copia[str(ruta.relative_to(BASE_DIR))] = redefinidas
        self.assertEqual(
            con_copia, {},
            f"estos ficheros REDEFINEN piezas de ayuda_de_alcanzabilidad en vez de importarlas: {con_copia}",
        )

    def test_mutacion_una_redefinicion_se_detecta(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "app" / "tests_copia.py"
            ruta.parent.mkdir(parents=True)
            ruta.write_text("def nada_lo_tapa(caso, contenido, coincide, nombre):\n    pass\n")
            texto = _texto(ruta)
            redefinidas = [
                nombre for nombre in _NOMBRES_DE_LAS_OCHO_PIEZAS
                if re.search(rf"^(def|class)\s+{nombre}\b|^{nombre}\s*=", texto, re.M)
            ]
            self.assertEqual(redefinidas, ["nada_lo_tapa"])
