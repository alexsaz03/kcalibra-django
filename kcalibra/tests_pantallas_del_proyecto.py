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
from kcalibra.ayuda_de_alcanzabilidad import atributos, el_estado_es_compartido, elementos_con_texto
from kcalibra.tests_nada_escondido import _rutas_enlazadas
from kcalibra.tests_pantallas import (
    _CLASE_CON_ETIQUETA_RE,
    _CLASES_DEL_BOTON_REDONDO,
    _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE,
    _PALETA_VIEJA_RE,
    _VARIABLE_DE_DJANGO_RE,
    _NumerosDeDatoEnElTexto,
    _algun_elemento_de_la_cadena_es_identificador_opaco,
    _algun_elemento_de_la_cadena_lleva_cifra,
    _boton_redondo_es_alcanzable,
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

    def test_hoy_hay_al_menos_veinticinco_pantallas_y_las_diez_excepciones_siguen_siendolo(self):
        """Número de control (evidencia de que el barrido corre, no una lista que sustituya al
        árbol) — y la mitad que de verdad importa para R8: cada excepción declarada tiene que
        SER una pantalla real hoy. Si una dejara de existir (o de extender `base.html`), la
        excepción sería papel muerto y R8 no podría ni comprobarla: sácala de la lista, no la
        dejes envejecer.

        `assertGreaterEqual`, no `assertEqual` (O1 de la revisión): un `assertEqual(…, 25)`
        pondría en rojo cualquier pantalla NUEVA y LEGÍTIMA que añada la 055/058 — la 055 y la
        058 tendrían que volver a tocar esta red permanente sólo para subir un número, que es
        exactamente lo que esta unidad existe para evitar. Bajar de 25 sigue siendo ROJO (una
        pantalla que desaparece del barrido sin querer), y R1 ya prueba, con su propia mutación
        en código, que subir SÍ se detecta y se nombra."""
        pantallas = pantallas_vigiladas()
        nombres = {str(p.relative_to(BASE_DIR)) for p in pantallas}
        self.assertEqual(len(pantallas), len(nombres), "hay una plantilla contada dos veces")
        self.assertGreaterEqual(
            len(pantallas), 25, f"se esperaban al menos 25 pantallas hoy, salieron: {sorted(nombres)}"
        )
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

    def test_mutacion_pegar_a_mano_solo_el_a_de_boton_redondo_dispara_la_firma(self):
        """H6 (vuelta de revisión 2) — «la puerta más ancha»: la firma vieja de `boton_redondo`
        sólo miraba las clases del `<div>` ENVOLTORIO que posiciona el botón, así que pegar a
        mano SÓLO el `<a>` clicable (lo único que hace falta para tener el botón) no disparaba
        ninguna de las quince firmas. Se pega el `<a>` REAL de `_ui.html#boton_redondo`, SIN su
        `<div>` envoltorio y SIN `aria-label` — el caso completo que medió el revisor."""
        copia_real_del_a_suelto = (
            '<a href="#destino-que-no-existe" class="pointer-events-auto flex h-14 w-14 '
            'items-center justify-center rounded-pastilla bg-tinta text-white shadow-lg '
            'active:scale-95">+</a>'
        )
        for coincidencia in _CLASE_CON_ETIQUETA_RE.finditer(copia_real_del_a_suelto):
            etiqueta = coincidencia.group("etiqueta").lower()
            clases = set(coincidencia.group("clases").split())
            self.assertTrue(
                _copia_el_marcado_de_la_pieza(etiqueta, clases, _FIRMAS_DE_CLASE_POR_PIEZA["boton_redondo"]),
                "la firma de «boton_redondo» no se disparó sobre una copia REAL de su `<a>` "
                "clicable, pegado a mano sin su `<div>` envoltorio",
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
    una lista de rutas escrita a mano). Devuelve `(encontradas, alcanzadas)`: la lista de
    `(ruta, contenido)` de siempre, MÁS el conjunto de nombres de pantalla que de verdad se
    vieron — O3 de la revisión: la guarda de rojo mudo de R5/R6 sólo contaba RUTAS, así que una
    pantalla que el recorrido dejara de alcanzar (un estado que la fixture no crea) se quedaba
    sin ninguna de las dos redes y nadie avisaba; comparar `alcanzadas` contra
    `_nombres_de_pantallas_reales_hoy()` cierra esa familia sin nombrar ni una pantalla."""
    encontradas = []
    alcanzadas = set()
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
        coincidentes = usadas & nombres_de_pantallas
        if coincidentes:
            encontradas.append((ruta, contenido))
            alcanzadas |= coincidentes
        for destino in _rutas_enlazadas(contenido):
            if destino not in visitadas:
                por_visitar.append(destino)
    return encontradas, alcanzadas


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
        paginas_alejandro, alcanzadas_alejandro = _paginas_de_pantallas_reales(self.client, nombres, "/")
        paginas_carlos, alcanzadas_carlos = _paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        objetivos = (
            [(self.client, ruta) for ruta, _ in paginas_alejandro]
            + [(self.client_carlos, ruta) for ruta, _ in paginas_carlos]
        )
        # Guarda de rojo mudo (misma familia que `kcalibra.tests_nada_escondido`): si el
        # recorrido se rompiera y no alcanzara nada, el barrido de abajo compararía una lista
        # vacía contra sí misma y colaría en verde sin haber mirado ni una pantalla.
        self.assertGreaterEqual(
            len(objetivos), 10, f"el recorrido apenas alcanzó pantallas reales: {objetivos}"
        )
        # O3 de la revisión: la guarda de arriba cuenta RUTAS, no PANTALLAS — una pantalla real
        # que el recorrido dejara de alcanzar (por hacer falta un estado que la fixture no crea)
        # podía quedarse sin R5 sin que nada lo dijera. Comparar el conjunto de nombres
        # alcanzados contra las quince reales de hoy cierra esa familia.
        alcanzadas = alcanzadas_alejandro | alcanzadas_carlos
        self.assertEqual(
            alcanzadas, nombres,
            f"pantallas reales que el recorrido no alcanzó, y R5 no las miró: {sorted(nombres - alcanzadas)}",
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
                    if _algun_elemento_de_la_cadena_es_identificador_opaco(cadena):
                        continue  # O6 de la revisión 3: un identificador, no un número de dato
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
# a rehacer esta pantalla, es que el fichero no lo puede tocar ESTA unidad.
#
# H8 (revisión 3): la exención de arriba, tal como estaba escrita, no tenía TRINQUETE (nada
# comprobaba que la ruta SIGUIERA teniendo su huérfano) y era GENEROSA (perdonaba CUALQUIER
# `aria-describedby` huérfano de esa ruta, no el medido) — exactamente lo que R8 existe para
# impedir, escrito 60 líneas más abajo de R8. Medido por el revisor: aplicada la línea propuesta
# en hallazgos.md, `Ran 22 tests — OK` (la exención sobra y sigue ahí, en verde, para siempre); y
# con `corregir.html` intacto pero un `id-que-no-existe-en-ninguna-parte` NUEVO pegado en la
# misma ruta, también `OK` (un defecto R6 distinto, en una pantalla real, colando en verde).
#
# Se estrecha al ID EXACTO que Django genera para ESE campo (`auto_id` por defecto,
# "id_%s" → "id_calorias_helptext" — no hay otro `help_text` en `FormularioEntreno`), lo que
# cierra (b) solo: cualquier OTRO huérfano de esa misma ruta ya no se libra. Y se le da su
# trinquete (a): la propia página tiene que SEGUIR pidiendo ese id exacto sin declararlo — el
# día que el padre aplique el diff de hallazgos.md, la exención deja de encontrar nada que eximir
# y el assert de abajo se pone ROJO pidiendo borrarla, en vez de quedarse muda para siempre.
_ID_DEL_HUECO_R6_FUERA_DE_FICHEROS = "id_calorias_helptext"


def _es_el_hueco_r6_fuera_de_ficheros(ruta, referenciado):
    return (
        ruta.startswith("/entrenos/") and ruta.endswith("/corregir/")
        and referenciado == _ID_DEL_HUECO_R6_FUERA_DE_FICHEROS
    )


class R6_AyudaAsociadaASuCampoTests(_ConLaAppEnteraYSusDatos):
    def test_todo_aria_describedby_apunta_a_un_id_que_existe(self):
        nombres = _nombres_de_pantallas_reales_hoy()
        paginas_alejandro, alcanzadas_alejandro = _paginas_de_pantallas_reales(self.client, nombres, "/")
        paginas_carlos, alcanzadas_carlos = _paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        paginas = paginas_alejandro + paginas_carlos
        self.assertGreaterEqual(len(paginas), 10, "el recorrido apenas alcanzó pantallas reales")
        # O3 de la revisión: ver el comentario gemelo en R5 — comparar PANTALLAS, no rutas.
        alcanzadas = alcanzadas_alejandro | alcanzadas_carlos
        self.assertEqual(
            alcanzadas, nombres,
            f"pantallas reales que el recorrido no alcanzó, y R6 no las miró: {sorted(nombres - alcanzadas)}",
        )
        huerfanos = []
        total_referencias = 0
        vista_la_exencion_de_entrenos_corregir = False
        for ruta, contenido in paginas:
            lector = _IdsYAriaDescribedby()
            lector.feed(contenido)
            for referenciado in lector.referencias:
                total_referencias += 1
                if referenciado not in lector.ids:
                    if _es_el_hueco_r6_fuera_de_ficheros(ruta, referenciado):
                        vista_la_exencion_de_entrenos_corregir = True
                        continue  # ver el comentario de arriba: hueco fuera de `ficheros:`
                    huerfanos.append(f"{ruta}: aria-describedby='{referenciado}' sin ningún id igual")
        self.assertGreater(
            total_referencias, 0,
            "ninguna página trajo ni un aria-describedby: la fixture no está ejercitando "
            "ningún help_text — el test no probaría nada",
        )
        self.assertEqual(huerfanos, [], f"aria-describedby huérfanos: {huerfanos}")
        # H8 (revisión 3), el trinquete que le faltaba a esta SEGUNDA lista de excepciones: si
        # `entrenos/corregir.html` deja de pedir `id_calorias_helptext` sin declararlo —porque el
        # padre aplicó el diff de hallazgos.md—, la exención ya no encuentra nada que eximir y
        # esto se pone ROJO pidiendo borrarla, en vez de quedarse muda para siempre en verde.
        self.assertTrue(
            vista_la_exencion_de_entrenos_corregir,
            "la exención de `_es_el_hueco_r6_fuera_de_ficheros` ya no encontró su huérfano "
            f"medido ({_ID_DEL_HUECO_R6_FUERA_DE_FICHEROS} en /entrenos/.../corregir/): "
            "probablemente el padre ya aplicó la línea propuesta en hallazgos.md — borra la "
            "exención, el trinquete acaba de cazarla",
        )

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
# R7 (la mitad real, Hueco H1 de la revisión) — los controles que abren algo son alcanzables DE
# VERDAD, sobre las QUINCE pantallas reales, no sólo sobre las siete que ya vigilaban a mano
# `kcalibra/tests_pantallas.py`/`tests_pantallas_de_la_casa.py`. Antes de esto, la red permanente
# sólo cubría la mitad ESTRUCTURAL de R7 (más abajo: nadie redefine las ocho piezas) — una
# pantalla nueva con un botón redondo que no lleva a ningún sitio pasaba con las 887 en verde,
# porque la alcanzabilidad de verdad seguía viviendo en dos listas de rutas escritas a mano.
#
# El botón/menú redondo se identifica por la FIRMA de clases que las dos piezas comparten en su
# propio `<a>`/`<button>` clicable (`_ui.html#boton_redondo`/`#boton_redondo_menu`,
# `_CLASES_DEL_BOTON_REDONDO`) — NUNCA por `aria-label` como puerta de entrada (H6, vuelta de
# revisión 2: `etiqueta` es un parámetro opcional del `{% include %}` sin valor por defecto, así
# que filtrar por `aria-label` no vacío borraba del barrido entero justo al control que más falta
# hace cazar). Que el `aria-label` no esté vacío se exige como ASSERT dentro del propio test
# (R11), lo contrario de un filtro de entrada. `_boton_redondo_es_alcanzable`
# (importada de `kcalibra.tests_pantallas`, nunca copiada — la 27ª cara) comprueba que el control
# en sí se puede usar; el DESTINO sale del propio HTML renderizado, no de una lista: el `href`
# del elemento con `aria-label`, y si es un ancla interna (`#id`), el `id` al que apunta tiene
# que EXISTIR en la misma página (los `href` a una ruta absoluta ya los sigue y comprueba
# `kcalibra.tests_nada_escondido`, que sólo seguía `href`/`hx-get` que empiezan por "/" — un
# ancla suelta como `#destino-que-no-existe` es precisamente el hueco que ese barrido no mira).
# ------------------------------------------------------------------------------------------ #

def _es_boton_o_menu_redondo(etiqueta, attrs):
    """Un `<a>`/`<button>` con la FORMA del control clicable de `boton_redondo`/
    `boton_redondo_menu` (`_ui.html`): las dos piezas comparten esta firma de clases en el
    elemento que de verdad se toca (no en el `<div>` envoltorio, que sólo posiciona) —
    `_CLASES_DEL_BOTON_REDONDO`, IMPORTADA de `kcalibra.tests_pantallas` (la misma que ya usa la
    firma de copia de R4), nunca copiada. Nunca exige `aria-label` como PUERTA DE ENTRADA (H6,
    vuelta de revisión 2): `etiqueta` es un parámetro opcional del `{% include %}` sin valor por
    defecto, y `aria-label` es exactamente lo que un copiador/olvido suelta al pegar — filtrar
    por él aquí borraba el control del barrido entero de R7 en vez de nombrarlo roto (la 27ª
    cara, otra vez, dentro del código escrito para impedirla). Las ocho clases solas ya no
    colisionan con ningún otro control de las quince pantallas reales (verificado con el barrido
    de abajo, en verde); que el `aria-label` esté vacío se comprueba como ASSERT del propio test,
    nunca como filtro."""
    if etiqueta not in ("a", "button"):
        return False
    clases = set((attrs.get("class") or "").split())
    return _CLASES_DEL_BOTON_REDONDO <= clases


def _destino_de_ancla_interna_no_existe(contenido, attrs):
    """`None` si el botón no es una ancla interna (nada que comprobar aquí: una ruta absoluta
    ya la sigue `kcalibra.tests_nada_escondido`); si no, el `id` al que apunta si NO existe en
    la misma página, o `""` si existe — nunca se decide leyendo el fichero fuente, siempre sobre
    el HTML YA renderizado."""
    href = (attrs.get("href") or "").strip()
    if not href.startswith("#") or len(href) < 2:
        return None
    id_destino = href[1:]
    existe = bool(elementos_con_texto(contenido, lambda e, a, i=id_destino: a.get("id") == i))
    return "" if existe else id_destino


def _es_disparador_de_menu_redondo(etiqueta, attrs):
    """El `<button>` que ABRE `boton_redondo_menu` — la misma firma de clases de
    `_es_boton_o_menu_redondo`, pero sólo la mitad que es un disparador de menú (el `<a>` de
    `boton_redondo` simple no abre nada, así que no cuenta para la pieza 7)."""
    return etiqueta == "button" and _es_boton_o_menu_redondo(etiqueta, attrs)


def _es_menu_redondo_abierto(etiqueta, attrs):
    """El contenedor que `boton_redondo_menu` despliega: se reconoce por su `role="menu"` — la
    forma que lo hace un menú, no una lista de pantallas."""
    return (attrs.get("role") or "").strip().lower() == "menu"


def _es_item_de_menu(etiqueta, attrs):
    """Una OPCIÓN de `boton_redondo_menu`: se reconoce por su `role="menuitem"` — la forma que
    la hace un destino pulsable (pieza 8 del módulo compartido: "un menú alcanzable con los
    destinos tapados sigue siendo un menú inútil"), nunca por pertenecer a una pantalla
    concreta de una lista escrita a mano."""
    return (attrs.get("role") or "").strip().lower() == "menuitem"


class R7_LosBotonesRedondosLlevanAAlgunSitioTests(_ConLaAppEnteraYSusDatos):
    def test_ningun_boton_o_menu_redondo_real_es_inalcanzable_o_lleva_a_ningun_sitio(self):
        nombres = _nombres_de_pantallas_reales_hoy()
        paginas_alejandro, alcanzadas_alejandro = _paginas_de_pantallas_reales(self.client, nombres, "/")
        paginas_carlos, alcanzadas_carlos = _paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        paginas = paginas_alejandro + paginas_carlos
        self.assertGreaterEqual(len(paginas), 10, "el recorrido apenas alcanzó pantallas reales")
        # O3 de la revisión: ver el comentario gemelo en R5/R6 — comparar PANTALLAS, no rutas.
        alcanzadas = alcanzadas_alejandro | alcanzadas_carlos
        self.assertEqual(
            alcanzadas, nombres,
            f"pantallas reales que el recorrido no alcanzó, y R7 no las miró: {sorted(nombres - alcanzadas)}",
        )
        total_controles = 0
        rotos = []
        sin_nombre_accesible = []
        for ruta, contenido in paginas:
            for attrs, _texto_visible in elementos_con_texto(contenido, _es_boton_o_menu_redondo):
                total_controles += 1
                etiqueta_aria = attrs.get("aria-label") or ""
                coincide = lambda e, a, al=etiqueta_aria: _es_boton_o_menu_redondo(e, a) and (
                    a.get("aria-label") or ""
                ) == al
                with self.subTest(ruta=ruta, control=etiqueta_aria):
                    _boton_redondo_es_alcanzable(
                        self, contenido, coincide, f"el botón/menú redondo «{etiqueta_aria}» de {ruta}"
                    )
                id_roto = _destino_de_ancla_interna_no_existe(contenido, attrs)
                if id_roto:
                    rotos.append(
                        f"{ruta}: «{etiqueta_aria}» apunta a #{id_roto}, y no hay ningún "
                        f"elemento con ese id en la página — no lleva a ningún sitio"
                    )
                # R11 (H6, vuelta de revisión 2) — `aria-label` no vacío como ASSERT del propio
                # test, lo CONTRARIO de usarlo como filtro de entrada de `_es_boton_o_menu_redondo`:
                # `etiqueta` es un parámetro opcional del `{% include %}` sin valor por defecto, y
                # un control de sólo icono sin nombre accesible tiene que caer en ROJO nombrando
                # la ruta, no desaparecer del barrido.
                if not etiqueta_aria.strip():
                    sin_nombre_accesible.append(
                        f"{ruta}: un botón/menú redondo sin aria-label (o vacío) — un lector de "
                        f"pantalla no puede nombrar ese control de sólo icono"
                    )
        self.assertGreater(
            total_controles, 0,
            "el recorrido no encontró ningún botón/menú redondo: este test no probaría nada",
        )
        self.assertEqual(rotos, [], f"controles redondos que no llevan a ningún sitio: {rotos}")
        self.assertEqual(
            sin_nombre_accesible, [],
            f"controles redondos sin nombre accesible: {sin_nombre_accesible}",
        )

        # H7 (revisión 3) — R7 sólo miraba el DISPARADOR de `boton_redondo_menu`; sus opciones
        # (los destinos que hay que poder pulsar, pieza 8) no las miraba nadie en una pantalla
        # nueva. Se identifican por su `role="menuitem"` — la forma que las hace un destino
        # pulsable — nunca por una lista de rutas, y se comprueban con `_boton_redondo_es_alcanzable`
        # (IMPORTADA, nunca copiada): usar `nada_lo_tapa` a pelo daría FALSO ROJO sobre el
        # `pointer-events-none` legítimo del envoltorio `fixed` que también las envuelve a ellas.
        total_items = 0
        for ruta, contenido in paginas:
            for attrs, texto_item in elementos_con_texto(contenido, _es_item_de_menu):
                total_items += 1
                href_item = (attrs.get("href") or "").strip()
                coincide_item = lambda e, a, h=href_item: (
                    _es_item_de_menu(e, a) and (a.get("href") or "").strip() == h
                )
                with self.subTest(ruta=ruta, item=texto_item):
                    _boton_redondo_es_alcanzable(
                        self, contenido, coincide_item, f"la opción «{texto_item}» del menú de {ruta}"
                    )
                id_roto_item = _destino_de_ancla_interna_no_existe(contenido, attrs)
                if id_roto_item:
                    rotos.append(
                        f"{ruta}: la opción de menú «{texto_item}» apunta a #{id_roto_item}, y "
                        f"no hay ningún elemento con ese id en la página — no lleva a ningún sitio"
                    )
        self.assertGreater(
            total_items, 0,
            "el recorrido no encontró ninguna opción de menú: esa mitad no probaría nada",
        )
        self.assertEqual(
            rotos, [], f"controles/opciones redondos que no llevan a ningún sitio: {rotos}"
        )

        # Pieza 7 del módulo compartido (`el_estado_es_compartido`): el disparador y el menú
        # tienen que colgar del MISMO `x-data` que declara `abierto` — un `x-data` renombrado o
        # duplicado deja a los dos perfectos por separado y el menú no abre jamás. Hoy `_ui.html`
        # pinta el `x-data` dentro del propio partial, así que una pantalla que use
        # `{% include %}` no puede romperlo por fuera — no es la mitad bloqueante de H7 — pero es
        # la única de las ocho piezas que seguía viviendo sólo en una lista de rutas escrita a
        # mano (`R8_BotonRedondoDeProgresoTests`), y esta unidad existe para acabar con eso.
        total_disparadores_de_menu = 0
        for ruta, contenido in paginas:
            if not elementos_con_texto(contenido, _es_disparador_de_menu_redondo):
                continue
            total_disparadores_de_menu += 1
            with self.subTest(ruta=ruta, pieza="el_estado_es_compartido"):
                el_estado_es_compartido(
                    self, contenido, _es_disparador_de_menu_redondo, _es_menu_redondo_abierto,
                    "abierto", f"el disparador del menú redondo de {ruta}", f"el menú redondo de {ruta}",
                )
        self.assertGreater(
            total_disparadores_de_menu, 0,
            "el recorrido no encontró ningún disparador de menú redondo: la pieza 7 no se "
            "comprobaría",
        )

    def test_mutacion_un_boton_redondo_que_apunta_a_un_ancla_inexistente_se_pone_rojo(self):
        """R9 en código, permanente — el Hueco H1 de la revisión, reproducido EXACTAMENTE: el
        marcado real de `_ui.html#boton_redondo` (mismas ocho clases, mismo `aria-label`) con
        el `href` apuntando a un ancla que la página nunca declara. `_es_boton_o_menu_redondo`
        tiene que reconocerlo como el control que es, y `_destino_de_ancla_interna_no_existe`
        tiene que decir que el destino NO existe — nunca leyendo el fichero fuente de una
        pantalla nueva, siempre sobre el HTML ya renderizado."""
        html_con_boton_muerto = (
            '<div class="pointer-events-none fixed inset-x-0 z-40"><div class="mx-auto w-full '
            'max-w-movil px-4"><div class="flex justify-end"><a href="#destino-que-no-existe" '
            'aria-label="Botón que no lleva a ningún sitio" class="pointer-events-auto flex '
            'h-14 w-14 items-center justify-center rounded-pastilla bg-tinta text-white '
            'shadow-lg active:scale-95">x</a></div></div></div>'
        )
        encontrados = elementos_con_texto(html_con_boton_muerto, _es_boton_o_menu_redondo)
        self.assertEqual(
            len(encontrados), 1,
            "la firma no reconoció el marcado REAL de boton_redondo: el mutante no probaría nada",
        )
        attrs, _texto_visible = encontrados[0]
        self.assertEqual(
            _destino_de_ancla_interna_no_existe(html_con_boton_muerto, attrs),
            "destino-que-no-existe",
            "un botón redondo que apunta a un ancla que no existe debía detectarse como roto",
        )
        # Y el control: la MISMA pieza, con un destino que SÍ existe, no debe reportar nada.
        html_con_boton_sano = html_con_boton_muerto.replace(
            "#destino-que-no-existe", "#formulario-de-verdad"
        ) + '<div id="formulario-de-verdad"></div>'
        attrs_sano, _ = elementos_con_texto(html_con_boton_sano, _es_boton_o_menu_redondo)[0]
        self.assertEqual(_destino_de_ancla_interna_no_existe(html_con_boton_sano, attrs_sano), "")

    def test_mutacion_un_boton_redondo_sin_aria_label_sigue_dentro_del_barrido(self):
        """H6 (vuelta de revisión 2) — `aria-label` no puede ser una PUERTA DE ENTRADA: es
        justo el atributo que `etiqueta`, un parámetro opcional del `{% include %}` SIN valor
        por defecto, deja vacío si se olvida. `_es_boton_o_menu_redondo` tiene que seguir
        reconociendo el control aunque `aria-label` esté vacío o ausente — quien lo tapa o lo
        deja sin destino se sigue cazando por R7, en vez de desaparecer del barrido entero."""
        html_con_aria_label_vacio = (
            '<a href="#destino-que-no-existe" aria-label="" class="pointer-events-auto flex '
            'h-14 w-14 items-center justify-center rounded-pastilla bg-tinta text-white '
            'shadow-lg active:scale-95">x</a>'
        )
        encontrados = elementos_con_texto(html_con_aria_label_vacio, _es_boton_o_menu_redondo)
        self.assertEqual(
            len(encontrados), 1,
            "un `aria-label` vacío no debía borrar el control del barrido de R7",
        )
        html_sin_aria_label_del_todo = (
            '<a href="#destino-que-no-existe" class="pointer-events-auto flex h-14 w-14 '
            'items-center justify-center rounded-pastilla bg-tinta text-white shadow-lg '
            'active:scale-95">x</a>'
        )
        encontrados_sin_atributo = elementos_con_texto(
            html_sin_aria_label_del_todo, _es_boton_o_menu_redondo
        )
        self.assertEqual(
            len(encontrados_sin_atributo), 1,
            "un control SIN el atributo aria-label (nunca lo llegó a pintar) tampoco debía "
            "desaparecer del barrido de R7",
        )

    def test_mutacion_una_opcion_de_menu_que_apunta_a_un_ancla_inexistente_se_pone_rojo(self):
        """H7 (revisión 3), reproducido EXACTAMENTE: el marcado real de
        `_ui.html#boton_redondo_menu` (mismo envoltorio `fixed`, mismo disparador, mismas dos
        opciones con `role="menuitem"`) con UNA opción apuntando a un ancla que la página nunca
        declara. `_es_item_de_menu` tiene que reconocer la opción por su `role`, y
        `_destino_de_ancla_interna_no_existe` tiene que decir que el destino NO existe — nunca
        leyendo el fichero fuente, siempre sobre el HTML ya renderizado."""
        html_con_menu_redondo = (
            '<div class="pointer-events-none fixed inset-x-0 z-40" x-data="{ abierto: false }">'
            '<div class="mx-auto w-full max-w-movil px-4"><div class="relative flex justify-end">'
            '<button type="button" @click="abierto = !abierto" @click.outside="abierto = false" '
            ':aria-expanded="abierto" aria-haspopup="true" aria-label="Abrir dos cosas" '
            'class="pointer-events-auto flex h-14 w-14 items-center justify-center '
            'rounded-pastilla bg-tinta text-white shadow-lg active:scale-95">+</button>'
            '<div x-show="abierto" role="menu" aria-label="Abrir dos cosas" '
            'class="pointer-events-auto absolute bottom-16 right-0 w-56 rounded-control '
            'bg-superficie py-1 shadow-lg ring-1 ring-linea">'
            '<a href="#destino-1-que-no-existe" role="menuitem" class="block px-4 py-2 '
            'text-[15px] text-tinta">Uno</a>'
            '<a href="#formulario-de-verdad" role="menuitem" class="block px-4 py-2 '
            'text-[15px] text-tinta">Dos</a>'
            '</div></div></div></div><div id="formulario-de-verdad"></div>'
        )
        items = elementos_con_texto(html_con_menu_redondo, _es_item_de_menu)
        self.assertEqual(
            len(items), 2,
            "la firma no reconoció las opciones REALES de boton_redondo_menu: el mutante no "
            "probaría nada",
        )
        rotas = {
            texto: _destino_de_ancla_interna_no_existe(html_con_menu_redondo, attrs)
            for attrs, texto in items
        }
        self.assertEqual(
            rotas, {"Uno": "destino-1-que-no-existe", "Dos": ""},
            "una opción de menú que apunta a un ancla que no existe debía detectarse como rota, "
            "y la que sí existe no debía reportar nada",
        )

    def test_mutacion_un_menu_redondo_con_x_data_renombrado_se_pone_rojo(self):
        """Pieza 7 del módulo compartido (`el_estado_es_compartido`): el disparador y el menú de
        `boton_redondo_menu` tienen que colgar del MISMO `x-data` que declara `abierto` —
        renombrar la variable (aquí, `abiertoV2`) los deja perfectos por separado y el menú no
        abre jamás. Reproducido con el marcado REAL del disparador y del menú."""
        html_con_x_data_renombrado = (
            '<div class="pointer-events-none fixed inset-x-0 z-40" x-data="{ abiertoV2: false }">'
            '<div class="relative flex justify-end">'
            '<button type="button" @click="abierto = !abierto" @click.outside="abierto = false" '
            ':aria-expanded="abierto" aria-haspopup="true" aria-label="Abrir dos cosas" '
            'class="pointer-events-auto flex h-14 w-14 items-center justify-center '
            'rounded-pastilla bg-tinta text-white shadow-lg active:scale-95">+</button>'
            '<div x-show="abierto" role="menu" aria-label="Abrir dos cosas" '
            'class="pointer-events-auto absolute bottom-16 right-0 w-56 rounded-control '
            'bg-superficie py-1 shadow-lg ring-1 ring-linea">'
            '<a href="#a" role="menuitem" class="block px-4 py-2 text-[15px] text-tinta">Uno</a>'
            '</div></div></div>'
        )
        self.assertTrue(
            elementos_con_texto(html_con_x_data_renombrado, _es_disparador_de_menu_redondo),
            "la firma no reconoció el disparador REAL de boton_redondo_menu: el mutante no "
            "probaría nada",
        )
        with self.assertRaises(
            AssertionError, msg="un x-data renombrado debía romper el_estado_es_compartido"
        ):
            el_estado_es_compartido(
                self, html_con_x_data_renombrado, _es_disparador_de_menu_redondo,
                _es_menu_redondo_abierto, "abierto",
            )


# ------------------------------------------------------------------------------------------ #
# R7 (la mitad ESTRUCTURAL) — los controles que abren algo se comprueban importando
# `kcalibra.ayuda_de_alcanzabilidad`, nunca copiándola. Guarda ESTRUCTURAL: ningún fichero de
# tests redefine las piezas del módulo compartido — si alguien las copiara a mano (el error que
# abrió siete agujeros en la 053), este barrido lo cazaría por la FORMA del fichero, no leyendo
# el diff.
# ------------------------------------------------------------------------------------------ #

_NOMBRES_DE_LAS_OCHO_PIEZAS = (
    "TAPADERAS_DE_CLASE", "TAPADERAS_DE_ESTILO", "CadenaDeAncestros", "cadena_unica",
    "claves_de_primer_nivel", "nada_lo_tapa", "el_estado_es_compartido", "re_de_atributo",
)


def _ficheros_de_test_que_redefinen_piezas(raiz, modulo_compartido):
    """El barrido recorre TODO fichero `test*.py` del árbol — `rglob`, no `glob`: cubre
    `tests_x.py` Y `test_x.py` (el patrón `test*.py` casa con los dos) en CUALQUIER
    subdirectorio, las mismas dos formas que `manage.py test` descubre y ejecuta por defecto.
    (Hueco medido en la revisión, H4: `BASE_DIR.glob("*/tests*.py")` no bajaba de un nivel ni
    casaba `test_*.py` — `paginas/test_copia.py` y `paginas/pruebas/tests_copia.py` colaban en
    verde con una redefinición dentro.) Salvo el propio módulo compartido: se busca una
    definición PROPIA (`def nombre(` / `class nombre` / `nombre =`) de cualquiera de las ocho
    piezas — no una lista de ficheros de test escrita a mano: un fichero de test nuevo que
    copiara el patrón entraría solo en este barrido."""
    raiz = Path(raiz)
    con_copia = {}
    for ruta in sorted(raiz.rglob("test*.py")):
        if ruta.resolve() == Path(modulo_compartido).resolve():
            continue
        if ".venv" in ruta.parts:
            continue
        texto = _texto(ruta)
        redefinidas = [
            nombre for nombre in _NOMBRES_DE_LAS_OCHO_PIEZAS
            if re.search(rf"^(def|class)\s+{nombre}\b|^{nombre}\s*=", texto, re.M)
        ]
        if redefinidas:
            con_copia[str(ruta.relative_to(raiz))] = redefinidas
    return con_copia


class R7_LaAlcanzabilidadSeImportaNuncaSeCopiaTests(SimpleTestCase):
    databases = set()

    def test_ningun_fichero_de_tests_redefine_las_piezas_de_alcanzabilidad(self):
        con_copia = _ficheros_de_test_que_redefinen_piezas(
            BASE_DIR, BASE_DIR / "kcalibra" / "ayuda_de_alcanzabilidad.py"
        )
        self.assertEqual(
            con_copia, {},
            f"estos ficheros REDEFINEN piezas de ayuda_de_alcanzabilidad en vez de importarlas: {con_copia}",
        )

    def test_mutacion_una_redefinicion_se_detecta_en_test_guion_bajo_y_en_subdirectorios(self):
        """R9 en código, y el propio Hueco H4 de la revisión: la misma redefinición, pegada dos
        veces, cambiando sólo DÓNDE y CÓMO se llama el fichero — `test_x.py` (guion bajo, no
        `tests_x.py`) y un fichero DOS niveles bajo la raíz — para probar el `rglob`, no sólo
        el regex de la pieza (eso ya lo prueba, indirectamente, el test de arriba)."""
        with TemporaryDirectory() as tmp:
            definicion = "def nada_lo_tapa(caso, contenido, coincide, nombre):\n    pass\n"
            con_guion_bajo = Path(tmp) / "paginas" / "test_copia_de_revision.py"
            con_guion_bajo.parent.mkdir(parents=True)
            con_guion_bajo.write_text(definicion)
            en_subdirectorio = Path(tmp) / "paginas" / "pruebas" / "tests_copia.py"
            en_subdirectorio.parent.mkdir(parents=True)
            en_subdirectorio.write_text(definicion)

            con_copia = _ficheros_de_test_que_redefinen_piezas(
                tmp, Path(tmp) / "kcalibra" / "ayuda_de_alcanzabilidad.py"
            )
            self.assertEqual(
                con_copia,
                {
                    "paginas/test_copia_de_revision.py": ["nada_lo_tapa"],
                    "paginas/pruebas/tests_copia.py": ["nada_lo_tapa"],
                },
            )
