r"""
Tests de la unidad 053 (las-pantallas-del-dia-a-dia.md): R1, R2, R4, R5, R6, R7, R8 de su
especificación (revisión 2). R3 ("no romper nada") no tiene test propio aquí: es el resto de
la suite (los 800 de antes) siguiendo en verde. R9 y R10 se prueban en su propio sitio:
R9 (vocabulario) en `test_las_pildoras_de_la_comida_llevan_su_nombre_junto_al_color` de aquí
mismo (los nombres esperados ya son "Carbohidratos"/"Grasa"); R10 (las dos zonas del bug 027)
en `hogares/tests_personas_de_la_casa.py`, que es donde vivían antes de la unidad.

Las diez pantallas del día a día pasan a verse como el resto del marco (unidad 050): título
grande arriba (R1), botón redondo de acción rápida cuando hay una acción principal (R2), sin
paleta vieja (R4), macros con su nombre siempre escrito (R5), cifras de ancho fijo (R6),
piezas compartidas viviendo una sola vez en `templates/_ui.html` (R7) y, en Progreso, un
botón redondo que ofrece las dos acciones que el mapa aprobado nombra (R8).

Escritos ANTES de tocar las plantillas (tests primero, en rojo, igual que el resto de la
suite) — hoy fallarían contra las pantallas planas de antes de esta unidad.

Una subcadena no prueba nada sobre un CSS o un HTML que escribe una plantilla compartida
(docs/conocimiento/tailwind-4-sin-node.md, la 10ª cara de tests-que-no-fallan-cuando-deben.md):
cada assert de aquí se mutó a mano contra la plantilla o la pieza que vigila y se comprobó que
cae — la mutación y su salida en rojo están pegadas en hallazgos.md, no descritas en prosa.
"""

import re
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.template import base as _django_template_base
from django.test import SimpleTestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from kcalibra.ayuda_de_alcanzabilidad import (
    SIN_CIERRE,
    atributos,
    cadena_unica,
    el_estado_es_compartido,
    elementos_con_texto,
    nada_lo_tapa,
)
from cierres.models import CierreDeDia
from hogares.models import Persona

BASE_DIR = Path(settings.BASE_DIR)


def _texto(ruta):
    return ruta.read_text(encoding="utf-8")


# Las nueve plantillas de pantalla de esta unidad (todo `ficheros:` salvo `_ui.html`, el CSS
# compilado y este mismo fichero de tests) — se usan tanto para el barrido de R4 (ninguna
# conserva la paleta vieja) como para el barrido de R7 (qué piezas incluye cada una).
PLANTILLAS = [
    BASE_DIR / "paginas" / "templates" / "paginas" / "inicio.html",
    BASE_DIR / "planes" / "templates" / "planes" / "apuntar.html",
    BASE_DIR / "entrenos" / "templates" / "entrenos" / "ver.html",
    BASE_DIR / "entrenos" / "templates" / "entrenos" / "corregir.html",
    BASE_DIR / "perfiles" / "templates" / "perfiles" / "peso.html",
    BASE_DIR / "progreso" / "templates" / "progreso" / "ver.html",
    BASE_DIR / "progreso" / "templates" / "progreso" / "_grafica.html",
    BASE_DIR / "cierres" / "templates" / "cierres" / "cerrar.html",
    BASE_DIR / "cierres" / "templates" / "cierres" / "_pregunta_pendiente.html",
]
RUTA_UI = BASE_DIR / "templates" / "_ui.html"

# Las piezas que `_ui.html` porta de verdad (R7), derivadas de sus propios
# `{% partialdef %}` — no de una lista escrita a mano (E, revisión 8ª vuelta: "si la 054 añade
# una pieza nueva a `_ui.html`, esa pieza no está en `PIEZAS_PORTADAS` ni tiene fila en
# `_FIRMAS_DE_CLASE_POR_PIEZA`, así que ni se cuenta que viva una sola vez, ni se detecta si
# alguien la copia"). Se excluyen los partials `_privados` (`_pildora_macro_interna`,
# `_barra_macro_interna`): son implementación interna de `pildora_macro`/`barra_macro`, ninguna
# pantalla los incluye directamente, y ya tienen su propia red en R5/R6
# (`test_las_piezas_de_macro_no_tienen_un_camino_sin_nombre`,
# `test_las_piezas_compartidas_no_tienen_un_camino_sin_cifra`).
_NOMBRE_DE_PARTIALDEF_RE = re.compile(r"\{%\s*partialdef\s+([\w-]+)\b(?:\s+inline)?\s*%\}")


def _piezas_portadas_de_ui_html():
    vistas = []
    for nombre in _NOMBRE_DE_PARTIALDEF_RE.findall(_texto(RUTA_UI)):
        if not nombre.startswith("_") and nombre not in vistas:
            vistas.append(nombre)
    return vistas


PIEZAS_PORTADAS = _piezas_portadas_de_ui_html()
# `barra_macro` se porta (lo pide el paso 1 del "Cómo") pero NINGUNA de las diez pantallas de
# esta unidad tiene un dato de "gramos + porcentaje" que mostrar con ella — mismo caso que los
# tokens de macro/racha en la 050 ("nace con la primera pantalla que la use"): existe, una sola
# vez, lista para cuando haga falta, pero no está en el barrido de "piezas usadas" de abajo.
#
# `PLANTILLAS` (arriba) SIGUE a mano, y es a propósito, no deuda (E, revisión 8ª vuelta lo
# preguntaba): es la lista blanca del ALCANCE de esta unidad — coincide byte a byte con
# `ficheros:` de la especificación, y derivarla de un glob del árbol tragaría cualquier
# plantilla nueva de la 054/055 sin que esta unidad lo decidiera (la propia especificación,
# "Fuera de alcance", prohíbe tocar nada que no sea esto).
#
# Unidad 059 — `_rutas_de_las_siete_pantallas` (que vivía aquí) y el barrido de
# `test_ningun_numero_de_dato_escrito_en_linea_se_queda_sin_cifra` que la usaba se SACARON de
# este fichero: la red permanente de `kcalibra/tests_pantallas_del_proyecto.py` cubre ya ese
# mismo barrido (R6 de esta unidad, R5 de la 059) sobre las QUINCE pantallas reales de hoy, con
# un vocabulario más ancho (derivado de las `choices` de `despensa`/`recetas`, no solo
# `kcal|kg|g|min|%`) y rutas que salen de un recorrido real de la app, no de una lista de siete
# escrita a mano — mantenerlo aquí también habría sido la misma duplicación que esta unidad
# existe para cerrar. Los tres tests de `id` concretos y el de las piezas compartidas, más
# abajo, se quedan: no barren "todo", prueban un caso puntual cada uno.
#
# FR-I (revisión, 9ª vuelta): `PIEZAS_USADAS_EN_LAS_PANTALLAS` derivaba de `PIEZAS_PORTADAS` —
# TODA pieza que _ui.html porte hoy, salvo `barra_macro`. Medido: una pieza nueva añadida a
# `_ui.html` para la 054/055 (que también tocan ese fichero, la especificación lo dice) y sin
# usar por ninguna de las diez pantallas de ESTA unidad pone la 053 en ROJO aunque esta unidad
# no cambie una coma. Es el mismo tipo de fuga que ya justificaba dejar `PLANTILLAS` a mano:
# esto es alcance, no un catálogo que tenga que crecer solo. `PIEZAS_QUE_ESTA_UNIDAD_USA` es
# la foto de HOY, escrita como literal (no derivada de `_ui.html`, a propósito: si se derivara
# de nuevo con el mismo criterio de "todo lo que exista menos `barra_macro`" el hueco
# reaparecería en cuanto la 054/055 añadieran su pieza) — sigue vigilando que ESTAS doce piezas
# no se queden huérfanas (si `entrenos/ver.html` deja de incluir `distintivo`, esto se entera),
# y sencillamente no pregunta por ninguna pieza que esta unidad no conocía al escribirse.
# `PIEZAS_PORTADAS` (arriba) sigue derivándose del fichero para las otras dos preguntas de R7
# ("definida una sola vez", "no copiada") — ésas SÍ tienen que crecer con cada pieza nueva,
# porque la protección contra un duplicado o una copia de una pieza que todavía no existe no
# puede vivir en una lista de antes de que exista.
PIEZAS_QUE_ESTA_UNIDAD_USA = frozenset({
    "tarjeta_abre", "tarjeta_cierra", "titulo_seccion", "numero_grande", "pildora_macro",
    "anillo_abre", "anillo_cierra", "boton", "aviso", "distintivo", "boton_redondo",
    "boton_redondo_menu",
})


# Borra `{% … %}` Y `{# … #}` de Django del texto fuente de una plantilla: lo que el navegador
# ve ahí es texto plano (una vez Django resuelve la etiqueta o descarta el comentario) — usada
# por R7 (la detección de copia, más abajo) para leer un `class="…"` del FICHERO fuente sin que
# la sintaxis de Django rompa el atributo. FR-C (revisión, 8ª vuelta): antes sólo borraba
# `{{ … }}`/`{% … %}`; un `class="…"` escrito DENTRO de un comentario (`{# usa el include #}`)
# sobrevivía y disparaba el detector de copia de R7 sobre texto que el navegador nunca pinta.
#
# `{{ … }}` (una VARIABLE) YA NO se borra a ciegas aquí (vuelta 12b, C2): borrarla asumía que
# una variable en medio de un `class="…"` siempre renderiza a "nada" — una pieza copiada con
# UN TOKEN DE SU FIRMA sustituido por una variable (`class="rounded-tarjeta {{ c }} p-5"`, con
# `c='bg-superficie'` en el `{% with %}` que la envuelve) perdía ese token al borrarlo y la
# copia colaba en VERDE (medido, hallazgos.md, vuelta 12b). El fichero fuente no puede saber a
# qué renderiza esa variable sin ejecutar Django — y esta casa falla CERRADO ante esa duda, no
# a favor: `_copia_el_marcado_de_la_pieza` (abajo) cuenta cada `{{ … }}` que quede DENTRO de un
# `class="…"` como un COMODÍN que podría ser cualquier token que le falte a la firma.
#
# (Vuelta 11: R6 ya NO usa esto. La exención de "prosa fija" comparaba antes VALORES contra el
# texto FUENTE de las diez plantillas — y por tanto dependía de lo que cualquiera de los diez
# ficheros escribiera, vivo o muerto (`{% if False %}`, un `{% partialdef %}` sin incluir). Ver
# `_con_procedencia_marcada` más abajo: ahora la exención sale de cómo se RENDERIZÓ cada
# ocurrencia, no de qué dice el fichero.)
_ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE = re.compile(r"\{%.*?%\}|\{#.*?#\}", re.S)
_VARIABLE_DE_DJANGO_RE = re.compile(r"\{\{.*?\}\}", re.S)
# Vuelta 13 — I3 (falso verde MEDIDO, dejado como DEUDA): un `{% … %}` dentro de un `class="…"`
# también puede suplir un token de la firma de una pieza (`{% firstof %}`, `{% cycle %}`, un tag
# propio…), igual que un `{{ … }}`, y al borrarlo a secas esa copia escapa. El padre intentó
# cerrarlo contando cada `{% … %}` como comodín y MIDIÓ que no vale: las pantallas reales usan
# `{% if %}` dentro de sus `class`, así que la suite base se ponía en ROJO (`failures=1`) y con
# ella todas las mediciones que debían salir verdes. Cerrarlo de verdad exige distinguir qué
# `{% … %}` IMPRIME, y eso es otra lista de literales — justo lo que esta unidad lleva doce
# vueltas quitando. La 11ª revisión lo dejó explícitamente fuera de lo que hace falta para
# firmar. Se pasa por escrito a la 054/055.


def _indices_del_h1_de_titulo(contenido):
    """El `<h1>` que `{% block titulo_grande %}` pinta dentro de `<header>` (`base.html`), o
    `None` si esta pantalla no lo llena.

    Hueco 1 (revisión, 3ª vuelta): comparar la posición del título contra `<main>` no basta —
    `base.html:7` pinta `<title>{% block titulo %}…{% endblock %} · KCalibra</title>` DENTRO
    de `<head>`, que también va antes de `<main>` trivialmente, y cuatro de las siete
    pantallas llenan `{% block titulo %}` con el MISMO texto que `{% block titulo_grande %}`:
    la primera aparición del texto buscado era la del `<head>`, así que el assert se cumplía
    aunque `titulo_grande` estuviera vacío del todo (medido: vaciándolo en
    `entrenos/corregir.html`, la pantalla se queda sin título grande y `Ran 834 tests — OK`;
    hallazgos.md). El arreglo mira DENTRO del `<h1>`, el mismo patrón que
    `_indices_del_h1_de_titulo`/`_fragmento_esta_dentro_del_h1_de_titulo` de
    `hogares/tests_personas_de_la_casa.py` (R10 de esta misma unidad)."""
    inicio_header = contenido.index("<header")
    fin_header = contenido.index("</header>", inicio_header) + len("</header>")
    try:
        inicio_h1 = contenido.index("<h1", inicio_header, fin_header)
    except ValueError:
        return None
    fin_h1 = contenido.index("</h1>", inicio_h1, fin_header) + len("</h1>")
    return inicio_h1, fin_h1


