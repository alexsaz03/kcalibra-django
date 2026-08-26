r"""
Tests de la unidad 050 (el-marco-de-app-de-movil.md): R1-R7 de su especificación.

El marco compartido (`templates/base.html`, `templates/_iconos.html`,
`assets/tailwind/input.css` -> `static/css/tailwind.css`) es lo único que cambia esta unidad.
Ninguna pantalla se toca, así que estos tests solo miran el MARCO: la barra inferior de cinco
pestañas, el menú de ajustes de la cabecera, la pestaña activa, el caso sin sesión, los tokens
del CSS compilado y las dos curas de R6.

Escritos ANTES de tocar `templates/base.html` (tests primero y en rojo, igual que el resto de
la suite) — hoy fallan contra el marco de la barra de arriba plana.
"""

import re

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from kcalibra.ayuda_de_alcanzabilidad import (
    el_estado_es_compartido,
    atributos,
    elementos_con_texto,
    nada_lo_tapa,
    re_de_atributo,
)
from hogares.models import Persona
from recetas.models import Receta

# --- Ayudas para leer la barra inferior sin depender del orden de los atributos ---------- #

_ANCLA_RE = re.compile(r"<a\b[^>]*>.*?</a>", re.S)
_HREF_RE = re.compile(r'href="([^"]+)"')
_ETIQUETA_RE = re.compile(r"<span[^>]*>([^<]+)</span>")


def _zona_de_la_barra_inferior(contenido):
    inicio = contenido.index('aria-label="Navegación principal"')
    fin = contenido.index("</nav>", inicio)
    return contenido[inicio:fin]


def _pestanas(contenido):
    """Devuelve [(etiqueta, href, activa), ...] en el orden en que aparecen en la barra."""
    zona = _zona_de_la_barra_inferior(contenido)
    pestanas = []
    for ancla in _ANCLA_RE.findall(zona):
        href = _HREF_RE.search(ancla).group(1)
        etiqueta = _ETIQUETA_RE.search(ancla).group(1).strip()
        activa = 'aria-current="page"' in ancla
        pestanas.append((etiqueta, href, activa))
    return pestanas


