r"""
Tests de la unidad 054 (las-pantallas-de-la-casa.md): R1, R2, R4, R5, R6, R8 de su
especificación. R3 ("no romper nada") no tiene test propio aquí: es el resto de la suite
siguiendo en verde. R7 (la fila de ingrediente clonada por JS) se comprueba a mano, en el
navegador — se escribe en hallazgos.md, no aquí (ningún test de Django ejecuta JavaScript).
R9 se prueba importando `kcalibra.ayuda_de_alcanzabilidad` sobre el botón redondo de cada
pantalla, dentro de `R2_BotonRedondoTests` (mismo sitio que ya hace la 053 para su propio R2).
R10 (el `<h1>` de verdad) se prueba junto a R1: `_indices_del_h1_de_titulo` exige el `<h1>`
dentro de `<header>`, no solo que el texto aparezca en algún sitio.

Igual que la 053, esto se escribió ANTES de tocar las plantillas (rojo primero). Y, como allí,
una subcadena no prueba nada sobre un CSS o un HTML de una plantilla compartida
(docs/conocimiento/tailwind-4-sin-node.md) — los helpers pesados de R6/R7/alcanzabilidad se
IMPORTAN de `kcalibra.tests_pantallas`/`kcalibra.ayuda_de_alcanzabilidad` en vez de copiarse:
son la misma máquina, ya endurecida contra los mismos agujeros, y una unidad nueva copiándola a
mano fue exactamente el error que la 053 cometió con la de alcanzabilidad (ver la nota de R9 en
la especificación de esta unidad).
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from kcalibra.ayuda_de_alcanzabilidad import elementos_con_texto, nada_lo_tapa
from kcalibra.tests_pantallas import (
    _CLASE_CON_ETIQUETA_RE,
    _ETIQUETAS_DE_BLOQUE_O_COMENTARIO_RE,
    _VARIABLE_DE_DJANGO_RE,
    _NumerosDeDatoEnElTexto,
    _algun_elemento_de_la_cadena_lleva_cifra,
    _boton_redondo_es_alcanzable,
    _con_procedencia_marcada,
    _texto,
)
from hogares.models import Persona, SolicitudEntrada

BASE_DIR = Path(settings.BASE_DIR)

# Las nueve plantillas de esta unidad (todo `ficheros:` salvo `_ui.html`, el CSS compilado y
# este mismo fichero de tests) — mismo papel que `PLANTILLAS` en `kcalibra/tests_pantallas.py`:
# la lista blanca del ALCANCE, a mano y a propósito (coincide byte a byte con `ficheros:`).
PLANTILLAS = [
    BASE_DIR / "despensa" / "templates" / "despensa" / "ver.html",
    BASE_DIR / "recetas" / "templates" / "recetas" / "lista.html",
    BASE_DIR / "recetas" / "templates" / "recetas" / "detalle.html",
    BASE_DIR / "recetas" / "templates" / "recetas" / "formulario.html",
    BASE_DIR / "recetas" / "templates" / "recetas" / "_fila_ingrediente.html",
    BASE_DIR / "hogares" / "templates" / "hogares" / "mi_hogar.html",
    BASE_DIR / "hogares" / "templates" / "hogares" / "esperando_aceptacion.html",
    BASE_DIR / "hogares" / "templates" / "hogares" / "borrar_persona_a_cargo.html",
    BASE_DIR / "perfiles" / "templates" / "perfiles" / "ver.html",
]
RUTA_UI = BASE_DIR / "templates" / "_ui.html"


def _indices_del_h1_de_titulo(contenido):
    """Igual que su gemelo de `kcalibra/tests_pantallas.py` (R10 de la 053): el `<h1>` que
    `{% block titulo_grande %}` pinta dentro de `<header>`, o `None` si esta pantalla no lo
    llena. Comparar solo POSICIONES (¿el texto aparece antes de `<main>`?) no basta — R10 de
    la 053 lo midió con el bug 027: el `<title>` de `<head>` también va antes de `<main>`."""
    inicio_header = contenido.index("<header")
    fin_header = contenido.index("</header>", inicio_header) + len("</header>")
    try:
        inicio_h1 = contenido.index("<h1", inicio_header, fin_header)
    except ValueError:
        return None
    fin_h1 = contenido.index("</h1>", inicio_h1, fin_header) + len("</h1>")
    return inicio_h1, fin_h1


class _ConLaCasaMontada(PruebaConRegistroAbierto):
    """Alejandro con su cuenta, Euridice a su cargo (sin cuenta propia), Berta con su propia
    cuenta en el MISMO hogar (con el código de invitación) — así "Quién vive en la casa"
    enseña las DOS formas de estar dentro (R3 de la 024) en una sola fixture. Además: dos
    productos en la despensa (uno para el barrido de R6, R9 en la disciplina "cantidades") y
    una receta con DOS ingredientes (R4/R7 de la especificación de esta unidad)."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        respuesta_alta = self.client.post(
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
        assert respuesta_alta.status_code == 200
        self.euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)

        # Pedir entrar con el código deja la solicitud PENDIENTE (unidad 003/004): hace falta
        # que alguien de dentro la acepte — no basta con registrarse con el código correcto.
        codigo = self.alejandro.hogar.codigo
        self.client.logout()
        self.registrar_y_verificar("berta@example.com", codigo_hogar=codigo, sexo="mujer")
        self.berta = Persona.objects.get(usuario__email="berta@example.com")

        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud_de_berta = SolicitudEntrada.objects.get(
            usuario__email="berta@example.com", estado=SolicitudEntrada.PENDIENTE
        )
        respuesta_aceptar = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{solicitud_de_berta.pk}/aceptar/", follow=True
        )
        assert respuesta_aceptar.status_code == 200
        self.berta.refresh_from_db()
        assert self.berta.hogar_id == self.alejandro.hogar_id  # control: la aceptó de verdad

        respuesta_stock = self.client.post(
            "/despensa/anadir/",
            {"nombre": "Tomate", "cantidad": "2", "unidad": "lata", "categoria": "verdura"},
        )
        assert respuesta_stock.status_code == 200

        respuesta_receta = self.client.post(
            "/recetas/nueva/",
            {
                "nombre": "Crema de champiñones",
                "raciones": "4",
                "comidas": ["comida"],
                "preparacion": "Se pochan y se trituran.",
                "ingrediente_nombre": ["Champiñones", "Nata"],
                "ingrediente_cantidad": ["300", "100"],
                "ingrediente_unidad": ["g", "ml"],
            },
            follow=True,
        )
        assert respuesta_receta.status_code == 200
        from recetas.models import Receta

        self.receta = Receta.objects.get(nombre="Crema de champiñones")


