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
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from kcalibra.ayuda_de_alcanzabilidad import (
    cadena_unica,
    el_estado_es_compartido,
    elementos_con_texto,
    nada_lo_tapa,
)
from hogares.models import Persona

BASE_DIR = Path(settings.BASE_DIR)

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

# Las nueve piezas que nombra la especificación (R7) más `boton_redondo`, el hueco de
# `{% block accion_rapida %}` — ver la nota de `_ui.html` sobre por qué esta última también
# vive ahí. `barra_macro` se porta (lo pide el paso 1 del "Cómo") pero NINGUNA de las diez
# pantallas de esta unidad tiene un dato de "gramos + porcentaje" que mostrar con ella —
# mismo caso que los tokens de macro/racha en la 050 ("nace con la primera pantalla que la
# use"): existe, una sola vez, lista para cuando haga falta, pero no está en el barrido de
# "piezas usadas" de abajo.
PIEZAS_PORTADAS = [
    "tarjeta_abre",
    "tarjeta_cierra",
    "titulo_seccion",
    "numero_grande",
    "pildora_macro",
    "barra_macro",
    "anillo_abre",
    "anillo_cierra",
    "boton",
    "aviso",
    "distintivo",
    "boton_redondo",
    "boton_redondo_menu",
]
PIEZAS_USADAS_EN_LAS_PANTALLAS = [p for p in PIEZAS_PORTADAS if p != "barra_macro"]


def _texto(ruta):
    return ruta.read_text(encoding="utf-8")