class _ConAlejandroYSusDatos(PruebaConRegistroAbierto):
    """Alejandro, con sesión abierta, un plan de hoy con una comida, un entreno de hoy y dos
    pesadas — la fixture que pide la fila 1 de "Cómo lo pruebas tú" de la especificación
    ("fixture con hogar, plan, entreno y pesadas"), montada por HTTP contra las URLs reales
    (nunca `Model.objects.create(...)` a mano cuando lo que hace falta es que la petición
    LLEGUE a la pantalla — docs/conocimiento/tests-que-no-fallan-cuando-deben.md)."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        hoy = timezone.localdate().isoformat()

        self.client.post(
            f"/planes/{self.alejandro.id}/apuntar/",
            {
                "nombre": "Tortilla de claras",
                "momento_del_dia": "desayuno",
                "calorias": "500",
                "proteina_g": "40",
                "grasa_g": "15",
                "carbos_g": "35",
            },
        )
        respuesta_entreno = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {
                "fecha": hoy,
                "deporte": "correr",
                "intensidad": "media",
                "minutos": "30",
                "calorias": "300",
            },
        )
        from entrenos.models import Entreno

        self.entreno = Entreno.objects.get(persona=self.alejandro)
        assert respuesta_entreno.status_code == 200  # control: se guardó de verdad

        self.client.post(
            f"/perfiles/{self.alejandro.id}/peso/apuntar/",
            {"fecha": hoy, "peso_kg": "80", "grasa_pct": "", "cintura_cm": ""},
        )


# ------------------------------------------------------------------------------------------ #
# R1 — cada pantalla llena `{% block titulo_grande %}` con su propio título.
# ------------------------------------------------------------------------------------------ #


class R1_TituloGrandeTests(_ConAlejandroYSusDatos):
    """R1 — el título de cada pantalla sale DENTRO del `<h1>` que pinta
    `{% block titulo_grande %}` en `<header>` (`base.html`), no suelto en cualquier parte del
    contenido: si una pantalla dejara el título donde estaba antes (dentro de
    `{% block content %}`) el título seguiría "apareciendo en la página", pero no llenaría
    `{% block titulo_grande %}` — de ahí que el test mire el `<h1>` de la cabecera, no solo
    presencia. (Antes miraba la POSICIÓN del texto contra `<main>`, no el `<h1>`: el `<title>`
    de `<head>` también va antes de `<main>` y cuatro pantallas repiten el mismo texto ahí —
    Hueco 1, revisión 3ª vuelta, hallazgos.md.)"""

    def _titulo_esta_en_la_cabecera(self, ruta, titulo_esperado):
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 200, ruta)
        contenido = respuesta.content.decode()
        limites_h1 = _indices_del_h1_de_titulo(contenido)
        self.assertIsNotNone(
            limites_h1,
            f"{ruta} no tiene ningún <h1> dentro de <header>: ¿sigue llenando "
            "{% block titulo_grande %}?",
        )
        inicio_h1, fin_h1 = limites_h1
        self.assertIn(
            titulo_esperado, contenido[inicio_h1:fin_h1],
            f"'{titulo_esperado}' no está dentro del <h1> de la cabecera en {ruta}",
        )

    def test_portada_hola_nombre(self):
        self._titulo_esta_en_la_cabecera("/", "Hola, Alejandro")

    def test_apuntar_el_plan(self):
        self._titulo_esta_en_la_cabecera(
            f"/planes/{self.alejandro.id}/apuntar/", "Apuntar tu plan de hoy"
        )

    def test_entrenos(self):
        self._titulo_esta_en_la_cabecera("/entrenos/", "Tus entrenos")

    def test_corregir_entreno(self):
        self._titulo_esta_en_la_cabecera(
            f"/entrenos/{self.alejandro.id}/{self.entreno.id}/corregir/", "Corregir entreno"
        )

    def test_tu_peso(self):
        self._titulo_esta_en_la_cabecera("/perfiles/peso/", "Tu peso")

    def test_tu_progreso(self):
        self._titulo_esta_en_la_cabecera("/progreso/", "Tu progreso")

    def test_cerrar_un_dia(self):
        self._titulo_esta_en_la_cabecera(f"/cierres/{self.alejandro.id}/", "Cerrar un día")


# ------------------------------------------------------------------------------------------ #
# R2 — el botón redondo lleva AL FORMULARIO que ya vive en esa misma pantalla.
# ------------------------------------------------------------------------------------------ #


class R2_BotonRedondoTests(_ConAlejandroYSusDatos):
    """R2 — no basta con que exista un ancla con el texto del ancla apuntando a "algo": el
    elemento al que apunta tiene que EXISTIR en la misma página (un ancla a un id que no
    existe no da error, no hace nada — el hallazgo que ya advierte la tabla de verificación
    de la especificación)."""

    def _ancla_lleva_a_un_elemento_que_existe(self, ruta, etiqueta_boton, id_destino):
        """Hueco 5 + Hueco 7 (revisión, 4ª vuelta): la versión anterior comprobaba dos
        cadenas sueltas (`href="#id"`, `id="id"`) con comillas dobles FIJAS — `id='…'` (HTML
        idéntico para cualquier navegador) ponía esto en ROJO con la pantalla funcionando
        (medido: reescribiendo `boton_redondo` entero con comillas simples, `Ran 44 — FAILED
        (failures=4)`, hallazgos.md), Y las dos cadenas no se ataban entre sí: un `href` de
        SEÑUELO apuntando al mismo id que otro enlace cualquiera de la pantalla colaba en
        verde (medido con un segundo `<a href="#formulario-plan">` de adorno). Se lee el HTML
        de verdad con `elementos_con_texto` (ya importado): el `href` sale del PROPIO botón
        redondo (identificado por su `aria-label`, igual que
        `test_el_boton_redondo_se_puede_usar_de_verdad`), y sólo entonces se busca un
        elemento con ese id."""
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 200, ruta)
        contenido = respuesta.content.decode()

        coincide_boton = lambda e, a, etiqueta_boton=etiqueta_boton: (
            e == "a" and a.get("aria-label") == etiqueta_boton
        )
        botones = elementos_con_texto(contenido, coincide_boton)
        self.assertEqual(
            len(botones), 1, f"no hay un único botón redondo «{etiqueta_boton}» en {ruta}"
        )
        self.assertEqual(
            botones[0][0].get("href"), f"#{id_destino}",
            f"el botón redondo «{etiqueta_boton}» de {ruta} no apunta a #{id_destino}",
        )

        coincide_destino = lambda e, a, id_destino=id_destino: a.get("id") == id_destino
        self.assertTrue(
            elementos_con_texto(contenido, coincide_destino),
            f"el botón redondo «{etiqueta_boton}» de {ruta} apunta a #{id_destino}, pero no "
            "hay ningún elemento con ese id",
        )

    def test_apuntar_el_plan_lleva_al_formulario_de_apuntar_comida(self):
        self._ancla_lleva_a_un_elemento_que_existe(
            f"/planes/{self.alejandro.id}/apuntar/", "Apuntar comida", "formulario-plan"
        )

    def test_entrenos_lleva_al_formulario_de_apuntar_entreno(self):
        self._ancla_lleva_a_un_elemento_que_existe(
            "/entrenos/", "Apuntar un entreno", "formulario-entreno"
        )

    def test_tu_peso_lleva_al_formulario_de_apuntar_peso(self):
        self._ancla_lleva_a_un_elemento_que_existe(
            "/perfiles/peso/", "Apuntar una pesada", "formulario-peso"
        )

    def test_cerrar_un_dia_lleva_a_su_formulario(self):
        self._ancla_lleva_a_un_elemento_que_existe(
            f"/cierres/{self.alejandro.id}/", "Cerrar un día", "formulario-cierre"
        )

    def test_quien_solo_mira_no_ve_un_boton_que_el_servidor_le_rechazaria(self):
        """El criterio de fondo de R2 ("nunca ofrece un formulario que el servidor rechace")
        ya lo prueban `entrenos/tests.py`/`cierres/tests.py` con `puede_editar=False` de
        verdad contra la puerta de acceso; aquí se aísla la PLANTILLA (`entrenos/ver.html`):
        con `puede_editar=False` en el contexto, el bloque `accion_rapida` (el botón redondo,
        R2) tiene que quedar vacío, igual que ya queda vacío el formulario de apuntar.

        Se renderiza con `RequestFactory` (mismo patrón que
        `tests_marco.R7_SinPersonaNoRompeLaPaginaTests`) para tener un `user` autenticado de
        verdad en el contexto de `base.html`, sin pasar por el servidor: lo que se aísla aquí
        es la decisión de LA PLANTILLA, no la de la puerta de acceso."""
        from django.template import engines
        from django.test import RequestFactory
        from django.urls import resolve

        request = RequestFactory().get(f"/entrenos/{self.alejandro.id}/")
        request.user = self.alejandro.usuario
        request.resolver_match = resolve("/entrenos/")

        html = engines["django"].get_template("entrenos/ver.html").render(
            {
                "persona_objetivo": self.alejandro,
                "es_propio": False,
                "puede_editar": False,
                "form": None,
                "entrenos": [],
                "calorias_hoy": 0,
                "objetivo": None,
            },
            request,
        )
        self.assertNotIn("formulario-entreno", html)
        self.assertNotIn('aria-label="Apuntar un entreno"', html)

    def test_el_boton_redondo_se_puede_usar_de_verdad(self):
        """Hueco 2 (R2) de la revisión (2ª vuelta): `_ancla_lleva_a_un_elemento_que_existe` de
        arriba sólo mira que existan dos cadenas sueltas (`href="#id"`, `id="id"`) en la misma
        respuesta — con `_ui.html#boton_redondo` tapado (`class="hidden invisible opacity-0
        pointer-events-none …"`), los cuatro botones morían a la vez y ese test seguía en
        verde (medido, hallazgos.md). Mismo agujero, mismo arreglo que R8: se importa de
        `kcalibra.ayuda_de_alcanzabilidad` en vez de copiarse a mano — ver
        `_boton_redondo_es_alcanzable` más abajo, la pieza compartida entre R2 y R8."""
        casos = (
            (f"/planes/{self.alejandro.id}/apuntar/", "Apuntar comida"),
            ("/entrenos/", "Apuntar un entreno"),
            ("/perfiles/peso/", "Apuntar una pesada"),
            (f"/cierres/{self.alejandro.id}/", "Cerrar un día"),
        )
        for ruta, etiqueta in casos:
            with self.subTest(ruta=ruta):
                contenido = self.client.get(ruta).content.decode()
                coincide = lambda e, a, etiqueta=etiqueta: (
                    e == "a" and a.get("aria-label") == etiqueta
                )
                _boton_redondo_es_alcanzable(self, contenido, coincide, f"el botón redondo «{etiqueta}»")


# ------------------------------------------------------------------------------------------ #
# R4 — ninguna de las diez plantillas conserva utilidades de la paleta vieja.
# ------------------------------------------------------------------------------------------ #

_PALETA_VIEJA_RE = re.compile(r"\b(?:emerald|slate)-\d{2,3}\b")


class R4_SinPaletaViejaTests(SimpleTestCase):
    """R4 — ninguna de las nueve plantillas (ni `_ui.html`) usa `emerald-*`/`slate-*`. Se mira
    el FICHERO fuente (no una respuesta renderizada): una plantilla sin sesión no se
    renderiza en estos tests, y R4 es sobre el fichero, no sobre una ruta."""

    databases = set()

    def test_ninguna_plantilla_de_la_unidad_usa_emerald_ni_slate(self):
        con_paleta_vieja = {}
        for ruta in PLANTILLAS + [RUTA_UI]:
            hallazgos = _PALETA_VIEJA_RE.findall(_texto(ruta))
            if hallazgos:
                con_paleta_vieja[str(ruta.relative_to(BASE_DIR))] = hallazgos
        self.assertEqual(
            con_paleta_vieja,
            {},
            f"quedan clases de la paleta vieja: {con_paleta_vieja}",
        )


# ------------------------------------------------------------------------------------------ #
# R5 — toda píldora o barra de macro lleva el nombre del macro escrito.
# ------------------------------------------------------------------------------------------ #

# Cada píldora es un `<span class="inline-flex ...">...</span>` que _pildora_macro_interna
# genera entera: se aísla CADA una (no la página completa) para que el assert compruebe que
# EL NOMBRE Y LOS GRAMOS viven dentro del MISMO chip, no que las dos cosas aparecen en algún
# sitio de la respuesta (lo que pasaría también si el nombre apareciera suelto en otra parte
# de la pantalla, sin ninguna relación con el color).
#
# Hueco 9 (revisión, 5ª vuelta): la versión anterior era un `re.compile` con las comillas del
# `class` y el ORDEN de sus cuatro primeras clases escritos a mano
# (`class="inline-flex items-center gap-1\.5 rounded-pastilla…`) — ni las comillas ni el orden
# de las clases de un atributo Tailwind significan nada para un navegador, y
# `prettier-plugin-tailwindcss` reordena solo (medido, dos formas: comillas simples y orden de
# clases distinto, hallazgos.md). Se aísla la píldora por los TOKENS de su `class`
# (`rounded-pastilla` + una de las tres clases de fondo, que es lo que de verdad la identifica
# como píldora de macro y no como cualquier otro `<span>`), leyendo HTML de verdad con
# `elementos_con_texto` — mismo patrón que ya usa `_elemento_lleva_cifra` (R6) para el mismo
# problema.
_CLASES_DE_FONDO_DE_MACRO = {"bg-proteina-suave", "bg-carbos-suave", "bg-grasa-suave"}


def _es_pildora_de_macro(etiqueta, attrs):
    clases = (attrs.get("class") or "").split()
    return (
        etiqueta == "span"
        and "rounded-pastilla" in clases
        and _CLASES_DE_FONDO_DE_MACRO & set(clases)
    )


class R5_NombreDelMacroSiempreEscritoTests(_ConAlejandroYSusDatos):
    def test_las_pildoras_de_la_comida_llevan_su_nombre_junto_al_color(self):
        respuesta = self.client.get(f"/planes/{self.alejandro.id}/apuntar/")
        contenido = respuesta.content.decode()
        pildoras = elementos_con_texto(contenido, _es_pildora_de_macro)
        self.assertEqual(len(pildoras), 3, "se esperaban las 3 píldoras de la comida apuntada")

        # R9 — el vocabulario de la app, no el del prototipo viejo: "Carbohidratos" y "Grasa"
        # (`planes/forms.py`: "Carbohidratos (g)"/"Grasa (g)"), nunca "Carbos"/"Grasas".
        nombres_esperados = {"Proteína", "Grasa", "Carbohidratos"}
        nombres_vistos = set()
        for _, texto in pildoras:
            # Cada chip trae su nombre Y sus gramos con `.cifra` — ni el nombre solo (sin
            # dato) ni el dato solo (sin nombre, el fallo que prohíbe R5) pasa este assert.
            self.assertRegex(texto, r"\d+\s*g", texto)
            for nombre in nombres_esperados:
                if nombre in texto:
                    nombres_vistos.add(nombre)
        self.assertEqual(nombres_vistos, nombres_esperados)

    def test_las_piezas_de_macro_no_tienen_un_camino_sin_nombre(self):
        """Mutación fijada en el propio test: `_pildora_macro_interna`/`_barra_macro_interna`
        (`_ui.html`) siempre imprimen `{{ nombre_macro }}` antes de los gramos — se comprueba
        aquí, sobre las piezas en sí, no solo sobre una pantalla que las usa (para que un
        futuro uso nuevo de cualquiera de las dos no pueda perder el nombre sin que este test
        lo note).

        Hueco de muestreo hallado en el repaso R1-R10 pedido por la revisión de la 6ª vuelta
        (la misma familia que sus dos falsos verdes de R6/R7, aunque la revisión no llegó a
        auditar R5): este test, antes de esta vuelta, sólo miraba `_pildora_macro_interna` —
        pero R5 dice, literal, "Toda píldora **o barra** de macro lleva el nombre", y
        `_barra_macro_interna` es la otra mitad de esa frase, sin ninguna prueba propia
        (comprobado: `grep -rn "_barra_macro_interna"` fuera de este fichero no encuentra
        nada). Ninguna de las nueve pantallas usa hoy `barra_macro` (nace con la primera que
        la use, nota de `PIEZAS_PORTADAS` más arriba), así que el único sitio donde HOY se
        puede comprobar es la propia pieza — igual que ya hace R6 con
        `test_las_piezas_compartidas_no_tienen_un_camino_sin_cifra` para el mismo motivo.

        Hueco 11 (revisión, 5ª vuelta): el `re.search` de `{% partialdef … %}` llevaba los
        espacios alrededor del nombre escritos a mano — Django acepta
        `{%partialdef _pildora_macro_interna%}` igual que con espacios (esta misma unidad ya
        lo usó como CONTROL verde para R1 en la 3ª revisión, y `hogares/` lo trata con `\\s*`
        por el mismo motivo). Se tolera con `\\s*`, como `_BLOQUE_TITULO_GRANDE_DECLARADO_RE`
        en `hogares/tests_personas_de_la_casa.py`."""
        contenido = _texto(RUTA_UI)
        for pieza in ("_pildora_macro_interna", "_barra_macro_interna"):
            with self.subTest(pieza=pieza):
                interna = re.search(
                    rf"\{{%\s*partialdef\s+{pieza}\s*%\}}(.*?)\{{%\s*endpartialdef\s*%\}}",
                    contenido,
                    re.S,
                ).group(1)
                self.assertIn("{{ nombre_macro }}", interna)
                self.assertIn("{{ gramos }} g", interna)
                # El nombre no puede ir detrás de un `{% if %}` que lo esconda: tiene que
                # estar en la rama incondicional del partial (lo que exige R5: "SIEMPRE").
                self.assertNotIn("{% if", interna)


# ------------------------------------------------------------------------------------------ #
# R6 — todo número de dato lleva la clase `.cifra`.
# ------------------------------------------------------------------------------------------ #

# Para leer `class="…"` en el FICHERO fuente de una pieza (con `{{ }}`/`{% %}` de Django
# dentro, no HTML ya renderizado): sólo cierra en la comilla del MISMO tipo que abrió el
# atributo (`\1`), nunca en la primera comilla de cualquier tipo — a diferencia de `_CLASE_RE`
# (más abajo, pensada para HTML renderizado sin Django dentro), aguanta un argumento de filtro
# con la comilla contraria, como `{{ tam|default:'text-[44px]' }}` dentro de un `class="…"`.
_CLASE_DE_LA_PIEZA_RE = re.compile(r'''class=(["'])(?P<clases>.*?)\1''', re.S)


# Falso verde 1 (revisión, 6ª vuelta): R6 dice "TODO número de dato (kcal, peso, gramos,
# minutos) lleva `.cifra`", pero los tres tests de la clase de abajo fijan tres `id` escritos
# a mano y el de las piezas compartidas fija tres piezas — ninguno barre los números que las
# propias pantallas escriben en línea, que son la mayoría. Medido por el revisor:
# `planes/apuntar.html:65` se entregaba sin `.cifra` en un número que HTMX repinta
# (`hx-target="#plan-de-hoy"`) y los 835 tests seguían en verde. Se recorre el HTML
# RENDERIZADO buscando texto que combine un número con una de las unidades que R6 enumera, y
# se exige `.cifra` en el propio elemento o en ALGUNO de sus ancestros — se hereda de verdad
# (`font-variant-numeric`/`letter-spacing`, medido por el revisor en el CSS servido), así que
# un envoltorio con `.cifra` también vale.
#
# Falso verde 1, 2ª mitad (revisión, 7ª vuelta): esta versión SEGUÍA saliendo del texto PROPIO
# de cada elemento (`_flush()` cortaba en cada `<tag>`/`</tag>`) — si el valor y su unidad
# viven en elementos DISTINTOS (`perfiles/peso.html:152`:
# `<span class="cifra">{{ medicion.peso_kg }}</span> kg`, la unidad fuera del `<span>`), el
# barrido no ve un número de dato EN ABSOLUTO: no es que lo perdone, es que no lo encuentra.
# Medido por el revisor: quitando `cifra` a ese `<span>`, `Ran 45 — OK`. Y el `\\b` final
# detrás de `%` nunca podía casar (`%` no es carácter de palabra: `78%`, `78% de`, `78%)` no
# casaban nunca, sólo `5%de`, que no existe) — la rama `%` del regex no había cazado nada
# jamás. Los dos arreglos: (a) el barrido sale del VALOR, no de la unidad — se recorre el
# texto renderizado en el orden del documento SIN cortar en cada etiqueta, y cada coincidencia
# se ancla a la UNIÓN de las cadenas de ancestros de todos los trozos de texto que la
# componen (basta que UNO — el que envuelve el número, aunque la unidad quede fuera — lleve
# `.cifra`); (b) `%` se ancla con `(?!\\w)` en vez de `\\b`, igual que el resto de unidades
# (`(?!\\w)` y `\\b` coinciden para las que terminan en letra, y sólo `(?!\\w)` funciona
# también para `%`, que no es un carácter de palabra).
#
# H9 (revisión 4 de la 059) — frontera IZQUIERDA: el regex sólo anclaba por la derecha
# (`(?!\w)`), así que un dígito pegado a una letra a su IZQUIERDA (`...KMN3G`, la cola de un
# identificador alfanumérico al azar como el código de hogar) casaba igual («3G» ~ «3 gramos»,
# con `re.I`). `(?<!\w)` exige que el dígito no venga precedido de una letra/dígito/`_`, cerrando
# esa entrada sin tocar ningún número de dato real (medido: "4 raciones", "500 g", "2 lata",
# "1800 kcal", "72.5 kg" siguen casando igual con la frontera puesta).
#
# H10 (revisión 5 de la 059, BLOQUEANTE) — el `(?<!\w)` de H9 rompía TAMBIÉN dos números de
# dato REALES: `hallazgos` (más abajo) concatenaba los sub-trozos del documento SIN separador
# (`"".join(piezas)`), así que `<dt>Altura</dt><dd>...<span>{{ perfil.altura_cm }}</span> cm</dd>`
# llegaba al regex como `"Altura167 cm"` — la `a` de "Altura" quedaba PEGADA al `1`, y la
# frontera izquierda mataba una coincidencia real (medido: `perfiles/ver.html:98` y `:101`,
# con las 893 en VERDE). El arreglo no es del regex: es del PEGADO — refinado en H11 (revisión 6
# de la 059) para que sólo separe un salto de elemento de BLOQUE, no cualquier `handle_data`
# distinto. Ver `_SEPARADOR_ENTRE_TROZOS`/`_ETIQUETAS_INLINE`/`_piezas_por_procedencia`/
# `hallazgos`, abajo.
_NUMERO_CON_UNIDAD_RE = re.compile(r"(?<!\w)\d[\d.,]*\s*(?:kcal|kg|g|min|%)(?!\w)", re.I)

# Vuelta 12 — la 10ª revisión (BLOQUEANTE) midió que la procedencia "por construcción" de la
# vuelta 11 sólo cubría UNO de los caminos: parcheaba `render_value_in_context`
# (`django.template.base`), pero esa función se IMPORTA POR NOMBRE en
# `django/template/defaulttags.py` (`CycleNode`/`FirstOfNode`) y en
# `django/templatetags/i18n.py` (`TranslateNode`/`BlockTranslateNode`) — el parche no les llega
# —, y `{% now %}`/`{% widthratio %}`/todo `{% simple_tag %}` no pasan NUNCA por esa función:
# la devuelven directamente. Ocho caminos ordinarios se colaban como "prosa fija" (el barrido
# hace `if not de_variable: continue`, y lo que el parche no toca se exime en silencio):
# FALLABA HACIA VERDE — la afirmación "por construcción" del comentario anterior era falsa.
#
# El arreglo cambia el PUNTO DE ENGANCHE, no la lista de tags a cubrir: deja de perseguir
# funciones/tags y mira el ÁRBOL. `Node.render_annotated` (`django/template/base.py`) es el
# ÚNICO sitio por el que Django hace pasar CUALQUIER nodo cuando lo renderiza dentro de un
# `NodeList` (`NodeList.render`: `"".join(node.render_annotated(context) for node in self)`,
# verificado leyendo el fuente instalado) — y `TextNode` es el ÚNICO tipo de nodo que
# SOBRESCRIBE `render_annotated` con su propia versión (la clase base sólo la define para
# capturar excepciones; `TextNode.render_annotated` se limita a `return self.s`). Parcheando
# `Node.render_annotated` en la clase BASE, la sobrescritura de `TextNode` queda intacta —
# Python resuelve el método por MRO y encuentra el suyo primero, nunca el parche—, y el parche
# SÍ llega a todos los demás: `VariableNode`, `CycleNode`, `FirstOfNode`, `NowNode`,
# `WidthRatioNode`, `SimpleNode` (TODO `{% simple_tag %}`, con nombre o sin nombre, exista hoy
# o lo escriba una pantalla futura), `TranslateNode`, `BlockTranslateNode` — sin enumerar
# ninguno por nombre. O el texto lo escribió una persona en el fichero (`TextNode`), o es
# dinámico: no hay tercera opción, y la clasificación sale del AST de Django, no de una lista.
#
# Falta un hueco: `IfNode`/`ForNode`/`BlockNode`/`IncludeNode`/`DefinePartialNode` (`{% partial
# … inline %}`) TAMBIÉN son "no-`TextNode`", pero no imprimen nada por sí mismos — sólo deciden
# QUÉ `NodeList` renderizar y devuelven ese resultado tal cual (verificado leyendo cada uno en
# `django/template/{defaulttags,loader_tags}.py` y
# `template_partials/templatetags/partials.py`). Envolver TAMBIÉN su salida marcaría entero
# como "de variable" cualquier prosa fija que viva dentro de un `{% if %}`/`{% for %}` — el
# defecto contrario: falsos ROJOS masivos sobre marcado normal, que habrían roto las 41
# mediciones de la vuelta 11.
#
# La vuelta 12 distinguía esto con una segunda marca en `NodeList.render`, preguntando "¿este
# nodo DELEGÓ en una NodeList durante su render()?". Esa pregunta es falsa por los dos lados
# (11ª revisión, BLOQUEANTE, medido contra el fuente instalado de Django 5.2.17): `ForNode` NO
# pasa por `NodeList.render` — itera `self.nodelist_loop` llamando a `node.render_annotated` a
# mano (`django/template/defaulttags.py`) —, así que "delegó" salía `False` para cualquier
# `{% for %}` y su salida entera se envolvía como "de dato": falso ROJO sobre prosa fija
# corriente dentro de un bucle. Y un nodo que SÍ delega en una `NodeList` y ADEMÁS construye su
# propia salida a partir de eso (`SimpleBlockNode.get_resolved_arguments` llama a
# `self.nodelist.render(context)` para armar un argumento y LUEGO la función del usuario
# devuelve otra cosa; `FilterNode.render` hace `output = self.nodelist.render(context)` y
# LUEGO `self.filter_expr.resolve(context)`) marcaba "delegó" en `True` y quedaba SIN envolver:
# falso VERDE, y bloqueante — la página pinta el número sin `.cifra` y el barrido lo exime como
# prosa fija. "¿Delegó?" mide un hecho que no implica lo que se le hacía decir.
#
# El arreglo deja de preguntar eso y pregunta "¿la salida de este nodo ES la de sus hijos?".
# Cada nodo acumula, durante su propio `render()`, lo que devolvieron sus hijos — y "hijos" es
# CUALQUIER llamada a `render_annotated` que ocurra mientras ese `render()` está en marcha, la
# reciba `NodeList.render` o, como `ForNode`, un bucle a mano: todas pasan por el mismo parche
# de abajo, incluida la de `TextNode` (con un segundo parche que sólo ACUMULA su valor en el
# padre, nunca lo envuelve — sigue siendo la hoja de verdad). Al terminar, un nodo envuelve su
# propia salida SI Y SÓLO SI esa salida no es EXACTAMENTE la concatenación de lo acumulado. Un
# contenedor que se limita a devolver lo que sus hijos produjeron nunca se envuelve —
# `{% for %}` incluido, sin necesidad de nombrarlo — y un nodo que delega y LUEGO transforma o
# añade a lo delegado sí se envuelve, exista hoy el tag que lo hace o lo escriba una pantalla
# futura: la regla mira el ÁRBOL, no una lista de tags.
#
# `\x01`/`\x02` no son caracteres que HTML o esta app usen nunca en texto real (ni en un
# `{{ … }}` ya escapado): sobreviven intactos a `conditional_escape` y no rompen el parser de
# `html.parser` ni dentro de un atributo entre comillas.
_INICIO_VARIABLE = "\x01"
_FIN_VARIABLE = "\x02"
_MARCA_DE_PROCEDENCIA_RE = re.compile(f"[{_INICIO_VARIABLE}{_FIN_VARIABLE}]")

# H10 (revisión 5 de la 059) — el separador que `_NumerosDeDatoEnElTexto.hallazgos` mete ENTRE
# sub-trozos que vienen de un `handle_data` distinto (ver `_piezas_por_procedencia`/`hallazgos`,
# más abajo). Tiene que ser un espacio DE VERDAD, no un carácter de control como `\x00`: el
# regex reencuentra un número con su unidad a través de `\s*`, que absorbe un espacio de más
# sin problema, pero NO absorbe `\x00` — un separador que no fuera espacio rompería el propio
# caso que este mecanismo existe para arreglar (`<span>{{ v }}</span> kg`, la unidad en un
# elemento distinto del número).
_SEPARADOR_ENTRE_TROZOS = " "

# H11 (revisión 6 de la 059, MEDIO) — H10 separaba TODO límite entre `handle_data` distintos,
# sin mirar QUÉ etiqueta cruzaba ese límite. Eso también despega las mitades de una palabra que
# una etiqueta parte por dentro (`r<b>a</b>ciones`, `Mili<wbr>litros`, `k<span>g</span>`): cada
# apertura o cierre dispara un `handle_data` nuevo igual que un salto de bloque de verdad, y el
# espacio insertado deja "raciones" convertido en "r a ciones" — la unidad ya no casa con ningún
# vocabulario y la detección desaparece entera (falso VERDE, medido en la Revisión 6, cuatro
# formas: `k<span>g</span>`, `Mili<wbr>litros`, `kc<br>al`, `<b>Gra</b>mos`).
#
# La regla no es "pegar" ni "separar": es lo que VE EL LECTOR. El HTML colapsa los espacios de la
# fuente, así que dos trozos de texto sin espacio entre etiquetas INLINE se leen como UNA palabra
# (van PEGADOS); un salto de elemento de BLOQUE se lee como una separación real (va SEPARADO). Un
# `<span>`/`<b>`/`<wbr>`/etc. dentro de una palabra no cambia lo que un lector ve; un `</dt><dd>`
# sin espacio en la fuente, sí. `_ETIQUETAS_INLINE` es la lista CERRADA que no separa; cualquier
# otra etiqueta (las de bloque explícitas, `_ETIQUETAS_DE_BLOQUE` más abajo) SÍ separa.
#
# H12 (revisión 7 de la 059, MEDIO) — O13: esta misma sección afirmaba, hasta esta vuelta, que
# entre "todo lo desconocido pega" y "todo lo desconocido separa" la segunda "sólo arriesga un
# falso ROJO — deuda —, nunca un falso VERDE — silencio". MEDIDO Y FALSO, por los DOS lados
# (DIANA 1 de la Revisión 7, `.runtime/rev7/diana1.py`): una etiqueta desconocida que en
# realidad es de nivel de texto (`<mark>`, `<u>`, `<time>`…) cae del lado "separa" por defecto y
# PIERDE la detección ENTERA en cuanto parte la palabra de la unidad — 52 de 104 medidas, falso
# VERDE, no falso rojo —; y una desconocida que en realidad fuera de bloque, si el mecanismo
# pegara por defecto, también fallaría hacia falso VERDE (es H10). Ninguna de las dos ramas de
# esa disyuntiva falla hacia rojo: la lista es una ELECCIÓN con riesgo de falso VERDE por los dos
# lados, y por eso necesita un TRINQUETE (`TodaEtiquetaUsadaEnElArbolEstaClasificadaTests`,
# `kcalibra/tests_pantallas_del_proyecto.py`), no una frase que prometa una garantía que la red
# no da — la tercera vez en esta unidad que pasa (R10, O12, y ésta).
#
# El trinquete exige que TODA etiqueta que el árbol de plantillas usa de verdad esté nombrada en
# una de las dos listas de aquí abajo (H14, revisión 8 de la 059: eran tres, hasta que esa
# tercera familia demostró perder cobertura y se retiró — ver el comentario de
# `_ETIQUETAS_DE_BLOQUE`) — nunca "lo que no está en `_ETIQUETAS_INLINE` es de bloque por
# descarte": `_ETIQUETAS_DE_BLOQUE` es explícita, y una etiqueta que no esté en NINGUNA de las
# dos pone la suite roja nombrándola (H12, Medición C de la Revisión 7: antes de esa vuelta,
# `_ETIQUETAS_INLINE` no la vigilaba nadie). H13 (revisión 8) — este trinquete sólo mira los
# `.html` del repositorio, una población DISTINTA de la que `_NumerosDeDatoEnElTexto` recorre de
# verdad (HTML ya renderizado): `kcalibra/tests_pantallas_del_proyecto.py` añade un segundo
# trinquete, sobre páginas renderizadas, para que la población deje de ser una lista paralela.
#
# Efecto lateral medido (Revisión 6, Medición 3): con H10 (separaba SIEMPRE), dos `<span>`
# hermanos —los dos inline— también se separaban, y eso le devolvía a un identificador opaco
# PARTIDO entre ellos (`<span>ABC</span><span>{{v}}</span>`, familia H9) la frontera izquierda
# que H9 le había quitado (`ABC2G` pegado no casa; `ABC 2G` separado sí). Con la regla de
# bloque/inline, dos `<span>` seguidos NO separan: ese falso ROJO latente desaparece solo, sin
# tocar H9.
#
# O14 (Revisión 7) — la mitad que el párrafo de arriba NO dice: ese mismo efecto lateral sigue
# VIVO, igual que en `838f51d`, cuando el identificador opaco se parte entre dos elementos de
# BLOQUE hermanos (`<div>`/`<div>`, `<p>`/`<p>`, `<dt>`/`<dd>`, `<li>`/`<li>`): el separador de
# bloque le regala la misma frontera izquierda que H9 le había quitado, y vuelve a casar
# (medido: `.runtime/rev7/h9-partido.py`, los cuatro casos de bloque dan `[('32G', True)]`, igual
# que el pegado total de `838f51d`). Hoy no ocurre en ninguna pantalla real —el código de hogar
# se pinta entero dentro de un único `<p>`, medido vivo— así que es DEUDA, no bloqueo; se deja
# escrito para que la mitad cerrada no esconda la mitad abierta.
_ETIQUETAS_INLINE = frozenset({
    "b", "i", "span", "wbr", "br", "a", "em", "strong", "small", "sup", "sub", "abbr", "code",
    # H12 (revisión 7 de la 059) — de nivel de texto: el lector las lee SEGUIDAS de lo que las
    # rodea, igual que un `<span>` (`<label>Peso <span>80</span> kg</label>` se lee corrido).
    "button", "label", "select", "option",
    # H13 (revisión 8 de la 059, BLOQUEANTE) — otro control de formulario de nivel de texto, el
    # mismo papel que `input`/`select`/`button` arriba: el navegador la pinta `inline-block`, no
    # rompe la línea que la contiene. Medido en vivo (sin mutar nada): `<textarea>` la emite
    # `forms.Textarea` (`recetas/forms.py`, `perfiles/forms.py`, `hogares/forms.py`) en nueve
    # páginas reales de hoy, en NINGÚN `.html` del repositorio — el trinquete sobre el árbol
    # (H12) no podía verla nunca; el trinquete sobre páginas renderizadas
    # (`_etiquetas_sin_clasificar_en_paginas`, `kcalibra/tests_pantallas_del_proyecto.py`) sí.
    "textarea",
    # H12 — vacía (`SIN_CIERRE`): nunca lleva texto propio y no rompe la línea que la contiene,
    # el mismo papel que `<br>`, ya en esta lista.
    "input",
    # H12 — vacías (`SIN_CIERRE`) y sin texto propio: son coordenadas vectoriales de un icono,
    # nunca encierran un `handle_data` entre su apertura y su cierre — da igual si la etiqueta
    # que las envuelve (`<svg>`) es INLINE o de BLOQUE (ahora de BLOQUE, H14 más abajo), porque
    # jamás hay texto que pegar o separar con ellas. Se clasifican aquí sólo para que el
    # trinquete no las señale como huérfanas.
    "path", "circle", "polyline",
})

# H12 (revisión 7 de la 059) — la lista EXPLÍCITA de lo que separa: antes de esta vuelta, "no
# está en `_ETIQUETAS_INLINE`" bastaba para tratar una etiqueta como de bloque, sin que nadie la
# nombrara — así es como `_ETIQUETAS_INLINE`, la CUARTA lista escrita a mano de esta unidad,
# llevaba siete pantallas usando `button`/`label`/`input`/`svg`/`select`/`option`/`path`/
# `circle`/`template` sin que nadie las clasificara nunca. Cada una de éstas es un elemento de
# BLOQUE de verdad — el lector las lee como líneas o párrafos aparte, no corridas con el texto
# que las rodea —, medidas sobre el árbol real de hoy (`kcalibra/tests_pantallas_del_proyecto.py`,
# `TodaEtiquetaUsadaEnElArbolEstaClasificadaTests`).
#
# H14 (revisión 8 de la 059, BLOQUEANTE) — `svg`/`template` viven AQUÍ, no en una tercera lista
# aparte. La vuelta 8 los sacó de aquí a una `_ETIQUETAS_SIN_TEXTO` propia que dejaba de acumular
# TODO su interior como texto, con la premisa "dentro de `<svg>` no hay prosa, son coordenadas
# vectoriales" — verdad de los `<svg>` que había entonces (`templates/_iconos.html`,
# `progreso/_grafica.html`, los dos sin una sola palabra dentro), FALSA de `<svg>` en general:
# `<svg><text>` es texto que el navegador PINTA, `<svg><title>` es el NOMBRE ACCESIBLE que un
# lector de pantalla lee, y `<foreignObject>` lleva HTML de verdad. Medido: de nueve formas
# realistas, SEIS pasaron de detectarse a NO detectarse (`<svg><text>`, `<svg><foreignObject>`,
# `<template>` con contenido, un `<svg>` que envuelve algo legible, y un `<svg>`/`<template>` SIN
# CERRAR) — cobertura perdida, el lado que la 26ª cara prohíbe expresamente ("cuando el mecanismo
# no sabe clasificar, la respuesta segura es vigílalo, no exímelo"). El agravante: un `<svg>` o
# `<template>` sin cerrar dejaba el contador de esa tercera familia atascado por encima de cero
# PARA SIEMPRE, apagando R5/R6 para el resto de la página entera en silencio — la misma familia
# que el `max(0, …)` de la 11ª revisión de la 054 cerró del lado de la procedencia, reabierta aquí
# del lado de "sin texto". Tratarlos como BLOQUE (lo que eran antes de la vuelta 8) cierra las dos
# cosas de una vez: el contenido de un `<template>` vuelve a contar como texto de verdad —
# precisamente lo que JS clona al DOM (`recetas/_fila_ingrediente.html` vive dentro de uno) —, y
# no queda ningún contador que un desbalance pueda dejar descuadrado. Ninguna plantilla real de
# hoy tiene texto DENTRO de un `<svg>` (los iconos y la gráfica sólo llevan `<path>`/`<circle>`/
# `<polyline>`, vacíos), así que este cambio no abre ningún falso rojo sobre el árbol de hoy
# (barrido de las 39 rutas, cero diferencias contra antes de esta vuelta — hallazgos.md).
_ETIQUETAS_DE_BLOQUE = frozenset({
    "body", "dd", "div", "dl", "dt", "form", "h1", "h2", "h3", "head", "header", "html",
    "li", "link", "main", "meta", "nav", "p", "script", "section", "svg", "template", "title",
    "ul",
})


@contextmanager
def _con_procedencia_marcada():
    """Envuelve la salida de un nodo de plantilla entre `_INICIO_VARIABLE`/`_FIN_VARIABLE`,
    mientras dura el `with`, SI Y SÓLO SI esa salida no es exactamente la concatenación de lo
    que devolvieron sus hijos durante su propio `render()` — ver el comentario de arriba. Dos
    parches, un solo mecanismo: `Node.render_annotated` acumula, en la llamada activa que lo
    contiene, cada resultado de sus hijos (los reciba vía `NodeList.render` o, como `ForNode`,
    en un bucle a mano — da igual: cualquier hijo pasa por uno de los dos parches de aquí) y al
    terminar compara; `TextNode.render_annotated` (que NUNCA pasa por el parche de `Node`, por
    tener su propia sobrescritura — MRO) se parchea aparte, sólo para acumular su valor tal
    cual en el padre, nunca para envolverlo: sin esto, cualquier contenedor con texto literal Y
    un hijo dinámico (el caso normal) parecería estar "construyendo su propia salida" al faltar
    el texto literal en lo acumulado, y se envolvería entero."""
    Node = _django_template_base.Node
    TextNode = _django_template_base.TextNode
    original_render_annotated = Node.render_annotated
    original_text_render_annotated = TextNode.render_annotated
    pila_hijos = []  # una lista por llamada activa: lo que devolvieron SUS hijos, en orden

    def _render_annotated_envuelto(self, context):
        pila_hijos.append([])
        try:
            resultado = original_render_annotated(self, context)
        finally:
            hijos = pila_hijos.pop()
        # Un nodo puede devolver algo que no sea `str` (`{% filter length %}` devuelve un
        # `int`); `NodeList.render` ya lo pasa por `str()`, así que aquí se hace lo mismo antes
        # de concatenar el centinela. Sin esto, ese caso reventaba con `TypeError` en vez de
        # medirse (lo destapó el barrido G5 de la vuelta 13).
        if not isinstance(resultado, str):
            resultado = str(resultado)
        if resultado == "".join(hijos):
            final = resultado
        else:
            final = _INICIO_VARIABLE + resultado + _FIN_VARIABLE
        if pila_hijos:
            pila_hijos[-1].append(final)
        return final

    def _text_render_annotated_envuelto(self, context):
        resultado = original_text_render_annotated(self, context)
        if pila_hijos:
            pila_hijos[-1].append(resultado)
        return resultado

    with mock.patch.object(Node, "render_annotated", _render_annotated_envuelto), \
            mock.patch.object(TextNode, "render_annotated", _text_render_annotated_envuelto):
        yield


class _NumerosDeDatoEnElTexto(HTMLParser):
    """Acumula TODO el texto de la página en el orden del documento (sin cortar en cada
    etiqueta) para que un número y su unidad se encuentren aunque vivan en elementos
    hermanos distintos, recordando para cada sub-trozo la cadena de ancestros que lo envolvía
    Y si viene de una variable (`_con_procedencia_marcada`, arriba) o es texto literal.

    Vuelta 12 — el emparejado de `_INICIO_VARIABLE`/`_FIN_VARIABLE` ya NO es un regex por cada
    `handle_data` por separado: es un CONTADOR DE PROFUNDIDAD sobre el DOCUMENTO ENTERO
    (`_piezas_por_procedencia`, abajo). Si el valor de una variable lleva etiquetas dentro
    (`|safe`, `mark_safe`, un widget de formulario — `entrenos/ver.html:92` ya renderiza un
    `{{ field }}` así hoy), `html.parser` PARTE ese valor en varios `handle_data`: uno antes de
    la etiqueta interior, otro dentro, otro después — y `\\x01` cae en uno mientras `\\x02` cae
    en otro más adelante. Un regex por trozo (la vuelta 11) nunca los encontraba juntos: el
    número quedaba sin procedencia y, peor, el `\\x02` suelto se colaba entre el número y su
    unidad en el texto concatenado, así que ni siquiera casaban — ceguera, no exención. El
    contador cruza los límites de `handle_data`; sólo se resetea al empezar el documento.

    Y una coincidencia se cuenta como "de dato" si ALGÚN sub-trozo que la compone viene de
    fuera de un `TextNode` — no sólo el del primer dígito (Vuelta 12: `1{{ resto }} kg` o
    `<span>8</span><span>{{ decimales }}</span> kg` tenían su primer dígito literal y el resto
    de una variable; anclar sólo al primer dígito los eximía enteros).

    FALSO VERDE 2, mitad "ancla" (revisión, 8ª vuelta, y sigue igual): la cadena de ANCESTROS
    que se usa para mirar `.cifra` sigue siendo la del sub-trozo que trae el PRIMER DÍGITO —
    eso no cambia; lo que cambia es sólo la decisión de "de_variable", arriba.

    H11 (revisión 6 de la 059, MEDIO) — un tercer dato por sub-trozo, `separa_del_anterior`
    (`_piezas_por_procedencia`/`hallazgos`, abajo): si el `handle_data` que lo trajo queda al
    otro lado de un límite de BLOQUE (`_ETIQUETAS_INLINE`) del `handle_data` anterior. Se
    calcula aquí, en `handle_starttag`/`handle_endtag`, porque sólo aquí se ve QUÉ etiqueta cruzó
    ese límite — `_piezas_por_procedencia` sólo ve el resultado ya trazado.

    H12 (revisión 7 de la 059, MEDIO) introdujo un contador, `_profundidad_sin_texto`, que
    dejaba de acumular texto en absoluto dentro de `<template>`/`<svg>`. H14 (revisión 8,
    BLOQUEANTE) lo retiró: medido en vivo, esa exención perdía seis de nueve formas de texto que
    un usuario SÍ lee o SÍ escucha (`<svg><text>`, `<svg><title>`, `<foreignObject>`, el
    contenido de un `<template>` que JS clona al DOM…), y un `<svg>`/`<template>` sin cerrar
    dejaba el contador atascado por encima de cero para siempre, apagando R5/R6 para el resto
    del documento en silencio. `<svg>`/`<template>` son ahora etiquetas de BLOQUE normales
    (`_ETIQUETAS_DE_BLOQUE`, arriba): su contenido cuenta como texto igual que el de cualquier
    otro elemento, y `_cruza_bloque_pendiente` (abajo) es lo único que decide si un salto de
    etiqueta pega o separa."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila = []
        self._trozos = []  # (texto, cadena_de_ancestros, separa_del_anterior), en orden
        # H11 — `True` mientras, desde el último `handle_data`, se haya abierto o cerrado
        # ALGUNA etiqueta que no sea inline (`_ETIQUETAS_INLINE`); se consume (y se resetea a
        # `False`) en el PRÓXIMO `handle_data`, así que "al menos una fue de bloque" sobrevive
        # aunque entre medias también se cruce alguna inline.
        self._cruza_bloque_pendiente = False

    def handle_starttag(self, etiqueta, atributos_crudos):
        # Vuelta 12b: el centinela marca la PROCEDENCIA DEL TEXTO (`handle_data`, abajo) — pero
        # `Node.render_annotated` envuelve la salida de CUALQUIER nodo que no sea `TextNode`, y
        # eso incluye uno que renderiza VACÍO justo dentro de una etiqueta (un `{% if %}` sin
        # rama, un atributo condicional) o el valor de un `{{ … }}` dentro de un `class="…"`.
        # `html.parser` no distingue eso de texto de verdad: el centinela se cuela en el NOMBRE
        # de la etiqueta (medido: `'section\x01\x02'` como ancestro, `.runtime/vuelta12/parte1.log`)
        # y en valores de atributo — estructura, no texto — y ahí rompe cualquiera que trocee
        # `class` en tokens. Se borra de los dos ANTES de construir la cadena de ancestros; la
        # procedencia del texto (lo único para lo que existe) no pasa por aquí.
        etiqueta = _MARCA_DE_PROCEDENCIA_RE.sub("", etiqueta)
        atributos_crudos = [
            (nombre, _MARCA_DE_PROCEDENCIA_RE.sub("", valor) if valor is not None else valor)
            for nombre, valor in atributos_crudos
        ]
        attrs = atributos(atributos_crudos)
        if etiqueta not in _ETIQUETAS_INLINE:
            self._cruza_bloque_pendiente = True
        if etiqueta not in SIN_CIERRE:
            self.pila.append((etiqueta, attrs))

    def handle_data(self, datos):
        if datos:
            self._trozos.append((datos, list(self.pila), self._cruza_bloque_pendiente))
            self._cruza_bloque_pendiente = False

    def handle_endtag(self, etiqueta):
        etiqueta = _MARCA_DE_PROCEDENCIA_RE.sub("", etiqueta)
        if etiqueta not in _ETIQUETAS_INLINE:
            self._cruza_bloque_pendiente = True
        for k in range(len(self.pila) - 1, -1, -1):
            if self.pila[k][0] == etiqueta:
                del self.pila[k:]
                return

    def _piezas_por_procedencia(self):
        """`(subtexto, cadena_de_ancestros, de_variable, separa_del_anterior)` de cada sub-trozo
        del documento entero, en orden, con el contador de profundidad cruzando los
        `handle_data`: abre con `_INICIO_VARIABLE` (profundidad += 1), cierra con
        `_FIN_VARIABLE` (profundidad -= 1, ACOTADA en 0), y todo lo que cae con profundidad > 0
        es "de variable". Las dos marcas se BORRAN del texto (no forman parte de ningún
        sub-trozo), así que un número y su unidad separados sólo por el centinela de cierre
        quedan pegados otra vez.

        La cota en 0 (11ª revisión, BLOQUEANTE): un `_FIN_VARIABLE` que se cuela dentro de una
        etiqueta (fuera de `handle_data`, ver `handle_starttag`/`handle_endtag` arriba) mientras
        su `_INICIO_VARIABLE` sí llega al texto deja el contador descompensado — SIN la cota,
        cae a -1 y a partir de ahí un `{{ … }}` de verdad sólo lo sube a 0: `de_variable = False`
        para TODO lo que quede de página, apagando R6 en silencio de punta a punta. Con la cota,
        un centinela descompensado sólo hace perder profundidad de más (falso ROJO, el lado
        seguro) en vez de apagar el resto del documento.

        `separa_del_anterior` (H11, revisión 6 de la 059): `True` sólo para el PRIMER sub-trozo
        de un `handle_data` cuyo límite con el anterior cruzó una etiqueta de BLOQUE
        (`self._cruza_bloque_pendiente`, calculado en `handle_starttag`/`handle_endtag`);
        `False` para cualquier sub-trozo que salga de PARTIR ese mismo `handle_data` por el
        centinela de procedencia (nunca hay una etiqueta real entre ellos, así que nunca
        separan) y para el primer sub-trozo de un `handle_data` cuyo límite sólo cruzó
        etiquetas INLINE. `hallazgos`, abajo, sólo separa con un espacio los `True`."""
        piezas = []
        profundidad = 0
        for texto, cadena, cruza_bloque in self._trozos:
            cursor = 0
            primer_subtrozo = True
            for marca in _MARCA_DE_PROCEDENCIA_RE.finditer(texto):
                if marca.start() > cursor:
                    piezas.append((
                        texto[cursor:marca.start()], cadena, profundidad > 0,
                        primer_subtrozo and cruza_bloque,
                    ))
                    primer_subtrozo = False
                if marca.group() == _INICIO_VARIABLE:
                    profundidad += 1
                else:
                    profundidad = max(0, profundidad - 1)
                cursor = marca.end()
            if cursor < len(texto):
                piezas.append((
                    texto[cursor:], cadena, profundidad > 0, primer_subtrozo and cruza_bloque,
                ))
        return piezas

    @property
    def hallazgos(self):
        """H10 (revisión 5 de la 059, BLOQUEANTE) — `texto_completo` ya NO es la concatenación
        a pelo de todos los sub-trozos (`"".join(piezas)`): eso pegaba también el texto de
        ELEMENTOS DISTINTOS que en la fuente no llevan ni un espacio entre sí
        (`<dt>Altura</dt><dd>...` → `"Altura167 cm"`), y la frontera izquierda de H9 (`(?<!\\w)`)
        confundía la `a` de "Altura" con el dígito de un número de dato real y lo eximía.

        H11 (revisión 6 de la 059, MEDIO) — separar TODO límite entre `handle_data` (el arreglo
        de H10) también despegaba las mitades de una palabra que una etiqueta INLINE parte por
        dentro (`r<b>a</b>ciones`, `Mili<wbr>litros`): la unidad dejaba de casar con su
        vocabulario y la detección desaparecía entera. La regla ya no es "handle_data nuevo":
        es **lo que separa un salto de elemento de BLOQUE** (`separa_del_anterior`, arriba) —
        dos trozos que sólo cruzan etiquetas INLINE (o que vienen del mismo `handle_data`,
        partido sólo por el centinela de procedencia) se quedan pegados a pelo, como los leería
        un lector: `\\s*` en `_NUMERO_CON_UNIDAD_RE` sigue absorbiendo sin esfuerzo el espacio
        que SÍ se añade en un salto de bloque, y si el literal que sigue YA traía el suyo
        (`" cm"`), el resultado son dos espacios seguidos, que `\\s*` también absorbe. Con esto,
        las cadenas que cambian de comportamiento frente al pegado total de `6dc5924` son las
        que cruzan un salto de BLOQUE sin espacio en la fuente (`Altura167 cm`, el caso de H10,
        y sus hermanas) — no "la única", como afirmaba una versión anterior de este docstring,
        medible y falsa: la Medición 3 de la Revisión 6 midió once formas que cambian de
        comportamiento con el separador puesto (`hallazgos.md`, "Vuelta de revisión 6")."""
        limites = []  # (inicio, fin, cadena_de_ancestros, de_variable) de cada sub-trozo
        piezas = []
        cursor = 0
        for subtexto, cadena, de_variable, separa_del_anterior in self._piezas_por_procedencia():
            if piezas and separa_del_anterior:
                piezas.append(_SEPARADOR_ENTRE_TROZOS)
                cursor += len(_SEPARADOR_ENTRE_TROZOS)
            piezas.append(subtexto)
            limites.append((cursor, cursor + len(subtexto), cadena, de_variable))
            cursor += len(subtexto)
        texto_completo = "".join(piezas)
        resultado = []
        for coincidencia in _NUMERO_CON_UNIDAD_RE.finditer(texto_completo):
            inicio, fin = coincidencia.start(), coincidencia.end()
            solapan = [lim for lim in limites if lim[0] < fin and lim[1] > inicio]
            cadena_del_primer_digito = solapan[0][2]
            de_variable = any(lim[3] for lim in solapan)
            resultado.append((coincidencia.group(), cadena_del_primer_digito, de_variable))
        return resultado