# ------------------------------------------------------------------------------------------ #
# R1/R10 — cada pantalla llena `{% block titulo_grande %}` con su propio `<h1>` DE VERDAD.
# ------------------------------------------------------------------------------------------ #


class R1_TituloGrandeTests(_ConLaCasaMontada):
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

    def test_la_despensa(self):
        self._titulo_esta_en_la_cabecera("/despensa/", "La despensa")

    def test_lista_de_recetas(self):
        self._titulo_esta_en_la_cabecera("/recetas/", "Recetas")

    def test_detalle_de_una_receta(self):
        self._titulo_esta_en_la_cabecera(f"/recetas/{self.receta.id}/", "Crema de champiñones")

    def test_formulario_de_receta_nueva(self):
        self._titulo_esta_en_la_cabecera("/recetas/nueva/", "Añadir receta")

    def test_formulario_de_editar_receta(self):
        self._titulo_esta_en_la_cabecera(f"/recetas/{self.receta.id}/editar/", "Editar receta")

    def test_las_personas_de_la_casa(self):
        self._titulo_esta_en_la_cabecera("/hogares/mi-hogar/", "Las personas de la casa")

    def test_esperando_a_que_te_acepten(self):
        # Un cuarto usuario pide entrar con el código de la casa y queda pendiente: para él,
        # `/hogares/mi-hogar/` es `esperando_aceptacion.html`, no `mi_hogar.html`.
        self.client.logout()
        self.registrar_y_verificar(
            "carlos@example.com", codigo_hogar=self.alejandro.hogar.codigo, sexo="hombre"
        )
        assert SolicitudEntrada.objects.filter(
            usuario__email="carlos@example.com", estado=SolicitudEntrada.PENDIENTE
        ).exists()  # control: sigue pendiente, no se coló
        self._titulo_esta_en_la_cabecera("/hogares/mi-hogar/", "Esperando a que te acepten")

    def test_borrar_la_ficha_de_una_persona_a_cargo(self):
        self._titulo_esta_en_la_cabecera(
            f"/hogares/mi-hogar/personas/{self.euridice.id}/borrar/",
            "Borrar la ficha de Euridice",
        )

    def test_tus_datos_propios(self):
        self._titulo_esta_en_la_cabecera("/perfiles/", "Tus datos")

    def test_los_datos_de_otra_persona_de_la_casa(self):
        self._titulo_esta_en_la_cabecera(f"/perfiles/{self.berta.id}/", "Datos de Berta")