def _indice_inicio_main(contenido):
    """El primer carácter DESPUÉS del que empieza `<main>` (base.html): todo lo que hay antes
    de aquí es cabecera (nombre, `{% block titulo_grande %}`, ajustes) — nunca el contenido de
    la pantalla."""
    return contenido.index('<main class="space-y-4 px-4 pb-32">')


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
    """R1 — el título de cada pantalla sale DENTRO de la cabecera (antes de `<main>`), no
    suelto en cualquier parte del contenido: si una pantalla dejara el título donde estaba
    antes (dentro de `{% block content %}`) el título seguiría "apareciendo en la página",
    pero no llenaría `{% block titulo_grande %}` — de ahí que el test compare posiciones, no
    solo presencia."""

    def _titulo_esta_en_la_cabecera(self, ruta, titulo_esperado):
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 200, ruta)
        contenido = respuesta.content.decode()
        self.assertIn(titulo_esperado, contenido, ruta)
        self.assertLess(
            contenido.index(titulo_esperado),
            _indice_inicio_main(contenido),
            f"'{titulo_esperado}' no está en la cabecera (antes de <main>) en {ruta}",
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

    def _ancla_lleva_a_un_elemento_que_existe(self, ruta, id_destino):
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 200, ruta)
        contenido = respuesta.content.decode()
        self.assertIn(f'href="#{id_destino}"', contenido, ruta)
        self.assertIn(f'id="{id_destino}"', contenido, ruta)

    def test_apuntar_el_plan_lleva_al_formulario_de_apuntar_comida(self):
        self._ancla_lleva_a_un_elemento_que_existe(
            f"/planes/{self.alejandro.id}/apuntar/", "formulario-plan"
        )

    def test_entrenos_lleva_al_formulario_de_apuntar_entreno(self):
        self._ancla_lleva_a_un_elemento_que_existe("/entrenos/", "formulario-entreno")

    def test_tu_peso_lleva_al_formulario_de_apuntar_peso(self):
        self._ancla_lleva_a_un_elemento_que_existe("/perfiles/peso/", "formulario-peso")

    def test_cerrar_un_dia_lleva_a_su_formulario(self):
        self._ancla_lleva_a_un_elemento_que_existe(
            f"/cierres/{self.alejandro.id}/", "formulario-cierre"
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
_PILDORA_MACRO_RE = re.compile(r'<span class="inline-flex items-center gap-1\.5 rounded-pastilla.*?</span>\s*</span>', re.S)


class R5_NombreDelMacroSiempreEscritoTests(_ConAlejandroYSusDatos):
    def test_las_pildoras_de_la_comida_llevan_su_nombre_junto_al_color(self):
        respuesta = self.client.get(f"/planes/{self.alejandro.id}/apuntar/")
        contenido = respuesta.content.decode()
        pildoras = _PILDORA_MACRO_RE.findall(contenido)
        self.assertEqual(len(pildoras), 3, "se esperaban las 3 píldoras de la comida apuntada")

        # R9 — el vocabulario de la app, no el del prototipo viejo: "Carbohidratos" y "Grasa"
        # (`planes/forms.py`: "Carbohidratos (g)"/"Grasa (g)"), nunca "Carbos"/"Grasas".
        nombres_esperados = {"Proteína", "Grasa", "Carbohidratos"}
        nombres_vistos = set()
        for pildora in pildoras:
            # Cada chip trae su nombre Y sus gramos con `.cifra` — ni el nombre solo (sin
            # dato) ni el dato solo (sin nombre, el fallo que prohíbe R5) pasa este assert.
            self.assertRegex(pildora, r"\d+\s*g", pildora)
            for nombre in nombres_esperados:
                if nombre in pildora:
                    nombres_vistos.add(nombre)
        self.assertEqual(nombres_vistos, nombres_esperados)

    def test_la_pieza_pildora_macro_no_tiene_un_camino_sin_nombre(self):
        """Mutación fijada en el propio test: `_pildora_macro_interna` (`_ui.html`) siempre
        imprime `{{ nombre_macro }}` antes de los gramos — se comprueba aquí, sobre la pieza
        en sí, no solo sobre una pantalla que la usa (para que un futuro uso nuevo de la
        pieza no pueda perder el nombre sin que este test lo note)."""
        contenido = _texto(RUTA_UI)
        interna = re.search(
            r"\{% partialdef _pildora_macro_interna %\}(.*?)\{% endpartialdef %\}",
            contenido,
            re.S,
        ).group(1)
        self.assertIn("{{ nombre_macro }}", interna)
        self.assertIn("{{ gramos }} g", interna)
        # El nombre no puede ir detrás de un `{% if %}` que lo esconda: tiene que estar en la
        # rama incondicional del partial (mismo criterio que exige R5: "SIEMPRE").
        self.assertNotIn("{% if", interna)


# ------------------------------------------------------------------------------------------ #
# R6 — todo número de dato lleva la clase `.cifra`.
# ------------------------------------------------------------------------------------------ #


class R6_CifraEnLosNumerosDeDatoTests(_ConAlejandroYSusDatos):
    def _elemento_lleva_cifra(self, ruta, id_elemento):
        respuesta = self.client.get(ruta)
        contenido = respuesta.content.decode()
        # El id y la clase `cifra` tienen que estar en el MISMO atributo `class`, pegados al
        # id del elemento — no en cualquier parte de la respuesta (una `.cifra` suelta en
        # otro número de la misma pantalla no demuestra nada de ESTE número).
        self.assertRegex(
            contenido,
            rf'id="{id_elemento}"\s+class="cifra\b',
            f"{id_elemento} no lleva `.cifra` en {ruta}",
        )

    def test_kcal_quemadas_hoy_lleva_cifra(self):
        self._elemento_lleva_cifra("/entrenos/", "calorias-quemadas-hoy")

    def test_peso_de_la_bascula_lleva_cifra(self):
        self._elemento_lleva_cifra("/perfiles/peso/", "peso-bascula")

    def test_peso_de_calculo_lleva_cifra(self):
        self._elemento_lleva_cifra("/perfiles/peso/", "peso-calculo")


# ------------------------------------------------------------------------------------------ #
# R7 — las piezas compartidas viven UNA SOLA VEZ, en `_ui.html`, y las pantallas las usan.
# ------------------------------------------------------------------------------------------ #


class R7_PiezasCompartidasUnaSolaVezTests(SimpleTestCase):
    databases = set()

    def test_cada_pieza_se_define_exactamente_una_vez_en_ui_html(self):
        contenido = _texto(RUTA_UI)
        conteos = {}
        for pieza in PIEZAS_PORTADAS:
            conteos[pieza] = len(re.findall(rf"\{{% partialdef {pieza} %\}}", contenido))
        self.assertEqual(
            conteos,
            {pieza: 1 for pieza in PIEZAS_PORTADAS},
            f"alguna pieza no está definida exactamente una vez: {conteos}",
        )

    def test_cada_pieza_usada_la_incluye_alguna_de_las_diez_pantallas(self):
        fuente_de_las_pantallas = "\n".join(_texto(p) for p in PLANTILLAS)
        sin_uso = [
            pieza
            for pieza in PIEZAS_USADAS_EN_LAS_PANTALLAS
            if f'_ui.html#{pieza}"' not in fuente_de_las_pantallas
        ]
        self.assertEqual(sin_uso, [], f"piezas portadas que ninguna pantalla incluye: {sin_uso}")

    def test_ninguna_pantalla_copia_el_marcado_de_la_tarjeta_en_vez_de_incluirlo(self):
        """El "hueco" que nombra R7 en persona: una pieza copiada y pegada en vez de incluida.
        Se comprueba con la más repetida de las nueve (`tarjeta`, en las nueve plantillas):
        ninguna puede tener el marcado (`rounded-tarjeta bg-superficie`) escrito a mano, solo
        el `{% include %}`."""
        for ruta in PLANTILLAS:
            contenido = _texto(ruta)
            self.assertNotIn(
                "rounded-tarjeta bg-superficie",
                contenido,
                f"{ruta.relative_to(BASE_DIR)} copia el marcado de `tarjeta` en vez de "
                "incluirla con `{% include \"_ui.html#tarjeta_abre\" %}`",
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


def _resuelto_como_pointer_events_auto(cadena):
    """El elemento (último de `cadena`) recibe el toque de verdad si, resolviendo
    `pointer-events` de DENTRO hacia FUERA —como un navegador: hereda del ancestro más
    cercano que lo declare—, el primero en decidir dice `auto`. Sin ninguna declaración, el
    valor por defecto del navegador es `auto`."""
    for etiqueta, attrs in reversed(cadena):
        clases = (attrs.get("class") or "").split()
        estilo = (attrs.get("style") or "").replace(" ", "")
        if "pointer-events-auto" in clases or "pointer-events:auto" in estilo:
            return True
        if "pointer-events-none" in clases or "pointer-events:none" in estilo:
            return False
    return True


def _boton_redondo_es_alcanzable(caso, contenido, coincide, nombre):
    """`nada_lo_tapa` (las siete piezas del módulo compartido que no son sobre
    `pointer-events`) MÁS la resolución de `pointer-events` de dentro hacia fuera que el
    módulo no cubre (ver la nota de arriba). Devuelve la cadena de ancestros, por si quien
    llama necesita mirar algún atributo del propio elemento."""
    cadena = cadena_unica(caso, contenido, coincide, nombre)
    caso.assertTrue(
        _resuelto_como_pointer_events_auto(cadena),
        f"«{nombre}» queda bajo un envoltorio con 'pointer-events-none' sin que nada más "
        "cerca lo reactive con 'pointer-events-auto': en un navegador real el toque no le "
        "llega",
    )
    # Ya resuelto aparte: se neutraliza el único 'pointer-events-none' legítimo de la página
    # para que el resto de `nada_lo_tapa` (hidden/invisible/opacity-0/…, <template>, tabindex,
    # aria-hidden, unicidad) no dé un rojo falso sobre código bueno.
    nada_lo_tapa(caso, contenido.replace("pointer-events-none", ""), coincide, nombre)
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
        respuesta = self.client.get(f"/progreso/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn(f'href="/perfiles/{self.alejandro.id}/peso/"', contenido)
        self.assertIn(f'href="/cierres/{self.alejandro.id}/"', contenido)
        self.assertIn("Apuntar una pesada", contenido)
        self.assertIn("Cerrar un día", contenido)
        # Accesible con teclado y lector de pantalla (R8), no solo con el dedo: el botón que
        # despliega el menú se anuncia como tal y dice qué desplegará.
        self.assertIn('aria-haspopup="true"', contenido)
        self.assertIn('role="menu"', contenido)
        self.assertIn('role="menuitem"', contenido)

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
        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn(f'href="/perfiles/{self.euridice.id}/peso/"', contenido)
        self.assertIn(f'href="/cierres/{self.euridice.id}/"', contenido)
        # El hueco exacto que cazó el bug 028: sin estos dos `assertNotIn`, un menú que
        # SIEMPRE llevara a Alejandro (quien mira) en vez de a Euridice (a quien se mira)
        # seguía pasando por los dos `assertIn` de arriba.
        self.assertNotIn(f'href="/perfiles/{self.alejandro.id}/peso/"', contenido)
        self.assertNotIn(f'href="/cierres/{self.alejandro.id}/"', contenido)