def _algun_elemento_de_la_cadena_lleva_cifra(cadena):
    return any("cifra" in (attrs.get("class") or "").split() for _, attrs in cadena)


class R6_CifraEnLosNumerosDeDatoTests(_ConAlejandroYSusDatos):
    def setUp(self):
        super().setUp()
        # Cierra el día de hoy (revisión, 7ª vuelta): sin ningún `CierreDeDia`,
        # `cumplimiento.cerrados` es 0 y `progreso/ver.html` nunca llega a renderizar la `<p
        # class="cifra …">{{ cumplimiento.porcentaje }}%</p>` (l.178) — el barrido de abajo no
        # puede vigilar un elemento que nunca aparece. Mismo POST que ya usa `cierres/tests.py`.
        #
        # D (revisión, 8ª vuelta) — rojo mudo: sin comprobar que el POST funcionó, si algo lo
        # rompe (p.ej. otra unidad renombra `lo_segui`) el día no se cierra, esa `<p>` deja de
        # renderizarse, y la medición de arriba pasaría a VERDE sin que nada lo dijera — la
        # misma familia de "guarda de rojo mudo" que ya exige R10 para las dos zonas del bug
        # 027.
        #
        # `status_code` NO sirve de control aquí (a diferencia del entreno, más abajo):
        # `cierres/views.py:cerrar` nunca redirige — con el formulario inválido vuelve a
        # renderizar la MISMA plantilla con los errores, así que un `respuesta` roto sigue
        # devolviendo 200 (medido: `assertEqual(status_code, 200)` no habría cazado nada, la
        # mutación "romper `lo_segui`" pasa con 200 y CERO `CierreDeDia` creados). El control
        # real de que el cierre pasó de verdad es que la fila exista.
        fecha_de_hoy = timezone.localdate()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {
                "fecha": fecha_de_hoy.isoformat(),
                "respuesta": "lo_segui",
                "calorias_comidas": "",
                "nota": "",
            },
        )
        assert CierreDeDia.objects.filter(
            persona=self.alejandro, fecha=fecha_de_hoy
        ).exists()  # control: el día se cerró de verdad

    def _elemento_lleva_cifra(self, ruta, id_elemento):
        """Hueco 6 (revisión, 4ª vuelta): la versión anterior exigía, con comillas dobles
        FIJAS, que `class` fuera pegado JUSTO DETRÁS de `id` (`id="…"\\s+class="cifra\\b`) —
        cualquier atributo entre medias, o `class` con comillas simples, o `class` ANTES de
        `id`, ponía esto en ROJO con `.cifra` en su sitio (medido, tres formas, hallazgos.md:
        `class` antes de `id`, comillas simples, y un `hx-swap-oob="true"` entre medias — el
        caso realista, porque `peso.html`/`entrenos/ver.html` ya son pantallas HTMX). Se busca
        el elemento por su `id` con `elementos_con_texto` (ya importado) y se mira `cifra` en
        los TOKENS de su `class`, sin depender del orden de los atributos."""
        respuesta = self.client.get(ruta)
        contenido = respuesta.content.decode()
        coincide = lambda e, a, id_elemento=id_elemento: a.get("id") == id_elemento
        elementos = elementos_con_texto(contenido, coincide)
        self.assertEqual(
            len(elementos), 1, f"no hay un único elemento con id={id_elemento!r} en {ruta}"
        )
        clases = (elementos[0][0].get("class") or "").split()
        self.assertIn("cifra", clases, f"{id_elemento} no lleva `.cifra` en {ruta}")

    def test_kcal_quemadas_hoy_lleva_cifra(self):
        self._elemento_lleva_cifra("/entrenos/", "calorias-quemadas-hoy")

    def test_peso_de_la_bascula_lleva_cifra(self):
        self._elemento_lleva_cifra("/perfiles/peso/", "peso-bascula")

    def test_peso_de_calculo_lleva_cifra(self):
        self._elemento_lleva_cifra("/perfiles/peso/", "peso-calculo")

    def test_las_piezas_compartidas_no_tienen_un_camino_sin_cifra(self):
        """Hueco 2 (revisión, 3ª vuelta): R6 dice "TODO número de dato lleva `.cifra`", pero
        los tres tests de arriba solo miran TRES ids escritos a mano en sus plantillas — las
        piezas de `_ui.html` que imprimen números (justo las que R7 obliga a COMPARTIR, y por
        tanto las que rompen VARIAS pantallas a la vez si fallan) no las mira nadie. Medido:
        quitando `cifra` de `numero_grande` y de `_pildora_macro_interna` (los gramos de las
        seis píldoras de macro de Inicio y de Apuntar el plan, que se refrescan por HTMX —
        justo donde "bailar" se ve), la suite completa seguía en verde (hallazgos.md). Mismo
        patrón que `test_la_pieza_pildora_macro_no_tiene_un_camino_sin_nombre` (R5): se
        comprueba la PIEZA en sí, no solo una pantalla que la usa.

        Quinta ocurrencia de la misma familia (vuelta 6, sweep del constructor — no la nombró
        ninguna revisión): `assertRegex(interna, r'class="cifra\\b', …)` exigía comillas dobles
        Y `cifra` como PRIMER token del atributo `class` — reordenar las clases dentro de la
        propia pieza (`class="… font-bold leading-none cifra"`, con `.cifra` intacto) ponía
        esto en ROJO (medido: `vuelta6-hueco6b-mutacion-orden-en-la-pieza-ROJO.log`). Este
        assert lee el FICHERO fuente de la pieza (con sintaxis de Django dentro), no HTML
        renderizado, así que `elementos_con_texto` no aplica aquí.

        Reutilizar tal cual `_CLASE_RE` (la de `_sin_pointer_events_none_del_envoltorio_fijo`,
        pensada para HTML ya renderizado) rompía EN FALSO sobre el propio `numero_grande` sin
        mutar nada: su `class="cifra {{ tam|default:'text-[44px]' }} font-bold leading-none"`
        lleva una comilla simple DENTRO del valor (el argumento del filtro de Django), y
        `[^"']*` —que excluye las dos comillas, no solo la de apertura— se para ahí y nunca
        llega a `cifra`. `_CLASE_DE_LA_PIEZA_RE`, abajo, sólo para en la comilla de la MISMA
        clase que abrió el atributo (`\\1`, no `[^"']`), que es la regla real de HTML: una
        comilla del otro tipo dentro del valor no cierra nada.

        Hueco 11 (revisión, 5ª vuelta): el `re.search` de `{% partialdef … %}` llevaba los
        espacios alrededor del nombre escritos a mano — se tolera con `\\s*`, mismo motivo y
        mismo arreglo que `test_la_pieza_pildora_macro_no_tiene_un_camino_sin_nombre` (R5)."""
        contenido = _texto(RUTA_UI)
        for pieza in ("numero_grande", "_pildora_macro_interna", "_barra_macro_interna"):
            with self.subTest(pieza=pieza):
                interna = re.search(
                    rf"\{{%\s*partialdef\s+{pieza}\s*%\}}(.*?)\{{%\s*endpartialdef\s*%\}}",
                    contenido,
                    re.S,
                ).group(1)
                tokens = set()
                for coincidencia in _CLASE_DE_LA_PIEZA_RE.finditer(interna):
                    tokens.update(coincidencia.group("clases").split())
                self.assertIn("cifra", tokens, f"{pieza} perdió `.cifra`")

    # Unidad 059 — `test_ningun_numero_de_dato_escrito_en_linea_se_queda_sin_cifra` (el barrido
    # sobre HTML renderizado que vivía aquí, FALSO VERDE 1 BLOQUEANTE de la revisión 6ª vuelta)
    # se SACÓ de este fichero: `kcalibra/tests_pantallas_del_proyecto.py` corre ya el mismo
    # barrido — mismo mecanismo (`_con_procedencia_marcada`/`_NumerosDeDatoEnElTexto`,
    # importados de aquí, no copiados) — sobre las QUINCE pantallas reales de hoy (no solo las
    # siete de esta unidad) y con un vocabulario más ancho, derivado de las `choices` de
    # `despensa`/`recetas` en vez de fijo a `kcal|kg|g|min|%`. Mantenerlo aquí también habría
    # sido exactamente la duplicación que la 059 existe para cerrar.