# ------------------------------------------------------------------------------------------ #
# R2/R9 — el botón redondo lleva al formulario que ya vive en esa pantalla, y se puede USAR de
# verdad (alcanzabilidad importada, no copiada — ver la nota de la especificación).
# ------------------------------------------------------------------------------------------ #


class R2_BotonRedondoTests(_ConLaCasaMontada):
    def test_la_despensa_el_boton_lleva_al_formulario_de_anadir_y_se_puede_usar(self):
        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()

        coincide_boton = lambda e, a: e == "a" and a.get("aria-label") == "Añadir producto"
        botones = elementos_con_texto(contenido, coincide_boton)
        self.assertEqual(len(botones), 1, "no hay un único botón redondo «Añadir producto»")
        self.assertEqual(botones[0][0].get("href"), "#formulario-despensa")
        self.assertTrue(
            elementos_con_texto(contenido, lambda e, a: a.get("id") == "formulario-despensa"),
            "el botón redondo apunta a #formulario-despensa, pero no hay ningún elemento con ese id",
        )

        # `nada_lo_tapa` a secas revienta con el envoltorio `fixed pointer-events-none` que
        # `boton_redondo` lleva A PROPÓSITO (`_ui.html`) — `_boton_redondo_es_alcanzable`
        # (importada, no copiada: nota de R9 de la especificación) lo resuelve de dentro hacia
        # fuera antes de comprobar el resto.
        _boton_redondo_es_alcanzable(self, contenido, coincide_boton, "el botón redondo «Añadir producto»")
        nada_lo_tapa(
            self, contenido, lambda e, a: a.get("id") == "formulario-despensa",
            "el formulario de añadir producto",
        )

    def test_recetas_el_boton_lleva_a_la_receta_nueva_y_se_puede_usar(self):
        respuesta = self.client.get("/recetas/")
        contenido = respuesta.content.decode()

        coincide_boton = lambda e, a: e == "a" and a.get("aria-label") == "Nueva receta"
        botones = elementos_con_texto(contenido, coincide_boton)
        self.assertEqual(len(botones), 1, "no hay un único botón redondo «Nueva receta»")
        # Aquí el botón lleva a OTRA pantalla (el formulario de recetas vive en su propia
        # ruta, a diferencia de la despensa: ver "Diseño conversado" de la especificación) —
        # no un ancla dentro de la misma página, así que se comprueba el destino real.
        self.assertEqual(botones[0][0].get("href"), "/recetas/nueva/")

        _boton_redondo_es_alcanzable(self, contenido, coincide_boton, "el botón redondo «Nueva receta»")

    def test_quien_solo_mira_una_receta_no_ve_un_boton_de_anadir_ahi(self):
        """El criterio de fondo de R2 ("nunca se ofrece algo que no lleve a ningún sitio de
        esta pantalla"): el detalle de una receta no tiene botón redondo — el «+» de esta
        unidad es sólo para Stock y Recetas (lista), no para cada ficha."""
        respuesta = self.client.get(f"/recetas/{self.receta.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn('aria-label="Añadir producto"', contenido)
        self.assertNotIn('aria-label="Nueva receta"', contenido)


# ------------------------------------------------------------------------------------------ #
# R4 — ninguna de las nueve plantillas conserva utilidades de la paleta vieja.
# ------------------------------------------------------------------------------------------ #

_PALETA_VIEJA_RE = re.compile(r"\b(?:emerald|slate)-\d{2,3}\b")


class R4_SinPaletaViejaTests(SimpleTestCase):
    databases = set()

    def test_ninguna_plantilla_de_la_unidad_usa_emerald_ni_slate(self):
        con_paleta_vieja = {}
        for ruta in PLANTILLAS + [RUTA_UI]:
            hallazgos = _PALETA_VIEJA_RE.findall(_texto(ruta))
            if hallazgos:
                con_paleta_vieja[str(ruta.relative_to(BASE_DIR))] = hallazgos
        self.assertEqual(con_paleta_vieja, {}, f"quedan clases de la paleta vieja: {con_paleta_vieja}")


# ------------------------------------------------------------------------------------------ #
# R5 — las piezas se REUSAN de `_ui.html`, no se copian; una pieza duplicada es un hueco.
# ------------------------------------------------------------------------------------------ #

_NOMBRE_DE_PARTIALDEF_RE = re.compile(r"\{%\s*partialdef\s+([\w-]+)\b(?:\s+inline)?\s*%\}")


def _piezas_portadas_de_ui_html():
    vistas = []
    for nombre in _NOMBRE_DE_PARTIALDEF_RE.findall(_texto(RUTA_UI)):
        if not nombre.startswith("_") and nombre not in vistas:
            vistas.append(nombre)
    return vistas


PIEZAS_PORTADAS = _piezas_portadas_de_ui_html()

# La foto de HOY de qué piezas usan las nueve pantallas de esta unidad (mismo motivo que
# `PIEZAS_QUE_ESTA_UNIDAD_USA` de la 053, FR-I: una pieza que _ui.html porte para la 055 y que
# esta unidad no conozca no debe ponerla en rojo).
PIEZAS_QUE_ESTA_UNIDAD_USA = frozenset({
    "tarjeta_abre", "tarjeta_cierra", "titulo_seccion", "boton", "aviso", "distintivo",
    "boton_redondo", "fila_lista_abre", "fila_lista_cierra", "chip", "segmentado",
})


class R5_PiezasCompartidasUnaSolaVezTests(SimpleTestCase):
    databases = set()

    def test_cada_pieza_se_define_exactamente_una_vez_en_ui_html(self):
        contenido = "\n".join(_texto(p) for p in PLANTILLAS + [RUTA_UI])
        conteos = {}
        for pieza in PIEZAS_PORTADAS:
            conteos[pieza] = len(
                re.findall(rf"\{{%\s*partialdef\s+{pieza}\b(?:\s+inline)?\s*%\}}", contenido)
            )
        self.assertEqual(
            conteos, {pieza: 1 for pieza in PIEZAS_PORTADAS},
            f"alguna pieza no está definida exactamente una vez: {conteos}",
        )

    def test_cada_pieza_usada_la_incluye_alguna_de_las_nueve_pantallas(self):
        fuente = "\n".join(_texto(p) for p in PLANTILLAS)
        sin_uso = [
            pieza for pieza in PIEZAS_QUE_ESTA_UNIDAD_USA
            if not re.search(rf"""_ui\.html#{pieza}["']""", fuente)
        ]
        self.assertEqual(sin_uso, [], f"piezas que ninguna pantalla incluye: {sin_uso}")

    # Firma de clases por pieza — mismo formato que `kcalibra/tests_pantallas.py`
    # (`_FIRMAS_DE_CLASE_POR_PIEZA`): candidatas independientes, cada una con sus tokens FIJOS
    # (todos por defecto, o un `minimo`), opcionalmente acotada por etiqueta. El token
    # discriminante nunca es uno que un copiador omita por accidente (FALSO VERDE 3 de la
    # 053): es la FORMA de la pieza.
    _FIRMAS_DE_CLASE_POR_PIEZA = {
        "tarjeta_abre": [{"fija": {"rounded-tarjeta", "bg-superficie"}}],
        "titulo_seccion": [{"fija": {"mb-3", "items-end", "justify-between"}}],
        "boton": [{"fija": {"px-6", "py-3.5", "transition-opacity", "disabled:opacity-40"}}],
        "aviso": [
            {
                "fija": {"rounded-control", "px-4", "py-3", "font-medium"},
                "etiquetas_prohibidas": {"button", "a"},
            }
        ],
        "distintivo": [{"fija": {"rounded-pastilla", "px-2.5", "py-1"}}],
        "boton_redondo": [{"fija": {"pointer-events-none", "fixed", "inset-x-0", "z-40"}}],
        # Un `<li>` con exactamente estas dos clases: la forma de `fila_lista_abre` (el borde
        # superior es condicional — `border-t border-linea` sólo cuando `primera` es falso —
        # así que no puede ser parte de la firma: una fila copiada a mano de la PRIMERA fila de
        # una tarjeta, sin borde, seguiría siendo una copia y este par de tokens la caza igual).
        "fila_lista_abre": [{"fija": {"px-4", "py-3"}, "etiquetas": {"li"}}],
        "chip": [
            {
                "fija": {"cursor-pointer", "has-[:checked]:bg-tinta", "has-[:checked]:text-white"},
                "etiquetas": {"label"},
            }
        ],
        "segmentado": [{"fija": {"mb-4", "gap-1", "rounded-pastilla", "bg-lienzo"}}],
    }

    def test_toda_pieza_incluida_por_esta_unidad_tiene_firma_de_clase(self):
        fuente = "\n".join(_texto(p) for p in PLANTILLAS)
        piezas_incluidas = [
            pieza for pieza in PIEZAS_PORTADAS
            if re.search(rf"""_ui\.html#{pieza}["']""", fuente)
        ]
        sin_firma = [
            pieza for pieza in piezas_incluidas
            if not pieza.endswith("_cierra") and pieza not in self._FIRMAS_DE_CLASE_POR_PIEZA
        ]
        self.assertEqual(sin_firma, [], f"piezas incluidas sin firma de clase: {sin_firma}")

    @staticmethod
    def _copia_el_marcado_de_la_pieza(etiqueta, clases, candidatas, comodines=0):
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
# R6 — todo número de dato (cantidades, raciones, calorías) va con la clase `.cifra`.
# ------------------------------------------------------------------------------------------ #


def _rutas_de_las_pantallas_con_datos(persona_otra, receta):
    """Las rutas de verdad que tienen algo que mostrar con la fixture de esta unidad — mismo
    papel que `_rutas_de_las_siete_pantallas` de `kcalibra/tests_pantallas.py`."""
    return [
        "/despensa/",
        "/recetas/",
        f"/recetas/{receta.id}/",
        f"/recetas/{receta.id}/editar/",
        "/hogares/mi-hogar/",
        f"/perfiles/{persona_otra.id}/",
    ]


class R6_CifraEnLosNumerosDeDatoTests(_ConLaCasaMontada):
    def _elemento_lleva_cifra(self, ruta, id_elemento):
        respuesta = self.client.get(ruta)
        contenido = respuesta.content.decode()
        coincide = lambda e, a, id_elemento=id_elemento: a.get("id") == id_elemento
        elementos = elementos_con_texto(contenido, coincide)
        self.assertEqual(len(elementos), 1, f"no hay un único elemento con id={id_elemento!r} en {ruta}")
        clases = (elementos[0][0].get("class") or "").split()
        self.assertIn("cifra", clases, f"{id_elemento} no lleva `.cifra` en {ruta}")

    def test_la_cantidad_legible_de_un_producto_lleva_cifra(self):
        producto_id = self.client.get("/despensa/").content.decode()
        m = re.search(r'id="cantidad-legible-(\d+)"', producto_id)
        self.assertIsNotNone(m, "no se encontró ningún producto en la despensa")
        self._elemento_lleva_cifra("/despensa/", f"cantidad-legible-{m.group(1)}")

    def test_las_calorias_del_dia_llevan_cifra(self):
        self._elemento_lleva_cifra(f"/perfiles/{self.alejandro.id}/", "calorias-del-dia")

    @staticmethod
    def _es_la_excepcion_de_r3_sobre_r6(ruta, cadena):
        """`perfiles/ver.html` imprime "Proteína: <strong>N g</strong>" (y Grasa/Carbohidratos)
        SIN `.cifra` en el `<strong>`, a propósito: `perfiles/tests.py` (unidad 004, fuera de
        `ficheros:` de esta unidad) exige el literal EXACTO `<strong>136 g</strong>` — un
        `class="cifra"` ahí rompería ese assert (medido: R3 es "el que manda"). Es la MISMA
        familia de conflicto que ya resolvió `paginas/templates/paginas/inicio.html` para su
        propio "N kcal" (comentario de esa plantilla), aplicada aquí al mismo patrón. Se acota
        a la ruta y a la FORMA exacta del hueco (último ancestro `<strong>` sin clase, dentro de
        un `<p>`) para no eximir, sin querer, cualquier otro número futuro de esta pantalla."""
        if "/perfiles/" not in ruta:
            return False
        if len(cadena) < 2:
            return False
        etiqueta_strong, attrs_strong = cadena[-1]
        etiqueta_p, _ = cadena[-2]
        return (
            etiqueta_strong == "strong"
            and not (attrs_strong.get("class") or "").strip()
            and etiqueta_p == "p"
        )

    def test_ningun_numero_de_dato_escrito_en_linea_se_queda_sin_cifra(self):
        """Barrido de verdad sobre HTML renderizado, no una muestra escrita a mano — mismo
        patrón (y la misma máquina, importada) que `test_ningun_numero_de_dato_escrito_en_
        linea_se_queda_sin_cifra` de `kcalibra/tests_pantallas.py` (vuelta 12 de la 053: la
        exención sale de si el sub-trozo viene de una variable, no de comparar valores)."""
        sin_cifra = []
        with _con_procedencia_marcada():
            for ruta in _rutas_de_las_pantallas_con_datos(self.berta, self.receta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200, ruta)
                lector = _NumerosDeDatoEnElTexto()
                lector.feed(respuesta.content.decode())
                for numero, cadena, de_variable in lector.hallazgos:
                    if not de_variable:
                        continue
                    if _algun_elemento_de_la_cadena_lleva_cifra(cadena):
                        continue
                    if self._es_la_excepcion_de_r3_sobre_r6(ruta, cadena):
                        continue
                    sin_cifra.append(f"{ruta}: «{numero}» dentro de {[e for e, _ in cadena]}")
        self.assertEqual(sin_cifra, [], f"números de dato sin `.cifra`, ni propio ni heredado: {sin_cifra}")


# ------------------------------------------------------------------------------------------ #
# R8 — el aviso de "no puedes tocar esto" sigue saliendo, con el mismo texto, en la pieza
# `aviso`.
#
# Medido (no supuesto): ninguna de las nueve pantallas de esta unidad muestra HOY ese aviso.
# `perfiles/ver.html` (la única candidata real: es la que enseña el perfil de otra persona)
# sólo deja de mostrar el formulario cuando `puede_editar` es falso — no hay, ni había antes
# de esta unidad, ningún texto de "esto es de otra persona" en ese fichero (comprobado leyendo
# el fichero de antes de esta unidad y con `grep` en todo el árbol: cero coincidencias de "no
# puedes"/"es de otra persona"/"solo lectura" en las nueve plantillas). El texto que SÍ existe
# con ese propósito ("Solo lectura: el resto del hogar ve el peso, pero solo…") vive en
# `perfiles/templates/perfiles/peso.html:47-50` — un fichero de la unidad 053, fuera de
# `ficheros:` de ÉSTA. Se deja escrito en `hallazgos.md` como discrepancia entre la
# especificación y lo medido; aquí se prueba lo que SÍ es cierto hoy y no puede romperse: quien
# no puede editar sigue viendo sus datos, en solo lectura, sin ningún formulario ni botón.
# ------------------------------------------------------------------------------------------ #


class R8_SoloLecturaSinFormularioTests(_ConLaCasaMontada):
    def test_quien_no_puede_editar_ve_los_datos_sin_formulario_ni_boton_guardar(self):
        respuesta = self.client.get(f"/perfiles/{self.berta.id}/")
        contenido = respuesta.content.decode()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("<form", contenido.split('id="tarjeta-perfil"', 1)[1].split("</div>", 1)[0])
        self.assertNotIn(">Guardar<", contenido)
