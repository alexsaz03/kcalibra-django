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
from hogares.models import Persona

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
    alcanzables desde el marco nuevo (cinco como pestañas, cuatro más Salir en ajustes)."""

    def test_los_nueve_destinos_siguen_alcanzables(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()

        # Inicio, Tu progreso, Entrenos, Despensa: cubiertos por las pestañas (R1).
        self.assertIn('href="/"', contenido)
        self.assertIn('href="/progreso/"', contenido)
        self.assertIn('href="/entrenos/"', contenido)
        self.assertIn('href="/despensa/"', contenido)

        # Tus datos, Tu peso, Recetas, El hogar: en el menú de ajustes.
        self.assertIn('href="/perfiles/"', contenido)
        self.assertIn('href="/perfiles/peso/"', contenido)
        self.assertIn('href="/recetas/"', contenido)
        self.assertIn('href="/hogares/mi-hogar/"', contenido)

        # Salir: un formulario que postea al logout de allauth (como hoy).
        self.assertIn('action="/cuentas/logout/"', contenido)

    def test_el_enlace_a_recetas_dice_recetas_a_secas(self):
        """`recetas/tests.py:501` ya exige `>Recetas<` literal — la red del padre."""
        respuesta = self.client.get("/recetas/")
        contenido = respuesta.content.decode()
        self.assertIn('href="/recetas/"', contenido)
        self.assertIn(">Recetas<", contenido)

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
