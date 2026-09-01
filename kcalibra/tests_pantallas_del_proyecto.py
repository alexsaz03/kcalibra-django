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
from datetime import timedelta
from html.parser import HTMLParser
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django import forms
from django.apps import apps
from django.conf import settings
from django.template import engines
from django.template import Context as ContextoDeDjango
from django.template.base import Origin as OrigenDeDjango, Template as PlantillaDeDjango, TextNode
from django.template.loader import get_template
from django.template.utils import get_app_template_dirs
from django.test import Client, SimpleTestCase
from django.utils import timezone
from django.utils.html import escape

from cierres.logica import dia_pendiente_de_preguntar
from cierres.models import CierreDeDia
from cuentas.ayuda_pruebas import PruebaConRegistroAbierto
from despensa.logica import _PALABRA_DE_UNIDAD, _PLURAL_SI_NO_ES_UNA
from despensa.models import UNIDADES
from hogares.models import Persona, SolicitudEntrada
from planes.models import PlanDeDia
from recetas.models import Receta

import kcalibra.tests_pantallas as _tests_pantallas
import kcalibra.tests_pantallas_de_la_casa as _tests_pantallas_de_la_casa
from kcalibra.ayuda_de_alcanzabilidad import atributos, el_estado_es_compartido, elementos_con_texto
from kcalibra.tests_nada_escondido import _rutas_enlazadas
from kcalibra.tests_pantallas import (
    _CLASE_CON_ETIQUETA_RE,
    _CLASES_DEL_BOTON_REDONDO,
    _ETIQUETAS_DE_BLOQUE,
    _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE,
    _ETIQUETAS_INLINE,
    _PALETA_VIEJA_RE,
    _VARIABLE_DE_DJANGO_RE,
    SIN_CIERRE,
    _NumerosDeDatoEnElTexto,
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

    def test_mutacion_extends_con_variantes_de_espacio_y_comillas_sigue_siendo_pantalla(self):
        """H37-L (vuelta 20 de la 059, BLOQUEANTE) — `_es_pantalla` decide con un REGEX
        (`_EXTENDS_BASE_RE`), no comparando una subcadena fija: Django acepta cualquier
        cantidad de espacio alrededor de `{%`/`extends`/`%}` y comillas simples o dobles —
        las dos formas de abajo son `{% extends %}` igual de válido. Medido por el revisor
        (Revisión 16, D3): sustituir el regex por
        `'{% extends "base.html" %}' in texto` (subcadena FIJA, un único espacio y comilla
        doble) deja los 205 tests de `kcalibra` en verde — porque ninguna de las 25 pantallas
        reales de hoy usa una variante distinta, no porque el defecto no exista."""
        with TemporaryDirectory() as tmp:
            for variante in ("{%extends 'base.html'%}", '{%  extends  "base.html"  %}'):
                with self.subTest(variante=variante):
                    ruta = Path(tmp) / "pantalla_de_prueba_h37l.html"
                    ruta.write_text(variante)
                    self.assertTrue(
                        _es_pantalla(ruta),
                        f"«{variante}» (HTML/Django igualmente válido, distinto espaciado o "
                        f"tipo de comilla) no se reconoció como pantalla: `_es_pantalla` "
                        f"volvió a comparar una subcadena fija en vez de un regex",
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
# H12 (revisión 7 de la 059, MEDIO) — el trinquete que le faltaba a `_ETIQUETAS_INLINE`: toda
# etiqueta que el árbol de plantillas usa de verdad tiene que estar NOMBRADA en una de las dos
# listas de `kcalibra/tests_pantallas.py` (`_ETIQUETAS_INLINE`, `_ETIQUETAS_DE_BLOQUE`) — el
# mismo papel que R8 hace para `EXCEPCIONES`: hasta esa vuelta, `_ETIQUETAS_INLINE` era una
# lista cerrada sin trinquete, la CUARTA de esta unidad, y nueve etiquetas que el árbol ya usaba
# (`button`, `label`, `input`, `svg`, `select`, `option`, `path`, `circle`, `template`) llevaban
# desde siempre sin que nadie las clasificara. (Hubo una tercera lista, `_ETIQUETAS_SIN_TEXTO`,
# entre la 7ª y la 8ª vuelta — H14, `kcalibra/tests_pantallas.py`, la retiró por perder
# cobertura: hoy sólo quedan dos.)
#
# H13 (revisión 8 de la 059, BLOQUEANTE) — este trinquete mira los `.html` del REPOSITORIO, pero
# `_NumerosDeDatoEnElTexto` (R5/R6, más abajo) actúa sobre HTML ya RENDERIZADO: son poblaciones
# DISTINTAS, y algo que llega al HTML sin pasar por un `.html` propio —un widget de Django
# (`forms.Textarea`), `mark_safe`, `format_html`, `|safe`— le es invisible a este trinquete.
# Medido, sin mutar nada: `<textarea>` aparece en nueve páginas reales de hoy (lo emiten
# `recetas/forms.py`, `perfiles/forms.py`, `hogares/forms.py`), no está en NINGÚN `.html` del
# repo, y no estaba clasificado — el trinquete de abajo seguía en VERDE. Por eso hay un SEGUNDO
# trinquete, `_etiquetas_sin_clasificar_en_paginas` (justo después), que corre sobre la MISMA
# población que la red: páginas YA renderizadas, dentro del barrido de R5 que ya las tiene en la
# mano — cero renderizados extra. Los dos trinquetes se quedan, ninguno sustituye al otro: el de
# aquí abajo caza lo que una RAMA de plantilla usa y el recorrido de R5/R6 no llega a pintar; el
# de páginas renderizadas caza lo que sale al HTML sin pasar por ningún `.html` propio.
# ------------------------------------------------------------------------------------------ #


class _RecolectorDeEtiquetas(HTMLParser):
    """El NOMBRE de cada etiqueta que el parser ve — ni atributos ni texto, que es lo único que
    hace falta para el trinquete de abajo. Recoge en `handle_starttag` Y `handle_endtag`.

    H16 (revisión 9 de la 059, MEDIO) — hasta esta vuelta sólo implementaba `handle_starttag`,
    pero `_NumerosDeDatoEnElTexto` (`kcalibra/tests_pantallas.py`) consulta `_ETIQUETAS_INLINE`
    en DOS sitios — `handle_starttag` Y `handle_endtag` — para decidir si un salto de etiqueta
    pega o separa el texto de dato de su unidad: una etiqueta que llegue al HTML renderizado
    SÓLO como cierre (una `</mark>` huérfana, típica de un `mark_safe`/`format_html`
    desbalanceado) decide esa pega-o-separa igual que una etiqueta completa, y este recolector,
    con sólo aperturas, no la veía nunca — apagaba una detección real con la suite entera en
    verde. Medido (`.runtime/rev9-revision/d1_punto_ciego.py` de la revisión 9): con
    `help_text=mark_safe("… 300 Gra</mark>mos.")`, la red deja de detectar «300 Gramos» y el
    trinquete, antes de esta vuelta, no decía nada — `Ran 85 tests … OK`.

    `HTMLParser.handle_startendtag` (un `<path … />` autocerrado) ya llama a `handle_starttag` Y
    a `handle_endtag` por dentro —es la implementación por defecto de `html.parser`—, así que no
    hace falta sobrescribirlo aparte: con las dos aquí abajo, una etiqueta autocerrada añade el
    mismo nombre dos veces a un `set`, sin efecto."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.etiquetas = set()

    def handle_starttag(self, etiqueta, atributos_crudos):
        self.etiquetas.add(etiqueta)

    def handle_endtag(self, etiqueta):
        self.etiquetas.add(etiqueta)


def _plantillas_del_arbol_propio(directorios=None):
    """`_todas_las_plantillas_html` (arriba) incluye TODO lo que Django ve, y `django.contrib.
    admin` está en `INSTALLED_APPS` — así que también trae las plantillas VENDIDAS de paquetes
    instalados (`django/contrib/admin/templates/…`, `allauth/templates/…`, bajo
    `site-packages`), que nadie de este proyecto escribe ni puede clasificar y que no son "el
    árbol" que el encargo de H12 pide vigilar (medido: sin este filtro, el inventario de
    etiquetas subía de 36 a 58 y aparecían básicamente las plantillas propias de Django/allauth,
    nunca tocadas por esta unidad). Se filtra por `site-packages` en la ruta — no por `.venv` —
    porque es portable a cualquier nombre de entorno virtual. El `directorios` que usa el test
    EN CÓDIGO más abajo (un directorio de usar y tirar) nunca cae bajo `site-packages`, así que
    el filtro no le afecta."""
    return [
        r for r in _todas_las_plantillas_html(directorios)
        if "site-packages" not in Path(r).resolve().parts
    ]


def _etiquetas_usadas_en_el_arbol(directorios=None):
    """Toda etiqueta HTML que aparece de verdad en las plantillas PROPIAS del proyecto — misma
    definición de caso que R1 (lo que Django ve, no una lista escrita a mano). Se despoja
    `{% … %}`/`{# … #}` antes de parsear (`_ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE`, ya usado por
    el resto de este fichero): una etiqueta de Django partida a mitad por su propia sintaxis
    (`<div {% if … %}data-x="1"{% endif %}>`) confunde a `html.parser` si no se limpia antes —
    medido: sin este paso aparecían etiquetas fantasma como `div{%`/`h{{` que no existen en
    ningún HTML real."""
    etiquetas = set()
    for ruta in _plantillas_del_arbol_propio(directorios):
        recolector = _RecolectorDeEtiquetas()
        recolector.feed(_ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE.sub("", _texto(ruta)))
        etiquetas |= recolector.etiquetas
    return etiquetas


def _etiquetas_sin_clasificar(directorios=None):
    """Lo que R8 hace para `EXCEPCIONES`, aquí para la separación de H11/H12: cualquier etiqueta
    del árbol que no esté en NINGUNA de las dos listas explícitas."""
    clasificadas = _ETIQUETAS_INLINE | _ETIQUETAS_DE_BLOQUE
    return sorted(_etiquetas_usadas_en_el_arbol(directorios) - clasificadas)


def _etiquetas_sin_clasificar_en_paginas(paginas):
    """H13 (revisión 8 de la 059, BLOQUEANTE) — la MISMA pregunta que `_etiquetas_sin_clasificar`
    (arriba), pero sobre la población REAL sobre la que actúa `_NumerosDeDatoEnElTexto`: HTML YA
    RENDERIZADO, no los `.html` del repositorio. `TodaEtiquetaUsadaEnElArbolEstaClasificadaTests`
    cierra H12 mirando el árbol de plantillas — pero un widget de Django (`forms.Textarea`),
    `mark_safe`, `format_html` o un filtro `|safe` puede poner una etiqueta en el HTML servido sin
    que exista en ningún `.html` propio, y ese trinquete no la ve (medido: `<textarea>` en nueve
    páginas reales de hoy, en ningún `.html` del repo, sin clasificar en ninguna de las dos
    listas — sobre HEAD limpio, sin mutar nada).

    `paginas` es una lista de `(ruta, contenido)` YA renderizado — la misma forma que devuelve
    `_paginas_de_pantallas_reales` — para que quien la llame no tenga que renderizar nada de más:
    el barrido de R5 (abajo) ya tiene ese HTML en la mano antes de comprobar `.cifra`, con cero
    renderizados extra.

    Lo que esto garantiza: la misma LISTA DE RUTAS que recorre la red. Los EVENTOS de parseo
    (`handle_starttag`/`handle_endtag`) los comparten por COPIA A MANO, NO por construcción —
    `_RecolectorDeEtiquetas` y `_NumerosDeDatoEnElTexto` son dos subclases de `HTMLParser`
    independientes que alguien mantiene sincronizadas, y hasta H18 (revisión 10) nada lo
    comprobaba. Y `_NumerosDeDatoEnElTexto` consulta, por cada etiqueta, una TERCERA estructura
    que ninguno de los dos trinquetes de arriba vigilaba — `SIN_CIERRE`
    (`kcalibra/ayuda_de_alcanzabilidad.py`), que decide si la etiqueta entra en la cadena de
    ancestros que R5/R6 usan para eximir por `.cifra` — hasta que
    `test_toda_etiqueta_vacia_clasificada_esta_en_sin_cierre` (abajo) se convirtió en el
    tercero. Lo que tampoco garantiza: `paginas` es el HTML del PRIMER render de cada ruta;
    `_NumerosDeDatoEnElTexto` recorre un SEGUNDO render de las mismas rutas, hecho bajo
    `_con_procedencia_marcada` —no es el mismo HTML byte a byte, aunque hoy produzca las mismas
    etiquetas (medido, revisión 9: `RED − TRINQUETE = []`)."""
    clasificadas = _ETIQUETAS_INLINE | _ETIQUETAS_DE_BLOQUE
    etiquetas = set()
    for _, contenido in paginas:
        recolector = _RecolectorDeEtiquetas()
        recolector.feed(contenido)
        etiquetas |= recolector.etiquetas
    return sorted(etiquetas - clasificadas)


# H18 (revisión 10 de la 059, MEDIO) — el trinquete que le faltaba a `SIN_CIERRE`
# (`kcalibra/ayuda_de_alcanzabilidad.py`): `_NumerosDeDatoEnElTexto.handle_starttag`
# (`kcalibra/tests_pantallas.py`) decide DOS cosas por etiqueta, contra DOS estructuras — si
# pega o separa (`_ETIQUETAS_INLINE`, vigilada por el trinquete de arriba) Y si entra en la
# cadena de ancestros (`SIN_CIERRE`, que NINGÚN trinquete vigilaba). Una etiqueta perfectamente
# clasificada (trinquete de arriba VERDE) que HTML considere VACÍA y que falte de `SIN_CIERRE`
# se apila y no se desapila NUNCA —no hay cierre que la saque—, así que se queda de ancestro de
# todo lo que venga detrás dentro de su padre y le regala su `class="cifra"`: falso VERDE.
# `_VACIAS_DE_HTML` es universo EXTERNO (las 13 "void elements" del HTML Living Standard vigente
# — `param` salió de esa lista, pero se deja aquí de más: sólo puede apretar, nunca aflojar), no
# una lista de pantallas ni de piezas de este proyecto: sirve sólo para comprobar la COHERENCIA
# entre lo que el trinquete de arriba ya clasifica y lo que `SIN_CIERRE` cubre.
_VACIAS_DE_HTML = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


def _etiquetas_vacias_clasificadas_sin_sin_cierre(clasificadas=None, sin_cierre=None, vacias=None):
    """H18: qué etiquetas están CLASIFICADAS (`_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE`) y son
    VACÍAS de HTML, pero `SIN_CIERRE` no las trae — el hueco exacto que deja una etiqueta
    apilada para siempre en `_NumerosDeDatoEnElTexto`. Los tres conjuntos son PARÁMETROS (nunca
    los reales metidos a fuego en el cuerpo) para que la mutación de
    `TodaEtiquetaUsadaEnElArbolEstaClasificadaTests` los sustituya por sintéticos, nunca por los
    reales."""
    clasificadas = _ETIQUETAS_INLINE | _ETIQUETAS_DE_BLOQUE if clasificadas is None else clasificadas
    sin_cierre = SIN_CIERRE if sin_cierre is None else sin_cierre
    vacias = _VACIAS_DE_HTML if vacias is None else vacias
    return sorted((vacias & clasificadas) - set(sin_cierre))


_LA_ETIQUETA_DEL_HUECO_H18_FUERA_DE_FICHEROS = "wbr"


def _es_el_hueco_h18_fuera_de_ficheros(etiqueta):
    """`wbr` (revisión 10 de la 059, H18): está en `_ETIQUETAS_INLINE` desde H11 (revisión 6) y
    ausente de `SIN_CIERRE` — `kcalibra/ayuda_de_alcanzabilidad.py`, fuera de `ficheros:` de
    esta unidad, no se puede tocar aquí ("Reglas del constructor"). Se propone en
    `hallazgos.md` que el padre añada `wbr` a `SIN_CIERRE`. Trinqueteada aparte, como
    `_es_el_hueco_r6_fuera_de_ficheros` (arriba): si el padre ya la corrigió, este test se pone
    ROJO pidiendo borrar la excepción, en vez de quedarse callado para siempre en verde."""
    return etiqueta == _LA_ETIQUETA_DEL_HUECO_H18_FUERA_DE_FICHEROS


# H20 (revisión 11 de la 059, MEDIO) — el mismo mecanismo de H18, una familia de etiquetas más
# allá. H18 cerró las VACÍAS: una etiqueta clasificada, vacía de HTML, ausente de `SIN_CIERRE`,
# se apila y no se desapila nunca. Pero hay una SEGUNDA forma de dejar una etiqueta apilada para
# siempre sin que sea "vacía": el HTML Living Standard permite dejar SIN cerrar `<p>`, `<li>`,
# `<dt>`, `<dd>`, `<option>`… (cierre opcional), de TRES formas — cualquier navegador la
# autocierra (a) al abrir el siguiente HERMANO del mismo tipo, (b) al abrirse dentro de ella un
# HIJO que su modelo de contenido no admite (un `<p>` sólo admite contenido de frase: CUALQUIER
# etiqueta de bloque que se abra dentro la cierra sola, `§13.1.2.4`), o (c) al cerrarse su PADRE
# estando ella todavía abierta — y `html.parser` NO implementa ninguna de las tres: la etiqueta
# se queda en la pila de `CadenaDeAncestros`/`_ElementosConTexto`/`_NumerosDeDatoEnElTexto` igual
# que `wbr`, regalando su `class="cifra"` a todo lo que la siga dentro de su padre.
#
# `_CIERRE_OPCIONAL_DE_HTML` es universo EXTERNO (igual que `_VACIAS_DE_HTML`, arriba): la lista
# completa de etiquetas de cierre opcional del HTML Living Standard, no una lista de pantallas ni
# de piezas de este proyecto. Lo que hace falta vigilar no es TODO ese universo (etiquetas de
# tabla como `<tr>`/`<td>` no están clasificadas hoy, y clasificarlas no es parte de este hueco),
# sino la INTERSECCIÓN con lo que el proyecto YA clasifica — el mismo patrón que
# `_etiquetas_vacias_clasificadas_sin_sin_cierre` usa para H18.
_CIERRE_OPCIONAL_DE_HTML = frozenset({
    "html", "head", "body", "p", "li", "dt", "dd", "option",
    "optgroup", "colgroup", "caption", "thead", "tbody", "tfoot", "tr", "td", "th", "rp", "rt",
})


def _etiquetas_de_cierre_opcional_clasificadas(clasificadas=None, cierre_opcional=None):
    """H20: qué etiquetas CLASIFICADAS (`_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE`) son, además,
    de cierre opcional en HTML — la población exacta que el trinquete de abajo vigila. Parámetros,
    no los reales metidos a fuego, por la misma razón que en H18: para que la mutación los
    sustituya por sintéticos."""
    clasificadas = _ETIQUETAS_INLINE | _ETIQUETAS_DE_BLOQUE if clasificadas is None else clasificadas
    cierre_opcional = _CIERRE_OPCIONAL_DE_HTML if cierre_opcional is None else cierre_opcional
    return cierre_opcional & clasificadas


# H27/H28 (vuelta 18 de la 059, revisión 14) — hasta esta vuelta, la regla (1) de
# `_ContadorDeAperturasYCierres` preguntaba `etiqueta in _ETIQUETAS_DE_BLOQUE`
# (`kcalibra/tests_pantallas.py`). Esa lista NO es el universo de lo que pregunta la regla: nació
# para clasificar "qué etiquetas usa el árbol como bloque" (H12), no "qué etiquetas provocan el
# *implied end tag* de `<p>`" — y las dos preguntas se cruzan mal por los dos lados. Trae `svg`,
# `script` y `template`, que son contenido de frase/metadatos LEGAL dentro de un `<p>` y que
# ningún navegador usa para cerrarlo (H27, falso ROJO: un `{% include "_iconos.html#…" %}` dentro
# de un `<p>` real ponía la suite roja con el mensaje equivocado). Y le falta `hr`, que SÍ cierra
# un `<p>` (§13.2.6.4.7) y que además es una etiqueta VACÍA: como la regla (1) sólo se evaluaba
# tras el `return` de "no apilar lo que HTML no cierra", clasificar `hr` como bloque no bastaba
# para que la regla (1) llegara a verla — indetectable por construcción (H28, falso VERDE
# BLOQUEANTE: la altura de `perfiles/ver.html` se quedaba fuera de su `<p class="cifra">` con la
# suite entera en verde).
#
# `_CIERRAN_UN_PARRAFO_DE_HTML` es el universo EXTERNO correcto: hermana de `_VACIAS_DE_HTML` y
# `_CIERRE_OPCIONAL_DE_HTML` — no una lista que le convino a otro trinquete.
#
# H31 (revisión 15 de la 059, BLOQUEANTE) — esta constante se declaró, TRES veces y con esas
# palabras, "la lista LITERAL del HTML Living Standard §13.2.6.4.7". No lo era: quien la escribió
# transcribió a mano el bloque grande del estándar (`address…ul`) y dio por transcritas las demás
# reglas de *close a p element*, que están en párrafos aparte — faltaban `li`, `dd`, `dt` y
# `search`, y las tres primeras estaban en `_ETIQUETAS_DE_BLOQUE` hasta la vuelta anterior a ésta,
# así que fue además una REGRESIÓN (se cazaban antes de que naciera esta constante). El defecto de
# fondo no era "faltan cuatro etiquetas": era que el conjunto colgaba de que un humano recordara
# bien el estándar, sin nada que lo comprobara. Por eso esta constante YA NO se declara "literal
# del estándar" de palabra: se ACREDITA, con un test permanente
# (`LaConstanteCierranUnParrafoDeHtmlCoincideConElNavegadorTests`, más abajo), contra un navegador
# de verdad (Chromium vía Playwright) — para cada etiqueta candidata, la verdad es lo que el DOM
# hace con `<p>x<ETIQUETA>y</p>`, no lo que alguien recuerde. Ese test es el que impide que esta
# lista se vuelva a desviar del estándar en silencio; el comentario de aquí ya no es la autoridad.
# Incluye los obsoletos que el estándar sigue tratando igual (`center`, `dir`, `listing`,
# `plaintext`, `xmp`).
_CIERRAN_UN_PARRAFO_DE_HTML = frozenset({
    "address", "article", "aside", "blockquote", "center", "dd", "details", "dialog", "dir",
    "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hgroup", "hr", "li", "listing", "main", "menu", "nav", "ol", "p", "plaintext",
    "pre", "search", "section", "summary", "table", "ul", "xmp",
})


# H31 (revisión 15 de la 059, BLOQUEANTE) — la sonda contra el navegador de abajo necesita un
# UNIVERSO de etiquetas candidatas a comprobar, y construirlo escribiendo una lista nueva a mano
# sería repetir exactamente el error que abrió H31 (un conjunto que sale de lo que alguien
# recuerda). En vez de eso: la base es la UNIÓN de las cinco listas que el proyecto YA mantiene
# (`_ETIQUETAS_INLINE`, `_ETIQUETAS_DE_BLOQUE`, `_VACIAS_DE_HTML`, `_CIERRE_OPCIONAL_DE_HTML`,
# `_CIERRAN_UN_PARRAFO_DE_HTML`) — así el propio caso de H31 (`li`/`dd`/`dt`, ya clasificadas en
# otra lista) queda cubierto sin transcribir nada nuevo. Y como esa unión sólo trae lo que el
# ÁRBOL DE HOY usa (H12: ninguna plantilla usa `search` todavía), se amplía a mano con el resto
# de "contenido de flujo" del HTML Living Standard — `search`, el elemento concreto de H31,
# incluido. Que esta ampliación no sea perfectamente exhaustiva es un riesgo ACOTADO y no la
# misma clase de fallo que H31: una etiqueta que falte aquí queda SIN EJERCITAR (igual que hoy,
# ni mejor ni peor), nunca produce un veredicto INCORRECTO sobre lo que sí se ejercita — al
# contrario que `_CIERRAN_UN_PARRAFO_DE_HTML` antes de este arreglo, donde faltar de la lista
# significaba "el código actúa como si no cerrara, y nada lo comprueba nunca".
_ETIQUETAS_DESCARTADAS_DE_LA_SONDA_POR_SER_OTRA_FAMILIA = frozenset({
    # Singletons de la estructura del documento: sueltas dentro de un `<p>`, el parser FUSIONA
    # sus atributos con el `<html>`/`<head>`/`<body>` implícito que ya existe, o las descarta
    # (`frameset`/`frame`, obsoletas fuera de un documento de frames) — la sonda las vería "fuera
    # del párrafo" por ese motivo, no por §13.2.6.4.7. Medido con Playwright, `.runtime/v19/`.
    "html", "head", "body", "frameset", "frame",
    # Sub-estructura de `<table>`: sueltas fuera de una tabla, el parser las DESCARTA enteras (ni
    # quedan en el documento) — la sonda las vería igual de "fuera del párrafo" sin que eso diga
    # nada sobre si cierran un `<p>`. Medido con Playwright, `.runtime/v19/`.
    "col", "colgroup", "caption", "thead", "tbody", "tfoot", "tr", "td", "th",
})
_CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR = frozenset(
    (_ETIQUETAS_INLINE | _ETIQUETAS_DE_BLOQUE | _VACIAS_DE_HTML | _CIERRE_OPCIONAL_DE_HTML
     | _CIERRAN_UN_PARRAFO_DE_HTML)
    - _ETIQUETAS_DESCARTADAS_DE_LA_SONDA_POR_SER_OTRA_FAMILIA
    | {
        "search", "math", "audio", "canvas", "cite", "data", "datalist", "del", "iframe", "ins",
        "kbd", "legend", "map", "mark", "meter", "noscript", "object", "output", "picture",
        "progress", "q", "ruby", "s", "samp", "slot", "style", "time", "title", "u", "var",
        "video", "bdi", "bdo", "big", "strike", "tt", "marquee", "nobr", "noembed",
    }
)


class LaSondaNoDescartaNingunaEtiquetaDeLaConstantePropiaTests(SimpleTestCase):
    """H35 (Revisión 16 de la 059, MEDIO) — `_ETIQUETAS_DESCARTADAS_DE_LA_SONDA_POR_SER_OTRA_
    FAMILIA` es una VÁLVULA sin vigilar: se resta de la unión de las cinco listas que construyen
    `_CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR` —incluida `_CIERRAN_UN_PARRAFO_DE_HTML`, la propia
    constante que H31 acredita— y nada comprobaba que esa resta no se tragara un miembro suyo. El
    revisor midió (D1/H35, hallazgos.md): revertir H31 (sacar `li`/`dd`/`dt` de
    `_CIERRAN_UN_PARRAFO_DE_HTML`) Y meterlas en las descartadas, A LA VEZ, deja los 933 tests en
    verde — la mutación exacta de H31 vuelve a entrar por esta puerta trasera, porque las tres
    etiquetas dejan de formar parte del universo que la sonda ejercita contra el navegador.

    Este trinquete, sin depender de Playwright (compara dos `frozenset` en tiempo de import, no
    lanza ningún navegador), exige que `_CIERRAN_UN_PARRAFO_DE_HTML` sea SIEMPRE subconjunto de
    `_CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR`: si una etiqueta de la constante cae en las
    descartadas (o se quita de la unión de las cinco listas de origen), deja de ejercitarse
    contra el navegador y H31 se puede reabrir en verde por esta vía, aunque el test que SÍ
    lanza Chromium (`LaConstanteCierranUnParrafoDeHtmlCoincideConElNavegadorTests`, abajo) siga
    en verde para las etiquetas que le quedan."""

    databases = set()

    def test_ninguna_etiqueta_de_cierran_un_parrafo_esta_descartada_de_la_sonda(self):
        self.assertLessEqual(
            _CIERRAN_UN_PARRAFO_DE_HTML, _CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR,
            f"etiquetas de `_CIERRAN_UN_PARRAFO_DE_HTML` que la sonda del navegador YA NO "
            f"ejercita — la lista de descartadas se ha tragado un miembro de la propia "
            f"constante que H31 acredita: "
            f"{sorted(_CIERRAN_UN_PARRAFO_DE_HTML - _CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR)}",
        )

    def test_mutacion_meter_una_etiqueta_de_la_constante_en_las_descartadas_se_pone_rojo(self):
        """La mutación EXACTA de H35, en código: `li` (miembro real de
        `_CIERRAN_UN_PARRAFO_DE_HTML` desde H31) metido a mano en las descartadas — la
        maniobra que un desarrollador haría para "apagar un rojo raro de la sonda", el mismo
        motivo por el que el propio código ya mete ahí catorce etiquetas legítimas."""
        descartadas_con_la_valvula_abierta = (
            _ETIQUETAS_DESCARTADAS_DE_LA_SONDA_POR_SER_OTRA_FAMILIA | {"li"}
        )
        candidatos_con_la_valvula_abierta = frozenset(
            (_ETIQUETAS_INLINE | _ETIQUETAS_DE_BLOQUE | _VACIAS_DE_HTML | _CIERRE_OPCIONAL_DE_HTML
             | _CIERRAN_UN_PARRAFO_DE_HTML)
            - descartadas_con_la_valvula_abierta
        )
        self.assertNotIn(
            "li", candidatos_con_la_valvula_abierta,
            "control: la mutación debía sacar «li» del universo de la sonda",
        )
        self.assertFalse(
            _CIERRAN_UN_PARRAFO_DE_HTML <= candidatos_con_la_valvula_abierta,
            "meter «li» (miembro real de `_CIERRAN_UN_PARRAFO_DE_HTML`) en las descartadas "
            "debía romper el trinquete de subconjunto — si esto no se pone rojo, la válvula "
            "sigue sin vigilar",
        )


def _cierra_un_parrafo_segun_el_navegador(navegador, etiqueta):
    """H31 — le pregunta a un Chromium DE VERDAD (Playwright) si abrir `etiqueta` mientras hay un
    `<p>` abierto lo cierra: mete la etiqueta candidata dentro de un `<p>`, con un hijo marcado
    por `id`, y comprueba si ese hijo sigue siendo descendiente del `<p>` una vez que el navegador
    ha terminado de parsear. Si el navegador lo sacó fuera (autocierre del `<p>`), `etiqueta`
    cierra un párrafo; si lo dejó dentro, no. Sin HTML a mano de una plantilla real: la pregunta
    es sobre la etiqueta sola, aislada, que es justo lo que `_CIERRAN_UN_PARRAFO_DE_HTML`
    necesita responder.

    **El `<!DOCTYPE html>` no es decorativo aquí**: sin él, `set_content` renderiza en modo
    QUIRKS (medido, `.runtime/v19/table-sin-doctype-vs-con-doctype.txt`) y `<table>` dejó de
    cerrar el `<p>` — el estándar hace esa regla CONDICIONAL a que el documento no esté en modo
    quirks (§13.2.6.4.7: "if the Document is not set to quirks mode"). Toda plantilla real del
    proyecto lleva `<!DOCTYPE html>` (`templates/base.html:2`), así que probar sin él habría sido
    exactamente el defecto de esta unidad otra vez: medir una condición que no es la real."""
    pagina = navegador.new_page()
    try:
        pagina.set_content(
            f'<!DOCTYPE html><div><p class="sonda">antes<{etiqueta} id="marca">x</{etiqueta}>'
            f'despues</p></div>',
            timeout=5000,
        )
        dentro_del_parrafo = pagina.eval_on_selector(
            "body",
            "b => { const p = b.querySelector('p.sonda'); "
            "return p ? !!p.querySelector('#marca') : null; }",
        )
    finally:
        pagina.close()
    return not dentro_del_parrafo


class LaConstanteCierranUnParrafoDeHtmlCoincideConElNavegadorTests(SimpleTestCase):
    """H31 (revisión 15 de la 059, BLOQUEANTE) — `_CIERRAN_UN_PARRAFO_DE_HTML` se declaró TRES
    veces "la lista LITERAL del HTML Living Standard §13.2.6.4.7" sin serlo: faltaban `li`, `dd`,
    `dt` y `search` (las tres primeras, además, una REGRESIÓN — se cazaban antes de que naciera
    esta constante, vía `_ETIQUETAS_DE_BLOQUE`). El defecto de fondo no era la lista incompleta:
    era que el conjunto colgaba de lo que un humano recordara del estándar, sin nada que lo
    comprobara — y "añadir las cuatro que faltan" habría cerrado el CASO sin cerrar la FAMILIA.

    Este test cierra la familia: para cada etiqueta candidata
    (`_CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR`, arriba) le pregunta a un Chromium de verdad si
    cierra un `<p>` abierto, y compara la respuesta con la constante. La autoridad deja de ser la
    memoria de quien la escribió — es lo que el navegador hace.

    **Deliberado**: si Playwright no está instalado, o lo está pero no hay Chromium descargado
    (`playwright install chromium`), este test NO se salta en silencio — `setUpClass` revienta
    con un mensaje que lo dice, y la suite se pone ROJA. Un test que dependa de un navegador y se
    limite a `skipTest` en su ausencia es la 24ª cara de esta misma casa
    (docs/conocimiento/tests-que-no-fallan-cuando-deben.md — una red inmedible dada por buena):
    aquí la ausencia del navegador es, ella misma, un fallo del entorno que hay que arreglar, no
    un motivo para callar. Que sea lento (lanza un Chromium y abre ~100 páginas) es aceptable;
    que mienta por ausencia no."""

    databases = set()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright no está instalado en este entorno (`pip install playwright`). H31, "
                "R5 y R9 exigen acreditar `_CIERRAN_UN_PARRAFO_DE_HTML` contra un navegador de "
                "verdad — este test no puede pasar en verde por no tener con qué comprobarlo. "
                "Instala Playwright y su Chromium (`playwright install chromium`); no lo saltes."
            ) from exc
        cls._playwright = sync_playwright().start()
        try:
            cls._navegador = cls._playwright.chromium.launch()
        except Exception as exc:
            cls._playwright.stop()
            raise RuntimeError(
                "Playwright está instalado pero no pudo lanzar Chromium — probablemente falta "
                "`playwright install chromium` en este entorno. Mismo motivo que arriba: este "
                "test no puede pasar en verde sin comprobar nada de verdad."
            ) from exc

    @classmethod
    def tearDownClass(cls):
        cls._navegador.close()
        cls._playwright.stop()
        super().tearDownClass()

    def test_la_constante_coincide_elemento_a_elemento_con_el_navegador(self):
        descuadres = []
        for etiqueta in sorted(_CANDIDATOS_PARA_LA_SONDA_DEL_NAVEGADOR):
            cierra_en_navegador = _cierra_un_parrafo_segun_el_navegador(self._navegador, etiqueta)
            cierra_en_la_constante = etiqueta in _CIERRAN_UN_PARRAFO_DE_HTML
            if cierra_en_navegador != cierra_en_la_constante:
                descuadres.append(
                    f"<{etiqueta}>: el navegador dice cierra_un_parrafo={cierra_en_navegador}, "
                    f"la constante dice {cierra_en_la_constante}"
                )
        self.assertEqual(
            descuadres, [],
            f"`_CIERRAN_UN_PARRAFO_DE_HTML` no coincide con lo que un Chromium de verdad hace "
            f"— la lista no está acreditada: {descuadres}",
        )


class _ContadorDeAperturasYCierres(HTMLParser):
    """H20/H23/H25 — lleva una PILA de lo que está abierto, no un CONTEO. Un conteo (aperturas ==
    cierres) sólo caza el cierre OMITIDO (`<p>Uno<p>Dos</p>`: 2 aperturas, 1 cierre — descuadra):
    se queda ciego al cierre DESPLAZADO por un hijo que su modelo de contenido no admite
    (`<p>Resumen<dl>…</dl></p>`: el navegador cierra el `<p>` al ver el `<dl>` —regla de "implied
    end tag" de `§13.1.2.4`—, pero `html.parser` no, así que el `</p>` de después SÍ llega: 1
    apertura, 1 cierre, el conteo CUADRA y no ve nada — medido, revisión 12: `perfiles/ver.html`
    con la `.cifra` de la altura envuelta así, `<p class="cifra">` regalado al `<dl>` entero, y
    las 915 en verde). Con la pila, una etiqueta de cierre opcional CLASIFICADA se marca
    DESPLAZADA (`self.desplazadas`) en dos momentos, sin reimplementar el autocierre completo del
    HTML Living Standard — sólo el ANIDAMIENTO IMPOSIBLE para la población que este proyecto ya
    clasifica:
    (1) hay un `<p>` ABIERTO EN ALGÚN PUNTO DE LA PILA (no sólo en la cima: cualquier etiqueta
        que el navegador SÍ cierra sola —una inline sin su propio cierre, `<span>x` sin
        `</span>`— puede quedar por encima suyo, y también una etiqueta VACÍA como `<hr>`: H28,
        vuelta 18) cuando se abre una etiqueta que provoca el *implied end tag* de `<p>`
        (`_CIERRAN_UN_PARRAFO_DE_HTML`, acreditada contra un navegador de verdad — ver su
        comentario más arriba y H31, revisión 15 — universo externo, no `_ETIQUETAS_DE_BLOQUE`:
        esa lista nació para clasificar "qué usa el árbol", no "qué cierra un `<p>`", y se cruzan
        mal por los dos lados — H27/H28, vuelta 18, revisión 14) — se cierra el `<p>` Y todo lo
        que quedara abierto por encima de él, que es
        lo que hace el navegador. Esto caza, con el MISMO mecanismo, el hermano (`<p>Uno<p>Dos`),
        el hijo de bloque (`<p>Resumen<dl>`) y el hijo VACÍO que además cierra por sí mismo
        (`<p>Resumen<hr>` — H28: `<hr>` está en `_CIERRAN_UN_PARRAFO_DE_HTML` Y en
        `_VACIAS_DE_HTML` a la vez, así que la regla (1) tiene que evaluarse SIEMPRE, apile o no
        apile luego la etiqueta que la disparó), y ya no lo tapa una etiqueta vacía de por medio
        (`<p>Resumen<br><dl>` — H25, revisión 13: con la CIMA en vez de la pila entera, un
        `<br>`/`<input>`/`<wbr>` sentado encima del `<p>` bloqueaba la comparación y el `</p>`
        de después limpiaba la pila entera como si el cierre hubiera sido legítimo, `EXIT=0`
        con la altura de `perfiles/ver.html` sin su `.cifra`). No se generaliza a
        `li`/`dt`/`dd`/`option`/`body`/`head`/`html`: su modelo de contenido SÍ admite hijos de
        bloque sin autocerrarse (un `<li>` puede contener un `<div>` de sobra), así que
        aplicarles esta misma regla abriría falsos rojos sobre marcado legítimo (medido,
        revisión 13, D4) — para ellos basta (2); y `_CIERRAN_UN_PARRAFO_DE_HTML` sólo se consulta
        cuando `"p" in self.cierre_opcional`, así que sigue sin afectarlos;
    (2) se cierra un ANCESTRO suyo (con su propio `</etiqueta>` explícito, o al terminar el
        documento) mientras ella sigue abierta por debajo, sin que su propio cierre haya llegado
        antes — cubre el hermano de cualquiera de las ocho clasificadas (`<li>A<li>B</li>`: el
        `<ul>` que las envuelve arrastra a la primera al cerrarse) y el caso general de "cierre
        omitido" que el conteo ya cazaba, sin necesitar el conteo.

    Y una tercera cosa, que no es una regla de desplazamiento sino de POBLACIÓN de la pila
    misma: una etiqueta que HTML no cierra nunca (`SIN_CIERRE | _VACIAS_DE_HTML` — la unión, no
    `SIN_CIERRE` sola: `wbr` está clasificada y es vacía de HTML, pero hoy falta de `SIN_CIERRE`,
    ver `_es_el_hueco_h18_fuera_de_ficheros` más arriba) no se apila. **Esto NO es necesario para
    que la regla (1) vea el desplazamiento** (medido, revisión 14 D4 y D9: quitarlo del todo deja
    los diez casos de control idénticos, porque la regla (1) mira la PILA ENTERA, no la cima, así
    que una etiqueta vacía sentada encima de un `<p>` no le tapa nada) — es sólo higiene de la
    pila, para no dejar basura sin cierre acumulándose sin motivo (una etiqueta vacía nunca es de
    cierre opcional, así que nunca puede aparecer en `self.desplazadas` ni en el barrido final)."""

    def __init__(self, cierre_opcional=None):
        super().__init__(convert_charrefs=True)
        self.cierre_opcional = (
            _etiquetas_de_cierre_opcional_clasificadas() if cierre_opcional is None else cierre_opcional
        )
        self.pila = []
        self.desplazadas = []

    def handle_starttag(self, etiqueta, atributos_crudos):
        # Regla (1): ¿esta etiqueta provoca el *implied end tag* de `<p>`? (§13.2.6.4.7, ver el
        # docstring de la clase). SIEMPRE se evalúa, apile o no apile luego `etiqueta` — `<hr>`
        # cierra un `<p>` Y es una etiqueta vacía a la vez (H28): evaluar esto DESPUÉS de decidir
        # si apilar dejaba a `<hr>` estructuralmente indetectable. Pregunta por la PILA ENTERA
        # (¿hay algún `<p>` abierto por debajo, no sólo en la cima?), cerrando todo lo que
        # quedara abierto por encima de él — lo que hace el navegador.
        if etiqueta in _CIERRAN_UN_PARRAFO_DE_HTML and "p" in self.cierre_opcional and "p" in self.pila:
            while self.pila[-1] != "p":
                cima = self.pila.pop()
                if cima in self.cierre_opcional:
                    self.desplazadas.append(cima)
            self.desplazadas.append(self.pila.pop())
        # Higiene de la pila (ver la "tercera cosa" del docstring): nunca apilar lo que HTML no
        # cierra — si no, una de estas etiquetas ocupa la cima para siempre (nadie la desapila).
        if etiqueta not in SIN_CIERRE and etiqueta not in _VACIAS_DE_HTML:
            self.pila.append(etiqueta)

    def handle_endtag(self, etiqueta):
        # Regla (2): cualquier etiqueta de cierre opcional clasificada que quede POR DEBAJO de
        # `etiqueta` en la pila se cierra sola al cerrarse ella — se marca desplazada; `etiqueta`
        # misma, si aparece, se saca limpia (SÍ tuvo su propio cierre explícito).
        if etiqueta not in self.pila:
            return
        while self.pila[-1] != etiqueta:
            cima = self.pila.pop()
            if cima in self.cierre_opcional:
                self.desplazadas.append(cima)
        self.pila.pop()


def _etiquetas_de_cierre_opcional_sin_cerrar(contenido, cierre_opcional=None):
    """H20/H23: de las etiquetas de cierre opcional CLASIFICADAS, cuáles se quedan ABIERTAS sin
    su propio cierre explícito — por ANIDAMIENTO (`_ContadorDeAperturasYCierres`, arriba: las dos
    reglas), no por conteo. Devuelve los NOMBRES afectados, ordenados y sin duplicar — mismo
    contrato que antes de H23, así que quien ya lo llama con `cierre_opcional={"p"}` sigue
    funcionando igual. Cubre las dos formas medidas de quedarse apilada para siempre en
    `html.parser`: el cierre OMITIDO y el cierre DESPLAZADO por un hijo de bloque o por el cierre
    de un ancestro."""
    cierre_opcional = (
        _etiquetas_de_cierre_opcional_clasificadas() if cierre_opcional is None else cierre_opcional
    )
    lector = _ContadorDeAperturasYCierres(cierre_opcional)
    lector.feed(contenido)
    sin_cerrar_al_final = (etiqueta for etiqueta in lector.pila if etiqueta in cierre_opcional)
    return sorted(set(lector.desplazadas) | set(sin_cerrar_al_final))


class TodaEtiquetaUsadaEnElArbolEstaClasificadaTests(SimpleTestCase):
    databases = set()

    def test_ninguna_etiqueta_del_arbol_real_queda_sin_clasificar(self):
        sin_clasificar = _etiquetas_sin_clasificar()
        self.assertEqual(
            sin_clasificar, [],
            f"etiquetas que el árbol usa y que `_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE` "
            f"(kcalibra/tests_pantallas.py) todavía no clasifican — "
            f"H12: clasifícalas una a una con su porqué, no las adivines: {sin_clasificar}",
        )

    def test_mutacion_una_etiqueta_nueva_sin_clasificar_pone_la_suite_roja(self):
        """H12 (revisión 7 de la 059) — el trinquete demostrado EN CÓDIGO, sobre un directorio de
        usar y tirar (nunca sobre un fichero real del repositorio): una plantilla con un
        `<mark>` —justo la etiqueta de la Medición A de la Revisión 7, "algo que cualquiera
        escribiría para resaltar una letra"— tiene que aparecer como sin clasificar; borrada, el
        barrido vuelve a estar vacío."""
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp) / "paginas" / "templates" / "paginas"
            directorio.mkdir(parents=True)
            plantilla = directorio / "prueba_h12_con_mark.html"
            plantilla.write_text("<p>Texto con <mark>resaltado</mark> de verdad.</p>\n")
            sin_clasificar = _etiquetas_sin_clasificar([Path(tmp)])
            self.assertIn(
                "mark", sin_clasificar,
                "una etiqueta nueva (<mark>) en una plantilla real no apareció como sin "
                "clasificar: el trinquete no la está vigilando de verdad",
            )
            plantilla.unlink()
            sin_clasificar_despues = _etiquetas_sin_clasificar([Path(tmp)])
            self.assertEqual(
                sin_clasificar_despues, [],
                "borrar la única plantilla con `<mark>` debía vaciar el barrido sin tocar "
                "ninguna lista, igual que R1",
            )

    def test_mutacion_una_etiqueta_sin_clasificar_en_una_pagina_renderizada_pone_la_suite_roja(self):
        """H13 (revisión 8 de la 059, BLOQUEANTE) — el trinquete de arriba mira el ÁRBOL de
        `.html`; `_etiquetas_sin_clasificar_en_paginas` mira PÁGINAS RENDERIZADAS, que es la
        población de la que H13 dice que el trinquete de arriba está ciego (un widget de Django,
        `mark_safe`, `|safe`… pueden poner una etiqueta en el HTML servido sin que exista en
        ningún `.html` del repo). Demostrado EN CÓDIGO, sobre HTML sintético (nunca sobre una
        plantilla ni un formulario reales): un `<mark>` en una "página" que ningún fichero del
        repositorio escribe tiene que aparecer como sin clasificar; sin él, el barrido vuelve a
        estar vacío — el mismo patrón que la mutación de arriba, sobre la otra población."""
        sin_clasificar = _etiquetas_sin_clasificar_en_paginas(
            [("/pagina-h13-de-prueba/", "<p>Texto con <mark>resaltado</mark> de verdad.</p>")]
        )
        self.assertIn(
            "mark", sin_clasificar,
            "un <mark> en HTML renderizado (sin escribirlo en ningún .html) no apareció como "
            "sin clasificar: el trinquete de páginas renderizadas no está vigilando de verdad",
        )
        sin_clasificar_sin_mark = _etiquetas_sin_clasificar_en_paginas(
            [("/pagina-h13-de-prueba/", "<p>Texto sin resaltado de verdad.</p>")]
        )
        self.assertEqual(
            sin_clasificar_sin_mark, [],
            "quitar el único <mark> debía vaciar el barrido sin tocar ninguna lista",
        )

    def test_toda_etiqueta_vacia_clasificada_esta_en_sin_cierre(self):
        """H18 (revisión 10 de la 059, MEDIO) — los dos trinquetes de arriba exigen que TODA
        etiqueta usada esté NOMBRADA en `_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE`, pero
        `_NumerosDeDatoEnElTexto` (R5/R6, `kcalibra/tests_pantallas.py`) decide una SEGUNDA
        cosa por etiqueta —si entra en la cadena de ancestros— contra una TERCERA lista,
        `SIN_CIERRE`, que ninguno de los dos vigilaba. `wbr` es hoy ese caso (medido, revisión
        10 de hallazgos.md): clasificada como INLINE desde H11 y ausente de `SIN_CIERRE` —el
        trinquete de arriba la da por buena, pero, si algún día aparece en el árbol, se apilaría
        y no se desapilaría nunca, regalando su `class="cifra"` a todo lo que la siga."""
        descuadradas = _etiquetas_vacias_clasificadas_sin_sin_cierre()
        problemas = []
        vista_la_excepcion_wbr = False
        for etiqueta in descuadradas:
            if _es_el_hueco_h18_fuera_de_ficheros(etiqueta):
                vista_la_excepcion_wbr = True
                continue  # ver el comentario de arriba: hueco fuera de `ficheros:`
            problemas.append(etiqueta)
        if not vista_la_excepcion_wbr:
            problemas.append(
                "la excepción de `_es_el_hueco_h18_fuera_de_ficheros` ('wbr') ya no encontró "
                "su descuadre: probablemente el padre ya añadió `wbr` a `SIN_CIERRE` "
                "(kcalibra/ayuda_de_alcanzabilidad.py) — borra la excepción, el trinquete "
                "acaba de cazarla"
            )
        self.assertEqual(
            problemas, [],
            f"H18: etiquetas vacías y clasificadas que `SIN_CIERRE` no cubre: {problemas}",
        )

    def test_mutacion_una_etiqueta_vacia_sin_sin_cierre_pone_la_suite_roja(self):
        """H18 — el trinquete demostrado EN CÓDIGO, sobre conjuntos SINTÉTICOS (nunca sobre
        `_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE`/`SIN_CIERRE` reales): una etiqueta vacía y
        clasificada que falte de `SIN_CIERRE` tiene que aparecer como descuadrada; puesta
        también en `SIN_CIERRE`, el barrido vuelve a estar vacío — el mismo patrón que las dos
        mutaciones de arriba, sobre la tercera lista."""
        descuadradas = _etiquetas_vacias_clasificadas_sin_sin_cierre(
            clasificadas={"track"}, sin_cierre=set(), vacias={"track"},
        )
        self.assertEqual(
            descuadradas, ["track"],
            "una etiqueta vacía y clasificada, ausente de SIN_CIERRE, no apareció como "
            "descuadrada: el trinquete no está vigilando de verdad",
        )
        descuadradas_con_sin_cierre = _etiquetas_vacias_clasificadas_sin_sin_cierre(
            clasificadas={"track"}, sin_cierre={"track"}, vacias={"track"},
        )
        self.assertEqual(
            descuadradas_con_sin_cierre, [],
            "meter la misma etiqueta en SIN_CIERRE debía vaciar el barrido",
        )

    def test_las_etiquetas_de_cierre_opcional_clasificadas_son_las_medidas(self):
        """H20 (revisión 11 de la 059, MEDIO) — guarda de rojo mudo del propio trinquete: si
        `_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE` dejaran de clasificar alguna de estas ocho, o
        clasificaran una novena de cierre opcional, el trinquete de abajo seguiría corriendo pero
        sobre una población distinta sin que nadie lo dijera — igual que O26 puso primero la
        población de H13 y la vuelta 12 la de H21."""
        self.assertEqual(
            _etiquetas_de_cierre_opcional_clasificadas(),
            {"body", "dd", "dt", "head", "html", "li", "option", "p"},
            "la población de etiquetas de cierre opcional clasificadas ha cambiado: revisa si "
            "H20 sigue vigilando lo mismo que cuando se midió (revisión 11, D4)",
        )

    def test_ninguna_etiqueta_de_cierre_opcional_clasificada_se_queda_sin_cerrar_en_el_arbol(self):
        """H20 — el mismo trinquete que H18, sobre la MISMA población del árbol propio
        (`_plantillas_del_arbol_propio`, la definición de caso de R1): hoy, cero desbalances
        (medido, revisión 11, D4: cero en las 32 plantillas propias). Si una etiqueta de cierre
        opcional clasificada aparece SIN su cierre explícito en cualquier plantilla propia, esto
        se pone rojo nombrándola."""
        problemas = []
        for ruta in _plantillas_del_arbol_propio():
            texto = _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE.sub("", _texto(ruta))
            for etiqueta in _etiquetas_de_cierre_opcional_sin_cerrar(texto):
                problemas.append(f"{ruta}: <{etiqueta}> sin cierre explícito que cuadre")
        self.assertEqual(
            problemas, [],
            f"H20: etiquetas de cierre opcional clasificadas que el árbol deja sin cerrar "
            f"explícitamente — se apilarían para siempre en html.parser: {problemas}",
        )

    def test_mutacion_una_etiqueta_de_cierre_opcional_sin_cerrar_pone_la_suite_roja(self):
        """H20 — la mutación EN CÓDIGO, sobre HTML sintético (nunca sobre una plantilla real): un
        `<p>` sin su `</p>` explícito, con un hermano `<p>` detrás — la forma exacta medida por
        la revisión 11 (D4): HTML válido, que cualquier navegador autocierra, y que `html.parser`
        deja apilado para siempre, regalando su `class` al hermano. Con los dos `</p>` puestos,
        el barrido vuelve a estar vacío — el mismo patrón que las mutaciones de H16/H18."""
        sin_cerrar = _etiquetas_de_cierre_opcional_sin_cerrar(
            "<div><p>Uno<p>Dos</p></div>", cierre_opcional={"p"},
        )
        self.assertEqual(
            sin_cerrar, ["p"],
            "un <p> sin cerrar, seguido de un hermano <p>, no apareció como descuadrado: el "
            "trinquete no está vigilando de verdad",
        )
        cerradas_las_dos = _etiquetas_de_cierre_opcional_sin_cerrar(
            "<div><p>Uno</p><p>Dos</p></div>", cierre_opcional={"p"},
        )
        self.assertEqual(
            cerradas_las_dos, [],
            "cerrar el primer <p> explícitamente debía vaciar el barrido",
        )

    def test_mutacion_un_cierre_desplazado_por_un_hijo_de_bloque_pone_la_suite_roja(self):
        """H23 (revisión 12 de la 059, BLOQUEANTE) — la SEGUNDA forma, la que el conteo de antes
        de esta vuelta no veía: un `<p>` que envuelve un `<dl>` (o cualquier hijo de
        `_ETIQUETAS_DE_BLOQUE`) sin cerrarse ANTES de abrirlo. El navegador cierra el `<p>` solo
        al ver el `<dl>` (`§13.1.2.4`), así que el `</p>` que llega DESPUÉS no cierra nada de
        verdad — pero un CONTEO (1 apertura, 1 cierre) no lo distingue del caso legítimo. Medido
        en vivo (revisión 12): exactamente la forma en que `perfiles/ver.html:98` se quedó sin su
        `.cifra` con la suite entera en verde."""
        desplazado = _etiquetas_de_cierre_opcional_sin_cerrar(
            '<div><p class="cifra">Resumen<dl><dt>Altura</dt><dd>180 cm</dd></dl></p></div>',
            cierre_opcional={"p"},
        )
        self.assertEqual(
            desplazado, ["p"],
            "un <p> cerrado DESPUÉS de un <dl> que abre dentro no apareció como desplazado: el "
            "trinquete sigue viendo sólo conteos, no anidamiento",
        )
        # La contraprueba, para que no quepa duda de que es el ANIDAMIENTO lo que decide y no el
        # conteo (el mismo número de aperturas y cierres en los dos casos): el `</p>` puesto
        # ANTES del `<dl>`, que es HTML legítimo, no debe aparecer como problema.
        legitimo = _etiquetas_de_cierre_opcional_sin_cerrar(
            '<div><p class="cifra">Resumen</p><dl><dt>Altura</dt><dd>180 cm</dd></dl></div>',
            cierre_opcional={"p"},
        )
        self.assertEqual(
            legitimo, [],
            "un <p> cerrado ANTES del <dl> (HTML legítimo, mismo conteo que el caso de arriba) "
            "no debía aparecer como problema — si aparece, el trinquete está mirando conteos",
        )

    def test_mutacion_un_cierre_desplazado_tapado_por_una_etiqueta_vacia_pone_la_suite_roja(self):
        """H25 (revisión 13 de la 059, BLOQUEANTE) — el trinquete de arriba (H23) preguntaba por
        la CIMA de la pila (`self.pila[-1] == "p"`), y `_ContadorDeAperturasYCierres` apilaba
        TAMBIÉN las etiquetas vacías de HTML (no consultaba `SIN_CIERRE`, cosa que con un CONTEO
        daba igual y con una PILA es el fallo): cualquier `<br>`, `<input>` o `<wbr>` entre el
        texto del `<p>` y el hijo de bloque dejaba la CIMA ocupada por esa etiqueta vacía, la
        regla (1) no disparaba, y el `</p>` explícito de después limpiaba la pila entera como si
        el cierre hubiera sido legítimo. Medido en vivo (revisión 13, D2): exactamente la
        mutación de H23 de arriba, con un `<br>` de por medio, sobre `perfiles/ver.html:98` —
        `921 OK, EXIT=0`. Las tres etiquetas vacías medidas, una por una: ninguna debe tapar la
        detección ahora."""
        for vacia in ("<br>", "<input>", "<wbr>"):
            with self.subTest(vacia=vacia):
                desplazado = _etiquetas_de_cierre_opcional_sin_cerrar(
                    f'<div><p class="cifra">Resumen{vacia}<dl><dt>Altura</dt>'
                    f'<dd>180 cm</dd></dl></p></div>',
                    cierre_opcional={"p"},
                )
                self.assertEqual(
                    desplazado, ["p"],
                    f"un <p> desplazado por un <dl>, con {vacia} sentado en la cima de la pila "
                    f"en el momento del desplazamiento, no apareció como desplazado: la regla "
                    f"(1) sigue mirando sólo la cima, o {vacia} sigue apilándose",
                )

    def test_mutacion_un_inline_sin_cerrar_entre_la_vacia_y_el_hijo_de_bloque_pone_la_suite_roja(self):
        """H30 (revisión 14 de la 059, MEDIO) — el caso X, escrito porque NINGÚN test anterior lo
        cubría: con `<br>`/`<input>`/`<wbr>` puestos DIRECTAMENTE sobre la cima del `<p>` (el test
        de arriba), cualquiera de las dos mitades del arreglo de H25 —"no apilar lo vacío" o "la
        pila ENTERA, no sólo la cima"— basta por sí sola para verlo, y por eso ningún test las
        distinguía: se puede revertir cualquiera de las dos y las 55 del módulo siguen en verde
        (medido, revisión 14 D4). Aquí, entre medias, se cuela un INLINE SIN CERRAR (`<span>x`,
        sin `</span>`): con "no apilar lo vacío" puesta pero la pila entera revertida a
        `self.pila[-1] == "p"`, la cima en el momento del `<dl>` es el `<span>` sin cerrar, no el
        `<br>` — la regla (1) mirando sólo la cima ya no ve el `<p>` por debajo, y el desplazamiento
        se pierde. Sólo la pila ENTERA lo sigue viendo. Éste es el caso que de verdad separa las
        dos mitades; el de arriba no distinguía nada."""
        desplazado = _etiquetas_de_cierre_opcional_sin_cerrar(
            '<div><p class="cifra">Resumen<br><span>x<dl><dt>Altura</dt>'
            '<dd>180 cm</dd></dl></p></div>',
            cierre_opcional={"p"},
        )
        self.assertEqual(
            desplazado, ["p"],
            "un <p> desplazado por un <dl>, con un <br> y luego un <span> SIN CERRAR entre medias, "
            "no apareció como desplazado: la regla (1) ya no ve el <p> por debajo del <span> — "
            "sólo mirar la PILA ENTERA (no la cima) sigue cazando este caso",
        )

    def test_mutacion_un_hr_suelto_dentro_de_un_parrafo_lo_desplaza_pone_la_suite_roja(self):
        """H32 (revisión 15 de la 059, BLOQUEANTE) — H30 cerró el caso X, pero la propia vuelta
        que lo cerró (18ª) midió los casos L/M/O/P/S del arreglo de H27/H28 en una SONDA de usar
        y tirar (`.runtime/v18/probe-despues-del-arreglo.txt`) y no los convirtió en test: el
        enunciado exacto de H30, cometido otra vez sobre el arreglo nuevo. Medido por el revisor
        (Revisión 15, D2): revertir el ORDEN entre la higiene de la pila y la regla (1) —volver a
        hacer `return` antes de evaluar si `etiqueta` cierra un `<p>`, el defecto EXACTO de
        H28— deja las 926 en VERDE, porque nada ejercitaba ya ese orden. Éste es el caso L de la
        sonda, hecho permanente: un `<hr>` SOLO (sin otro hijo de bloque detrás) tiene que
        desplazar el `<p>` — si el `return` vuelve delante, `<hr>` nunca llega a la regla (1) y
        este test se pone rojo."""
        desplazado = _etiquetas_de_cierre_opcional_sin_cerrar(
            '<div><p class="cifra">Resumen<hr>Altura: <span>180</span> cm</p></div>',
            cierre_opcional={"p"},
        )
        self.assertEqual(
            desplazado, ["p"],
            "un <p> con un <hr> suelto dentro (sin otro hijo de bloque) no apareció como "
            "desplazado: o `_CIERRAN_UN_PARRAFO_DE_HTML` dejó de traer `hr`, o la higiene de la "
            "pila vuelve a evaluarse ANTES que la regla (1) — el defecto exacto de H28",
        )

    def test_mutacion_una_etiqueta_de_solo_cierran_un_parrafo_desplaza_aunque_no_sea_de_bloque(self):
        """H32 (revisión 15 de la 059, BLOQUEANTE) — el caso I de la sonda de la vuelta 18, hecho
        permanente: `<table>` está en `_CIERRAN_UN_PARRAFO_DE_HTML` pero NUNCA estuvo en
        `_ETIQUETAS_DE_BLOQUE` (H12 la clasifica para "qué usa el árbol", no para "qué cierra un
        `<p>`" — ninguna plantilla propia usa `<table>` hoy). Medido por el revisor: revertir la
        regla (1) de `etiqueta in _CIERRAN_UN_PARRAFO_DE_HTML` a `etiqueta in
        _ETIQUETAS_DE_BLOQUE` —el cambio ENTERO de H27/H28, el corazón de la 18ª vuelta— deja las
        926 en VERDE, porque ningún test distinguía las dos listas por el lado de lo que SÓLO
        está en la nueva. Este test sí: si la regla (1) vuelve a mirar `_ETIQUETAS_DE_BLOQUE`,
        `<table>` deja de disparar la regla y este test se pone rojo."""
        desplazado = _etiquetas_de_cierre_opcional_sin_cerrar(
            '<div><p class="cifra">Resumen<table><tr><td>180 cm</td></tr></table></p></div>',
            cierre_opcional={"p"},
        )
        self.assertEqual(
            desplazado, ["p"],
            "un <p> con un <table> dentro no apareció como desplazado: la regla (1) volvió a "
            "mirar `_ETIQUETAS_DE_BLOQUE` (que nunca trajo `table`) en vez de "
            "`_CIERRAN_UN_PARRAFO_DE_HTML`",
        )

    def test_svg_script_y_template_legitimos_dentro_de_un_parrafo_no_son_falso_rojo(self):
        """H32 (revisión 15 de la 059, BLOQUEANTE) — los casos M/O/P de la sonda de la vuelta 18,
        hechos permanentes, por el lado CONTRARIO al test de arriba: `svg`/`script`/`template`
        están en `_ETIQUETAS_DE_BLOQUE` (H14: ahí se quedan, los necesita el mecanismo de
        "pega/separa" texto) pero NO en `_CIERRAN_UN_PARRAFO_DE_HTML` — son contenido de
        frase/metadatos LEGAL dentro de un `<p>` (H27). Si la regla (1) vuelve a mirar
        `_ETIQUETAS_DE_BLOQUE`, las tres pasan a desplazar el `<p>` de golpe: un falso ROJO sobre
        marcado legítimo como el de `despensa/ver.html:27` (un icono `{% include
        "_iconos.html#…" %}` dentro de un `<p>` real)."""
        for etiqueta, contenido in (
            ("svg", '<svg viewBox="0 0 8 8"><path d="M0 0"></path></svg>'),
            ("script", '<script type="application/json">{}</script>'),
            ("template", "<template><span>x</span></template>"),
        ):
            with self.subTest(etiqueta=etiqueta):
                desplazado = _etiquetas_de_cierre_opcional_sin_cerrar(
                    f'<div><p class="cifra">Resumen{contenido}Altura: '
                    f'<span>180</span> cm</p></div>',
                    cierre_opcional={"p"},
                )
                self.assertEqual(
                    desplazado, [],
                    f"un <p> con un <{etiqueta}> LEGÍTIMO dentro apareció como desplazado: la "
                    f"regla (1) volvió a mirar `_ETIQUETAS_DE_BLOQUE` (que sí trae {etiqueta}) "
                    f"en vez de `_CIERRAN_UN_PARRAFO_DE_HTML`",
                )

    def test_un_hijo_de_bloque_legitimo_dentro_de_li_no_es_falso_rojo(self):
        """H23 — el control de que restringir la regla (1) del desplazamiento a `<p>` (ver el
        docstring de `_ContadorDeAperturasYCierres`) no abre un falso rojo sobre marcado
        LEGÍTIMO: a diferencia de `<p>`, el modelo de contenido de `<li>` SÍ admite un `<div>`
        dentro sin autocerrarse — sólo se cierra al abrirse un HERMANO `<li>` o al cerrarse su
        `<ul>`. Las dos formas se comprueban aquí."""
        con_div_dentro = _etiquetas_de_cierre_opcional_sin_cerrar(
            "<ul><li><div>contenido de sobra</div></li><li>Otro</li></ul>",
            cierre_opcional={"li"},
        )
        self.assertEqual(
            con_div_dentro, [],
            "un <div> LEGÍTIMO dentro de un <li> bien cerrado no debía marcar el <li> como "
            "desplazado — <li> sí admite hijos de bloque sin autocerrarse",
        )
        # Y el caso que SÍ tiene que seguir cazado: el hermano sin cerrar explícito, atrapado por
        # el cierre del <ul> — regla (2), no la (1) restringida a <p>.
        hermano_sin_cerrar = _etiquetas_de_cierre_opcional_sin_cerrar(
            "<ul><li>Uno<li>Dos</li></ul>", cierre_opcional={"li"},
        )
        self.assertEqual(
            hermano_sin_cerrar, ["li"],
            "un <li> sin cerrar seguido de un hermano <li> tenía que seguir cazado por la "
            "regla (2), aunque la (1) no se generalice a <li>",
        )

    def test_mutacion_un_p_ajeno_a_la_llamada_no_contamina_el_barrido_de_otra_etiqueta(self):
        """H33 (vuelta 19 de la 059, descubierto al buscar OTRO predicado revertible con la
        suite en verde — el mismo encargo de H32). `"p" in self.cierre_opcional` (ver el
        docstring de `_ContadorDeAperturasYCierres`, guarda de la regla (1)) no está para evitar
        un falso ROJO sobre `<li>`: los 203 tests del módulo siguen en verde si se quita
        (medido). Está para que la regla (1) no CONTAMINE una llamada que no pidió vigilar `<p>`
        en absoluto: sin la guarda, un `<p>` abierto y sin cerrar en el documento (algo que a
        ESTA llamada no le importa: sólo le pidieron `<li>`) dispara igual la regla (1) en cuanto
        se abre cualquier etiqueta de `_CIERRAN_UN_PARRAFO_DE_HTML` (aquí, el `<div>` LEGÍTIMO
        dentro del `<li>`, el mismo del test de arriba) y el `self.pila.pop()` final de la regla
        (1) mete `"p"` en `self.desplazadas` SIN comprobar si `"p"` está en `cierre_opcional` —
        `_etiquetas_de_cierre_opcional_sin_cerrar` no vuelve a filtrar por `cierre_opcional` al
        devolver, así que `"p"` sale en el resultado de una llamada que sólo preguntaba por
        `<li>`. Ninguna llamada real de hoy mezcla un `<p>` sin cerrar con `cierre_opcional`
        distinto de `{"p", ...}` (el único sitio que usa un subconjunto propio es el test de
        arriba, y no tiene ningún `<p>` en su HTML), así que esto no muerde en el árbol real
        todavía — pero es exactamente la misma familia de fallo que H23/H25/H30/H32: un
        predicado portante sin su rojo."""
        contaminado = _etiquetas_de_cierre_opcional_sin_cerrar(
            "<p>Resumen<li><div>contenido de sobra</div></li></p>",
            cierre_opcional={"li"},
        )
        self.assertEqual(
            contaminado, [],
            "una llamada que sólo pidió vigilar <li> devolvió <p> como desplazado: la regla (1) "
            "se disparó para una etiqueta (<p>) ajena a `cierre_opcional`, o la guarda "
            "`\"p\" in self.cierre_opcional` se ha perdido",
        )

    def test_mutacion_un_inline_ajeno_a_la_llamada_no_contamina_el_barrido_de_otra_etiqueta(self):
        """H34 (vuelta 19 de la 059, descubierto con el MISMO método que H33: revertir a mano
        cada predicado portante y mirar si las 203/204 siguen en verde). `handle_endtag` (regla
        (2)) filtra `if cima in self.cierre_opcional` antes de marcar `cima` como desplazada —
        sin ese filtro, los 204 tests del módulo siguen en verde (medido). El filtro evita que
        el cierre de un ANCESTRO arrastre a `self.desplazadas` cualquier etiqueta que quedara
        sin cerrar por debajo, aunque esa etiqueta no sea de las que `cierre_opcional` pidió
        vigilar — aquí, un `<span>` sin su `</span>`, atrapado por el `</ul>` que cierra el `<li>`
        de verdad. `_etiquetas_de_cierre_opcional_sin_cerrar` no vuelve a filtrar por
        `cierre_opcional` al devolver (mismo mecanismo que H33), así que sin el filtro un
        `<span>` sin cerrar se coló en el barrido de `<li>`. Ningún caso real de hoy deja un
        INLINE sin cerrar justo antes de que se cierre su `<ul>`/`<ol>`/`<dl>`, así que no muerde
        en el árbol todavía — misma familia que H23/H25/H30/H32/H33: un predicado portante sin
        su rojo."""
        contaminado = _etiquetas_de_cierre_opcional_sin_cerrar(
            "<ul><li>Uno<span>sin cerrar</ul>", cierre_opcional={"li"},
        )
        self.assertEqual(
            contaminado, ["li"],
            "un <span> sin cerrar, atrapado por el cierre del <ul>, apareció en el barrido de "
            "<li>: la regla (2) se disparó para una etiqueta (<span>) ajena a `cierre_opcional`, "
            "o el filtro `cima in self.cierre_opcional` de `handle_endtag` se ha perdido",
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

    def test_mutacion_una_copia_con_una_etiqueta_de_django_dentro_del_class_dispara_la_firma(self):
        """H37-K (vuelta 20 de la 059, BLOQUEANTE) — `_piezas_copiadas` normaliza `{% … %}`/
        `{# … #}` ANTES de tokenizar el `class="…"` (el mismo mecanismo que
        `kcalibra/tests_pantallas.py` endureció en su revisión 7ª/8ª vuelta, importado aquí,
        nunca copiado). Sin esa normalización, un `{% if %}…{% endif %}` DENTRO del atributo
        `class` de una copia real —lo que Django renderiza como texto plano, byte a byte
        igual— rompe uno de sus tokens fijos en fragmentos que ya no casan con la firma.
        Medido por el revisor (Revisión 16, D3): quitar la normalización previa deja los 205
        tests de `kcalibra` en verde — una copia real de `chip`, con un `{% if %}` de Django
        envolviendo dos de sus tres tokens fijos, deja de dispararse."""
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "pantalla_de_prueba_h37k.html"
            ruta.write_text(
                '{% extends "base.html" %}\n'
                '<label class="inline-flex cursor-pointer items-center gap-1.5 '
                'rounded-pastilla bg-lienzo px-4 py-2 text-[14px] font-semibold '
                "text-tinta-media transition-colors {% if tono == 'racha' %}"
                "has-[:checked]:bg-tinta has-[:checked]:text-white{% endif %}\">"
                '<input type="checkbox">comida</label>\n'
            )
            piezas = _piezas_copiadas(ruta)
        self.assertIn(
            "chip", piezas,
            "una copia real de `chip`, con un {% if %} de Django envolviendo dos de sus tres "
            'tokens fijos dentro del propio class="…", no disparó la firma: la normalización '
            "de `{% … %}`/`{# … #}` antes de tokenizar se ha perdido",
        )


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

        # H21 (revisión 11 de la 059, BLOQUEANTE) — `grasa_pct`/`cintura_cm` van CON VALOR, no
        # en blanco: `perfiles/peso.html:156-157` las pinta dentro de `{% if … != None %}`, así
        # que apuntarlas vacías dejaba esos dos `<span class="cifra">` FUERA de la población de
        # todos los barridos de este fichero. Ver el bloque de POBLACIÓN al final de este
        # `setUp` y el trinquete `test_el_barrido_renderiza_todos_los_sitios_de_cifra_del_arbol`.
        respuesta_peso = self.client.post(
            f"/perfiles/{self.alejandro.id}/peso/apuntar/",
            {"fecha": hoy, "peso_kg": "80", "grasa_pct": "18", "cintura_cm": "84"},
        )
        assert respuesta_peso.status_code == 200

        # ------------------------------------------------------------------------------------ #
        # H21 (revisión 11 de la 059, BLOQUEANTE) — LA POBLACIÓN. El barrido de `.cifra` de R5
        # vivía en `kcalibra/tests_pantallas.py`, cuya clase tiene un `setUp` que CIERRA EL DÍA
        # a propósito (su comentario lo dice: sin ningún `CierreDeDia`, `progreso/ver.html`
        # nunca llega a pintar la `<p class="cifra …">{{ cumplimiento.porcentaje }}%</p>` de la
        # l.178). Esta unidad MUDÓ el barrido aquí y la fixture nueva no cerraba ningún día: el
        # elemento se quedó fuera de la población de TODOS los barridos, y quitarle la `.cifra`
        # pasaba con las 906 en verde — una protección que `main` SÍ tenía. El inventario por
        # AST no puede ver ese hueco, porque el test mudado tiene MÁS asserts: lo que perdió no
        # son asserts, es POBLACIÓN.
        #
        # Lo de abajo NO es "los tres datos que le faltaban a esta fixture": es lo que hace
        # falta para que las 39 páginas del barrido pinten TODOS los sitios de `.cifra` que el
        # árbol declara — la lista salió de medirlo
        # (`test_el_barrido_renderiza_todos_los_sitios_de_cifra_del_arbol`, más abajo, que a
        # partir de ahora se pone ROJO si vuelve a encogerse).
        #
        # Cada POST lleva su control de ROJO MUDO (misma familia que el resto de este `setUp`):
        # si mañana algo rompe uno de estos caminos, la fixture deja de pintar su elemento y el
        # barrido encogería EN SILENCIO — que es exactamente el defecto que cierra H21.
        # ------------------------------------------------------------------------------------ #

        # (a) El día de HOY, cerrado y CON calorías: `progreso/ver.html:178` (el porcentaje de
        #     cumplimiento) y `cierres/cerrar.html:108` (`{% if cierre.calorias_comidas %}`).
        #     `status_code` NO sirve de control aquí — `cierres/views.py:cerrar` nunca redirige:
        #     con el formulario inválido vuelve a renderizar la MISMA plantilla con los errores,
        #     así que un POST roto sigue devolviendo 200 (medido en la 8ª vuelta de revisión,
        #     `kcalibra/tests_pantallas.py`). El control real es que la fila exista.
        fecha_de_hoy = timezone.localdate()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {
                "fecha": fecha_de_hoy.isoformat(),
                "respuesta": "lo_segui",
                "calorias_comidas": "1850",
                "nota": "",
            },
        )
        assert CierreDeDia.objects.filter(
            persona=self.alejandro, fecha=fecha_de_hoy, calorias_comidas=1850
        ).exists()  # control: el día se cerró de verdad, y con sus calorías

        # (b) El plan de AYER: `cierres/_pregunta_pendiente.html:36` pinta las comidas del plan
        #     del día PENDIENTE, y el pendiente es SIEMPRE ayer (`servicios/cierres.py:
        #     calcular_dia_pendiente`) — un plan de hoy no lo alcanza jamás. No hay ninguna ruta
        #     HTTP que apunte una comida a un día pasado (`planes/logica.py:apuntar_comida` usa
        #     `timezone.localdate()` a fuego), así que este es el único dato de este `setUp` que
        #     se crea por ORM, y a propósito: inventar una ruta para poder crearlo sería cambiar
        #     la aplicación para que quepa el test.
        ayer = fecha_de_hoy - timedelta(days=1)
        plan_de_ayer = PlanDeDia.objects.create(
            persona=self.alejandro, fecha=ayer, hogar=self.alejandro.hogar
        )
        plan_de_ayer.comidas.create(
            nombre="Lentejas", momento_del_dia="comida",
            calorias=600, proteina_g=30, grasa_g=10, carbos_g=80,
        )
        assert dia_pendiente_de_preguntar(self.alejandro) == ayer, (
            "control: la pregunta pendiente tiene que seguir siendo la de AYER — si dejara de "
            "serlo, `_pregunta_pendiente.html` no pintaría el plan y su `.cifra` saldría del "
            "barrido"
        )


def _visitar_pantallas_reales(cliente, nombres_de_pantallas, arranque):
    """El recorrido común (BFS con el cliente de test desde `arranque`, mismo mecanismo que
    `_recorrer_la_app` de `kcalibra.tests_nada_escondido`) que comparten
    `_paginas_de_pantallas_reales` y `_formularios_y_paginas_de_pantallas_reales`, abajo — para
    que las dos poblaciones (el HTML y los formularios del contexto) salgan de la MISMA visita, no
    de dos renderizados distintos que podrían acabar viendo pantallas distintas. Cede
    `(ruta, contenido, respuesta, coincidentes)` de cada página que renderiza alguna pantalla
    REAL; `_rutas_enlazadas`, importada de `tests_nada_escondido`, sigue cada `href`/`hx-get`, no
    una lista de rutas escrita a mano."""
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
            yield ruta, contenido, respuesta, coincidentes
        for destino in _rutas_enlazadas(contenido):
            if destino not in visitadas:
                por_visitar.append(destino)


def _paginas_de_pantallas_reales(cliente, nombres_de_pantallas, arranque):
    """Devuelve `(encontradas, alcanzadas)`: la lista de `(ruta, contenido)` de siempre, MÁS el
    conjunto de nombres de pantalla que de verdad se vieron — O3 de la revisión: la guarda de rojo
    mudo de R5/R6 sólo contaba RUTAS, así que una pantalla que el recorrido dejara de alcanzar (un
    estado que la fixture no crea) se quedaba sin ninguna de las dos redes y nadie avisaba;
    comparar `alcanzadas` contra `_nombres_de_pantallas_reales_hoy()` cierra esa familia sin
    nombrar ni una pantalla."""
    encontradas = []
    alcanzadas = set()
    for ruta, contenido, _respuesta, coincidentes in _visitar_pantallas_reales(
        cliente, nombres_de_pantallas, arranque
    ):
        encontradas.append((ruta, contenido))
        alcanzadas |= coincidentes
    return encontradas, alcanzadas


def _formularios_y_paginas_de_pantallas_reales(cliente, nombres_de_pantallas, arranque):
    """H19 (revisión 11 de la 059, MEDIO) — la MISMA visita que `_paginas_de_pantallas_reales`,
    pero conservando también los formularios del CONTEXTO de cada respuesta (`_campos_con_help_
    text_del_contexto`, junto a R6 abajo): la población que H19 necesita —qué campos declaran
    `help_text`— sale de la estructura que la vista monta, no de los atributos que la cura de R6
    escribe en el HTML, así que `(ruta, contenido)` no basta. Devuelve `(encontradas, alcanzadas)`
    con `encontradas = [(ruta, contenido, campos), ...]`."""
    encontradas = []
    alcanzadas = set()
    for ruta, contenido, respuesta, coincidentes in _visitar_pantallas_reales(
        cliente, nombres_de_pantallas, arranque
    ):
        campos = _campos_con_help_text_del_contexto(respuesta)
        encontradas.append((ruta, contenido, campos))
        alcanzadas |= coincidentes
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
# H9 (revisión 4 de la 059): frontera IZQUIERDA — ver el comentario gemelo en
# `kcalibra/tests_pantallas.py`, junto a `_NUMERO_CON_UNIDAD_RE`.
_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE = re.compile(
    r"(?<!\w)\d[\d.,]*\s*(?:" + "|".join(_VOCABULARIO) + r")(?!\w)", re.I
)


# ------------------------------------------------------------------------------------------ #
# H21 (revisión 11 de la 059, BLOQUEANTE) — EL CONTROL DE POBLACIÓN del barrido de R5.
#
# Los once huecos de esta unidad son el mismo defecto mudándose de piso: la detección cuelga de
# algo ACCIDENTAL en vez de de lo que hace que la cosa sea esa cosa (H12 etiquetas → H13 ficheros
# → H16 eventos → H18 listas → H21 LA POBLACIÓN). Aquí el accidente era: *qué hace renderizar
# ESTA fixture*. `progreso/ver.html:178` pinta el porcentaje de cumplimiento sólo si hay algún
# día cerrado; la fixture no cerraba ninguno, así que ese `<p class="cifra">` no estaba en la
# población de NINGÚN barrido y quitarle la `.cifra` pasaba en verde — con `main` en rojo.
#
# La cura no es "cerrar un día" (eso es tapar el caso), es **hacer que el barrido sepa cuál es su
# población y diga en ROJO cuando encoge**. La población DECLARADA sale de la esencia —lo que las
# plantillas PUEDEN pintar—: cada sitio del árbol propio donde se escribe un `class="… cifra …"`,
# recorriendo el `nodelist` COMPILADO de cada plantilla (los `TextNode` de Django), con la clave
# `(origin.template_name, token.lineno)` que el propio `Parser.extend_nodelist` de Django ya pone
# en cada nodo. La población RENDERIZADA sale de registrar ESOS MISMOS nodos mientras el barrido
# de R5 renderiza sus páginas (parcheando `TextNode.render_annotated`, el mismo mecanismo que ya
# usa `_con_procedencia_marcada`). Las dos derivaciones salen de la MISMA estructura, así que
# compararlas no puede desajustarse por la forma de la clave (medido: `vistos − declarados` es
# vacío, `.runtime/v12/poblacion-cifra.json`).
#
# Medido con esto el día que se escribió: 31 sitios declarados, 25 renderizados — H21 no estaba
# solo, eran SEIS. Cinco se han metido en la población arreglando la fixture (ver `setUp`); el
# sexto es inalcanzable de verdad y se declara abajo, con su trinquete.
# ------------------------------------------------------------------------------------------ #

_CLASE_CON_CIFRA_RE = re.compile(r"""class\s*=\s*["'][^"']*(?<![\w-])cifra(?![\w-])""")


def _desplazamientos_de_cifra(texto):
    return [c.start() for c in _CLASE_CON_CIFRA_RE.finditer(texto)]


def _sitio_del_nodo(nodo, desplazamiento):
    """La clave de un sitio de `.cifra`: plantilla y línea, LEÍDAS DE LO QUE DJANGO YA ESCRIBIÓ
    en el nodo al compilarlo (`node.origin`/`node.token`, que pone `Parser.extend_nodelist`) — no
    de un `grep` sobre el fichero ni de una lista. Un `TextNode` puede abarcar varias líneas, así
    que a la línea del token se le suman los saltos que haya ANTES del `class="…cifra…"`."""
    origen = getattr(nodo, "origin", None)
    token = getattr(nodo, "token", None)
    linea = getattr(token, "lineno", None)
    if linea is not None:
        linea += nodo.s[:desplazamiento].count("\n")
    return f"{getattr(origen, 'template_name', None)}:{linea}"


def _sitios_de_cifra_de_una_plantilla(plantilla):
    """Los sitios de `.cifra` de UNA plantilla ya compilada. `get_nodes_by_type` recorre también
    los `nodelist` de las ramas (`{% if %}`/`{% else %}`, `{% for %}`), que es justo lo que hace
    falta: el sitio de H21 vive dentro de un `{% if cumplimiento.cerrados %}`."""
    sitios = set()
    for nodo in plantilla.nodelist.get_nodes_by_type(TextNode):
        for desplazamiento in _desplazamientos_de_cifra(nodo.s):
            sitios.add(_sitio_del_nodo(nodo, desplazamiento))
    return sitios


def _sitios_de_cifra_declarados(directorios=None):
    """Toda la población: los sitios de `.cifra` de las plantillas PROPIAS del árbol, menos las
    diez `EXCEPCIONES` (que R8 vigila al revés y el barrido de R5 no recorre). Se compila cada
    plantilla por su nombre de Django, así que lo que se mide es lo que Django ve — la misma
    definición de caso que R1, no un `os.walk` con una regla aparte."""
    excepciones_absolutas = {(BASE_DIR / e).resolve() for e in EXCEPCIONES}
    sitios = set()
    for ruta in _plantillas_del_arbol_propio(directorios):
        if Path(ruta).resolve() in excepciones_absolutas:
            continue
        nombre = _nombre_de_plantilla(Path(ruta))
        if nombre is None:
            continue
        sitios |= _sitios_de_cifra_de_una_plantilla(get_template(nombre).template)
    return sitios


@contextmanager
def _registrando_los_sitios_de_cifra_que_se_pintan(vistos):
    """Anota en `vistos` cada sitio de `.cifra` que se RENDERIZA de verdad mientras dura el
    `with`. Mismo mecanismo (y mismas precauciones) que `_con_procedencia_marcada`, con el que se
    anida sin estorbarse: éste no cambia lo que devuelve el nodo, sólo lo apunta."""
    original = TextNode.render_annotated

    def envuelto(self, context):
        for desplazamiento in _desplazamientos_de_cifra(self.s):
            vistos.add(_sitio_del_nodo(self, desplazamiento))
        return original(self, context)

    with mock.patch.object(TextNode, "render_annotated", envuelto):
        yield


# La única pieza de `_ui.html` cuyo `.cifra` no puede pintar NINGUNA página: `barra_macro` no la
# incluye ninguna plantilla del árbol (medido), y `_barra_macro_interna` —donde vive el
# `<span class="cifra">`— sólo la incluye `barra_macro`. Se declara como las `EXCEPCIONES` de R8
# —por NOMBRE de pieza, no por número de línea, para que mover el fichero no la rompa— y con su
# TRINQUETE: lo que se comprueba en cada corrida no es "este sitio sigue sin pintarse" (eso sería
# generoso: valdría también si la pieza se empezara a usar y el barrido no la alcanzara), sino
# que **la pieza sigue sin usarla nadie**. El día que una plantilla la incluya, esto se pone ROJO
# pidiendo borrar la excepción, y el sitio entra en la población como los otros treinta.
_LA_PIEZA_DE_UI_QUE_NO_INCLUYE_NADIE = "barra_macro"
_LA_PIEZA_INTERNA_QUE_SOLO_ESA_USA = "_barra_macro_interna"


def _algun_modulo_python_propio_nombra_la_pieza_de_ui(pieza, base_dir=None):
    """H24 (revisión 12) — la SEGUNDA vía, ciega para `_alguna_plantilla_incluye_la_pieza_de_ui`:
    una VISTA puede pedir `"_ui.html#pieza"` como plantilla propia POR NOMBRE
    (`render(request, "_ui.html#pieza", contexto)` — `django-template-partials` lo permite, y
    este mismo repositorio ya usa el patrón: `cierres/views.py:68,82` renderiza
    `_pregunta_pendiente.html#pregunta_pendiente` así, sin que exista NUNCA ningún
    `{% include %}` en ninguna plantilla). Se busca la cadena LITERAL `"_ui.html#pieza"` en
    cualquier `.py` propio del repositorio — fuera `.venv`/`site-packages`, el mismo filtro que
    `_plantillas_del_arbol_propio` — sin exigir que sea un argumento de `render` concreto:
    cualquier constante o llamada que la nombre por su cadena entra sola, igual que
    `NOMBRE_DEL_PARTIAL_PREGUNTA` entraría si nombrara `barra_macro`.

    Salvo ESTE MISMO fichero (`__file__`), cuando `base_dir` es el real: sus propias mutaciones
    EN CÓDIGO (más abajo) escriben la cadena `"_ui.html#barra_macro"` dentro de un `.py` de
    USAR Y TIRAR — pero el DOCSTRING/fuente de esa mutación, al vivir en este mismo módulo, es
    también un `.py` bajo `BASE_DIR`. Mismo motivo por el que
    `_ficheros_de_test_que_redefinen_piezas` excluye su propio `modulo_compartido`: el fichero
    que hace la pregunta no puede contar su propia documentación como si fuera alguien
    respondiendo que sí."""
    base_dir = BASE_DIR if base_dir is None else Path(base_dir)
    propio = Path(__file__).resolve()
    patron = re.compile(r"""["']_ui\.html#""" + re.escape(pieza) + r"""(?![\w-])""")
    for ruta in base_dir.rglob("*.py"):
        resuelta = ruta.resolve()
        if resuelta == propio:
            continue
        partes = resuelta.parts
        if ".venv" in partes or "site-packages" in partes:
            continue
        if patron.search(_texto(ruta)):
            return True
    return False


def _alguna_plantilla_incluye_la_pieza_de_ui(pieza, directorios=None, base_dir=None):
    """¿Sigue siendo INALCANZABLE `_ui.html#pieza`? H24 (revisión 12) — la pregunta original
    ("¿la incluye alguna plantilla, salvo la propia `_ui.html`?") era ciega por DOS vías medidas:
    (a) una pieza de `_ui.html` que incluye a `pieza` DESDE DENTRO de `_ui.html` —si esa pieza
    contenedora SÍ la usa alguna página, `pieza` es alcanzable igual, y excluir `_ui.html` entero
    de la búsqueda lo escondía— y (b) una VISTA que la renderiza por NOMBRE
    (`_algun_modulo_python_propio_nombra_la_pieza_de_ui`, arriba), sin ningún `{% include %}` en
    ninguna plantilla. Se busca ahora en TODAS las plantillas propias, `_ui.html` incluida
    (`barra_macro` no se autoincluye bajo su propio nombre — sólo incluye a
    `_barra_macro_interna`, un nombre distinto — así que esto no crea un falso positivo con la
    propia pieza), y también en los `.py` propios."""
    patron = re.compile(r"""\{%\s*include\s+["']_ui\.html#""" + re.escape(pieza) + r"""(?![\w-])""")
    for ruta in _plantillas_del_arbol_propio(directorios):
        if patron.search(_texto(Path(ruta))):
            return True
    return _algun_modulo_python_propio_nombra_la_pieza_de_ui(pieza, base_dir)


def _sitios_de_cifra_de_la_pieza_de_ui_sin_usar():
    """Los sitios de la pieza inalcanzable, sacados de COMPILARLA (django-template-partials deja
    pedir `"_ui.html#pieza"` como plantilla propia, igual que hace `cierres/views.py`) — así la
    excepción no nombra ninguna línea y sigue valiendo si el fichero se reordena."""
    return _sitios_de_cifra_de_una_plantilla(
        get_template(f"_ui.html#{_LA_PIEZA_INTERNA_QUE_SOLO_ESA_USA}").template
    )


def _poblacion_de_cifra_que_el_barrido_no_pinto(vistos, directorios=None):
    """El corazón de H21: qué sitios de `.cifra` DECLARA el árbol que el barrido NO renderizó.
    Devuelve `(sitios_perdidos, problemas_del_trinquete)`."""
    perdidos = sorted(_sitios_de_cifra_declarados(directorios) - set(vistos))
    exentos = _sitios_de_cifra_de_la_pieza_de_ui_sin_usar()
    problemas = []
    if _alguna_plantilla_incluye_la_pieza_de_ui(_LA_PIEZA_DE_UI_QUE_NO_INCLUYE_NADIE, directorios):
        problemas.append(
            f"alguna plantilla ya incluye `_ui.html#{_LA_PIEZA_DE_UI_QUE_NO_INCLUYE_NADIE}`: la "
            f"excepción de `_sitios_de_cifra_de_la_pieza_de_ui_sin_usar` ya no vale — bórrala, y "
            f"haz que el barrido pinte también sus sitios de `.cifra`"
        )
    else:
        perdidos = [s for s in perdidos if s not in exentos]
    return perdidos, problemas


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
        # H13 (revisión 8 de la 059, BLOQUEANTE) — el trinquete de etiquetas
        # (`TodaEtiquetaUsadaEnElArbolEstaClasificadaTests`, arriba) sólo mira los `.html` del
        # repositorio; `_NumerosDeDatoEnElTexto`, más abajo, actúa sobre ESTE HTML — ya
        # renderizado, con las 39 rutas de las dos sesiones — que es una población distinta
        # (un widget de Django, `mark_safe`, `|safe`… puede poner una etiqueta aquí sin que
        # exista en ningún `.html` propio; medido: `<textarea>` en nueve páginas reales, en
        # ningún `.html`, sin clasificar). Se recolecta sobre el HTML que este mismo barrido ya
        # tiene en la mano (`paginas_alejandro`/`paginas_carlos`, antes de re-renderizar bajo
        # `_con_procedencia_marcada` para la comprobación de `.cifra`) — cero renderizados
        # extra — y se exige que toda etiqueta vista esté clasificada. Lo que esto garantiza: la
        # misma LISTA DE RUTAS que recorre la red. Los EVENTOS de parseo (`handle_starttag`/
        # `handle_endtag`, `_RecolectorDeEtiquetas`) los comparten por COPIA A MANO, no por
        # construcción, y `_NumerosDeDatoEnElTexto` consulta además una TERCERA estructura,
        # `SIN_CIERRE`, que hasta H18 (revisión 10) ningún trinquete vigilaba — ver el comentario
        # completo junto a `_etiquetas_sin_clasificar_en_paginas`, arriba. Tampoco garantiza el
        # mismo HTML byte a byte: éste es el render de `paginas_alejandro`/`paginas_carlos`; la
        # red, más abajo, recorre un SEGUNDO render de las mismas rutas, bajo
        # `_con_procedencia_marcada`.
        #
        # O26 (revisión 9): este `assertEqual` va ANTES de las dos guardas de abajo —no después,
        # como hasta esta vuelta— para que diagnostique siempre: si fuera el TERCERO, una guarda
        # anterior que cayera en rojo le impedía correr, y el hueco que H13/H16 vigilan se
        # quedaba sin decir nada.
        sin_clasificar_en_render = _etiquetas_sin_clasificar_en_paginas(
            paginas_alejandro + paginas_carlos
        )
        self.assertEqual(
            sin_clasificar_en_render, [],
            f"H13: etiquetas en HTML renderizado (no necesariamente en ningún .html del "
            f"repo) que `_ETIQUETAS_INLINE`/`_ETIQUETAS_DE_BLOQUE` todavía no clasifican: "
            f"{sin_clasificar_en_render}",
        )
        # H20 (revisión 11 de la 059, MEDIO) — el gemelo de H13, sobre la MISMA población
        # (`_etiquetas_de_cierre_opcional_sin_cerrar`, junto a H18 arriba): el trinquete del árbol
        # de `TodaEtiquetaUsadaEnElArbolEstaClasificadaTests` sólo mira los `.html` propios; un
        # widget de Django, `mark_safe` o `|safe` podrían dejar una etiqueta de cierre opcional
        # sin cerrar en el HTML SERVIDO sin que ningún `.html` del repo lo muestre nunca. Cero
        # renderizados extra: el mismo HTML que ya tiene en la mano el barrido de arriba.
        sin_cerrar_en_render = [
            f"{ruta}: <{etiqueta}> sin cierre explícito que cuadre"
            for ruta, contenido in paginas_alejandro + paginas_carlos
            for etiqueta in _etiquetas_de_cierre_opcional_sin_cerrar(contenido)
        ]
        self.assertEqual(
            sin_cerrar_en_render, [],
            f"H20: etiquetas de cierre opcional clasificadas, en HTML renderizado, que se "
            f"quedan sin cerrar explícitamente: {sin_cerrar_en_render}",
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
        # H21 (revisión 11, BLOQUEANTE) — el control de POBLACIÓN se registra DENTRO de este
        # mismo `with` y sobre estas mismas páginas, no en un test aparte: un test aparte
        # volvería a recorrer la app y podría acabar mirando una población distinta de la que
        # este barrido examina, que es justo el error que H21 castiga.
        sitios_de_cifra_pintados = set()
        with _con_procedencia_marcada(), self._vocabulario_ancho(), \
                _registrando_los_sitios_de_cifra_que_se_pintan(sitios_de_cifra_pintados):
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
        # H21 — la POBLACIÓN, ANTES que el resultado del barrido y por el mismo motivo que O26
        # pone el trinquete de H13 el primero: un `sin_cifra` VACÍO sobre una población que ha
        # encogido no dice nada (es literalmente lo que pasó con `progreso/ver.html:178`, verde
        # con las 906 mientras `main` lo cazaba). Si esto cae, el resultado de abajo no vale y
        # hay que arreglar la fixture antes de mirarlo.
        perdidos, trinquete = _poblacion_de_cifra_que_el_barrido_no_pinto(sitios_de_cifra_pintados)
        self.assertEqual(
            perdidos + trinquete, [],
            f"H21: el árbol declara sitios de `class=\"cifra\"` que este barrido NO llegó a "
            f"pintar — su población ha encogido y ahí ya no vigila nadie (arregla la fixture "
            f"para que la página los pinte, no el barrido para que no los mire): "
            f"{perdidos + trinquete}",
        )
        self.assertEqual(
            sin_cifra, [], f"números de dato sin `.cifra`, ni propio ni heredado: {sin_cifra}"
        )

    def test_mutacion_un_sitio_de_cifra_que_no_se_renderiza_pone_la_suite_roja(self):
        """H21 — el control de población demostrado EN CÓDIGO, sobre una plantilla SINTÉTICA
        (nunca sobre el árbol real): un `class="cifra"` dentro de una rama que no se toma queda
        DECLARADO y no VISTO; con la rama tomada, desaparece de la diferencia. Es exactamente lo
        que le pasaba a `progreso/ver.html:178` con una fixture que no cerraba ningún día."""
        motor = engines["django"].engine
        fuente = (
            "{% if hay_datos %}<p class=\"cifra\">{{ n }} kcal</p>"
            "{% else %}<p>Todavía nada</p>{% endif %}"
        )
        plantilla = PlantillaDeDjango(
            fuente, origin=OrigenDeDjango("sintética", template_name="sintetica.html"), engine=motor
        )
        declarados = _sitios_de_cifra_de_una_plantilla(plantilla)
        self.assertEqual(
            sorted(declarados), ["sintetica.html:1"],
            "la población DECLARADA no salió del nodelist compilado: el control no mide nada",
        )

        vistos_sin_datos = set()
        with _registrando_los_sitios_de_cifra_que_se_pintan(vistos_sin_datos):
            plantilla.render(ContextoDeDjango({"hay_datos": False, "n": 0}))
        self.assertEqual(
            sorted(declarados - vistos_sin_datos), ["sintetica.html:1"],
            "un `class=\"cifra\"` cuya rama no se renderiza tenía que aparecer como población "
            "PERDIDA: el control no está vigilando de verdad",
        )

        vistos_con_datos = set()
        with _registrando_los_sitios_de_cifra_que_se_pintan(vistos_con_datos):
            plantilla.render(ContextoDeDjango({"hay_datos": True, "n": 500}))
        self.assertEqual(
            sorted(declarados - vistos_con_datos), [],
            "con la rama tomada, el sitio ya se pinta y no debía quedar población perdida",
        )

    def test_mutacion_un_sitio_de_cifra_en_la_segunda_linea_de_un_nodo_multilinea_se_localiza_bien(self):
        """H37-R (vuelta 20 de la 059, MEDIO, encontrado en la 4ª ronda de barrido) —
        `_sitio_del_nodo` suma los saltos de línea internos del propio `TextNode` (`nodo.s[
        :desplazamiento].count("\\n")`) a la línea de apertura que Django ya escribió, porque
        un `TextNode` puede abarcar varias líneas de la plantilla. Medido por mí, mismo método
        del revisor: quitar esa suma deja los 205 tests de `kcalibra` en verde — la clave sigue
        coincidiendo consigo misma en los dos lados de la comparación (declarado y renderizado
        se calculan con la MISMA fórmula, acertada o no), así que ningún assert de POBLACIÓN lo
        distingue. No es un falso VERDE sobre R5 (H21 sigue cazando el sitio perdido, esté bien
        o mal numerada su línea), pero SÍ es la línea de diagnóstico que alguien va a leer para
        arreglar un sitio perdido de verdad — y estaría mintiendo."""
        motor = engines["django"].engine
        fuente = 'línea 1 de texto\nlínea 2 con <p class="cifra">{{ n }}</p>'
        plantilla = PlantillaDeDjango(
            fuente,
            origin=OrigenDeDjango("sintética_r", template_name="sintetica_r.html"),
            engine=motor,
        )
        declarados = _sitios_de_cifra_de_una_plantilla(plantilla)
        self.assertEqual(
            sorted(declarados), ["sintetica_r.html:2"],
            'un `class="cifra"` en la SEGUNDA línea de un `TextNode` que empieza en la '
            "primera no se localizó en la línea 2: `_sitio_del_nodo` dejó de sumar los saltos "
            "de línea internos del propio nodo",
        )

    def test_la_excepcion_de_la_pieza_de_ui_sin_usar_sigue_siendo_exacta(self):
        """El trinquete de la única excepción del control de población (misma forma que R8 y que
        `_es_el_hueco_h18_fuera_de_ficheros`): lo que se comprueba NO es "ese sitio sigue sin
        pintarse" —eso sería generoso— sino que **la pieza sigue sin usarla nadie**, y que la
        excepción sigue cubriendo un sitio de `.cifra` de verdad (si `_ui.html` dejara de tener
        ninguno ahí, la excepción sobraría y hay que borrarla)."""
        self.assertFalse(
            _alguna_plantilla_incluye_la_pieza_de_ui(_LA_PIEZA_DE_UI_QUE_NO_INCLUYE_NADIE),
            f"alguna plantilla ya incluye `_ui.html#{_LA_PIEZA_DE_UI_QUE_NO_INCLUYE_NADIE}`: "
            f"borra la excepción del control de población, su sitio de `.cifra` ya es alcanzable",
        )
        self.assertTrue(
            _sitios_de_cifra_de_la_pieza_de_ui_sin_usar(),
            f"la pieza `_ui.html#{_LA_PIEZA_INTERNA_QUE_SOLO_ESA_USA}` ya no tiene ningún "
            f"`class=\"cifra\"`: la excepción del control de población no exime nada — bórrala",
        )
        # Y el control de que la excepción no se ha ensanchado: exime UN sitio, no una plantilla
        # entera ni un fichero.
        self.assertEqual(
            len(_sitios_de_cifra_de_la_pieza_de_ui_sin_usar()), 1,
            "la excepción del control de población ha crecido: solo puede encoger",
        )

    def test_mutacion_una_pieza_de_ui_que_incluye_a_otra_dentro_de_ui_se_pone_rojo(self):
        """H24 (revisión 12 de la 059, MENOR) — la primera vía ciega: una pieza de `_ui.html` que
        SÍ usa alguna página puede incluir a `barra_macro` DESDE DENTRO de `_ui.html`, y la
        búsqueda de antes de esta vuelta excluía el fichero entero — no lo veía. Con un `_ui.html`
        de usar y tirar (nunca el real), un `{% include "_ui.html#barra_macro" %}` dentro de OTRA
        pieza tiene que aparecer como alcanzable; sin él, vuelve a ser inalcanzable — el mismo
        patrón de mutación que el resto de este fichero. `base_dir` apunta al mismo directorio de
        usar y tirar (sin ningún `.py`), para aislar esta mutación de la vía (b) —si no, la
        segunda mitad de `_alguna_plantilla_incluye_la_pieza_de_ui` recorrería el `BASE_DIR` real
        del proyecto entero, que es una cuestión aparte, ya cubierta por el test de abajo."""
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp) / "templates"
            directorio.mkdir(parents=True)
            (directorio / "_ui.html").write_text(
                '{% load partials %}\n'
                '{% partialdef pildora_macro_interna %}\n'
                '{% include "_ui.html#barra_macro" with tipo="ninguno" %}\n'
                '{% endpartialdef %}\n'
            )
            self.assertTrue(
                _alguna_plantilla_incluye_la_pieza_de_ui("barra_macro", [Path(tmp)], Path(tmp)),
                "un {% include %} de barra_macro DENTRO de _ui.html (en otra pieza) no apareció "
                "como alcanzable: la búsqueda sigue sin mirar dentro de _ui.html",
            )
            (directorio / "_ui.html").write_text(
                '{% load partials %}\n'
                '{% partialdef pildora_macro_interna %}sin incluir nada{% endpartialdef %}\n'
            )
            self.assertFalse(
                _alguna_plantilla_incluye_la_pieza_de_ui("barra_macro", [Path(tmp)], Path(tmp)),
                "quitar el único include debía volver a dejar la pieza inalcanzable",
            )

    def test_mutacion_una_pieza_con_nombre_prefijo_de_otra_no_la_confunde_por_modulo_python(self):
        """H37-N (vuelta 20 de la 059, BLOQUEANTE, encontrado en la 2ª ronda de barrido) —
        `_algun_modulo_python_propio_nombra_la_pieza_de_ui` ancla el nombre de la pieza con
        `(?![\\w-])` para que buscar «barra_macro» no case DENTRO de una referencia a OTRA
        pieza cuyo nombre lo tiene como prefijo (`barra_macro_2`, un nombre perfectamente
        legítimo que una unidad futura podría añadir a `_ui.html`). Medido por mí, mismo
        método del revisor: quitar esa frontera deja los 205 tests de `kcalibra` en verde —
        nada del árbol de hoy tiene una pieza con ese prefijo, así que el hueco no muerde
        todavía, pero sí en cuanto exista una."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "vista_de_prueba_h37n.py").write_text(
                'from django.shortcuts import render\n\n'
                'def una_vista(request):\n'
                '    return render(request, "_ui.html#barra_macro_2", {})\n'
            )
            self.assertFalse(
                _algun_modulo_python_propio_nombra_la_pieza_de_ui("barra_macro", base),
                'una vista que sólo nombra "_ui.html#barra_macro_2" (OTRA pieza, con '
                '"barra_macro" como prefijo de su nombre) hizo aparecer "barra_macro" como '
                'alcanzable: la frontera `(?![\\w-])` se ha perdido',
            )

    def test_mutacion_una_pieza_con_nombre_prefijo_de_otra_no_la_confunde_en_plantillas(self):
        """H37-O (vuelta 20 de la 059, BLOQUEANTE, encontrado en la 2ª ronda de barrido) — el
        gemelo de H37-N un piso más arriba: `_alguna_plantilla_incluye_la_pieza_de_ui` también
        ancla el nombre con `(?![\\w-])`, para que un `{% include "_ui.html#barra_macro_2" %}`
        (OTRA pieza, con «barra_macro» como prefijo de su nombre) no haga aparecer
        «barra_macro» como alcanzable. Medido por mí, mismo método del revisor: quitar esa
        frontera deja los 205 tests de `kcalibra` en verde."""
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp) / "templates"
            directorio.mkdir(parents=True)
            (directorio / "otra_pantalla.html").write_text(
                '{% extends "base.html" %}\n'
                '{% include "_ui.html#barra_macro_2" %}\n'
            )
            self.assertFalse(
                _alguna_plantilla_incluye_la_pieza_de_ui("barra_macro", [Path(tmp)], Path(tmp)),
                'un {% include "_ui.html#barra_macro_2" %} (OTRA pieza, con "barra_macro" como '
                'prefijo de su nombre) hizo aparecer "barra_macro" como alcanzable: la '
                'frontera `(?![\\w-])` se ha perdido',
            )

    def test_mutacion_una_vista_que_renderiza_la_pieza_por_nombre_se_pone_rojo(self):
        """H24 — la segunda vía ciega: una VISTA puede pedir `_ui.html#barra_macro` por NOMBRE
        (el mismo patrón que `cierres/views.py` ya usa con otra pieza), sin que exista ningún
        `{% include %}` en ninguna plantilla — invisible para la búsqueda sobre plantillas.
        Con un `.py` de usar y tirar (nunca uno real del repositorio), la cadena literal
        `"_ui.html#barra_macro"` tiene que hacer que la pieza aparezca como alcanzable."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "vista_de_prueba_h24.py").write_text(
                'from django.shortcuts import render\n\n'
                'def una_vista(request):\n'
                '    return render(request, "_ui.html#barra_macro", {"tipo": "ninguno"})\n'
            )
            self.assertTrue(
                _algun_modulo_python_propio_nombra_la_pieza_de_ui("barra_macro", base),
                "una vista que renderiza _ui.html#barra_macro por nombre, sin ningún "
                "{% include %}, no apareció como alcanzable",
            )
            (base / "vista_de_prueba_h24.py").write_text(
                'def una_vista(request):\n    return None\n'
            )
            self.assertFalse(
                _algun_modulo_python_propio_nombra_la_pieza_de_ui("barra_macro", base),
                "quitar la única referencia debía volver a dejar la pieza inalcanzable",
            )

    def test_la_poblacion_declarada_no_sale_de_un_grep_sino_del_arbol_compilado(self):
        """Guarda de rojo mudo del propio control: si `_sitios_de_cifra_declarados` dejara de
        encontrar nada (un cambio en los cargadores, un filtro de más), la comparación de arriba
        compararía el vacío contra el vacío y colaría en verde para siempre — exactamente la
        familia de fallo que H21 es. Se exige que la población declarada traiga sitios de VARIAS
        plantillas distintas, sin nombrar ninguna."""
        declarados = _sitios_de_cifra_declarados()
        self.assertGreater(
            len(declarados), 20,
            f"la población declarada de `.cifra` se ha quedado en {len(declarados)} sitios: el "
            f"control de H21 estaría comparando casi nada contra casi nada",
        )
        plantillas = {sitio.rsplit(":", 1)[0] for sitio in declarados}
        self.assertGreater(
            len(plantillas), 5,
            f"la población declarada solo cubre {sorted(plantillas)}: no está saliendo del árbol",
        )

    def test_mutacion_la_clase_cifra_exige_frontera_de_token(self):
        """H37-A (vuelta 20 de la 059, BLOQUEANTE, generalización de H30/H32/H33/H34) — es la
        cura LITERAL de H9 (revisión 4 de esta unidad, hallazgos.md: un código de hogar al azar
        como `…KMN3G` casaba como «3 gramos»), mudada de piso: aquí es `_CLASE_CON_CIFRA_RE`
        —quien decide qué sitios de `class="…"` CUENTAN como `.cifra` para el control de
        población de H21— la que lleva las mismas fronteras `(?<![\\w-])`/`(?![\\w-])`. Medido
        por el revisor (Revisión 16, D3): quitar CUALQUIERA de las dos fronteras deja los 205
        tests de `kcalibra` en verde — quince vueltas después, la cura se puede quitar sin que
        nada chille. Sin frontera, cualquier clase que sólo CONTENGA «cifra» como subcadena
        (`descifrado`, `cifra-vieja`) contaría como sitio de `.cifra`."""
        self.assertTrue(
            bool(_CLASE_CON_CIFRA_RE.search('<p class="cifra">')),
            "la clase EXACTA `cifra` tenía que seguir detectándose",
        )
        self.assertTrue(
            bool(_CLASE_CON_CIFRA_RE.search('<p class="numero cifra grande">')),
            "`cifra` como un token más, entre otros, tenía que seguir detectándose",
        )
        for clase_ajena in ("descifrado", "cifra-vieja", "unacifraespecial", "cifrado"):
            with self.subTest(clase=clase_ajena):
                self.assertFalse(
                    bool(_CLASE_CON_CIFRA_RE.search(f'<p class="{clase_ajena}">')),
                    f"«{clase_ajena}» contiene «cifra» como subcadena pero NO es la clase "
                    f"`cifra`: no debía detectarse sin frontera de token — la cura de H9, "
                    f"mudada aquí, se ha perdido",
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

    def test_mutacion_un_digito_pegado_a_una_letra_por_la_izquierda_no_es_un_numero_de_dato(self):
        """H37-C (vuelta 20 de la 059, BLOQUEANTE) — la cura LITERAL de H9 (revisión 4 de esta
        misma unidad, hallazgos.md): un código de hogar al azar como `…KMN3G` casaba como
        «3 gramos» y abría un falso rojo. `_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE` (el vocabulario
        ANCHO de este fichero) lleva la misma frontera izquierda `(?<!\\w)` que
        `_NUMERO_CON_UNIDAD_RE` en `kcalibra/tests_pantallas.py` — pero es una constante
        DISTINTA, con su propio regex compilado, y nada la ejercitaba por este lado. Medido
        por el revisor (Revisión 16, D3): quitar `(?<!\\w)` de aquí deja los 205 tests de
        `kcalibra` en verde — quince vueltas después, la cura se puede quitar sin que nada
        chille."""
        for texto in ("ABCKMN3G", "XYZ9kg", "HOGAR42kcal", "COD7Litros"):
            with self.subTest(texto=texto):
                self.assertFalse(
                    bool(_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE.search(texto)),
                    f"«{texto}» (un dígito pegado a una letra por la IZQUIERDA, la forma de un "
                    f"código de hogar al azar) casó como número de dato: la frontera izquierda "
                    f"`(?<!\\w)` de H9 se ha perdido en el vocabulario ancho",
                )
        # Y el control: el mismo número, con espacio de verdad delante (no pegado), sigue
        # detectándose igual — la frontera no rompe ningún número de dato real.
        self.assertTrue(bool(_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE.search("KMN 3G")))
        self.assertTrue(bool(_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE.search("42 kg")))

    def test_mutacion_vocabulario_reconoce_gramos_mililitros_y_raciones(self):
        """R9 en código: el vocabulario ancho tiene que casar justo las palabras que el
        vocabulario ESTRECHO de la 053 (`kcal|kg|g|min|%`) dejaba escapar — medido en vivo por
        la revisión de la 054 (hueco H2): "raciones", "cm", "Gramos", "Mililitros", "2 latas".

        H10 (revisión 5 de la 059, BLOQUEANTE) — las diez cadenas de abajo empiezan TODAS por
        el dígito, que es justo el único caso que una frontera izquierda (`(?<!\\w)`, H9) no
        puede romper: por eso este test, con `regex.search()` sobre cadenas sueltas, no cazó
        que el arreglo de H9 mataba también dos números de dato reales cuando quedaban pegados
        al texto del elemento ANTERIOR (`Altura167 cm`). Ese caso lo prueba
        `test_mutacion_un_numero_pegado_a_la_etiqueta_anterior_se_detecta_sobre_el_texto_que_construye_el_barrido`,
        abajo, sobre el texto que el barrido CONSTRUYE de verdad, no sobre un `regex.search`
        aislado."""
        for texto, debe_casar in [
            ("4 raciones", True), ("1 ración", True), ("167 cm", True),
            ("300,00 Gramos", True), ("100,00 Mililitros", True), ("2 latas", True),
            ("3 Kilos", True), ("6 Litros", True), ("1 Unidades", True),
            ("hola mundo", False),
        ]:
            with self.subTest(texto=texto):
                encontrado = bool(_NUMERO_CON_UNIDAD_DEL_PROYECTO_RE.search(texto))
                self.assertEqual(encontrado, debe_casar, texto)

    def test_mutacion_un_numero_pegado_a_la_etiqueta_anterior_se_detecta_sobre_el_texto_que_construye_el_barrido(self):
        """(3a) del arreglo de H10 (revisión 5 de la 059, hallazgos.md) — el hueco que dejó
        pasar H10: todas las cadenas de `test_mutacion_vocabulario_reconoce_gramos_...` (arriba)
        y las cinco del comentario de `_NUMERO_CON_UNIDAD_RE` (`kcalibra/tests_pantallas.py`)
        empiezan por el dígito, y ninguna reproduce lo que el barrido real construye: un número
        de dato que en la FUENTE queda pegado, sin ningún espacio, al texto del elemento
        anterior (`<dt>Altura</dt><dd>...<span>{{ v }}</span> cm</dd>`, sin espacio entre
        `</dt>` y `<dd>` — exactamente `perfiles/ver.html:98`). Este test alimenta la tubería
        DE VERDAD (`_con_procedencia_marcada` + `_NumerosDeDatoEnElTexto.hallazgos`, la misma
        que usa el barrido universal), no un `regex.search` sobre una cadena inventada."""
        plantilla = engines["django"].from_string(
            "<dl><dt>Altura</dt><dd><span>{{ altura }}</span> cm</dd></dl>"
        )
        with _con_procedencia_marcada(), self._vocabulario_ancho():
            html = plantilla.render({"altura": 167})
            lector = _NumerosDeDatoEnElTexto()
            lector.feed(html)
            hallazgos = lector.hallazgos
        # El espacio añadido ENTRE `167` (la variable) y ` cm` (el literal que la sigue, ya con
        # su propio espacio) da dos espacios seguidos en el número capturado — cosmético: `\s*`
        # los absorbe igual al buscar, y lo único que importa aquí es que la coincidencia exista
        # y esté marcada `de_variable`.
        numeros_de_variable = [
            numero for numero, _, de_variable in hallazgos
            if de_variable and " ".join(numero.split()) == "167 cm"
        ]
        self.assertTrue(
            numeros_de_variable,
            f"«167 cm» pegado a «Altura» (sin espacio en la fuente) no se detectó: {hallazgos}",
        )

    def test_altura_de_perfiles_en_solo_lectura_lleva_cifra(self):
        """(3b) del arreglo de H10 (revisión 5 de la 059, hallazgos.md): el plan de trabajo
        (paso 6) nombra ESTA mutación en concreto — quitar `.cifra` del `cm` de
        `perfiles/ver.html:98` — como una de las cuatro obligatorias en rojo, y hasta H10 sólo
        la vigilaba el barrido genérico de arriba, que con el `(?<!\\w)` de H9 había dejado de
        verla del todo (`Altura167 cm`, sin ningún separador entre el `</dt>` anterior y el
        número). Test dedicado, con el fichero y la línea nombrados, para que esta mutación
        concreta no vuelva a depender solo de que el recorrido genérico alcance esa pantalla —
        Alejandro viendo el perfil de Berta (dos personas adultas del mismo hogar, sin relación
        de responsable entre ellas) cae siempre en la rama "solo lectura"
        (`puede_editar=False`) de `perfiles/ver.html`, la que lleva el `<dl>` con `Altura`/`cm`
        pegados sin espacio en la fuente."""
        with _con_procedencia_marcada(), self._vocabulario_ancho():
            respuesta = self.client.get(f"/perfiles/{self.berta.id}/")
            self.assertEqual(respuesta.status_code, 200)
            lector = _NumerosDeDatoEnElTexto()
            lector.feed(respuesta.content.decode())
            hallazgos = lector.hallazgos
        numeros_de_altura = [
            (numero, cadena) for numero, cadena, de_variable in hallazgos
            if de_variable and numero.strip().endswith("cm")
        ]
        self.assertTrue(
            numeros_de_altura,
            f"perfiles/ver.html:98 no mostró ningún «… cm» en /perfiles/{self.berta.id}/: {hallazgos}",
        )
        for numero, cadena in numeros_de_altura:
            self.assertTrue(
                _algun_elemento_de_la_cadena_lleva_cifra(cadena),
                f"«{numero}» sin `.cifra` en perfiles/ver.html:98: {[e for e, _ in cadena]}",
            )

    def test_un_salto_de_bloque_sin_espacio_en_la_fuente_separa_aunque_no_sea_dt_dd(self):
        """(3c) H11 (revisión 6 de la 059) — 3a sólo mide el caso concreto de H10 (`<dt>…</dt>
        <dd>…`). Este test mide el lado BLOQUE de la regla general: cualquier salto de elemento
        de bloque (aquí, `<p>` a `<p>`, sin espacio en la fuente) tiene que seguir separando —
        que un lector vería como dos frases sin nada entre medias, no como una palabra pegada —
        y por tanto el número tiene que seguir detectándose, igual que 3a con `<dt>`/`<dd>`."""
        plantilla = engines["django"].from_string(
            "<p>Peso</p><p><span>{{ peso }}</span> kg</p>"
        )
        with _con_procedencia_marcada(), self._vocabulario_ancho():
            html = plantilla.render({"peso": 80})
            lector = _NumerosDeDatoEnElTexto()
            lector.feed(html)
            hallazgos = lector.hallazgos
        numeros_de_variable = [
            numero for numero, _, de_variable in hallazgos
            if de_variable and " ".join(numero.split()) == "80 kg"
        ]
        self.assertTrue(
            numeros_de_variable,
            f"«80 kg» pegado a «Peso» (salto de bloque `<p></p><p>` sin espacio en la fuente) "
            f"no se detectó: {hallazgos}",
        )

    def test_una_etiqueta_inline_dentro_de_la_unidad_no_apaga_la_deteccion(self):
        """(3d) H11 (revisión 6 de la 059, MEDIO) — el hueco que dejó pasar H10 en el sentido
        contrario a 3a/3c: separar TODO límite entre `handle_data` (el arreglo de H10) despegaba
        también las mitades de una palabra que una etiqueta INLINE parte por dentro
        (`k<span>g</span>`, el `<wbr>` de una unidad larga en móvil…): el espacio insertado deja
        la unidad sin casar con ningún vocabulario, y la detección desaparece ENTERA — no es que
        el número se cuele sin `.cifra`, es que ni siquiera se reconoce como número de dato.
        `k<span>g</span>` reproduce, con el vocabulario ancho, la forma exacta que la Revisión 6
        midió como PÉRDIDA (`.runtime/v7/formas-separado-838f51d.txt`, fila 4)."""
        plantilla = engines["django"].from_string(
            "<span>{{ peso }}</span> k<span>g</span>"
        )
        with _con_procedencia_marcada(), self._vocabulario_ancho():
            html = plantilla.render({"peso": 80})
            lector = _NumerosDeDatoEnElTexto()
            lector.feed(html)
            hallazgos = lector.hallazgos
        numeros_de_variable = [
            numero for numero, _, de_variable in hallazgos
            if de_variable and " ".join(numero.split()) == "80 kg"
        ]
        self.assertTrue(
            numeros_de_variable,
            f"«80 kg» con la unidad partida por un `<span>` (`k<span>g</span>`, inline) dejó de "
            f"detectarse: {hallazgos}",
        )

    def test_una_etiqueta_inline_dentro_de_la_palabra_de_la_unidad_no_apaga_la_deteccion_en_pantalla_real(self):
        """(3e) H11 (revisión 6 de la 059) — la mutación EXACTA que la Revisión 6 pidió, sobre
        `recetas/templates/recetas/detalle.html:14`: sin `.cifra` y con la palabra "raciones"
        partida por una etiqueta `<b>` (algo que cualquiera escribiría para resaltar una letra).
        Hasta H11 esto pasaba con las 895 en VERDE: el separador de H10 rompía "raciones" en
        "r a ciones", que no casa con ningún vocabulario, y el número quedaba invisible para el
        barrido — no sólo sin `.cifra` marcado, sino sin ver siquiera que había un número."""
        plantilla = engines["django"].from_string(
            '<span>{{ raciones }}</span> '
            '{% if raciones == 1 %}ración{% else %}r<b>a</b>ciones{% endif %}'
        )
        with _con_procedencia_marcada(), self._vocabulario_ancho():
            html = plantilla.render({"raciones": 4})
            lector = _NumerosDeDatoEnElTexto()
            lector.feed(html)
            hallazgos = lector.hallazgos
        numeros_de_variable = [
            numero for numero, _, de_variable in hallazgos
            if de_variable and " ".join(numero.split()) == "4 raciones"
        ]
        self.assertTrue(
            numeros_de_variable,
            f"«4 raciones» con la unidad partida por un `<b>` (`r<b>a</b>ciones`, inline) dejó de "
            f"detectarse: {hallazgos}",
        )

    def test_una_etiqueta_de_nivel_de_texto_fuera_de_la_lista_sigue_perdiendo_la_deteccion_en_la_palabra_de_la_unidad(self):
        """La sexta dirección, H12 (revisión 7 de la 059) — los cinco tests de arriba (3a/3c del
        lado BLOQUE, 3b/3d/3e del lado INLINE) miden los dos lados del separador, pero los DOS
        con etiquetas que YA estaban en `_ETIQUETAS_INLINE`: ninguno mide qué pasa con una
        etiqueta que NO esté clasificada — que es justo donde vivía H12. `_ETIQUETAS_INLINE`
        era una lista CERRADA, y una etiqueta ajena, aunque fuera de nivel de texto de verdad,
        perdía la detección ENTERA (DIANA 1 de la Revisión 7: 52 pérdidas de 104 medidas, con
        `mark`/`u`/`s`/`del`/`ins`/`time`/`q`/`var`… — las 26 probadas dieron el mismo patrón).

        Esto NO se arregla añadiendo `mark`/`u`/`time`/`q`/`x-foo` a `_ETIQUETAS_INLINE` — sería
        la OCTAVA recaída, adivinar la próxima lista cerrada. El arreglo es el TRINQUETE
        (`TodaEtiquetaUsadaEnElArbolEstaClasificadaTests`, arriba): cualquier etiqueta nueva que
        aparezca de VERDAD en una plantilla pone la suite roja hasta que alguien la clasifique.
        Este test deja escrito, de forma permanente, QUÉ pasa mientras una etiqueta no está
        clasificada: sigue perdiendo la detección entera si parte la palabra de la unidad —
        exactamente las formas que la Revisión 7 midió (`Mili<T>litros</T>`, `k<T>g</T>`), sobre
        cinco etiquetas representativas que hoy NO existen en el árbol real (por eso el
        trinquete de arriba no las nombra: `mark`, `u`, `time`, `q`, y una personalizada
        `x-foo`, que corrobora que el efecto no depende de que la etiqueta sea HTML estándar)."""
        for etiqueta in ("mark", "u", "time", "q", "x-foo"):
            with self.subTest(etiqueta=etiqueta):
                plantilla = engines["django"].from_string(
                    f"<span>{{{{ cantidad }}}}</span> Mili<{etiqueta}>litros</{etiqueta}>"
                )
                with _con_procedencia_marcada(), self._vocabulario_ancho():
                    html = plantilla.render({"cantidad": 300})
                    lector = _NumerosDeDatoEnElTexto()
                    lector.feed(html)
                    hallazgos = lector.hallazgos
                numeros_de_variable = [
                    numero for numero, _, de_variable in hallazgos
                    if de_variable and " ".join(numero.split()) == "300 Mililitros"
                ]
                self.assertEqual(
                    numeros_de_variable, [],
                    f"«300 Mililitros» con la unidad partida por `<{etiqueta}>` (fuera de "
                    f"`_ETIQUETAS_INLINE`) se detectó igualmente — si esto se ha vuelto a "
                    f"clasificar, esta lista de etiquetas de control ya no vale de testigo: "
                    f"{hallazgos}",
                )

                plantilla_kg = engines["django"].from_string(
                    f"<span>{{{{ cantidad }}}}</span> k<{etiqueta}>g</{etiqueta}>"
                )
                with _con_procedencia_marcada(), self._vocabulario_ancho():
                    html_kg = plantilla_kg.render({"cantidad": 80})
                    lector_kg = _NumerosDeDatoEnElTexto()
                    lector_kg.feed(html_kg)
                    hallazgos_kg = lector_kg.hallazgos
                numeros_de_variable_kg = [
                    numero for numero, _, de_variable in hallazgos_kg
                    if de_variable and " ".join(numero.split()) == "80 kg"
                ]
                self.assertEqual(
                    numeros_de_variable_kg, [],
                    f"«80 kg» con la unidad partida por `<{etiqueta}>` (fuera de "
                    f"`_ETIQUETAS_INLINE`) se detectó igualmente — si esto se ha vuelto a "
                    f"clasificar, esta lista de etiquetas de control ya no vale de testigo: "
                    f"{hallazgos_kg}",
                )


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


# H19 (revisión 11 de la 059, MEDIO) — las dos flechas de abajo (`aria-describedby → id existe` /
# `id_helptext → algún aria-describedby lo pide`) sacan su población de los ATRIBUTOS QUE LA CURA
# ESCRIBIÓ en el HTML renderizado: revertir la cura ENTERA de una pantalla (las dos líneas a la
# vez, el `help_text` pintado sin `id` y sin nada que lo asocie) borra el elemento de las DOS
# poblaciones a la vez, y ninguna de las dos ve nada — el contrato promete "la red impide que
# vuelva" y no lo impedía. La población de ESTE control no sale de lo que la cura escribió: sale
# de la estructura que existe SIN la cura — el propio formulario, montado por la vista, del
# contexto de la respuesta. `BoundField.aria_describedby` (django/forms/boundfield.py, la MISMA
# propiedad que usa el `field.html` canónico de Django para decidir su id) ya calcula
# `f"{auto_id}_helptext"` para todo campo visible con `help_text` — reutilizarla evita reinventar
# la regla y sigue valiendo si el criterio de Django cambiara alguna vez.
def _campos_con_help_text_del_contexto(respuesta):
    """`[(nombre_de_la_clase_del_form, bound_field), ...]` de cada campo VISIBLE con `help_text`
    de cada `django.forms.BaseForm` que aparezca en el contexto de `respuesta` — sin nombrar
    ningún formulario ni ninguna pantalla: cualquier vista que meta un `Form`/`ModelForm` en su
    contexto entra sola. `respuesta.context` es un solo `Context` o, si la petición renderizó más
    de una plantilla, un `ContextList` (`django.test.utils.ContextList`) — en los dos casos,
    `.flatten()` da el diccionario final de nombres que la plantilla vio; se recorren los
    VALORES, no las claves, porque la clave ("form", "formulario"…) no es parte de ninguna
    definición de caso de esta unidad."""
    contexto = respuesta.context
    if contexto is None:
        return []
    subcontextos = contexto if isinstance(contexto, list) else [contexto]
    vistos = set()
    campos = []
    for sub in subcontextos:
        plano = sub.flatten() if hasattr(sub, "flatten") else dict(sub)
        for valor in plano.values():
            if not isinstance(valor, forms.BaseForm) or id(valor) in vistos:
                continue
            vistos.add(id(valor))
            for campo in valor.visible_fields():
                if campo.help_text:
                    campos.append((type(valor).__name__, campo))
    return campos


def _campos_pintados_de_help_text(campos, contenido):
    """De `campos` (toda la población de `_campos_con_help_text_del_contexto`: CUALQUIER campo
    visible con `help_text` de CUALQUIER formulario del contexto), cuáles tienen su `help_text`
    REALMENTE PINTADO en `contenido` — el contrato de R6, letra a letra: "en toda pantalla
    vigilada que PINTE `help_text`…". Un formulario que la vista mete en el contexto pero que
    esta RAMA de la plantilla no muestra (p.ej. `entrenos/ver.html` con `puede_editar=False`:
    Alejandro viendo los entrenos de Berta, otro adulto del mismo hogar, sin relación de
    responsable) no pinta nada, y R6 no promete nada sobre un campo que nadie ve. Se mide
    buscando el TEXTO auto-escapado de `help_text` (como lo escribe `{{ field.help_text }}`, sin
    `|safe` en ninguna de las plantillas que lo pintan — verificado) en el HTML.

    O34 (revisión 12) — esto es un filtro LEGÍTIMO (no todo campo del formulario se pinta en toda
    plantilla) pero es un artefacto ACCIDENTAL de CÓMO la plantilla escribe hoy el texto: sólo ve
    el campo si la plantilla lo imprime igual, letra a letra, que `{{ field.help_text }}` sin
    filtros que lo transformen. Si algún día una plantilla pinta el MISMO help_text de otra forma
    —a mano, con énfasis, por un filtro— este filtro deja de ver el campo, y las TRES flechas de
    R6 (`_campos_de_help_text_sin_asociar`, más abajo, y sus dos tests) se quedan mudas para él —
    medido, revisión 12: `<strong>` en el `help_text` de `comidas`, con la cura entera revertida,
    da `EXIT=0`. La cura de ESE hueco no es quitar este filtro (seguiría siendo generoso: contaría
    campos que ninguna rama pinta) — es
    `_campos_con_widget_pintado_y_ayuda_no_canonica` (H22, más abajo), que decide "pintado" por el
    WIDGET del campo, no por el texto de su ayuda, y vigila precisamente el hueco que este filtro
    deja."""
    return [
        (nombre_form, campo) for nombre_form, campo in campos
        if escape(campo.help_text) in contenido
    ]


# H22/H26 (revisiones 12 y 13 de la 059, BLOQUEANTE) — el hueco que `_campos_pintados_de_help_text`
# deja (O34, arriba): decide "pintado" por IGUALDAD DE TEXTO, así que una plantilla que pinte el
# MISMO `help_text` de otra forma (a mano, con `<strong>`, por un filtro) saca al campo de la
# población de R6 ENTERA, no sólo de este filtro — las tres flechas se quedan mudas a la vez. Este
# trinquete de POBLACIÓN, hermano del de H21 (`.cifra`) y del de H19-POBLACIÓN, no cambia el filtro
# de arriba (sigue siendo el correcto para decidir SOBRE QUÉ CAMPO exigir R6): decide "pintado"
# preguntándoselo al WIDGET —el conjunto de `name=` que declara de verdad, no una `f`-string que
# asuma `name="<html_name>"` (H26, revisión 13: falso para `MultiWidget`/`SelectDateWidget`, las
# dos familias con `use_fieldset=True` que escriben un `name=` POR SUBWIDGET)— y exige que, si el
# widget se pinta, su ayuda se pinte por la vía canónica O esté declarada aquí con su porqué.
# Vacía hoy: medido (revisión 12), los 5 campos que el barrido alcanza están, los 5, con su ayuda
# pintada por la vía canónica.
_CAMPOS_DE_HELP_TEXT_PINTADOS_SIN_LA_VIA_CANONICA_FUERA_DE_FICHEROS = frozenset()


def _nombres_de_name_de_subwidgets(contexto_widget):
    """H29 (revisión 14 de la 059, MEDIO) — un `subwidget` del contexto de un `MultiWidget` es él
    mismo el contexto que SU widget devolvió (`MultiWidget.get_context`: cada subwidget sale de
    `widget.get_context(...)["widget"]`), así que si ESE widget es a su vez compuesto —un rango
    "entre estas dos fechas-hora", dos `SplitDateTimeWidget`— trae su PROPIO `subwidgets` anidado.
    `_nombres_de_name_que_el_widget_escribe` (abajo) bajaba UN solo nivel y se quedaba con
    `entre_0`/`entre_1` cuando el HTML de verdad lleva `entre_0_0`/`entre_0_1`/`entre_1_0`/
    `entre_1_1` — devolvía "no pintado" sobre el HTML que el propio widget acababa de escribir.
    Recursiva: se expande cualquier nivel de anidamiento, no sólo uno."""
    subwidgets = contexto_widget.get("subwidgets")
    if not subwidgets:
        return [contexto_widget["name"]]
    return [
        nombre
        for subwidget in subwidgets
        for nombre in _nombres_de_name_de_subwidgets(subwidget)
    ]


def _nombres_de_name_que_el_widget_escribe(campo):
    """H26 (revisión 13 de la 059, BLOQUEANTE) — el conjunto de `name=` que el WIDGET de `campo`
    escribe de verdad, preguntándoselo al WIDGET (`get_context`) en vez de darlo por hecho. Un
    widget COMPUESTO (`MultiWidget` y sus subclases —`SplitDateTimeWidget`, `SelectDateWidget`—,
    dos de las CUATRO familias de Django con `use_fieldset=True`, las únicas para las que este
    trinquete existe) nunca escribe `name="<html_name>"`: escribe un `name=` POR SUBWIDGET
    (`get_context(...)["widget"]["subwidgets"]`, cada uno con el suyo — `SelectDateWidget` para
    `campo="c"` escribe `c_day`/`c_month`/`c_year`, medido en vivo), y ese subwidget puede a su vez
    ser compuesto (H29: `_nombres_de_name_de_subwidgets`, arriba, baja TODOS los niveles, no sólo
    uno). Para el resto (incluidas `CheckboxSelectMultiple`/`RadioSelect`, las otras dos familias
    con `use_fieldset=True`: `get_context` no les añade `subwidgets`, sólo `optgroups`), el único
    `name=` es `campo.html_name`, tal y como asumía H22."""
    contexto_widget = campo.field.widget.get_context(campo.html_name, campo.value(), {})["widget"]
    return _nombres_de_name_de_subwidgets(contexto_widget)


# O44 (revisión 14 de la 059, MENOR) — el patrón original no reconocía `name=x/>` (sin comillas
# y con la barra de autocierre pegada al valor, sin espacio delante): el delimitador de cierre no
# incluía `/`. Ampliado. La otra mitad de O44 —el patrón busca en la página ENTERA, no en la
# región del formulario, así que un `name=` de otro origen (`<meta name="viewport">`,
# `base.html:6`; o un segundo formulario con un campo del mismo nombre) puede marcar como
# "pintado" un campo que no lo está— sigue abierta: acotar la búsqueda a la región del formulario
# exigiría pasar qué HTML pertenece a qué `<form>`, algo que esta función no recibe hoy y que
# ningún caso real dispara todavía (ningún campo se llama "viewport", medido). Queda en
# `hallazgos.md` como deuda, no como bloqueo.
_NOMBRE_DE_WIDGET_EN_HTML_RE = r'name\s*=\s*["\']?{}["\'\s/>]'


def _campo_esta_pintado_por_su_widget(campo, contenido):
    """H22/H26 — si el CAMPO se pinta de verdad en esta página: ALGUNO de los `name=` que su
    WIDGET escribe (arriba) aparece en el HTML. A diferencia de `_campos_pintados_de_help_text`
    (que decide por el TEXTO del `help_text`), esto decide por el WIDGET — lo que Django escribe
    para CUALQUIER campo visible, tenga o no su `help_text` pintado de la forma canónica. "Lo que
    Django siempre escribe" era, hasta H29 (revisión 14), una promesa que la función NO cumplía
    para un `MultiWidget` con subwidgets compuestos (devolvía "no pintado" sobre el HTML que el
    propio widget acababa de escribir) — `_nombres_de_name_de_subwidgets` ahora baja TODOS los
    niveles de anidamiento, no sólo uno.

    H26 (revisión 13, BLOQUEANTE) — la versión anterior era `f'name="{campo.html_name}"' in
    contenido`: una igualdad de subcadena con las comillas DOBLES metidas a fuego (medido en vivo
    sobre `/perfiles/`: el mismo campo pintado a mano con `name='…'` — HTML igual de válido, la
    pantalla se ve igual — dejaba la ayuda visible, sin `id` y sin ningún `aria-describedby`, con
    la suite entera en verde) y que además asumía que TODO widget escribe `name="<html_name>"`
    (falso para los widgets compuestos, arriba). El patrón de aquí acepta comilla simple, doble o
    ninguna, igual que tendría que haber aceptado siempre — es la misma familia de defecto que el
    propio contrato de esta unidad ya trae documentada como falso rojo heredado de la 053
    (`assertIn('role="menu"', contenido)` con comillas dobles fijas)."""
    return any(
        re.search(_NOMBRE_DE_WIDGET_EN_HTML_RE.format(re.escape(nombre)), contenido)
        for nombre in _nombres_de_name_que_el_widget_escribe(campo)
    )


def _campos_con_widget_pintado_y_ayuda_no_canonica(campos, contenido):
    """H22 — de TODOS los campos con `help_text` del contexto (sin pasar por el filtro de
    `_campos_pintados_de_help_text`: aquí la población es la ESENCIAL, el campo entero, no el
    subconjunto que ya se pinta por texto), cuáles tienen su WIDGET pintado (el campo está de
    verdad en esta página, lo confirme o no el texto de su ayuda) pero su `help_text` NO aparece
    por la vía canónica. Devuelve `(nombre_form, campo)` de cada uno — la firma exacta que el
    test de abajo declara como excepción."""
    return [
        (nombre_form, campo) for nombre_form, campo in campos
        if _campo_esta_pintado_por_su_widget(campo, contenido)
        and escape(campo.help_text) not in contenido
    ]


def _campos_de_help_text_sin_asociar(campos, contenido):
    """El corazón de H19: de los campos REALMENTE PINTADOS (arriba), cuáles NO tienen su
    `f"{auto_id}_helptext"` EXISTENTE en `contenido` Y PEDIDO por algún `aria-describedby` — las
    dos cosas a la vez, así que quitar cualquiera de las dos mitades de la cura de R6 (o las dos
    juntas, que es exactamente H19) lo pone en la lista. Devuelve
    `[(nombre_form, nombre_campo, id_esperado, presente, referenciado), ...]`."""
    lector = _IdsYAriaDescribedby()
    lector.feed(contenido)
    referenciados = set(lector.referencias)
    problemas = []
    for nombre_form, campo in _campos_pintados_de_help_text(campos, contenido):
        id_esperado = f"{campo.auto_id}_helptext"
        presente = id_esperado in lector.ids
        referenciado = id_esperado in referenciados
        if presente and referenciado:
            continue
        problemas.append((nombre_form, campo.name, id_esperado, presente, referenciado))
    return problemas


# H19-POBLACIÓN (vuelta 14 de la 059) — la pregunta de la revisión 11, en la línea de lo que la
# vuelta 12 hizo con H21: ¿cuántos campos con `help_text` hay DECLARADOS en los formularios
# PROPIOS del proyecto (no los de Django ni de allauth, que traen los suyos), y cuántos ve
# realmente el barrido de arriba en las 39 rutas? Medido (vuelta 14, `.runtime/v14/poblacion-
# help-text.txt`): **7 declarados, 5 alcanzados**. La diferencia son, EXACTAMENTE, los dos campos
# de `cuentas.forms.FormularioAlta` (`codigo_hogar`, `ajuste_pct`): es el formulario de ALTA de
# allauth (`ACCOUNT_SIGNUP_FORM_CLASS`), que sólo se pinta SIN sesión iniciada — el barrido de
# H19 corre con Alejandro y Carlos YA logueados, a propósito (vigila pantallas YA vigiladas, no
# el flujo de alta), el mismo motivo por el que R1-R8 dejan fuera las diez pantallas de cuentas.
# No es una fuga silenciosa: está declarada aquí, con trinquete, para que si un OCTAVO campo se
# queda inalcanzable sin que nadie lo diga, el test de abajo se ponga rojo nombrándolo.
_CAMPOS_DE_HELP_TEXT_INALCANZABLES_POR_SESION_FUERA_DE_FICHEROS = frozenset({
    ("FormularioAlta", "codigo_hogar"),
    ("FormularioAlta", "ajuste_pct"),
})


def _campos_con_help_text_declarados_en_los_formularios_propios():
    """Universo DECLARADO de H19-POBLACIÓN: recorre los `AppConfig` del proyecto —excluye
    `django.contrib.*` y `allauth.*`, que traen sus propios formularios internos (login, cambiar
    contraseña…) ajenos a esta unidad—, importa `<app>.forms` si existe, y se queda con
    `(NombreDeLaClase, nombre_del_campo)` de cada campo de CUALQUIER `django.forms.BaseForm`
    DEFINIDO ahí (no importado: `obj.__module__ == modulo.__name__` descarta lo que un
    `forms.py` importa de otro sitio) cuyo `help_text` no esté vacío. `base_fields` es de CLASE
    (`FormularioReceta.base_fields`, no una instancia): no hace falta instanciar ningún
    formulario, y varios exigen argumentos que este barrido no tiene (`FormularioPasarACargo`
    pide `hogar`/`excluir`)."""
    declarados = set()
    for app_config in apps.get_app_configs():
        if app_config.name.startswith("django.") or app_config.name.startswith("allauth"):
            continue
        try:
            modulo = import_module(f"{app_config.name}.forms")
        except ModuleNotFoundError:
            continue
        for obj in vars(modulo).values():
            if not (isinstance(obj, type) and issubclass(obj, forms.BaseForm)
                    and obj.__module__ == modulo.__name__):
                continue
            for nombre_campo, campo in obj.base_fields.items():
                if campo.help_text:
                    declarados.add((obj.__name__, nombre_campo))
    return declarados


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
#
# H19 (vuelta 13): la misma exención, SIN ensancharla ni un milímetro, cubre también la flecha
# nueva de `test_todo_campo_con_help_text_del_formulario_tiene_su_id_asociado` — se llama con el
# mismo `id_esperado` ("id_calorias_helptext") sobre la misma ruta, así que es la función de
# siempre reutilizada, no una segunda exención que pudiera ensancharse por su cuenta.
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
        # H8 (revisión 3), el trinquete que le faltaba a esta SEGUNDA lista de excepciones: si
        # `entrenos/corregir.html` deja de pedir `id_calorias_helptext` sin declararlo —porque el
        # padre aplicó el diff de hallazgos.md—, la exención ya no encuentra nada que eximir y
        # esto se pone ROJO pidiendo borrarla, en vez de quedarse muda para siempre en verde.
        #
        # O9 (revisión 4) — el trinquete y los huérfanos reales se afirman JUNTOS, en un solo
        # `assertEqual`: antes, `assertEqual(huerfanos, [])` corría ANTES del `assertTrue` del
        # trinquete, así que una corrida con huérfanos reales Y el trinquete disparado sólo
        # nombraba los huérfanos — arreglar y volver a correr para ver el trinquete. Ningún rojo
        # se pierde (el trinquete seguía cayendo en la siguiente corrida); ahora uno solo cuenta
        # los dos de golpe.
        problemas = list(huerfanos)
        if not vista_la_exencion_de_entrenos_corregir:
            problemas.append(
                "la exención de `_es_el_hueco_r6_fuera_de_ficheros` ya no encontró su huérfano "
                f"medido ({_ID_DEL_HUECO_R6_FUERA_DE_FICHEROS} en /entrenos/.../corregir/): "
                "probablemente el padre ya aplicó la línea propuesta en hallazgos.md — borra la "
                "exención, el trinquete acaba de cazarla"
            )
        self.assertEqual(problemas, [], f"R6/H8 en rojo: {problemas}")

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

    def test_todo_id_helptext_tiene_algun_aria_describedby_que_lo_pida(self):
        """H17 (revisión 10 de la 059, MEDIO) — el test de arriba sólo comprueba la flecha
        `aria-describedby → id existe`; le falta la contraria. Un `<p id="..._helptext">` al
        que nadie apunte con `aria-describedby` es invisible para ese test aunque su `id` siga
        ahí escrito — es justo lo que le pasaba a `recetas/formulario.html` (campo `comidas`,
        un `CheckboxSelectMultiple` con `use_fieldset=True`: Django no le pone
        `aria-describedby` al widget de un grupo, así que hacía falta ponerlo a mano en el
        contenedor del grupo, como hace el propio `django/forms/templates/django/forms/
        field.html` con el `<fieldset>`). Derivado de la MISMA estructura que el test de
        arriba (`_IdsYAriaDescribedby`, todos los `id` de la página), sin nombrar ninguna
        pantalla: cualquier `id` que termine en `_helptext` tiene que aparecer en ALGÚN
        `aria-describedby` de la MISMA página."""
        nombres = _nombres_de_pantallas_reales_hoy()
        paginas_alejandro, alcanzadas_alejandro = _paginas_de_pantallas_reales(self.client, nombres, "/")
        paginas_carlos, alcanzadas_carlos = _paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        paginas = paginas_alejandro + paginas_carlos
        self.assertGreaterEqual(len(paginas), 10, "el recorrido apenas alcanzó pantallas reales")
        inertes = []
        total_helptexts = 0
        for ruta, contenido in paginas:
            lector = _IdsYAriaDescribedby()
            lector.feed(contenido)
            referenciados = set(lector.referencias)
            helptexts = sorted(id_ for id_ in lector.ids if id_.endswith("_helptext"))
            total_helptexts += len(helptexts)
            for id_ in helptexts:
                if id_ not in referenciados:
                    inertes.append(f"{ruta}: id='{id_}' sin ningún aria-describedby que lo pida")
        self.assertGreater(
            total_helptexts, 0,
            "ninguna página trajo ni un id de ayuda (*_helptext): la fixture no está "
            "ejercitando ningún help_text — el test no probaría nada",
        )
        self.assertEqual(
            inertes, [],
            f"H17: `id` de ayuda escrito pero inerte, sin nadie que lo pida: {inertes}",
        )

    def test_mutacion_un_id_helptext_sin_referencia_se_pone_rojo(self):
        """H17 — el mismo patrón de mutación EN CÓDIGO que el resto de esta clase, sobre HTML
        sintético: un `id="..._helptext"` sin ningún `aria-describedby` que lo pida tiene que
        aparecer como inerte; añadido el `aria-describedby`, deja de estarlo."""
        lector = _IdsYAriaDescribedby()
        lector.feed('<p id="id_nombre_helptext">ayuda</p>')
        inertes = [
            id_ for id_ in lector.ids
            if id_.endswith("_helptext") and id_ not in set(lector.referencias)
        ]
        self.assertEqual(
            inertes, ["id_nombre_helptext"],
            "el control: un id_helptext sin ningún aria-describedby debía aparecer como inerte",
        )
        lector_con_referencia = _IdsYAriaDescribedby()
        lector_con_referencia.feed(
            '<div aria-describedby="id_nombre_helptext"><p id="id_nombre_helptext">ayuda</p></div>'
        )
        inertes_con_referencia = [
            id_ for id_ in lector_con_referencia.ids
            if id_.endswith("_helptext") and id_ not in set(lector_con_referencia.referencias)
        ]
        self.assertEqual(inertes_con_referencia, [])

    def test_mutacion_el_help_text_pintado_escapado_no_se_confunde_con_el_texto_crudo(self):
        """H37-P (vuelta 20 de la 059, BLOQUEANTE, encontrado en la 2ª ronda de barrido) —
        `_campos_pintados_de_help_text` (el filtro que O34 documenta, la población de
        `_campos_de_help_text_sin_asociar`) busca el TEXTO auto-escapado de `help_text` —
        `escape(campo.help_text)`, lo que `{{ field.help_text }}` escribe de verdad, sin
        `|safe` en ninguna plantilla (verificado)— no el texto crudo. Medido por mí, mismo
        método del revisor: quitar `escape(...)` deja los 205 tests de `kcalibra` en verde,
        porque ninguno de los `help_text` reales de hoy lleva un carácter que el escapado
        transforme. Con un `help_text` que lleva un `&`, comparar contra el texto crudo deja
        de ver el campo como pintado: R6 dejaría de exigirle su `id`/`aria-describedby` sobre
        un campo que SÍ se ve en la pantalla — falso VERDE."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="Sal & pimienta, a tu gusto")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]

        pintados = _campos_pintados_de_help_text(campos, f"<p>{escape(campo.help_text)}</p>")
        self.assertEqual(
            [c.name for _, c in pintados], ["campo"],
            "un help_text con un carácter especial (&), pintado ESCAPADO — la forma en la que "
            "Django lo escribe de verdad — no se detectó como pintado: la comparación dejó de "
            "escapar el help_text antes de buscarlo en el HTML",
        )

    def test_todo_campo_con_help_text_del_formulario_tiene_su_id_asociado(self):
        """H19 (revisión 11 de la 059, MEDIO) — los dos tests de arriba sacan su población de los
        ATRIBUTOS QUE LA CURA DE R6 ESCRIBIÓ (los `id` y los `aria-describedby` PRESENTES en el
        HTML renderizado): revertir la cura ENTERA de una pantalla (las dos líneas a la vez, el
        `<p>` de `help_text` pintado, sin `id` y sin nada que lo asocie — el estado exacto
        anterior a esta unidad) borra el elemento de las DOS poblaciones a la vez, así que
        NINGUNA de las dos ve nada — medido, revisión 11, D2: `EXIT=0` con la mutación doble
        puesta, cuando el contrato promete "la red impide que vuelva".

        La población de ESTE test no sale de la cura: sale del FORMULARIO que la vista monta,
        que sigue existiendo pase lo que pase con el HTML (`_campos_con_help_text_del_contexto`,
        arriba) — así que ve el caso conjunto que las dos flechas, cada una por su lado, no
        podían ver."""
        nombres = _nombres_de_pantallas_reales_hoy()
        paginas_alejandro, alcanzadas_alejandro = _formularios_y_paginas_de_pantallas_reales(
            self.client, nombres, "/"
        )
        paginas_carlos, alcanzadas_carlos = _formularios_y_paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        paginas = paginas_alejandro + paginas_carlos
        self.assertGreaterEqual(len(paginas), 10, "el recorrido apenas alcanzó pantallas reales")
        alcanzadas = alcanzadas_alejandro | alcanzadas_carlos
        self.assertEqual(
            alcanzadas, nombres,
            f"pantallas reales que el recorrido no alcanzó, y H19 no las miró: {sorted(nombres - alcanzadas)}",
        )
        sin_asociar = []
        total_campos = 0
        vista_la_exencion_de_entrenos_corregir = False
        for ruta, contenido, campos in paginas:
            if not campos:
                continue
            total_campos += len(_campos_pintados_de_help_text(campos, contenido))
            for nombre_form, nombre_campo, id_esperado, presente, referenciado in \
                    _campos_de_help_text_sin_asociar(campos, contenido):
                if _es_el_hueco_r6_fuera_de_ficheros(ruta, id_esperado):
                    vista_la_exencion_de_entrenos_corregir = True
                    continue  # ver el comentario de la exención, arriba de esta clase
                sin_asociar.append(
                    f"{ruta}: {nombre_form}.{nombre_campo} declara help_text pero "
                    f"'{id_esperado}' no está asociado (presente={presente}, "
                    f"referenciado={referenciado})"
                )
        self.assertGreater(
            total_campos, 0,
            "ningún formulario del contexto trajo un campo visible con help_text: la fixture "
            "no está ejercitando ningún formulario — el test no probaría nada",
        )
        problemas = list(sin_asociar)
        if not vista_la_exencion_de_entrenos_corregir:
            problemas.append(
                "la exención de `_es_el_hueco_r6_fuera_de_ficheros` ya no encontró su huérfano "
                f"medido ({_ID_DEL_HUECO_R6_FUERA_DE_FICHEROS} en /entrenos/.../corregir/) por "
                "esta vía: probablemente el padre ya aplicó la línea propuesta en hallazgos.md "
                "— borra la exención, el trinquete acaba de cazarla"
            )
        self.assertEqual(problemas, [], f"H19: {problemas}")

    def test_mutacion_revertir_la_cura_entera_de_help_text_se_pone_rojo(self):
        """H19 — la mutación EN CÓDIGO que revierte la cura ENTERA (ni `id` ni
        `aria-describedby`), sobre un formulario y un HTML sintéticos, nunca sobre una plantilla
        real: la población de `_campos_de_help_text_sin_asociar` sale del FORMULARIO, que no
        cambia con la cura, así que ve el caso conjunto que las dos flechas de arriba, juntas
        (D2 de la revisión 11), no veían."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="ayuda")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]
        id_esperado = f"{campo.auto_id}_helptext"

        # la cura entera revertida: el <p> de help_text pintado, sin id y sin aria-describedby
        sin_nada = _campos_de_help_text_sin_asociar(campos, "<div><p>ayuda</p></div>")
        self.assertEqual(
            [c for _, c, *_ in sin_nada], ["campo"],
            f"la cura entera revertida (ni id ni aria-describedby) no se detectó: {sin_nada}",
        )

        # solo el id (falta el aria-describedby que lo pida)
        solo_id = _campos_de_help_text_sin_asociar(
            campos, f'<div><p id="{id_esperado}">ayuda</p></div>'
        )
        self.assertEqual([c for _, c, *_ in solo_id], ["campo"])

        # solo el aria-describedby (falta el id al que apuntar)
        solo_referencia = _campos_de_help_text_sin_asociar(
            campos, f'<div aria-describedby="{id_esperado}"><p>ayuda</p></div>'
        )
        self.assertEqual([c for _, c, *_ in solo_referencia], ["campo"])

        # las dos mitades de la cura, juntas: sin problemas
        con_las_dos = _campos_de_help_text_sin_asociar(
            campos,
            f'<div aria-describedby="{id_esperado}"><p id="{id_esperado}">ayuda</p></div>',
        )
        self.assertEqual(con_las_dos, [])

    def test_todo_campo_con_help_text_declarado_es_alcanzado_o_esta_eximido_por_sesion(self):
        """H19-POBLACIÓN (vuelta 14 de la 059, MEDIO) — el control de POBLACIÓN que le faltaba a
        H19, en la línea de lo que la vuelta 12 hizo con H21: los tests de arriba comprueban que
        todo lo que el barrido SÍ ve está bien asociado, pero ninguno pregunta si el barrido está
        viendo TODO lo que hay que ver. Medido (vuelta 14): 7 campos con `help_text` declarados
        en los formularios propios, 5 alcanzados por el barrido de Alejandro+Carlos — la
        diferencia son, EXACTAMENTE, los dos de `FormularioAlta` (el formulario de ALTA de
        allauth, que sólo se pinta SIN sesión iniciada). Si un OCTAVO campo se queda fuera sin
        que la excepción de arriba lo cubra, esto se pone rojo nombrándolo — la excepción es
        exacta, no generosa, igual que R8 con la lista de pantallas."""
        declarados = _campos_con_help_text_declarados_en_los_formularios_propios()
        self.assertGreaterEqual(
            len(declarados), 5,
            "el universo DECLARADO se ha quedado sospechosamente pequeño: revisa si "
            "`_campos_con_help_text_declarados_en_los_formularios_propios` sigue mirando los "
            "formularios propios de verdad",
        )

        nombres = _nombres_de_pantallas_reales_hoy()
        paginas_alejandro, _alcanzadas_alejandro = _formularios_y_paginas_de_pantallas_reales(
            self.client, nombres, "/"
        )
        paginas_carlos, _alcanzadas_carlos = _formularios_y_paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        alcanzados = {
            (nombre_form, campo.name)
            for _ruta, _contenido, campos in paginas_alejandro + paginas_carlos
            for nombre_form, campo in campos
        }

        problemas = []
        vistas_las_dos_exenciones = set()
        for clave in declarados:
            if clave in alcanzados:
                continue
            if clave in _CAMPOS_DE_HELP_TEXT_INALCANZABLES_POR_SESION_FUERA_DE_FICHEROS:
                vistas_las_dos_exenciones.add(clave)
                continue  # ver el comentario de la excepción, arriba
            problemas.append(
                f"{clave[0]}.{clave[1]} declara help_text pero el barrido de H19 no lo alcanzó, "
                "y no es ninguna de las dos exenciones conocidas de FormularioAlta"
            )
        exenciones_no_vistas = (
            _CAMPOS_DE_HELP_TEXT_INALCANZABLES_POR_SESION_FUERA_DE_FICHEROS - vistas_las_dos_exenciones
        )
        if exenciones_no_vistas:
            problemas.append(
                f"la excepción de sesión ya no encontró su inalcanzable medido {sorted(exenciones_no_vistas)}: "
                "o el barrido empezó a alcanzar `FormularioAlta` (borra la excepción, el "
                "trinquete acaba de cazarla) o el campo dejó de declarar help_text"
            )
        self.assertEqual(problemas, [], f"H19-POBLACIÓN: {problemas}")

    def test_mutacion_un_formulario_importado_de_otra_app_no_se_cuenta_como_propio(self):
        """H37-Q (vuelta 20 de la 059, BLOQUEANTE, encontrado en la 3ª ronda de barrido) —
        `_campos_con_help_text_declarados_en_los_formularios_propios` exige `obj.__module__ ==
        modulo.__name__` para quedarse sólo con los formularios DEFINIDOS en `<app>.forms`, no
        los que ese módulo IMPORTA de otra app (`from otra_app.forms import FormularioX`): sin
        el filtro, un formulario importado por DOS apps distintas se contaría dos veces en la
        población DECLARADA de H19, y el trinquete de arriba dejaría de ser exacto. Medido por
        mí, mismo método del revisor (mockeando `apps.get_app_configs`/`import_module`, nunca
        tocando el registro real de Django): ningún `forms.py` propio de hoy importa un
        formulario de otra app (verificado con grep), así que quitar el filtro deja los 205
        tests de `kcalibra` en verde — el hueco no muerde en el árbol real todavía."""
        class _FormularioDefinidoEnOtroSitio(forms.Form):
            campo_ajeno = forms.CharField(help_text="ayuda de un formulario de OTRA app")

        _FormularioDefinidoEnOtroSitio.__module__ = "app_h37q_definidora.forms"

        modulo_que_lo_importa = mock.Mock()
        modulo_que_lo_importa.__name__ = "app_h37q_importadora.forms"
        modulo_que_lo_importa.FormularioImportado = _FormularioDefinidoEnOtroSitio

        app_config_de_prueba = mock.Mock()
        app_config_de_prueba.name = "app_h37q_importadora"

        with mock.patch(
            "kcalibra.tests_pantallas_del_proyecto.apps.get_app_configs",
            return_value=[app_config_de_prueba],
        ), mock.patch(
            "kcalibra.tests_pantallas_del_proyecto.import_module",
            return_value=modulo_que_lo_importa,
        ):
            declarados = _campos_con_help_text_declarados_en_los_formularios_propios()
        self.assertEqual(
            declarados, set(),
            "un formulario IMPORTADO (definido en `app_h37q_definidora.forms`, no en el "
            "módulo que lo importa) se contó como propio de `app_h37q_importadora`: el "
            "filtro `obj.__module__ == modulo.__name__` se ha perdido",
        )

    def test_todo_campo_con_widget_pintado_pinta_su_ayuda_por_la_via_canonica_o_esta_eximido(self):
        """H22 (revisión 12 de la 059, BLOQUEANTE) — el trinquete de POBLACIÓN que le faltaba al
        filtro `_campos_pintados_de_help_text` (O34, ver su docstring): decide "pintado" por el
        WIDGET del campo (su `name=` en el HTML), no por el TEXTO de su ayuda, así que sigue
        viendo el campo aunque su `help_text` se pinte de otra forma — a mano, con énfasis, por
        un filtro. Si el widget se pinta y la ayuda NO aparece por la vía canónica, y no está
        eximido con su porqué, esto se pone rojo nombrándolo — es la POBLACIÓN correcta, no una
        tercera flecha que compita con las de `_campos_de_help_text_sin_asociar`: esas siguen
        siendo las que deciden si un campo cuya ayuda SÍ es canónica está bien asociada (`id`
        y `aria-describedby`); ésta decide si algún campo se le está escapando ENTERO a las dos.

        Hoy sale verde con CERO excepciones: los 5 campos que el barrido alcanza tienen, los 5,
        su ayuda pintada por la vía canónica. Mutación (revisión 12,
        `.runtime/rev12/m1-help-text-en-linea.diff`): revertir la cura entera de
        `recetas/templates/recetas/formulario.html` Y pintar el `help_text` de `comidas` a mano
        con un `<strong>` en una palabra deja su `<input>` pintado (`name="comidas"` sigue en el
        HTML) pero su ayuda ya no coincide letra a letra — este trinquete lo caza aunque las dos
        flechas de arriba (que ya no ven el campo, filtrado por `_campos_pintados_de_help_text`)
        se queden mudas."""
        nombres = _nombres_de_pantallas_reales_hoy()
        paginas_alejandro, _alcanzadas_alejandro = _formularios_y_paginas_de_pantallas_reales(
            self.client, nombres, "/"
        )
        paginas_carlos, _alcanzadas_carlos = _formularios_y_paginas_de_pantallas_reales(
            self.client_carlos, nombres, "/hogares/mi-hogar/"
        )
        paginas = paginas_alejandro + paginas_carlos
        self.assertGreaterEqual(len(paginas), 10, "el recorrido apenas alcanzó pantallas reales")
        problemas = []
        total_widgets_pintados = 0
        for ruta, contenido, campos in paginas:
            if not campos:
                continue
            no_canonicos = _campos_con_widget_pintado_y_ayuda_no_canonica(campos, contenido)
            total_widgets_pintados += len(
                [c for _, c in campos if _campo_esta_pintado_por_su_widget(c, contenido)]
            )
            for nombre_form, campo in no_canonicos:
                clave = (nombre_form, campo.name)
                if clave in _CAMPOS_DE_HELP_TEXT_PINTADOS_SIN_LA_VIA_CANONICA_FUERA_DE_FICHEROS:
                    continue
                problemas.append(
                    f"{ruta}: {nombre_form}.{campo.name} pinta su widget "
                    f"(name=\"{campo.html_name}\") pero su help_text no aparece por la vía "
                    f"canónica, y no está eximido"
                )
        self.assertGreater(
            total_widgets_pintados, 0,
            "ningún campo con help_text tuvo su widget pintado en ninguna página: la fixture "
            "no está ejercitando ningún formulario — el test no probaría nada",
        )
        self.assertEqual(problemas, [], f"H22: {problemas}")

    def test_mutacion_una_ayuda_pintada_de_otra_forma_se_pone_rojo(self):
        """H22 — la mutación EN CÓDIGO, sobre un formulario y un HTML sintéticos (nunca sobre una
        plantilla real): el widget pintado con su `name=` de siempre, pero el `help_text` escrito
        con un `<strong>` en vez de letra a letra — el defecto exacto que
        `_campos_pintados_de_help_text` no ve (O34) y que este trinquete sí."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="ayuda con una palabra clave")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]

        con_strong = _campos_con_widget_pintado_y_ayuda_no_canonica(
            campos,
            f'<input type="text" name="{campo.html_name}">'
            '<p>ayuda con una <strong>palabra</strong> clave</p>',
        )
        self.assertEqual(
            [c.name for _, c in con_strong], ["campo"],
            "un help_text pintado con <strong> en vez de letra a letra no apareció como "
            "no-canónico: el trinquete no está vigilando de verdad",
        )

        canonico = _campos_con_widget_pintado_y_ayuda_no_canonica(
            campos,
            f'<input type="text" name="{campo.html_name}">'
            '<p>ayuda con una palabra clave</p>',
        )
        self.assertEqual(canonico, [], "con el texto canónico, el barrido debía vaciarse")

        widget_no_pintado = _campos_con_widget_pintado_y_ayuda_no_canonica(
            campos, "<p>ayuda con una <strong>palabra</strong> clave</p>",
        )
        self.assertEqual(
            widget_no_pintado, [],
            "sin el name= del widget en el HTML, el campo no está pintado de verdad en esta "
            "rama — R6 no promete nada sobre un campo que nadie ve",
        )

    def test_mutacion_el_help_text_escapado_no_se_confunde_con_el_texto_crudo(self):
        """H37-J (vuelta 20 de la 059, BLOQUEANTE) —
        `_campos_con_widget_pintado_y_ayuda_no_canonica` compara `escape(campo.help_text)`
        contra el HTML, no el texto crudo: lo que `{{ field.help_text }}` escribe de verdad es
        auto-escapado (sin `|safe` en ninguna plantilla, verificado). Medido por el revisor
        (Revisión 16, D3): quitar `escape(...)` deja los 205 tests de `kcalibra` en verde —
        porque ninguna plantilla real de hoy tiene un `help_text` con un carácter que el
        escapado transforme. Con un `help_text` que lleva un `&` (HTML válido, cualquiera lo
        escribiría), el HTML renderizado trae `&amp;`, no `&` a secas: comparar contra el
        texto crudo declara la ayuda «no pintada por la vía canónica» cuando SÍ lo está —
        falso ROJO sobre marcado legítimo."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="Sal & pimienta, a tu gusto")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]

        pintado_por_la_via_canonica = _campos_con_widget_pintado_y_ayuda_no_canonica(
            campos,
            f'<input type="text" name="{campo.html_name}">'
            f"<p>{escape(campo.help_text)}</p>",
        )
        self.assertEqual(
            pintado_por_la_via_canonica, [],
            "un help_text con un carácter especial (&), pintado ESCAPADO — la vía canónica de "
            "verdad, letra a letra — se marcó como NO canónico: la comparación dejó de "
            "escapar el help_text antes de buscarlo en el HTML",
        )

    def test_mutacion_un_name_con_comillas_simples_se_pone_rojo(self):
        """H26 (revisión 13 de la 059, BLOQUEANTE) — la versión anterior de
        `_campo_esta_pintado_por_su_widget` era `f'name="{campo.html_name}"' in contenido`: fija
        las comillas DOBLES. Medido en vivo sobre `/perfiles/`: el mismo campo pintado a mano con
        `name='…'` (HTML igual de válido, la pantalla se ve igual) dejaba la ayuda visible, sin
        `id` y sin ningún `aria-describedby`, con la suite entera en verde. Comillas simples, sin
        comillas y dobles tienen que detectar el mismo widget pintado."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="ayuda con una palabra clave")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]

        for apertura, cierre in (('"', '"'), ("'", "'"), ("", "")):
            with self.subTest(comillas=repr(apertura)):
                no_canonico = _campos_con_widget_pintado_y_ayuda_no_canonica(
                    campos,
                    f"<input type={apertura}text{cierre} "
                    f"name={apertura}{campo.html_name}{cierre}>"
                    "<p>ayuda con una <strong>palabra</strong> clave</p>",
                )
                self.assertEqual(
                    [c.name for _, c in no_canonico], ["campo"],
                    f"un widget pintado con name={apertura}...{cierre} no se detectó como "
                    f"pintado: el trinquete fija un tipo de comilla",
                )

    def test_mutacion_un_name_sin_comillas_con_autocierre_pegado_se_pone_rojo(self):
        """H32/O44 (revisión 14 de la 059, MENOR; permanente desde la revisión 15) — el patrón
        original no reconocía `name=x/>`: sin comillas Y con la barra de autocierre pegada al
        valor, sin espacio delante. La vuelta 18 amplió el delimitador de cierre de
        `["\\'\\s>]` a `["\\'\\s/>]` y lo midió en una sonda de usar y tirar
        (`.runtime/v18/probe-*`) sin dejar test permanente — exactamente el enunciado de H30,
        repetido sobre este arreglo (H32, revisión 15): revertir el delimitador deja las 926 en
        verde. Este test lo fija: un `<input name=campo/>` sin comillas y sin espacio antes de la
        `/` tiene que seguir detectándose como pintado."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="ayuda con una palabra clave")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]

        no_canonico = _campos_con_widget_pintado_y_ayuda_no_canonica(
            campos,
            f"<input type=text name={campo.html_name}/>"
            "<p>ayuda con una <strong>palabra</strong> clave</p>",
        )
        self.assertEqual(
            [c.name for _, c in no_canonico], ["campo"],
            "un widget pintado con name=x/> (sin comillas, sin espacio antes de la barra de "
            "autocierre) no se detectó como pintado: el delimitador de "
            "`_NOMBRE_DE_WIDGET_EN_HTML_RE` volvió a excluir `/`",
        )

    def test_mutacion_un_name_con_espacios_alrededor_del_igual_se_pone_rojo(self):
        """H37-B (vuelta 20 de la 059, BLOQUEANTE) — H26 cerró las comillas (`name='…'`) y O44
        cerró la barra de autocierre pegada (`name=x/>`), pero ninguna de las dos cerró el
        ESPACIO alrededor del `=` (`name = "x"`, HTML igualmente válido: el navegador lo
        interpreta exactamente igual que `name="x"`). Medido por el revisor (Revisión 16, D3):
        revertir `name\\s*=\\s*` a `name=` deja los 205 tests de `kcalibra` en verde."""
        class _FormularioDePrueba(forms.Form):
            campo = forms.CharField(help_text="ayuda con una palabra clave")

        campo = _FormularioDePrueba()["campo"]
        campos = [("_FormularioDePrueba", campo)]

        no_canonico = _campos_con_widget_pintado_y_ayuda_no_canonica(
            campos,
            f'<input type="text" name = "{campo.html_name}">'
            "<p>ayuda con una <strong>palabra</strong> clave</p>",
        )
        self.assertEqual(
            [c.name for _, c in no_canonico], ["campo"],
            'un widget pintado con espacios alrededor del `=` (name = "x") no se detectó como '
            "pintado: `_NOMBRE_DE_WIDGET_EN_HTML_RE` volvió a exigir `name=` pegado, sin espacio",
        )

    def test_mutacion_un_widget_compuesto_pintado_se_pone_rojo(self):
        """H26 (revisión 13 de la 059, BLOQUEANTE) — la versión anterior también daba por hecho
        que TODO widget con `use_fieldset=True` escribe `name="<html_name>"`. Django tiene CUATRO
        familias con `use_fieldset=True` (las únicas para las que este trinquete existe, porque
        son las únicas a las que Django no les pone `aria-describedby` automático):
        `CheckboxSelectMultiple`/`RadioSelect` sí escriben `name="<html_name>"` (una copia por
        opción) y ya estaban cubiertas; `SplitDateTimeField`/`SelectDateWidget` son COMPUESTOS —
        cada subwidget escribe el suyo (`x_0`/`x_1`, `x_day`/`x_month`/`x_year`) y NUNCA
        `name="<html_name>"` — y sin recorrer el árbol de widgets eran invisibles para las TRES
        flechas de R6 a la vez, con o sin `help_text` canónico."""
        class _FormularioConFechas(forms.Form):
            cuando = forms.SplitDateTimeField(help_text="cuándo pasó")
            fecha = forms.DateField(widget=forms.SelectDateWidget, help_text="qué día")

        formulario = _FormularioConFechas()
        for nombre_campo, html in (
            ("cuando", '<input type="text" name="cuando_0"><input type="text" name="cuando_1">'),
            ("fecha", '<select name="fecha_month"></select><select name="fecha_day">'
                      '</select><select name="fecha_year"></select>'),
        ):
            with self.subTest(campo=nombre_campo):
                campo = formulario[nombre_campo]
                no_canonico = _campos_con_widget_pintado_y_ayuda_no_canonica(
                    [("_FormularioConFechas", campo)],
                    html + "<p>ayuda pintada de otra forma</p>",
                )
                self.assertEqual(
                    [c.name for _, c in no_canonico], [nombre_campo],
                    f"un {campo.field.widget.__class__.__name__} pintado por Django, con su "
                    f"ayuda no canónica, no se detectó como pintado — el predicado sigue "
                    f"asumiendo que todo widget escribe name=\"<html_name>\" a secas",
                )

    def test_mutacion_un_widget_compuesto_anidado_pintado_se_pone_rojo(self):
        """H29 (revisión 14 de la 059, MEDIO) — el gemelo de H26 un piso más abajo: un
        `MultiWidget` cuyos SUBWIDGETS sean a su vez compuestos (un rango "entre estas dos
        fechas-hora", dos `SplitDateTimeWidget`) escribe `entre_0_0`/`entre_0_1`/`entre_1_0`/
        `entre_1_1` — CUATRO `name=`, ninguno igual a lo que `_nombres_de_name_que_el_widget_escribe`
        calculaba antes de H29 (`entre_0`/`entre_1`, un solo nivel de profundidad). Medido en vivo
        (`str(campo)`, sin plantilla ni HTML a mano): Django pinta exactamente los cuatro `name=`
        de abajo."""
        class _WidgetDeRangoDeFechaHora(forms.MultiWidget):
            def __init__(self, attrs=None):
                super().__init__([forms.SplitDateTimeWidget(), forms.SplitDateTimeWidget()], attrs)

            def decompress(self, value):
                return [None, None]

        class _FormularioConRango(forms.Form):
            entre = forms.CharField(
                widget=_WidgetDeRangoDeFechaHora(), help_text="entre estas dos fechas",
            )

        campo = _FormularioConRango()["entre"]
        html = (
            '<input type="text" name="entre_0_0"><input type="text" name="entre_0_1">'
            '<input type="text" name="entre_1_0"><input type="text" name="entre_1_1">'
        )
        no_canonico = _campos_con_widget_pintado_y_ayuda_no_canonica(
            [("_FormularioConRango", campo)], html + "<p>ayuda pintada de otra forma</p>",
        )
        self.assertEqual(
            [c.name for _, c in no_canonico], ["entre"],
            "un MultiWidget con subwidgets COMPUESTOS, pintado por Django, con su ayuda no "
            "canónica, no se detectó como pintado — el predicado sigue bajando un solo nivel "
            "de subwidgets",
        )


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

        # O9 (revisión 4) — las DOS mitades de `rotos` (disparadores y opciones de menú) y
        # `sin_nombre_accesible` se afirman aquí, JUNTAS, en una sola vez, ya con las dos vueltas
        # (disparador + opciones) terminadas: antes, el primer `assertEqual(rotos, [])` corría
        # ANTES de la vuelta de opciones, así que una pantalla con el disparador roto Y las
        # opciones rotas sólo nombraba el disparador — arreglar y volver a correr para ver el
        # resto. No se pierde ningún rojo (el mismo defecto seguía cayendo en la siguiente
        # corrida); ahora un solo rojo lo cuenta todo de golpe.
        self.assertEqual(
            rotos, [], f"controles/opciones redondos que no llevan a ningún sitio: {rotos}"
        )
        self.assertEqual(
            sin_nombre_accesible, [],
            f"controles redondos sin nombre accesible: {sin_nombre_accesible}",
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

    def test_mutacion_el_role_de_menu_se_normaliza_antes_de_comparar(self):
        """H37-E/F (vuelta 20 de la 059, BLOQUEANTE) — `_es_boton_o_menu_redondo` tiene un
        docstring de once líneas explicando que un token accidental no puede ser PUERTA DE
        ENTRADA al barrido de R7… y sus dos hermanas, `_es_menu_redondo_abierto` e
        `_es_item_de_menu`, deciden la pertenencia al barrido con una comparación EXACTA de
        cadena —sin `.strip().lower()`— que nadie ejercitaba. Medido por el revisor
        (Revisión 16, D3): revertir cualquiera de las dos normalizaciones deja los 205 tests
        de `kcalibra` en verde. Con `role="Menu"` (mayúscula) o `role=" menu "` (espacio
        suelto) —los dos HTML igual de válidos, el navegador los trata idénticos— el menú
        entero desaparecía del barrido de R7 en silencio."""
        for role_de_menu in ("Menu", " menu ", "MENU", "menu"):
            with self.subTest(role=repr(role_de_menu)):
                self.assertTrue(
                    _es_menu_redondo_abierto("div", {"role": role_de_menu}),
                    f"role={role_de_menu!r} no se reconoció como el menú abierto: la "
                    f"normalización `.strip().lower()` de `_es_menu_redondo_abierto` se ha "
                    f"perdido",
                )
        for role_de_item in ("MenuItem", " menuitem ", "MENUITEM", "menuitem"):
            with self.subTest(role=repr(role_de_item)):
                self.assertTrue(
                    _es_item_de_menu("a", {"role": role_de_item}),
                    f"role={role_de_item!r} no se reconoció como opción de menú: la "
                    f"normalización `.strip().lower()` de `_es_item_de_menu` se ha perdido",
                )

    def test_mutacion_un_data_id_no_se_confunde_con_el_id_real_del_destino(self):
        """H37-G (vuelta 20 de la 059, BLOQUEANTE) — H26 sin terminar, la mitad que quedaba: la
        lectura del destino de un ancla interna tiene que preguntar por el ATRIBUTO `id`
        parseado (`elementos_con_texto(...).get("id") == destino`), no por una SUBCADENA
        fija (`f'id="{destino}"' in contenido`) — un `data-id="destino"` (atributo legítimo y
        distinto, no el `id` del elemento) CONTIENE esa subcadena entera. Medido por el
        revisor (Revisión 16, D3): revertir a la lectura por subcadena deja los 205 tests de
        `kcalibra` en verde — falso VERDE sobre un botón que en realidad no lleva a ningún
        sitio."""
        html_con_data_id_ajeno = (
            '<a href="#destino" aria-label="x" class="pointer-events-auto flex h-14 w-14 '
            'items-center justify-center rounded-pastilla bg-tinta text-white shadow-lg '
            'active:scale-95">x</a>'
            '<div data-id="destino">esto NO es el id del destino, es otro atributo</div>'
        )
        encontrados = elementos_con_texto(html_con_data_id_ajeno, _es_boton_o_menu_redondo)
        self.assertEqual(
            len(encontrados), 1,
            "la firma no reconoció el marcado REAL de boton_redondo: el mutante no probaría nada",
        )
        attrs, _texto_visible = encontrados[0]
        self.assertEqual(
            _destino_de_ancla_interna_no_existe(html_con_data_id_ajeno, attrs),
            "destino",
            'un `data-id="destino"` (no el `id` real de ningún elemento) hizo pasar el ancla '
            "«#destino» como existente: la lectura del destino volvió a ser una subcadena, no "
            "el atributo `id` parseado",
        )
        # Y el control: con un `id="destino"` DE VERDAD en la página, el ancla sí existe.
        html_con_id_real = html_con_data_id_ajeno + '<div id="destino"></div>'
        self.assertEqual(
            _destino_de_ancla_interna_no_existe(html_con_id_real, attrs), "",
            "con un id=\"destino\" real en la página, el ancla debía darse por existente",
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