# ------------------------------------------------------------------------------------------ #
# R7 — las piezas compartidas viven UNA SOLA VEZ, en `_ui.html`, y las pantallas las usan.
# ------------------------------------------------------------------------------------------ #

# `_ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE` (arriba, junto a `_texto`) borra `{% … %}`/`{# … #}`
# del texto fuente antes de tokenizar un `class="…"`: lo que el navegador ve ahí es texto plano
# (una vez Django resuelve la etiqueta o descarta el comentario), y una comilla de Django
# dentro del atributo (`{% if tono == 'racha' %}`) ya no rompe el cierre de `_CLASE_RE`
# (revisión, 7ª vuelta — ver el docstring de `test_ninguna_pantalla_copia_…` más abajo). Un
# `{{ … }}` que quede DENTRO del `class="…"` ya capturado se cuenta aparte, como comodín (vuelta
# 12b, C2) — no se borra aquí.
#
# Captura TAMBIÉN la etiqueta que abre el `class="…"` (FALSO VERDE 3, revisión 8ª vuelta): la
# firma de `aviso` necesita saber si es un `<div>` o un `<button>`, no sólo qué clases lleva.
_CLASE_CON_ETIQUETA_RE = re.compile(
    r'''<(?P<etiqueta>[a-zA-Z][\w-]*)[^<>]*?\sclass=(["'])(?P<clases>.*?)\2''', re.S
)