class _ConAlejandroYSuHogar(PruebaConRegistroAbierto):
    """Alejandro, con sesión abierta y su `Persona` (toda cuenta nace con la suya,
    `hogares/signals.py`), en su propio hogar."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")


class R1_CincoPestanasTests(_ConAlejandroYSuHogar):
    """R1 — la barra inferior trae exactamente cinco pestañas, en orden, que llevan a las
    cinco rutas del mapa."""

    def test_las_cinco_pestanas_estan_en_orden_y_apuntan_a_sus_rutas(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        pestanas = _pestanas(contenido)

        esperadas = [
            ("Inicio", "/"),
            ("Plan", f"/planes/{self.alejandro.id}/apuntar/"),
            ("Stock", "/despensa/"),
            ("Entrenos", "/entrenos/"),
            ("Progreso", "/progreso/"),
        ]
        self.assertEqual(
            [(etiqueta, href) for etiqueta, href, _ in pestanas],
            esperadas,
        )


class R2_NueveDestinosTests(_ConAlejandroYSuHogar):
    """R2 — el criterio de "no romper nada": los nueve destinos de la barra de hoy siguen
    alcanzables desde el marco nuevo (cinco como pestañas, cuatro más Salir en ajustes).

    Unidad 057, R3 — ÚNICA excepción autorizada a R6 ("no romper nada"), escrita en el propio
    contrato: `/perfiles/peso/` y `/recetas/` salen de la rueda de ajustes (que adelgaza a
    cuatro: Tus datos, El hogar, Cambiar tu contraseña, Salir — ver
    `R3_LaRuedaAdelgazaACuatroTests`, más abajo). Los NUEVE destinos siguen existiendo y
    siguen alcanzables — nada se ha quitado — pero estos dos ya no cuelgan de la rueda de la
    portada: `/perfiles/peso/` se alcanza desde Progreso (el botón redondo) y `/recetas/`
    desde su propia pestaña dentro de Plan (el segmentado, R1 de la 057). Por eso este test ya
    no los busca AQUÍ — la red que sí prueba que los nueve siguen alcanzables desde ALGUNA
    parte de la app es `kcalibra/tests_nada_escondido.py` (R4 de la 057), que manda sobre
    ésta."""

    def test_los_nueve_destinos_siguen_alcanzables(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()

        # Leído del HTML PARSEADO y no del texto: `href='/x'` con comillas simples es HTML igual
        # de válido y ningún navegador lo distingue, pero un `assertIn` con comillas dobles fijas
        # lo dejaba en ROJO con el enlace funcionando. Falso rojo, cazado en la 14ª revisión de la
        # 056 en otras dos piezas; estas nueve tenían el mismo defecto.
        rutas = {
            attrs.get("href")
            for attrs, _ in elementos_con_texto(contenido, lambda e, a: e == "a" and "href" in a)
        }
        for ruta in ("/", "/progreso/", "/entrenos/", "/despensa/",       # las pestañas (R1)
                     "/perfiles/", "/hogares/mi-hogar/"):
            with self.subTest(destino=ruta):
                self.assertIn(ruta, rutas)

        # Salir: un formulario que postea al logout de allauth (como hoy).
        acciones = {
            attrs.get("action")
            for attrs, _ in elementos_con_texto(contenido, lambda e, a: e == "form")
        }
        self.assertIn("/cuentas/logout/", acciones)

    def test_el_enlace_a_recetas_dice_recetas_a_secas(self):
        """`recetas/tests.py:501` ya exige `>Recetas<` literal — la red del padre."""
        contenido = self.client.get("/recetas/").content.decode()
        enlaces = elementos_con_texto(contenido, lambda e, a: e == "a" and a.get("href") == "/recetas/")
        self.assertTrue(enlaces, "no hay ningún enlace a /recetas/")
        self.assertIn("Recetas", [texto for _, texto in enlaces])

    def test_el_enlace_a_el_hogar_dice_el_hogar_a_secas(self):
        """`perfiles/tests.py:1598` ya exige `>El hogar<` literal — la red del padre."""
        respuesta = self.client.get("/perfiles/")
        contenido = respuesta.content.decode()
        self.assertIn(">El hogar<", contenido)


class R3_PestanaActivaTests(_ConAlejandroYSuHogar):
    """R3 — la pestaña activa es una, y solo una, y es la que toca (incluidas
    subpantallas)."""

    def test_en_el_inicio_la_encendida_es_inicio_y_solo_ella(self):
        respuesta = self.client.get("/")
        contenido = respuesta.content.decode()
        self.assertEqual(contenido.count('aria-current="page"'), 1)
        activas = [etiqueta for etiqueta, _, activa in _pestanas(contenido) if activa]
        self.assertEqual(activas, ["Inicio"])

    def test_en_una_subpantalla_de_entrenos_la_encendida_es_entrenos(self):
        self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "deporte": "correr",
                "intensidad": "media",
                "minutos": "30",
                "calorias": "",
            },
        )
        from entrenos.models import Entreno

        entreno = Entreno.objects.get(persona=self.alejandro)

        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertEqual(contenido.count('aria-current="page"'), 1)
        activas = [etiqueta for etiqueta, _, activa in _pestanas(contenido) if activa]
        self.assertEqual(activas, ["Entrenos"])


class R4_SinSesionSinMarcoTests(SimpleTestCase):
    """R4 — sin sesión abierta no hay barra inferior ni menú de ajustes: sigue lo de
    siempre."""

    databases = set()

    def test_la_portada_sin_sesion_no_trae_marco_de_app(self):
        from django.test import Client

        respuesta = Client().get("/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()

        self.assertNotIn('aria-label="Navegación principal"', contenido)
        self.assertNotIn('aria-label="Ajustes"', contenido)
        self.assertIn("Entrar", contenido)
        self.assertIn("Crear cuenta", contenido)

        # La cabecera "Entrar / Crear cuenta" es lo PRIMERO que se ve, no algo que aparece
        # al fondo del scroll tras el contenido de la portada (regresión: el `{% if not
        # user.is_authenticated %}` de la cabecera cayó detrás de `{% block content %}`).
        indice_crear_cuenta = contenido.index("Crear cuenta")
        indice_contenido = contenido.index("<h1")
        self.assertLess(
            indice_crear_cuenta,
            indice_contenido,
            "la cabecera 'Entrar / Crear cuenta' sale DESPUÉS del contenido de la portada",
        )


class R5_TokensYCifraEnCSSTests(SimpleTestCase):
    """R5 — el CSS servido trae los tokens del sistema de diseño con los valores EXACTOS del
    proyecto viejo, y la clase `.cifra` con `tabular-nums`."""

    databases = set()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ruta = finders.find("css/tailwind.css")
        assert ruta is not None, "static/css/tailwind.css no existe — falta compilar (AGENTS.md §1.6)"
        with open(ruta, encoding="utf-8") as f:
            cls.css = f.read()

    def test_los_colores_de_base_estan_con_su_valor_exacto(self):
        # Atado al NOMBRE del token, no solo al hex suelto: un hex correcto colgado del
        # token equivocado (p. ej. `acento` y `racha` intercambiados) tiene que dar rojo.
        css_sin_espacios = re.sub(r"\s+", "", self.css)
        for nombre, valores in [
            ("tinta", ["#0b0b0c"]),
            ("tinta-media", ["#6b7280"]),
            ("tinta-suave", ["#9ca3af"]),
            ("linea", ["#ececef"]),
            ("lienzo", ["#f4f4f5"]),
            # Tailwind minifica `#ffffff` a la forma corta `#fff` al compilar (no le pasa a
            # los demás valores de esta lista, ninguno tiene los tres pares repetidos).
            ("superficie", ["#ffffff", "#fff"]),
            ("acento", ["#12b76a"]),
            ("acento-suave", ["#e7f8f0"]),
            ("racha", ["#eb6834"]),
            ("racha-suave", ["#fdeee7"]),
        ]:
            with self.subTest(nombre=nombre, valores=valores):
                self.assertTrue(
                    any(f"--color-{nombre}:{valor}" in css_sin_espacios for valor in valores),
                    f"ninguno de {valores} encontrado como --color-{nombre}:<valor> en el CSS",
                )

    def test_los_colores_de_macros_estan_con_su_valor_exacto(self):
        css_sin_espacios = re.sub(r"\s+", "", self.css)
        for nombre, valor in [
            ("proteina", "#d55181"),
            ("proteina-suave", "#fbeef3"),
            ("carbos", "#c98500"),
            ("carbos-suave", "#fdf4e3"),
            ("grasa", "#2a78d6"),
            ("grasa-suave", "#eaf2fc"),
        ]:
            with self.subTest(nombre=nombre, valor=valor):
                self.assertIn(f"--color-{nombre}:{valor}", css_sin_espacios)

    def test_los_radios_y_el_ancho_de_movil_estan(self):
        # Comprobado atado al NOMBRE del token (tarjeta/control/pastilla/movil, tal cual
        # AppShell.jsx): el valor del TOKEN (`--radius-tarjeta: 1.5rem`), no la utilidad
        # derivada — `rounded-tarjeta` (la tarjeta, pieza de UI) no la usa todavía ninguna
        # plantilla ("Fuera de alcance": nace con la primera pantalla que la use) y Tailwind
        # solo genera la CLASE de una utilidad que de verdad se usa en algún sitio; el TOKEN
        # en sí, en cambio, va con `@theme static` (ver `assets/tailwind/input.css`) para que
        # esté SIEMPRE en el CSS servido, lo use ya alguien o no.
        css_sin_espacios = re.sub(r"\s+", "", self.css)
        self.assertRegex(css_sin_espacios, r"--radius-tarjeta:(1\.5rem|24px)")
        self.assertRegex(css_sin_espacios, r"--radius-control:(1rem|16px)")
        self.assertIn("--radius-pastilla:999px", css_sin_espacios)
        self.assertRegex(css_sin_espacios, r"--spacing-movil:(27rem|432px)")
        # `rounded-control`, `rounded-pastilla` y `max-w-movil` SÍ los usa ya `base.html`
        # (R1/R6): para esos tres, además del token, se comprueba que la utilidad compilada
        # exista y remita al mismo token (Tailwind referencia el `var(...)`, no inlinea el
        # valor en la propia utilidad).
        self.assertIn(".rounded-control{border-radius:var(--radius-control)", css_sin_espacios)
        self.assertIn(".rounded-pastilla{border-radius:var(--radius-pastilla)", css_sin_espacios)
        self.assertIn(".max-w-movil{max-width:var(--spacing-movil)", css_sin_espacios)

    def test_la_clase_cifra_trae_tabular_nums(self):
        css_sin_espacios = re.sub(r"\s+", "", self.css)
        self.assertIn(".cifra{", css_sin_espacios)
        self.assertIn("font-variant-numeric:tabular-nums", css_sin_espacios)


class R6_CasosLimiteDeMovilTests(_ConAlejandroYSuHogar):
    """R6 — la cura de los campos de fecha/hora de Safari, y el hueco del indicador del
    iPhone en la barra inferior."""

    def test_la_cura_de_los_campos_de_fecha_esta_en_el_css(self):
        # Las tres declaraciones tienen que estar en el MISMO bloque de regla, atado a los
        # tres selectores de fecha/hora — no como tres subcadenas sueltas en cualquier parte
        # del CSS: `appearance:none`, `min-width:0` y `max-width:100%` los pone Tailwind por
        # su cuenta en el preflight y en `.min-w-0`, sin la cura, así que buscarlas sueltas no
        # distingue si la cura existe de si Tailwind ya las traía por otro motivo.
        ruta = finders.find("css/tailwind.css")
        with open(ruta, encoding="utf-8") as f:
            css_sin_espacios = re.sub(r"\s+", "", f.read())
        self.assertIn(
            "input[type=date],input[type=time],input[type=datetime-local]"
            "{appearance:none;box-sizing:border-box;min-width:0;max-width:100%}",
            css_sin_espacios,
        )

    def test_la_barra_inferior_reserva_el_hueco_del_iphone(self):
        respuesta = self.client.get("/")
        contenido = respuesta.content.decode()
        # El único `<nav>` de la página es la barra inferior (R1): que el hueco del
        # indicador del iPhone aparezca en la página en absoluto ya localiza la comprobación
        # ahí, sin depender de en qué atributo exacto del `<nav>` se escriba.
        self.assertIn("<nav", contenido)
        self.assertIn("env(safe-area-inset-bottom)", contenido)


class R7_SinPersonaNoRompeLaPaginaTests(PruebaConRegistroAbierto):
    """R7 — una cuenta con sesión abierta pero sin `Persona` carga la página sin reventar: el
    marco no lanza `NoReverseMatch` y omite las pestañas que necesitan un id que no existe.

    Se renderiza `base.html` directamente (con `RequestFactory`, no `self.client`) en vez de
    pedir "/": `paginas.views.inicio` hace `persona_actual(request).hogar` sin guardarlo de un
    `None` (`hogares/acceso.py` documenta que `persona_actual` SÍ puede devolver `None` "para
    que las puertas no revienten" — pero esa vista no lo comprueba). Es un fallo AJENO al
    marco, en un fichero que esta unidad no tiene en `ficheros:` (reportado en
    `hallazgos.md`); R7 promete que el MARCO no revienta, así que se aísla el marco de esa
    vista para probar exactamente eso, ni más ni menos."""

    def test_el_marco_no_revienta_sin_persona_y_omite_el_tab_de_plan(self):
        from django.contrib.auth import get_user_model
        from django.template import engines
        from django.test import RequestFactory
        from django.urls import resolve

        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        Persona.objects.filter(usuario__email="alejandro@example.com").delete()
        usuario = get_user_model().objects.get(email="alejandro@example.com")

        request = RequestFactory().get("/")
        request.user = usuario
        request.resolver_match = resolve("/")

        # Si `base.html` lanzara `NoReverseMatch` (R7), esta llamada lo propagaría aquí.
        html = engines["django"].get_template("base.html").render({}, request)

        etiquetas = [etiqueta for etiqueta, _, _ in _pestanas(html)]
        self.assertNotIn("Plan", etiquetas)
        self.assertIn("Inicio", etiquetas)
        self.assertIn("Stock", etiquetas)
        self.assertIn("Entrenos", etiquetas)
        self.assertIn("Progreso", etiquetas)


# ------------------------------------------------------------------------------------------ #
# Unidad 056 (el-camino-que-faltaba-a-tu-contrasena.md): R1-R3.
#
# El marco es de la 050, pero el agujero es suyo: la rueda de ajustes nació con cuatro
# destinos y `/cuentas/password/change/` no quedó enlazada desde NINGUNA parte de la app —
# medido recorriendo la app entera con sesión y cruzándolo con la lista completa de rutas.
# La pantalla existía y funcionaba; solo se llegaba escribiendo la dirección a mano.
# ------------------------------------------------------------------------------------------ #

_ENLACE_RE = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', re.S)


# Tapaderas: formas de esconder algo que sobreviven a que Alpine "abra" el menú (`x-show` solo


# --------------------------------------------------------------------------------------------- #
# Alcanzabilidad. Las ocho piezas y el porqué de cada una viven en
# `kcalibra/ayuda_de_alcanzabilidad.py`, NO aquí: este patrón se copió a mano una vez (unidad 053)
# y se dejó cuatro de las ocho, lo que abrió siete agujeros que su revisión demostró uno a uno.
# Aquí solo quedan los emparejadores concretos de ESTA pantalla.
# --------------------------------------------------------------------------------------------- #

_MENU_RE = re_de_atributo("x-show", "ajustesAbierto")


def _es_el_menu(etiqueta, attrs):
    return (attrs.get("x-show") or "").strip() == "ajustesAbierto"


def _es_la_rueda(etiqueta, attrs):
    return etiqueta == "button" and attrs.get("aria-label") == "Ajustes"


def _es_el_enlace_de_la_contrasena(etiqueta, attrs):
    return etiqueta == "a" and attrs.get("href") == "/cuentas/password/change/"


# Los SEIS destinos de la rueda llevan `data-ajuste` en la plantilla. No es adorno: sin una marca
# propia habría que localizarlos por su ruta, y una ruta como `/perfiles/` aparece también en el
# cuerpo de varias pantallas — el test encontraría dos y daría un rojo falso. Con la marca, cada
# destino es exactamente uno y se puede exigir que TODOS sean alcanzables (13ª revisión: solo se
# comprobaban tres de los ocho elementos que hay que poder pulsar).
DESTINOS_DE_LA_RUEDA = (
    ("tus-datos", "Tus datos"), ("tu-peso", "Tu peso"), ("recetas", "Recetas"),
    ("el-hogar", "El hogar"), ("cambiar-contrasena", "Cambiar tu contraseña"), ("salir", "Salir"),
)


def _es_el_destino(marca):
    return lambda etiqueta, attrs: attrs.get("data-ajuste") == marca


def _zona_de_ajustes(contenido):
    """El menú que despliega la rueda: desde su `x-show` hasta el final de la cabecera.

    Se acota A PROPÓSITO. Si se mirara la página entera, un enlace a la misma ruta puesto en
    el cuerpo de una pantalla cualquiera dejaría verde un test que dice "está en la rueda":
    la misma cara del bug 027 que ya nos costó una unidad.
    """
    cuantos = len(_MENU_RE.findall(contenido))
    if cuantos != 1:
        # Con dos, `index` coge el primero y la zona se estira hasta `</header>` abarcando también
        # el otro: los destinos se encuentran por texto y el test miente sin mentir. 4ª revisión.
        raise AssertionError(
            f"hay {cuantos} elementos con x-show=\"ajustesAbierto\": no se sabe cuál es el menú"
        )
    inicio = _MENU_RE.search(contenido).start()
    fin = contenido.index("</header>", inicio)
    zona = contenido[inicio:fin]
    if not zona.strip():
        # Guarda de rojo mudo: sin esto, un cambio que vaciara la zona haría pasar todos los
        # `assertNotIn` y fallar los `assertIn` por el motivo equivocado, sin decir cuál.
        raise AssertionError("la zona del menú de ajustes salió VACÍA: el test no prueba nada")
    return zona


def _destinos_de_ajustes(contenido):
    """[(texto, ruta), ...] de los destinos de la rueda, leyendo HTML PARSEADO.

    Devuelve el par JUNTO, nunca las dos listas por separado: comprobarlo por un lado el texto y
    por otro la ruta deja verde un enlace que dice lo que toca y lleva a otro sitio (1ª vuelta).

    Y se lee con un parser, no con una expresión regular: `href='...'` con comillas simples es HTML
    igual de válido, y el regex de comillas dobles lo dejaba en ROJO con el enlace funcionando
    (14ª revisión). Ese falso rojo se curó primero solo en el botón de la rueda; aquí estaba el
    mismo defecto, sosteniendo la aserción central de esta unidad.
    """
    en_la_rueda = lambda etiqueta, attrs: etiqueta == "a" and "data-ajuste" in attrs
    return [(texto, attrs.get("href")) for attrs, texto in elementos_con_texto(contenido, en_la_rueda)]


class R1_LaRuedaLlevaACambiarLaContrasenaTests(_ConAlejandroYSuHogar):
    """R1 — desde cualquier pantalla, la rueda lleva a cambiar la contraseña."""

    ENLACE = ("Cambiar tu contraseña", "/cuentas/password/change/")

    def test_la_rueda_lleva_a_cambiar_la_contrasena(self):
        contenido = self.client.get("/").content.decode()
        self.assertIn(self.ENLACE, _destinos_de_ajustes(contenido))

    def test_esta_en_todas_las_pantallas_no_solo_en_la_portada(self):
        """El marco va en todas; si el enlace se colara en una sola plantilla, esto lo caza."""
        for ruta in ("/despensa/", "/entrenos/", "/progreso/", "/recetas/", "/perfiles/"):
            with self.subTest(ruta=ruta):
                contenido = self.client.get(ruta).content.decode()
                self.assertIn(self.ENLACE, _destinos_de_ajustes(contenido))


    def test_la_rueda_se_puede_abrir_de_verdad(self):
        """Que el enlace ESTÉ en el HTML no es que se pueda usar.

        Lo cazó el revisor de esta unidad: si alguien le quita al botón de la rueda el `@click`
        que despliega el menú, o le pone `hidden` al menú, el enlace sigue en el HTML y el test
        de R1 sigue verde — y la pantalla sigue sin poder alcanzarse, que era el problema que
        esta unidad venía a resolver. Así que aquí se ancla el botón AL MENÚ.
        """
        contenido = self.client.get("/").content.decode()

        # Todo lo que sigue se lee del HTML PARSEADO, nunca del texto crudo. La 13ª revisión
        # encontró que `'aria-label="Ajustes"' in etiqueta` daba un ROJO FALSO con comillas
        # simples, que son igual de válidas — el propio módulo predica tolerar lo que el navegador
        # tolera, y esta línea no lo hacía. Con el parser, las comillas dejan de existir como
        # problema. Y `@click` y `@click.outside` son atributos DISTINTOS, así que ya no hace falta
        # distinguirlos a mano.
        cadena_rueda = nada_lo_tapa(self, contenido, _es_la_rueda, "el botón de la rueda")
        attrs_rueda = cadena_rueda[-1][1]
        # Anclado a `@click=`, no a la palabra suelta: el botón lleva TAMBIÉN un
        # `@click.outside="ajustesAbierto = false"` (cerrar al tocar fuera), así que buscar solo
        # "ajustesAbierto" dejaba verde quitarle el que ABRE. Cazado mutando: la primera versión
        # de este test se quedó verde con el `@click` de abrir borrado.
        self.assertRegex(
            attrs_rueda.get("@click") or "",
            r"(?<![\w$])ajustesAbierto(?![\w$])",
            "el botón de la rueda no ABRE el menú: el enlace estaría ahí y sería inalcanzable",
        )

        # Y el botón no puede estar apagado: `disabled` no dispara click en ningún navegador,
        # así que el menú quedaría tan inalcanzable como sin `@click` — y el regex de arriba
        # seguiría contento. (Agujero 2 de la 2ª revisión.)
        self.assertNotIn("disabled", attrs_rueda)
        self.assertNotEqual(attrs_rueda.get("aria-disabled"), "true")

        # Y el menú no puede nacer tapado — ni él, NI NADIE QUE LO ENVUELVA. Alpine, con
        # `x-show`, solo alterna `display` en el propio elemento: si un padre está escondido, el
        # menú "abre" y sigue sin verse. Mirar solo la etiqueta del menú dejaba pasar eso, y es
        # el agujero que firmó la 3ª revisión (`<div class="hidden">` alrededor, test verde).
        #
        # Lo que queda fuera, dicho en vez de disimulado: `_TAPADERAS_*` es una lista negra y una
        # lista negra nunca está completa. Y sobre todo, este nivel de test (ADR-015: HTML
        # renderizado, sin motor de JavaScript) no puede ver si el navegador llegó a ejecutar
        # Alpine: borrando su `<script>`, el menú no abre y esto sigue verde. Cerrar eso pide un
        # navegador de verdad, y este contrato no lo pide.
        # La rueda TAMBIÉN: es lo primero que hay que poder pulsar, y hasta la 12ª revisión era el
        # único de los tres que nunca se pasaba por aquí — se le miraba la etiqueta (`disabled`,
        # el `@click`) pero jamás su cadena de ancestros. Envolviendo SOLO el botón en un
        # `<div class="hidden">`, los 20 tests seguían verdes y la rueda no existía en pantalla.
        # Es la pieza 8 del propio módulo ("sobre cada elemento que hay que poder USAR") sin
        # aplicar al elemento más obvio de los tres.
        nada_lo_tapa(self, contenido, _es_el_menu, "el menú de ajustes")
        # Y los SEIS destinos, no solo el de esta unidad: un menú alcanzable con los destinos
        # tapados sigue siendo un menú inútil (13ª revisión).
        for marca, etiqueta in DESTINOS_DE_LA_RUEDA:
            with self.subTest(destino=etiqueta):
                nada_lo_tapa(self, contenido, _es_el_destino(marca), f"el destino «{etiqueta}»")
        el_estado_es_compartido(
            self, contenido, _es_la_rueda, _es_el_menu, "ajustesAbierto",
            "el botón de la rueda", "el menú de ajustes",
        )


class R2_SinSesionNoHayNadaQueCambiarTests(_ConAlejandroYSuHogar):
    """R2 — quien no ha entrado no ve la rueda ni el camino a la contraseña."""

    def test_sin_sesion_no_hay_rueda_ni_enlace(self):
        self.client.logout()
        contenido = self.client.get("/").content.decode()
        self.assertNotIn('x-show="ajustesAbierto"', contenido)
        self.assertNotIn("/cuentas/password/change/", contenido)
        self.assertNotIn("Cambiar tu contraseña", contenido)


class R3_LosDestinosDeSiempreSiguenTests(_ConAlejandroYSuHogar):
    """R3 — el enlace nuevo SE SUMA: los cinco destinos de siempre siguen donde estaban."""

    def test_los_cuatro_enlaces_de_siempre_siguen_con_su_texto(self):
        destinos = _destinos_de_ajustes(self.client.get("/").content.decode())
        for esperado in (
            ("Tus datos", "/perfiles/"),
            ("Tu peso", "/perfiles/peso/"),
            ("Recetas", "/recetas/"),
            ("El hogar", "/hogares/mi-hogar/"),
        ):
            with self.subTest(destino=esperado):
                self.assertIn(esperado, destinos)

    def test_salir_sigue_siendo_un_formulario_que_postea(self):
        """Salir no es un enlace: cerrar sesión con un GET lo dispararía cualquier precarga."""
        contenido = self.client.get("/").content.decode()
        # Anclado al MISMO <form> que el action: el nombre de este test prometía que Salir postea,
        # pero la primera versión solo miraba el `action=` y dejaba VERDE cambiar el método a GET
        # (agujero 3 de la 2ª revisión). Un logout por GET lo dispara cualquier precarga del
        # navegador, así que la promesa importa.
        es_el_form = lambda etiqueta, attrs: etiqueta == "form" and attrs.get("action") == "/cuentas/logout/"
        formularios = elementos_con_texto(contenido, es_el_form)
        self.assertEqual(len(formularios), 1, "Salir ya no es un formulario que apunte al logout")
        self.assertEqual(
            (formularios[0][0].get("method") or "").lower(), "post",
            "Salir no postea: un logout por GET lo dispara cualquier precarga del navegador",
        )
        self.assertIn("Salir", formularios[0][1])


# ------------------------------------------------------------------------------------------ #
# Unidad 057 (cada-cosa-en-su-pestana.md): R1, R2, R3, R5 de su especificación. R4 (la red
# permanente de alcanzabilidad) vive en su propio fichero, `kcalibra/tests_nada_escondido.py`
# — es la que manda sobre todas las demás. R6 ("no romper nada") es el resto de la suite
# siguiendo en verde, con la única excepción escrita en `R2_NueveDestinosTests` de arriba. R7
# (el segmentado vive una sola vez, en `_ui.html`) lo prueba `kcalibra/tests_pantallas.py`
# (la firma de clase de la pieza en `_FIRMAS_DE_CLASE_POR_PIEZA`, unidad 053).
# ------------------------------------------------------------------------------------------ #


def _opcion_del_segmentado(contenido, segmento):
    """El `<a data-segmento="...">` de esa opción del control segmentado (R1), o revienta si
    no hay exactamente uno — mismo criterio que `cadena_unica` de `ayuda_de_alcanzabilidad`:
    cero es "no existe", dos es "hay un señuelo sin distinguir cuál es el de verdad". Anclado
    a `etiqueta == "a"` a propósito: un `<button>` (o cualquier otra cosa) con el mismo
    `data-segmento` NO cuenta como esta opción — es exactamente el hueco que R1 prohíbe
    ("convertirlo en botones sin dirección propia")."""
    coincide = lambda e, a: e == "a" and a.get("data-segmento") == segmento
    encontrados = elementos_con_texto(contenido, coincide)
    assert len(encontrados) == 1, (
        f"«{segmento}» del segmentado: {len(encontrados)} <a data-segmento=\"{segmento}\">, se esperaba 1"
    )
    return encontrados[0]


class R1_SegmentadoPlanRecetasTests(_ConAlejandroYSuHogar):
    """R1 — Recetas es una pestaña DENTRO de Plan: un control segmentado con dos opciones,
    Planificador y Recetas, cada una un enlace de verdad con su propia dirección — nunca un
    estado de JavaScript (así funciona el botón «atrás» del móvil, y se puede entrar directo a
    cualquiera de las dos)."""

    def test_el_segmentado_esta_en_el_planificador_con_planificador_marcado(self):
        contenido = self.client.get(f"/planes/{self.alejandro.id}/apuntar/").content.decode()
        attrs_plan, _ = _opcion_del_segmentado(contenido, "planificador")
        attrs_recetas, _ = _opcion_del_segmentado(contenido, "recetas")

        self.assertEqual(attrs_plan.get("href"), f"/planes/{self.alejandro.id}/apuntar/")
        self.assertEqual(attrs_recetas.get("href"), "/recetas/")
        self.assertEqual(attrs_plan.get("aria-current"), "page")
        self.assertNotEqual(attrs_recetas.get("aria-current"), "page")

    def test_el_segmentado_esta_en_recetas_con_recetas_marcado(self):
        contenido = self.client.get("/recetas/").content.decode()
        attrs_plan, _ = _opcion_del_segmentado(contenido, "planificador")
        attrs_recetas, _ = _opcion_del_segmentado(contenido, "recetas")

        self.assertEqual(attrs_plan.get("href"), f"/planes/{self.alejandro.id}/apuntar/")
        self.assertEqual(attrs_recetas.get("href"), "/recetas/")
        self.assertEqual(attrs_recetas.get("aria-current"), "page")
        self.assertNotEqual(attrs_plan.get("aria-current"), "page")


class R2_PestanaPlanEncendidaEnRecetasTests(_ConAlejandroYSuHogar):
    """R2 — Recetas vive DENTRO de Plan (R1): la pestaña de la barra de ABAJO que se enciende
    en `/recetas/` y en sus subpantallas es Plan — exactamente una, nunca una pestaña propia
    de Recetas (no existe ninguna)."""

    def _solo_plan_encendida(self, ruta):
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 200, ruta)
        contenido = respuesta.content.decode()
        # `_pestanas` ya acota la lectura a la zona de la barra inferior (`_zona_de_la_barra_
        # inferior`, arriba de este fichero): el `aria-current="page"` del segmentado de R1
        # vive dentro de `<main>`, ANTES de esa zona, así que no se cuela aquí por accidente.
        activas = [etiqueta for etiqueta, _, activa in _pestanas(contenido) if activa]
        self.assertEqual(activas, ["Plan"], f"{ruta}: pestañas encendidas = {activas}")

    def test_en_la_lista_de_recetas(self):
        self._solo_plan_encendida("/recetas/")

    def test_en_las_subpantallas_de_recetas(self):
        receta = Receta.objects.create(hogar=self.alejandro.hogar, nombre="Tortilla", raciones=2)
        for ruta in ("/recetas/nueva/", f"/recetas/{receta.id}/", f"/recetas/{receta.id}/editar/"):
            with self.subTest(ruta=ruta):
                self._solo_plan_encendida(ruta)


class R3_LaRuedaAdelgazaACuatroTests(_ConAlejandroYSuHogar):
    """R3 — la rueda de ajustes pasa a tener EXACTAMENTE cuatro destinos, en este orden: Tus
    datos, El hogar, Cambiar tu contraseña, Salir. Tu peso y Recetas salen de ahí — siguen
    alcanzables (Tu peso desde Progreso, Recetas desde su pestaña dentro de Plan, R1), y
    `kcalibra/tests_nada_escondido.py` (R4) es la red que lo prueba recorriendo la app
    entera, no ésta."""

    def test_la_rueda_tiene_exactamente_estos_tres_enlaces_en_este_orden_mas_salir(self):
        contenido = self.client.get("/").content.decode()
        # `_destinos_de_ajustes` (unidad 056, arriba) ya lee solo los `<a data-ajuste>` — Salir
        # es un `<button>`, así que no aparece aquí y se comprueba aparte, abajo.
        self.assertEqual(
            _destinos_de_ajustes(contenido),
            [
                ("Tus datos", "/perfiles/"),
                ("El hogar", "/hogares/mi-hogar/"),
                ("Cambiar tu contraseña", "/cuentas/password/change/"),
            ],
        )

        acciones = {
            attrs.get("action")
            for attrs, _ in elementos_con_texto(contenido, lambda e, a: e == "form")
        }
        self.assertIn("/cuentas/logout/", acciones)

    def test_tu_peso_y_recetas_ya_no_estan_en_la_rueda(self):
        """Mutación al revés de la que prueba R6: si alguien los deja, esto lo caza (y si
        alguien quita, de más, otro de los cuatro que sí tocan, lo caza el test de arriba)."""
        contenido = self.client.get("/").content.decode()
        destinos = _destinos_de_ajustes(contenido)
        self.assertNotIn(("Tu peso", "/perfiles/peso/"), destinos)
        self.assertNotIn(("Recetas", "/recetas/"), destinos)


class R5_LosAccesosDirectosDeSiempreSiguenRespondiendoTests(_ConAlejandroYSuHogar):
    """R5 — cambiar DÓNDE se enlaza algo no puede romper un enlace guardado en el móvil de
    nadie: `/recetas/` y `/perfiles/peso/` (ya fuera de la rueda, R3) siguen respondiendo 200 a
    quien las tenga guardadas como acceso directo."""

    def test_recetas_y_peso_mio_siguen_respondiendo_200(self):
        for ruta in ("/recetas/", "/perfiles/peso/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)