# Unidad 059, vuelta de revisión 2 (H6) — las ocho clases del `<a>` clicable que comparten
# `boton_redondo`/`boton_redondo_menu` en `_ui.html`, usadas TANTO por la firma de copia de R4
# (más abajo, candidata de `boton_redondo`) COMO por `_es_boton_o_menu_redondo` de
# `kcalibra.tests_pantallas_del_proyecto` (R7) — se define aquí, una sola vez, y las dos redes la
# IMPORTAN: hasta esta vuelta sólo la usaba R7, y la firma de copia de R4 seguía mirando las
# clases del `<div>` ENVOLTORIO (`pointer-events-none fixed inset-x-0 z-40`), así que pegar a
# mano sólo el `<a>` clicable no disparaba ninguna de las quince firmas.
_CLASES_DEL_BOTON_REDONDO = {
    "pointer-events-auto", "h-14", "w-14", "rounded-pastilla", "bg-tinta", "text-white",
    "shadow-lg", "active:scale-95",
}


class R7_PiezasCompartidasUnaSolaVezTests(SimpleTestCase):
    databases = set()

    def test_cada_pieza_se_define_exactamente_una_vez_en_ui_html(self):
        """Hueco 11 (revisión, 5ª vuelta): `{% partialdef … %}` llevaba los espacios alrededor
        del nombre escritos a mano — Django acepta `{%partialdef numero_grande%}` igual que con
        espacios. Se tolera con `\\s*`, mismo arreglo que en R5 más arriba.

        FALSO VERDE 2, mitad "definición" (revisión, 6ª vuelta): esto solo contaba las
        ocurrencias DENTRO de `_ui.html` — una pantalla podía declarar su PROPIO
        `{% partialdef distintivo %}` (una segunda definición, fuera de `_ui.html`, que es
        exactamente lo que R7 prohíbe: "una sola vez, en `templates/_ui.html`") y este test no
        se enteraba, porque nunca miraba fuera de ese fichero (medido por el revisor:
        añadiendo ese partial a `entrenos/ver.html`, `Ran 44 — OK`). Se cuenta sobre las NUEVE
        plantillas de pantalla MÁS `_ui.html`, no solo sobre `_ui.html` — ninguna de las
        nueve define hoy un partial con alguno de estos nombres, así que el recuento sigue
        dando 1 en cada uno sin tocar el código de producción.

        FALSO VERDE 2, mitad "inline" (revisión, 7ª vuelta): `{% partialdef nombre inline %}`
        es un argumento REAL de `django-template-partials`
        (`_START_TAG = r"\\{%\\s*(startpartial|partialdef)\\s+([\\w-]+)(\\s+inline)?\\s*%}"`,
        `template_partials/templatetags/partials.py:9`) y define la pieza IGUAL que sin
        `inline` — pero el `\\s*%\\}` de este regex exigía que el nombre fuera seguido
        directamente por el cierre, así que una segunda definición con `inline` no la contaba
        (medido: la misma mutación de arriba, con `inline` añadido, `Ran 44 — OK`). Se tolera
        el argumento opcional, y se ancla el nombre con `\\b` (que no lo llevaba: sin él,
        `distintivo` también casaría dentro de un futuro `distintivo_2`)."""
        contenido = "\n".join(_texto(p) for p in PLANTILLAS + [RUTA_UI])
        conteos = {}
        for pieza in PIEZAS_PORTADAS:
            conteos[pieza] = len(
                re.findall(rf"\{{%\s*partialdef\s+{pieza}\b(?:\s+inline)?\s*%\}}", contenido)
            )
        self.assertEqual(
            conteos,
            {pieza: 1 for pieza in PIEZAS_PORTADAS},
            f"alguna pieza no está definida exactamente una vez: {conteos}",
        )

    def test_cada_pieza_usada_la_incluye_alguna_de_las_diez_pantallas(self):
        """Hueco 10 (revisión, 5ª vuelta): la comilla de cierre de `_ui.html#{pieza}"` iba
        fija a doble — Django acepta `{% include '_ui.html#pieza' %}` con comillas simples
        igual que con dobles. Se acepta cualquiera de las dos con `["']`.

        FR-I (revisión, 9ª vuelta): antes se recorría `PIEZAS_USADAS_EN_LAS_PANTALLAS`, TODA
        pieza que `_ui.html` porte hoy salvo `barra_macro` — medido: una pieza `medalla` sin
        usar por ninguna de las diez pantallas (el caso de la 054, que también toca `_ui.html`
        y podría añadir una para sus propias pantallas) ponía esto en ROJO. Se recorre
        `PIEZAS_QUE_ESTA_UNIDAD_USA` (arriba), la foto congelada de HOY, así que una pieza que
        esta unidad no conocía al escribirse no se exige aquí."""
        fuente_de_las_pantallas = "\n".join(_texto(p) for p in PLANTILLAS)
        sin_uso = [
            pieza
            for pieza in PIEZAS_QUE_ESTA_UNIDAD_USA
            if not re.search(rf"""_ui\.html#{pieza}["']""", fuente_de_las_pantallas)
        ]
        self.assertEqual(sin_uso, [], f"piezas portadas que ninguna pantalla incluye: {sin_uso}")

    def test_toda_pieza_incluida_por_esta_unidad_tiene_firma_de_clase(self):
        """E, media cerrada (revisión, 9ª vuelta): `PIEZAS_PORTADAS` se deriva bien y se
        CUENTA, pero `test_ninguna_pantalla_copia_…` (más abajo) recorre
        `_FIRMAS_DE_CLASE_POR_PIEZA`, que sigue escrito a mano — una pieza nueva se cuenta pero
        no se VIGILA. Medido: una pieza `medalla` en `_ui.html`, incluida desde una pantalla y
        copiada a mano en otra, seguía en verde porque `medalla` no tenía fila en el
        diccionario de firmas.

        Se recorren las piezas que las PLANTILLAS de esta unidad incluyen HOY (recalculado en
        cada corrida, no la foto congelada `PIEZAS_QUE_ESTA_UNIDAD_USA` de FR-I) y no toda
        `PIEZAS_PORTADAS`, a propósito: la propia FR-I (revisión, 9ª vuelta) es la razón — si
        este test mirara TODA pieza que `_ui.html` porte, una pieza que la 054/055 añadan para
        SUS PANTALLAS (fuera de esta unidad, sin que ninguna de las diez la incluya nunca)
        pondría la 053 en rojo otra vez, exactamente el defecto que FR-I pide aflojar. Mirar
        "incluida hoy" en vez de "frozen" (a diferencia de `PIEZAS_QUE_ESTA_UNIDAD_USA`) es
        justo lo que necesita ESTE test: tiene que enterarse en el momento en que una pantalla
        de ESTA unidad empieza a incluir una pieza nueva, no sólo de las doce de siempre.

        `anillo_cierra`/`tarjeta_cierra` (los `*_cierra`) son la única excepción legítima: su
        marcado es sólo `</div>`/`</section>`, sin ninguna clase, así que no hay firma posible
        — ya razonado en el comentario de `_FIRMAS_DE_CLASE_POR_PIEZA` para `anillo_cierra`."""
        fuente_de_las_pantallas = "\n".join(_texto(p) for p in PLANTILLAS)
        piezas_incluidas = [
            pieza
            for pieza in PIEZAS_PORTADAS
            if re.search(rf"""_ui\.html#{pieza}["']""", fuente_de_las_pantallas)
        ]
        sin_firma = [
            pieza
            for pieza in piezas_incluidas
            if not pieza.endswith("_cierra") and pieza not in self._FIRMAS_DE_CLASE_POR_PIEZA
        ]
        self.assertEqual(
            sin_firma, [], f"piezas incluidas por esta unidad sin firma de clase: {sin_firma}"
        )

    # Firma de clases por pieza: lista de candidatas independientes (basta con que UNA case,
    # OR entre ellas), cada una `{"fija": tokens}` con, opcional, `"minimo"` (cuántos de esos
    # tokens tienen que estar — por defecto TODOS), `"etiquetas"` (lista BLANCA: el nombre de
    # etiqueta HTML tiene que ser uno de éstos) o `"etiquetas_prohibidas"` (lista NEGRA: el
    # nombre de etiqueta tiene que NO ser ninguno de éstos). Verificado (script aparte, no un
    # test — no hay nada que mutar en un negativo) que NINGUNA de las nueve plantillas tiene
    # hoy estos tokens juntos en un mismo `class` con la etiqueta que exige cada firma.
    # `anillo_cierra` no tiene firma posible (su marcado son sólo `</div></div>`, sin ninguna
    # clase): un cierre sin clase no se puede distinguir de cualquier otro `</div>`, así que
    # copiarlo no es "el hueco que nombra R7" en el mismo sentido — no hay clase que decir que
    # se copió.
    #
    # FALSO VERDE 3 (revisión, 8ª vuelta): las vueltas anteriores habían cerrado FR-A
    # estrechando la firma con un token discriminante (`cifra` en `numero_grande`, un trío de
    # pares de color en `aviso`) — pero R7 prohíbe "una pieza copiada y pegada", no "una pieza
    # copiada con todos sus tokens": una copia que omite justo el token discriminante volvía a
    # colar. El token discriminante no puede ser el que un copiador omite: tiene que ser algo
    # de la FORMA de la pieza que un copiador no reproduce por accidente.
    _FIRMAS_DE_CLASE_POR_PIEZA = {
        "tarjeta_abre": [{"fija": {"rounded-tarjeta", "bg-superficie"}}],
        "titulo_seccion": [{"fija": {"mb-3", "items-end", "justify-between"}}],
        # Dos candidatas independientes, por la FORMA de la pieza, no por un token que un
        # copiador pueda omitir sin querer: (a) el `<p>` exterior CON `.cifra` — sigue
        # cazando la copia completa de siempre; (b) el `<span>` INTERIOR del `{% if unidad %}`
        # con sus cinco clases fijas, que existe con o sin que el `<p>` lleve `cifra` — cierra
        # el hueco de un `numero_grande` de RECUENTO (entrenos, comidas, días, racha: la mitad
        # de sus usos, por eso `unidad` es opcional en `_ui.html:62`) pegado a mano SIN
        # `cifra`, que ni esta firma ni R6 veían (R6 sólo mira números CON unidad física:
        # kcal|kg|g|min|%, y un recuento no lleva ninguna). Ningún encabezado normal
        # (`<h2 class="text-[18px] font-bold leading-none tracking-tight">`, FR-A) lleva
        # ninguna de las dos.
        #
        # `"minimo": 4` (revisión, 9ª vuelta) — la candidata (b) exigía las CINCO clases del
        # `<span>` interior; medido: pegar la pieza a mano con CUATRO de las cinco
        # (`ml-1.5 text-base font-semibold text-tinta-media`, sin `tracking-normal`) colaba.
        # Ante la duda, ROJO: se exige un UMBRAL (4 de 5) en vez de la unión completa — un
        # `<span>` cualquiera que por azar comparta tres de estos cinco tokens de espaciado no
        # existe hoy en las nueve plantillas (verificado, mismo script aparte de siempre).
        "numero_grande": [
            {"fija": {"cifra", "font-bold", "leading-none"}},
            {
                "fija": {
                    "ml-1.5", "text-base", "font-semibold", "tracking-normal",
                    "text-tinta-media",
                },
                "minimo": 4,
            },
        ],
        # Unidad 059 — el falso ROJO que lo motivó era real (se veía al barrer las QUINCE
        # pantallas reales del proyecto entero, algo que ningún sweep de la 053 podía ver
        # porque solo mira sus siete): con solo `rounded-pastilla`+`px-3`+`py-1.5`, la firma
        # también disparaba sobre botones de "Guardar"/"Quitar" corrientes (`rounded-pastilla
        # … px-3 py-1.5 text-[13px] font-semibold`, el mismo tamaño de pastilla pequeña) en
        # `despensa/ver.html`, `hogares/mi_hogar.html` y `recetas/detalle.html` — código
        # correcto, sin ninguna copia.
        #
        # La 1ª vuelta de esta unidad lo cerró AÑADIENDO tres tokens (`inline-flex`,
        # `items-center`, `gap-1.5`) a `fija` — y eso es AFLOJAR, no apretar: exigir MÁS
        # tokens para dar por copiada una pieza es detectar MENOS copias (soltar cualquiera de
        # los tres deja escapar una copia real, medido por la revisión). El arreglo que sí
        # aprieta es el idiom que este mismo diccionario ya usa para `aviso`: `_pildora_macro_interna`
        # es un `<span>`; los botones de "Guardar"/"Quitar" que la motivaron son `<button>`/`<a>` —
        # lo que la distingue de ellos no es más forma, es la ETIQUETA.
        "pildora_macro": [
            {
                "fija": {"rounded-pastilla", "px-3", "py-1.5"},
                "etiquetas_prohibidas": {"button", "a"},
            }
        ],
        "barra_macro": [{"fija": {"h-2", "overflow-hidden", "rounded-pastilla", "bg-lienzo"}}],
        "anillo_abre": [{"fija": {"shrink-0", "rounded-full", "relative"}}],
        "boton": [{"fija": {"px-6", "py-3.5", "transition-opacity", "disabled:opacity-40"}}],
        # (revisión, 8ª vuelta): las tres vueltas anteriores enumeraban los tres pares de
        # color de la pieza para no disparar sobre el botón de "Comprobar hora del servidor"
        # (`paginas/inicio.html:50`, que comparte los tokens de espaciado) — pero un CUARTO
        # tono (`bg-lienzo text-tinta-media`, el neutro que la propia `distintivo` usa) no
        # está en la lista y colaba. Lo que de verdad distingue a `aviso` de ese botón no es
        # su color, es su FORMA: `aviso` es de puro texto; el botón es un `<button>`.
        #
        # `etiquetas={"div"}` → `etiquetas_prohibidas={"button", "a"}` (revisión, 9ª vuelta):
        # la lista BLANCA de un solo literal (`{"div"}`) es el mismo defecto que esta vuelta
        # lleva cerrando en todas partes — medido: la pieza pegada entera como `<section>`
        # (la propia etiqueta de `tarjeta_abre`, lo primero que coge quien busca un
        # contenedor semántico), `<p>` o `<article>` colaba. Lo que distingue a `aviso` del
        # botón no es "ser un `<div>`", es "no ser un `<button>`" (ni un `<a>`, el otro
        # elemento interactivo que podría llevar estos mismos tokens de espaciado) — una
        # lista NEGRA dice eso mismo sin dejar fuera a ningún contenedor de texto nuevo que
        # invente la 054/055.
        "aviso": [
            {
                "fija": {"rounded-control", "px-4", "py-3", "font-medium"},
                "etiquetas_prohibidas": {"button", "a"},
            }
        ],
        # `gap-1` fuera de la firma (revisión 7ª vuelta): un `gap-*` es el token MÁS fácil de
        # tocar sin querer al copiar (reordenar/ajustar espaciado) y no aporta nada que
        # `rounded-pastilla`+`px-2.5`+`py-1` ya no digan sobre la forma de la pieza —
        # verificado que este trío tampoco colisiona con nada de las nueve plantillas.
        "distintivo": [{"fija": {"rounded-pastilla", "px-2.5", "py-1"}}],
        # Dos candidatas independientes, por la FORMA de la pieza: (a) el `<div>` ENVOLTORIO
        # que posiciona el botón — sigue cazando la copia completa de siempre; (b) el `<a>`
        # clicable en sí, con `_CLASES_DEL_BOTON_REDONDO` (arriba) y `etiquetas={"a"}` para no
        # colisionar con el `<button>` disparador de `boton_redondo_menu` (mismas ocho clases,
        # etiqueta distinta). Sin (b), quien pega a mano SÓLO el `<a>` — lo único que hace
        # falta para tener el botón, sin su `<div>` envoltorio — no disparaba ninguna de las
        # quince firmas (H6, vuelta de revisión 2, medido: `¿el <a> suelto dispara …? -> NO`
        # en las cuatro firmas candidatas).
        "boton_redondo": [
            {"fija": {"pointer-events-none", "fixed", "inset-x-0", "z-40"}},
            {"fija": _CLASES_DEL_BOTON_REDONDO, "etiquetas": {"a"}},
        ],
        "boton_redondo_menu": [{"fija": {"bottom-16", "right-0", "w-56"}}],
        # Unidad 057, R1/R7 — `segmentado` (Planificador/Recetas), incluida por
        # `planes/apuntar.html`, una de las nueve plantillas de esta unidad (053): esta pieza
        # es nueva, así que `test_toda_pieza_incluida_por_esta_unidad_tiene_firma_de_clase` la
        # detecta sola (FR-I, revisión 9ª vuelta) y exige una fila aquí. `mb-4` no aparece en
        # ninguna de las nueve plantillas (verificado con grep) — sobra con ese único token
        # para no colisionar, pero se deja el trío completo del contenedor para que la firma
        # describa la FORMA de la pieza, no un accidente de una sola clase.
        "segmentado": [{"fija": {"mb-4", "gap-1", "rounded-pastilla", "bg-lienzo"}}],
        # Unidad 059 (R4/R10) — las tres piezas que la 054 dejó sin firma portante
        # (hallazgos.md de la 054, revisión, sección "Lo que sí quedó demostrado"): se contaban
        # en `PIEZAS_PORTADAS` pero nadie vigilaba si alguna pantalla las copiaba a mano en vez
        # de incluirlas. Apretar, no aflojar (misma disciplina que ya aplicó la 057 con FR-I).
        #
        # `boton_enlace` (`_ui.html`) es la hermana de `boton` sobre un `<a>` — MISMA lección de
        # la 27ª cara (docs/conocimiento/tests-que-no-fallan-cuando-deben.md): el token
        # discriminante no puede ser uno que el defecto real (copiar el aspecto de `boton` sobre
        # un `<a>`, que no entiende `:disabled`) se lleve por delante. `disabled:opacity-40` de
        # la firma de `boton` YA no sirve aquí a propósito: es justo el token que un `<a>` no
        # necesita, así que la firma de `boton_enlace` no depende de él.
        #
        # La 1ª vuelta de esta unidad añadió `text-[15px]`/`font-semibold` a la firma que la 054
        # ya había endurecido en tres vueltas — y esos dos son justo TAMAÑO y GROSOR de letra,
        # lo primero que se ajusta al adaptar un botón pegado a mano: la revisión midió que una
        # copia real sin `font-semibold` escapaba con esos seis tokens y ya no con estos cuatro.
        # Se reutiliza, letra por letra, la firma que la 054 dejó — no se re-deriva — y
        # `etiquetas={"a"}` sigue evitando colisionar con el propio `<button>` de `boton` (que
        # comparte casi los mismos tokens de espaciado, pero nunca es un `<a>`).
        "boton_enlace": [
            {
                "fija": {"rounded-pastilla", "px-6", "py-3.5", "active:opacity-80"},
                "etiquetas": {"a"},
            }
        ],
        # `fila_lista_abre` es sólo un `<li>` con su relleno — `etiquetas={"li"}` más los dos
        # tokens de espaciado que la definen; ninguna de las pantallas reales de hoy tiene otro
        # `<li>` con exactamente ese par (verificado con el barrido de esta misma unidad).
        "fila_lista_abre": [{"fija": {"px-4", "py-3"}, "etiquetas": {"li"}}],
        # `chip` no tiene ningún `{% if %}` en su `class`: toda su firma sobrevive a cualquier
        # copia completa. El par `has-[:checked]:…` es lo que de verdad la distingue de
        # cualquier otro `<label>` con `rounded-pastilla` (la forma de "casilla disfrazada de
        # pastilla" que ningún otro control de esta app repite) — sin depender de `bg-lienzo`
        # ni de `px-4 py-2`, que sí podrían coincidir con otro elemento por accidente.
        "chip": [
            {
                "fija": {"rounded-pastilla", "has-[:checked]:bg-tinta", "has-[:checked]:text-white"},
                "etiquetas": {"label"},
            }
        ],
    }

    @staticmethod
    def _copia_el_marcado_de_la_pieza(etiqueta, clases, candidatas, comodines=0):
        """`comodines` es cuántos `{{ … }}` quedaban en el `class="…"` de la coincidencia — cada
        uno cuenta como un token cualquiera de la firma que el fichero fuente no puede ver sin
        renderizar (vuelta 12b, C2): si a una candidata le faltan menos tokens de los que hay
        comodines para cubrir, se da por copiada en vez de por exenta."""
        for candidata in candidatas:
            minimo = candidata.get("minimo", len(candidata["fija"]))
            faltan = minimo - len(candidata["fija"] & clases)
            if faltan > comodines:
                continue
            etiquetas_permitidas = candidata.get("etiquetas")
            if etiquetas_permitidas is not None and etiqueta not in etiquetas_permitidas:
                continue
            etiquetas_prohibidas = candidata.get("etiquetas_prohibidas")
            if etiquetas_prohibidas is not None and etiqueta in etiquetas_prohibidas:
                continue
            return True
        return False

    def test_ninguna_pantalla_copia_el_marcado_de_ninguna_pieza_en_vez_de_incluirla(self):
        """El "hueco" que nombra R7 en persona: una pieza copiada y pegada en vez de incluida.

        Hueco 8 (revisión, 4ª vuelta): un `assertNotIn` de la cadena fija
        "rounded-tarjeta bg-superficie" FALLA ABIERTO — en un atributo `class` las clases no
        tienen orden, así que una copia a mano con las clases al revés
        (`class="bg-superficie rounded-tarjeta …"`) pasaba en verde (medido: `Ran 44 — OK` con
        esa copia añadida a `entrenos/corregir.html`, hallazgos.md). Se compara por TOKENS,
        como ya hace `_sin_pointer_events_none_del_envoltorio_fijo` más abajo en este mismo
        fichero (`_CLASE_RE`, definido ahí): tolera comillas simples o dobles, cualquier orden
        de clases y clases de más.

        FALSO VERDE 2, mitad "copia" (revisión, 6ª vuelta): esta comprobación, antes de esta
        vuelta, sólo miraba las dos clases de `tarjeta_abre` — la pieza más repetida, pero
        sólo UNA de nueve. Pegando a mano el marcado de OTRA pieza (`numero_grande`) dentro de
        `entrenos/ver.html`, en vez de incluirla, el revisor midió `Ran 44 — OK`: la red no se
        enteraba. Mismo bucle de antes, ahora contra un DICCIONARIO de pieza → firma de clase
        (`_FIRMAS_DE_CLASE_POR_PIEZA`, arriba) en vez de sólo `tarjeta`.

        FALSO VERDE 2, mitad "el fichero no es el HTML" (revisión, 7ª vuelta): esta
        comprobación leía el `class="…"` del FICHERO fuente con `_CLASE_RE`
        (`[^"']*` entre las dos comillas del mismo tipo) — una pieza pegada entera y literal,
        con un token de su firma envuelto en `{% if True %}` DENTRO del propio atributo
        `class` (Django la renderiza byte a byte igual: `{% if True %}py-1{% endif %}` imprime
        `py-1`), rompe ese token en fragmentos (`{%`, `if`, `True`, `%}py-1{%`, `endif`, `%}`)
        que ya no son el token de la firma — medido: `Ran 45 — OK` con esa copia. Y una pieza
        con una comilla de Django DENTRO del `class` (`{% if tono == 'racha' %}…`, el propio
        `distintivo`) hace que `_CLASE_RE` ni siquiera cierre el atributo (`[^"']*` no puede
        cruzar esa comilla simple), así que esa copia era invisible por partida doble. Se
        NORMALIZAN los `{{ … }}` y `{% … %}` de Django (se borran del texto) ANTES de buscar
        `class="…"` — lo que renderiza el navegador para un `{% if True %}` es texto plano, y
        eso es lo que se compara; `_CLASE_RE` ya no tropieza con una comilla de Django
        camuflada dentro del atributo tampoco.

        FALSO VERDE 3 (revisión, 8ª vuelta): además de las clases, ahora se captura la
        ETIQUETA que las lleva (`_CLASE_CON_ETIQUETA_RE`, abajo) — necesaria para que la
        firma de `aviso` pueda exigir "es un `<div>`, no un `<button>`" en vez de enumerar
        colores (ver la nota de `_FIRMAS_DE_CLASE_POR_PIEZA`).

        FALSO VERDE 4 (vuelta 12b, C2): una pieza pegada con UN TOKEN de su firma sustituido por
        una variable (`class="rounded-tarjeta {{ c }} p-5"`) borraba esa variable al normalizar
        y perdía el token — `{{ … }}` ya NO se borra a ciegas (ver el comentario de
        `_ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE`, arriba): se cuenta cuántas quedan dentro de cada
        `class="…"` y se pasan como comodines a `_copia_el_marcado_de_la_pieza`."""
        for ruta in PLANTILLAS:
            contenido = _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE.sub("", _texto(ruta))
            for coincidencia in _CLASE_CON_ETIQUETA_RE.finditer(contenido):
                etiqueta = coincidencia.group("etiqueta").lower()
                clases_crudas = coincidencia.group("clases")
                comodines = len(_VARIABLE_DE_DJANGO_RE.findall(clases_crudas))
                clases = set(_VARIABLE_DE_DJANGO_RE.sub(" ", clases_crudas).split())
                for pieza, candidatas in self._FIRMAS_DE_CLASE_POR_PIEZA.items():
                    self.assertFalse(
                        self._copia_el_marcado_de_la_pieza(etiqueta, clases, candidatas, comodines),
                        f"{ruta.relative_to(BASE_DIR)} copia el marcado de `{pieza}` en vez de "
                        f'incluirla con `{{% include "_ui.html#{pieza}" %}}`',
                    )


# ------------------------------------------------------------------------------------------ #
# Ayudas de alcanzabilidad (R2/R8) — que un botón redondo, su menú y sus destinos se puedan
# usar DE VERDAD, no solo que ciertas cadenas estén en el HTML. Las ocho piezas del patrón
# viven en `kcalibra/ayuda_de_alcanzabilidad.py` y se IMPORTAN, no se copian: la revisión de
# esta unidad (2ª vuelta) demostró que copiarlas a mano se dejó cuatro de las ocho y abrió
# siete agujeros medidos uno a uno (Hueco 1) — y que dejar la red sólo en el contenedor del
# menú, sin aplicarla a los otros cuatro botones redondos de la unidad, abría un octavo
# (Hueco 2).
#
# Lo único que el módulo compartido NO cubre es específico de esta unidad: el envoltorio
# `fixed` de `boton_redondo`/`boton_redondo_menu` (`_ui.html`) lleva `pointer-events-none` A
# PROPÓSITO (deja pasar el toque en el resto de la pantalla) y el elemento usable lo reactiva
# con `pointer-events-auto` — un patrón que la rueda de ajustes de la 056 (el origen del
# módulo) nunca necesitó, así que su lista negra trata `pointer-events-none` como tapadera
# INCONDICIONAL (medido: llamar a `nada_lo_tapa` tal cual sobre el botón real, sin mutar nada,
# revienta con ese envoltorio legítimo). Se resuelve aparte, de DENTRO hacia FUERA — la misma
# lógica que ya escribió la vuelta 2 —, y sólo entonces se neutraliza ESE `pointer-events-none`
# ya resuelto para que las otras siete piezas de `nada_lo_tapa` sigan comprobándose sin ese
# falso positivo.
# ------------------------------------------------------------------------------------------ #


def _resuelto_como_pointer_events_auto(caso, cadena, nombre):
    """El elemento (último de `cadena`) recibe el toque de verdad si, resolviendo
    `pointer-events` de DENTRO hacia FUERA —como un navegador: hereda del ancestro más
    cercano que lo declare—, el primero en decidir dice `auto`. Sin ninguna declaración, el
    valor por defecto del navegador es `auto`.

    Hueco 3 (revisión, 3ª vuelta): si el MISMO elemento lleva las DOS utilidades a la vez
    (`pointer-events-auto` Y `pointer-events-none` en el mismo `class`), la versión anterior
    preguntaba primero por `-auto` y devolvía `True` sin llegar a mirar `-none` — pero en el
    CSS servido `.pointer-events-none` se define DESPUÉS de `.pointer-events-auto` (misma
    especificidad, comprobado en `static/css/tailwind.css`): en un navegador real gana
    `none`, el toque no llega. Se comprueban las dos ANTES de decidir nada, y si conviven en
    el mismo elemento, es ROJO explícito, no un `True` por casualidad de orden."""
    for etiqueta, attrs in reversed(cadena):
        clases = (attrs.get("class") or "").split()
        estilo = (attrs.get("style") or "").replace(" ", "")
        tiene_auto = "pointer-events-auto" in clases or "pointer-events:auto" in estilo
        tiene_none = "pointer-events-none" in clases or "pointer-events:none" in estilo
        if tiene_auto and tiene_none:
            caso.fail(
                f"«{nombre}»: <{etiqueta}> lleva 'pointer-events-auto' Y 'pointer-events-none' "
                "en el mismo elemento — en el CSS servido gana 'none' (se define después, "
                "misma especificidad): el navegador no le deja pasar el toque"
            )
        if tiene_auto:
            return True
        if tiene_none:
            return False
    return True


_CLASE_RE = re.compile(r'''class=(["'])(?P<clases>[^"']*)\1''')


def _sin_pointer_events_none_del_envoltorio_fijo(contenido):
    """Neutraliza `pointer-events-none` SOLO en el `class` del envoltorio `fixed` de
    `boton_redondo`/`boton_redondo_menu` (`_ui.html`), que lo lleva A PROPÓSITO (nota de
    `_boton_redondo_es_alcanzable` más abajo) — nunca en el de cualquier otro elemento.

    Hueco 3 (revisión, 3ª vuelta), segunda mitad: la versión anterior hacía
    `contenido.replace("pointer-events-none", "")` sobre la página ENTERA, así que un
    `pointer-events-none` fuera de sitio en cualquier otro elemento (incluido el propio botón
    mutado con las dos utilidades a la vez) tampoco lo cazaba nadie. Se identifica el
    envoltorio por llevar el token `fixed` en el MISMO `class` —lo único que lo distingue de
    cualquier otro elemento de estas plantillas—, comparando TOKENS (no la cadena completa),
    así que tolera comillas simples o dobles, orden de clases y clases de más."""
    def _reemplazo(m):
        tokens = m.group("clases").split()
        if "pointer-events-none" in tokens and "fixed" in tokens:
            tokens = [t for t in tokens if t != "pointer-events-none"]
            comilla = m.group(1)
            return f"class={comilla}{' '.join(tokens)}{comilla}"
        return m.group(0)

    return _CLASE_RE.sub(_reemplazo, contenido)


def _boton_redondo_es_alcanzable(caso, contenido, coincide, nombre):
    """`nada_lo_tapa` (las siete piezas del módulo compartido que no son sobre
    `pointer-events`) MÁS la resolución de `pointer-events` de dentro hacia fuera que el
    módulo no cubre (ver la nota de arriba). Devuelve la cadena de ancestros, por si quien
    llama necesita mirar algún atributo del propio elemento."""
    cadena = cadena_unica(caso, contenido, coincide, nombre)
    caso.assertTrue(
        _resuelto_como_pointer_events_auto(caso, cadena, nombre),
        f"«{nombre}» queda bajo un envoltorio con 'pointer-events-none' sin que nada más "
        "cerca lo reactive con 'pointer-events-auto': en un navegador real el toque no le "
        "llega",
    )
    # Ya resuelto aparte: se neutraliza el 'pointer-events-none' del envoltorio `fixed`
    # legítimo (y SÓLO el suyo) para que el resto de `nada_lo_tapa` (hidden/invisible/
    # opacity-0/…, <template>, tabindex, aria-hidden, unicidad) no dé un rojo falso sobre
    # código bueno.
    nada_lo_tapa(
        caso, _sin_pointer_events_none_del_envoltorio_fijo(contenido), coincide, nombre
    )
    return cadena


# ------------------------------------------------------------------------------------------ #
# R8 — Progreso deja de ser la única pestaña sin botón redondo: su botón ofrece las DOS
# cosas que nombra el mapa aprobado (apuntar-el-peso.md §8, ver-tu-progreso.md §8) — apuntar
# una pesada y cerrar un día, las dos de la persona que se está mirando (`persona_objetivo`,
# no siempre la propia: `progreso/ver.html` se mira por persona).
# ------------------------------------------------------------------------------------------ #


def _es_el_boton_del_menu_de_progreso(etiqueta, attrs):
    return etiqueta == "button" and attrs.get("aria-label") == "Apuntar peso o cerrar un día"


def _es_el_menu_de_progreso(etiqueta, attrs):
    return (attrs.get("x-show") or "").strip() == "abierto"


def _es_un_destino_del_menu_de_progreso(etiqueta, attrs):
    return etiqueta == "a" and attrs.get("role") == "menuitem"


class R8_BotonRedondoDeProgresoTests(_ConAlejandroYSusDatos):
    """R8 — mismo criterio de fondo que R2 (un botón que el servidor rechazaría no se
    ofrece): las dos anclas del menú apuntan a rutas reales (no a un `#ancla` dentro de la
    misma página — Progreso no incrusta esos formularios, así que aquí SÍ toca navegar), y
    el menú entero desaparece cuando `puede_editar` es falso."""

    def test_el_menu_ofrece_apuntar_pesada_y_cerrar_dia_de_quien_se_esta_mirando(self):
        """Falso rojo confirmado (revisión, 3ª vuelta): los `assertIn` de comillas dobles
        FIJAS (`href="…"`, `aria-haspopup="true"`, `role="menu"`, `role="menuitem"`) ponían
        este test en ROJO con el menú funcionando perfectamente si el marcado se escribía con
        comillas simples — HTML igual de válido (medido con `boton_redondo_menu` reescrito
        así: `Ran 2 tests` de alcanzabilidad en VERDE, este test en ROJO; hallazgos.md). Se
        lee el HTML de verdad con `elementos_con_texto` (ya importado), como ya hace
        `test_el_boton_del_menu_se_puede_abrir_de_verdad` más abajo."""
        respuesta = self.client.get(f"/progreso/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()

        botones = elementos_con_texto(contenido, _es_el_boton_del_menu_de_progreso)
        self.assertEqual(len(botones), 1, "no hay un único botón que abra el menú de Progreso")
        # Accesible con teclado y lector de pantalla (R8), no solo con el dedo: el botón que
        # despliega el menú se anuncia como tal.
        self.assertEqual(botones[0][0].get("aria-haspopup"), "true")

        menus = elementos_con_texto(contenido, _es_el_menu_de_progreso)
        self.assertEqual(len(menus), 1, "no hay un único menú de Progreso")
        self.assertEqual(menus[0][0].get("role"), "menu")

        destinos = elementos_con_texto(contenido, _es_un_destino_del_menu_de_progreso)
        hrefs_y_textos = {(attrs.get("href"), texto) for attrs, texto in destinos}
        self.assertEqual(
            hrefs_y_textos,
            {
                (f"/perfiles/{self.alejandro.id}/peso/", "Apuntar una pesada"),
                (f"/cierres/{self.alejandro.id}/", "Cerrar un día"),
            },
        )

    def test_quien_solo_mira_no_ve_un_menu_que_el_servidor_le_rechazaria(self):
        """Aislada la PLANTILLA (mismo patrón de `RequestFactory` que
        `R2_BotonRedondoTests.test_quien_solo_mira_no_ve_un_boton_que_el_servidor_le_rechazaria`):
        con `puede_editar=False`, el bloque `accion_rapida` de Progreso tiene que quedar
        vacío del todo, no solo con el texto cambiado — ni el botón que abre el menú ni sus
        dos destinos."""
        from django.template import engines
        from django.test import RequestFactory
        from django.urls import resolve

        request = RequestFactory().get(f"/progreso/{self.alejandro.id}/")
        request.user = self.alejandro.usuario
        request.resolver_match = resolve("/progreso/")

        html = engines["django"].get_template("progreso/ver.html").render(
            {
                "persona_objetivo": self.alejandro,
                "es_propio": False,
                "puede_editar": False,
                "miembros_del_hogar": [],
                "semanas": 12,
                "semanas_min": 4,
                "semanas_max": 52,
                "tiene_alguna_medicion": False,
                "tiene_datos_en_periodo": False,
                "semanas_de_entreno": [],
                "cumplimiento": {"cerrados": 0},
            },
            request,
        )
        self.assertNotIn("Apuntar una pesada", html)
        self.assertNotIn("Cerrar un día", html)
        self.assertNotIn('aria-label="Apuntar peso o cerrar un día"', html)

    def test_el_boton_del_menu_se_puede_abrir_de_verdad(self):
        """Hueco 1 de la revisión (2ª vuelta): la primera versión de este test aplicaba
        `nada_lo_tapa` sólo al CONTENEDOR del menú, copiado a mano y sin cuatro de las ocho
        piezas del patrón de la 056. Siete mutaciones quedaban en verde (hallazgos.md, Hueco 1
        de la 2ª revisión): quitar `pointer-events-auto` del botón, taparlo con `hidden
        invisible opacity-0`, meter el menú en `<template x-if="false">`, renombrar o borrar el
        `x-data`, tapar los DOS destinos, y `tabindex="-1"` + `aria-hidden="true"` en el botón.
        Aquí se aplica `_boton_redondo_es_alcanzable` (que importa `nada_lo_tapa` del módulo
        compartido) al BOTÓN, al MENÚ y a CADA UNO de sus destinos — no sólo al contenedor —,
        más `el_estado_es_compartido` entre el botón y el menú."""
        contenido = self.client.get(f"/progreso/{self.alejandro.id}/").content.decode()

        cadena_boton = _boton_redondo_es_alcanzable(
            self, contenido, _es_el_boton_del_menu_de_progreso, "el botón del menú de Progreso"
        )
        # Anclado a `@click=`, no a la palabra suelta: el botón lleva TAMBIÉN un
        # `@click.outside="abierto = false"` (cerrar al tocar fuera), así que buscar solo
        # "abierto" dejaría verde quitarle el `@click` que ABRE. Con límites de palabra (no una
        # subcadena): `abiertoV2` no debe colar.
        attrs_boton = cadena_boton[-1][1]
        self.assertRegex(
            attrs_boton.get("@click") or "",
            r"(?<![\w$])abierto(?![\w$])",
            "el botón del menú de Progreso no ABRE el menú: los destinos estarían en el HTML "
            "y serían inalcanzables",
        )
        # Y el botón no puede estar apagado: `disabled` no dispara click en ningún navegador.
        self.assertNotIn("disabled", attrs_boton)
        self.assertNotEqual(attrs_boton.get("aria-disabled"), "true")

        # El menú entero, no sólo el botón que lo abre — el agujero que dejaba pasar tapar el
        # `<div x-show="abierto">` con `hidden` cuando sólo se miraba el contenedor.
        _boton_redondo_es_alcanzable(self, contenido, _es_el_menu_de_progreso, "el menú de Progreso")

        # Y los DOS destinos, no sólo el menú que los contiene: un menú alcanzable con sus
        # destinos tapados sigue siendo un menú inútil (pieza 8 del módulo). Identificados por
        # `role="menuitem"` Y su `href` — el `href` solo no basta: la propia pantalla repite la
        # misma ruta en un enlace de texto más abajo ("Ver tu histórico y apuntar una pesada
        # →"), y sin el `role` la unicidad de `cadena_unica` encontraría dos.
        destinos = elementos_con_texto(contenido, _es_un_destino_del_menu_de_progreso)
        self.assertEqual(len(destinos), 2, "el menú de Progreso no ofrece exactamente dos destinos")
        for attrs, texto in destinos:
            href = attrs.get("href")
            with self.subTest(destino=texto):
                _boton_redondo_es_alcanzable(
                    self, contenido,
                    lambda etiqueta, a, href=href: (
                        etiqueta == "a" and a.get("role") == "menuitem" and a.get("href") == href
                    ),
                    f"el destino «{texto}»",
                )

        # El botón y el menú tienen que colgar del MISMO `x-data` que declara `abierto`: un
        # `x-data` renombrado o duplicado deja a los dos perfectos por separado y el menú no
        # abre jamás (pieza 7 del módulo).
        el_estado_es_compartido(
            self, contenido, _es_el_boton_del_menu_de_progreso, _es_el_menu_de_progreso, "abierto",
            "el botón del menú de Progreso", "el menú de Progreso",
        )


class R8_ElMenuApuntaSiempreAQuienSeMiraTests(_ConAlejandroYSusDatos):
    """Hueco 2 de la revisión 2 (la trampa del bug 028): el único test de R8 que pide una URL
    (arriba) abre el progreso PROPIO de Alejandro, donde `persona_objetivo` y
    `request.user.persona` son la MISMA persona — indistinguibles ahí. Este test abre el
    progreso de alguien A CARGO (montaje igual que
    `hogares.tests_personas_de_la_casa._ConAlejandroYEuridiceACargo`) y exige que las dos rutas
    del menú sean las SUYAS, nunca las de quien mira: mutar los dos `{% url %}` de
    `progreso/ver.html` a `request.user.persona.id` (el bug 028 exacto) colaba en verde sin el
    `assertNotIn` de más abajo (medido, hallazgos.md). El código ya es correcto — esto es la
    red que le faltaba."""

    def setUp(self):
        super().setUp()
        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/",
            {
                "nombre": "Euridice",
                "sexo": "mujer",
                "fecha_nacimiento": "1997-06-29",
                "altura_cm": "167",
                "peso_kg": "62",
                "actividad": "moderado",
                "objetivo": "perder_grasa",
                "ajuste_pct": "",
                "dieta": "",
                "alergias": "",
                "intolerancias": "",
                "no_le_gusta": "",
            },
            follow=True,
        )
        # `follow=True` hace que este 200 sea el mismo tanto si el alta acierta como si el
        # formulario es inválido — lo que prueba que el alta no falló es que la Persona exista.
        self.assertTrue(
            Persona.objects.filter(nombre="Euridice", hogar=self.alejandro.hogar).exists()
        )  # control: el alta no falló
        self.euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)

    def test_el_menu_de_progreso_apunta_a_la_persona_a_cargo_no_a_quien_mira(self):
        """Falso rojo confirmado (revisión, 3ª vuelta), la mitad peor: los dos `assertNotIn`
        de abajo leían HTML como texto con comillas dobles FIJAS — un `assertNotIn` así
        FALLA ABIERTO por construcción (si el marcado pasara a comillas simples, la regresión
        del bug 028 volvería a colar en verde). `elementos_con_texto` (ya importado) lee el
        HTML de verdad; comparar el conjunto de destinos EXACTO ya implica que ninguno es el
        de Alejandro, sin depender de cómo estén escritas las comillas."""
        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()

        # El hueco exacto que cazó el bug 028: un menú que SIEMPRE llevara a Alejandro (quien
        # mira) en vez de a Euridice (a quien se mira) da un conjunto de hrefs DISTINTO al
        # esperado — se detecta sin necesitar un `assertNotIn` aparte, sin fallar abierto.
        destinos = elementos_con_texto(contenido, _es_un_destino_del_menu_de_progreso)
        hrefs = {attrs.get("href") for attrs, _texto in destinos}
        self.assertEqual(
            hrefs,
            {f"/perfiles/{self.euridice.id}/peso/", f"/cierres/{self.euridice.id}/"},
        )
