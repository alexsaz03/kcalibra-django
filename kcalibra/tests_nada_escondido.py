r"""
La red permanente que manda sobre todas las demás (unidad 057, R4): **ninguna funcionalidad
queda escondida**. Con sesión abierta, recorre la app de verdad desde "/" siguiendo cada
`href` y cada `hx-get` — el mismo mecanismo que ya usa `hx-get` en el navegador — y exige que
**toda** ruta con nombre que se sirva por GET y pinte una pantalla sea alcanzable así.

Es la red que habría cazado sola el agujero de la unidad 056 (cambiar la contraseña, sin un
solo enlace en toda la app): esa unidad se enteró en la 5ª/6ª revisión porque nadie había
escrito este barrido. Se queda para siempre — las unidades futuras que añadan una pantalla no
tocan este fichero salvo para sumar su ruta a `EXCEPCIONES` (con el motivo escrito) si de
verdad no se alcanza navegando.

Dos barridos, cero listas escritas a mano para lo que sí se puede derivar:

  1. El UNIVERSO — toda ruta con nombre del proyecto — sale de `django.urls.get_resolver()`,
     recorrido recursivamente. Una ruta nueva se suma sola en cuanto se registra en cualquier
     `urls.py`; nadie tiene que acordarse de venir aquí a añadirla.
  2. Lo ALCANZADO sale de recorrer la app DE VERDAD con el cliente de test, dos veces —
     con sesión (Alejandro, con hogar, un entreno de hoy, una receta y una persona a su
     cargo: la fixture mínima para que cada enlace condicional del árbol llegue a pintarse) y
     sin sesión (la portada, antes de entrar) — porque hay pantallas (entrar, crear cuenta)
     que solo se enlazan ANTES de tener sesión abierta.

Lo único escrito a mano es `EXCEPCIONES`: las rutas que legítimamente no se alcanzan
navegando (solo responden a POST, son de borrado, o necesitan una clave que solo llega por
correo o un estado de sesión de navegador que un alta real deja) — cada una con su motivo, uno
por uno. Una excepción sin motivo escrito es un agujero tapado (regla de esta casa); por eso el
propio test comprueba, además de que nada se quede fuera de las dos listas, que ninguna
excepción sea en realidad alcanzable (eso sobraría) ni apunte a una ruta que ya no existe.

El panel de administración de Django (`admin:`) se excluye del universo, no como una excepción
más: no es una pantalla que ninguna unidad de este proyecto prometa navegar, es infraestructura
ajena a la app (nunca ha estado en el `ficheros:` de ninguna especificación).
"""

from django.test import Client, SimpleTestCase
from django.urls import Resolver404, get_resolver, resolve
from django.urls.resolvers import URLPattern, URLResolver

from cuentas.ayuda_pruebas import PruebaConRegistroAbierto
from entrenos.models import Entreno
from hogares.models import Persona
from kcalibra.ayuda_de_alcanzabilidad import elementos_con_texto
from recetas.models import Receta

# ------------------------------------------------------------------------------------------ #
# 1. El universo: toda ruta con nombre, derivada de get_resolver() — nunca escrita a mano.
# ------------------------------------------------------------------------------------------ #


def _todas_las_rutas_con_nombre(patrones=None, prefijo=()):
    """{view_name: URLPattern} de TODA ruta con nombre del proyecto, salvo `admin:` (ver el
    docstring del módulo). Recorre `get_resolver()` recursivamente: un `include()` nuevo, o
    una ruta nueva dentro de uno que ya existe, se suman solos en la siguiente corrida."""
    if patrones is None:
        patrones = get_resolver().url_patterns
    rutas = {}
    for patron in patrones:
        if isinstance(patron, URLResolver):
            if patron.namespace == "admin" and not prefijo:
                continue
            siguiente = prefijo + ((patron.namespace,) if patron.namespace else ())
            rutas.update(_todas_las_rutas_con_nombre(patron.url_patterns, siguiente))
        elif isinstance(patron, URLPattern) and patron.name:
            rutas[":".join(prefijo + (patron.name,))] = patron
    return rutas


# ------------------------------------------------------------------------------------------ #
# 2. Lo alcanzado: un recorrido de verdad con el cliente de test, siguiendo href y hx-get.
# ------------------------------------------------------------------------------------------ #


def _rutas_enlazadas(contenido):
    """Los destinos INTERNOS (empiezan por "/", ni "//" ni un ancla suelta) de cada `href` y
    cada `hx-get` de la página, sin query ni fragmento — R4 sigue exactamente estos dos
    atributos, ni uno más. Leído con el parser de `ayuda_de_alcanzabilidad`, no con una
    expresión regular: un `href='...'` con comillas simples es HTML igual de válido."""
    destinos = set()
    for atributo in ("href", "hx-get"):
        coincide = lambda etiqueta, attrs, atributo=atributo: atributo in attrs
        for attrs, _ in elementos_con_texto(contenido, coincide):
            valor = (attrs.get(atributo) or "").strip()
            if valor.startswith("/") and not valor.startswith("//"):
                destinos.add(valor.split("?", 1)[0].split("#", 1)[0])
    return destinos


def _recorrer_la_app(cliente, arranque="/"):
    """BFS con el cliente de test desde `arranque`: por cada página que responde 200, se
    apunta su `view_name` (el nombre con el que se registró en `urls.py`) y se sigue cada
    `href`/`hx-get` que traiga. Una página que NO responde 200 (una redirección, un 404) no
    cuenta como alcanzada — R4 pide poder USAR la pantalla, no solo que la URL resuelva a
    algo — y no se sigue explorando desde ella."""
    por_visitar = [arranque]
    visitadas = set()
    nombres = set()
    while por_visitar:
        ruta = por_visitar.pop(0)
        if ruta in visitadas:
            continue
        visitadas.add(ruta)
        respuesta = cliente.get(ruta)
        if respuesta.status_code != 200:
            continue
        try:
            nombres.add(resolve(ruta).view_name)
        except Resolver404:
            pass
        contenido = respuesta.content.decode()
        for destino in _rutas_enlazadas(contenido):
            if destino not in visitadas:
                por_visitar.append(destino)
    return nombres


# ------------------------------------------------------------------------------------------ #
# 3. Las excepciones: escritas a mano, cada una con su motivo — regla 12 de esta casa.
# ------------------------------------------------------------------------------------------ #

EXCEPCIONES = {
    # --- Solo responden a POST (los formularios que las llaman lo hacen así; un GET a mano
    # no pinta ninguna pantalla, así que R4 no les pide un camino de navegación). ---
    "account_logout": (
        "el formulario de «Salir» (base.html) postea directamente; un GET aquí SÍ pinta una "
        "pantalla de confirmación (allauth, ACCOUNT_LOGOUT_ON_GET no está activado), pero "
        "ningún enlace de la app apunta a ella con GET."
    ),
    "cuentas:borrar_cuenta": "`@require_POST` (cuentas/views.py); ningún `href` la enlaza.",
    "hogares:aceptar_solicitud": "`@require_POST`; un formulario en mi_hogar.html, no un enlace.",
    "hogares:rechazar_solicitud": "`@require_POST`; un formulario en mi_hogar.html, no un enlace.",
    "hogares:dar_de_alta_persona_a_cargo": "`@require_POST`; el alta es un formulario, no un enlace.",
    "hogares:pasar_responsable": "`@require_POST`; un formulario en mi_hogar.html, no un enlace.",
    "perfiles:actualizar": "`@require_POST` (`hx-post`, perfiles/ver.html), nunca un `href`.",
    "perfiles:apuntar_peso": "`@require_POST` (`hx-post`, perfiles/peso.html), nunca un `href`.",
    "perfiles:borrar_peso": "`@require_POST` (`hx-post`, perfiles/peso.html), nunca un `href`.",
    "entrenos:apuntar": "`@require_POST` (`hx-post`, entrenos/ver.html), nunca un `href`.",
    "entrenos:borrar": "`@require_POST` (`hx-post`, entrenos/ver.html), nunca un `href`.",
    "cierres:responder": "`@require_POST` (`hx-post`, _pregunta_pendiente.html), nunca un `href`.",
    "cierres:saltar": "`@require_POST` (`hx-post`, _pregunta_pendiente.html), nunca un `href`.",
    "despensa:anadir": "`@require_POST`; el alta de producto es un formulario, no un enlace.",
    "despensa:corregir": "`@require_POST` (`hx-post`, despensa/ver.html), nunca un `href`.",
    "despensa:quitar": "`@require_POST` (`hx-post`, despensa/ver.html), nunca un `href`.",
    "recetas:borrar": "`@require_POST` (`action`, recetas/detalle.html), nunca un `href`.",
    # --- Necesitan una clave que solo llega por un correo real: no hay ningún valor de       #
    # verdad que fabricar sin mandarlo, y por diseño (R15/Q-14) nadie los enlaza dentro de    #
    # la app — llegan de un correo, o no llegan. ---
    "account_confirm_email": "necesita la `key` de un correo de verificación real.",
    "account_reset_password_from_key": "necesita `uidb36`/`key` de un correo real (R4 ya lo nombra).",
    "account_reset_password_from_key_done": "se llega solo tras completar ese formulario con el token del correo.",
    "account_reset_password_done": (
        "solo se ve tras enviar el formulario de «he olvidado mi contraseña» (un POST); "
        "ningún `href` de la app apunta aquí, es a donde ESE envío redirige."
    ),
    # --- Dependen de un estado de sesión de NAVEGADOR (no de usuario autenticado) que solo   #
    # deja un alta real a medio verificar (unidad 003, R14) — y con sesión de usuario ya      #
    # abierta la propia vista redirige, así que ni el recorrido autenticado ni el anónimo     #
    # (sin ese estado) pueden alcanzarlas navegando. ---
    "cuentas:esperando_verificacion": (
        "necesita un correo de alta pendiente en la sesión del navegador; con sesión de "
        "usuario abierta la propia vista redirige a «Mi hogar» (cuentas/views.py)."
    ),
    "cuentas:reenviar_verificacion": "GET no pinta nada: si el método no es POST, redirige — no es una pantalla.",
    "cuentas:corregir_correo": "GET no pinta nada: si el método no es POST, redirige — no es una pantalla.",
    "account_inactive": "a donde allauth redirige una cuenta marcada inactiva; ninguna cuenta de la app llega a ese estado hoy, y nada la enlaza.",
    # --- R3 de esta unidad la retira del único sitio que la enlazaba. ---
    "perfiles:peso_mio": (
        "R3 de esta unidad quita «Tu peso» de la rueda de ajustes, su único enlace; se llega "
        "desde Progreso con el id de la persona (`perfiles:peso`). Sigue respondiendo 200 a "
        "quien la tenga guardada como acceso directo (R5) — eso lo prueba `tests_marco.py`, "
        "no esta red de navegación."
    ),
}


# ------------------------------------------------------------------------------------------ #
# 4. La fixture: HTTP contra las URLs reales (nunca `Model.objects.create` a mano cuando lo #
# que hace falta es que la petición LLEGUE a la pantalla — mismo criterio que ya sigue        #
# `_ConAlejandroYSusDatos` en tests_pantallas.py), con lo mínimo para que CADA enlace         #
# condicional del árbol de navegación llegue a pintarse: un entreno de hoy (entrenos:corregir #
# solo se enlaza si hay alguno), una receta (recetas:detalle/editar, ídem) y una persona a    #
# cargo de Alejandro (hogares:borrar_persona_a_cargo solo se enlaza para quien es su          #
# responsable). #
# ------------------------------------------------------------------------------------------ #

_DATOS_DE_UNA_PERSONA_A_CARGO = {
    "nombre": "Marta",
    "sexo": "mujer",
    "fecha_nacimiento": "2015-04-10",
    "altura_cm": "140",
    "peso_kg": "35",
    "actividad": "moderado",
    "objetivo": "mantener",
    "ajuste_pct": "",
    "dieta": "",
    "alergias": "",
    "intolerancias": "",
    "no_le_gusta": "",
}


class R4_NadaEscondidoTests(PruebaConRegistroAbierto):
    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        respuesta_entreno = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {
                "fecha": "2026-08-20",
                "deporte": "correr",
                "intensidad": "media",
                "minutos": "30",
                "calorias": "300",
            },
        )
        assert respuesta_entreno.status_code == 200  # control: el entreno se guardó de verdad
        assert Entreno.objects.filter(persona=self.alejandro).exists()

        respuesta_receta = self.client.post(
            "/recetas/nueva/",
            {
                "nombre": "Tortilla de claras",
                "raciones": "2",
                "preparacion": "",
                "ingrediente_nombre": ["Claras de huevo"],
                "ingrediente_cantidad": ["6"],
                "ingrediente_unidad": ["ud"],
            },
        )
        assert respuesta_receta.status_code == 302  # control: crear redirige al detalle
        assert Receta.objects.filter(hogar=self.alejandro.hogar).exists()

        respuesta_a_cargo = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", _DATOS_DE_UNA_PERSONA_A_CARGO, follow=True
        )
        assert respuesta_a_cargo.status_code == 200
        assert Persona.objects.filter(
            nombre="Marta", hogar=self.alejandro.hogar, responsable=self.alejandro
        ).exists()  # control: el alta no falló (bug 032: un formulario inválido también da 200)

    def test_toda_pantalla_con_nombre_es_alcanzable_navegando_o_tiene_excepcion_escrita(self):
        universo = _todas_las_rutas_con_nombre()
        alcanzadas = _recorrer_la_app(self.client) | _recorrer_la_app(Client())

        sin_alcanzar = sorted(set(universo) - alcanzadas - set(EXCEPCIONES))
        self.assertEqual(
            sin_alcanzar,
            [],
            f"rutas con nombre que nadie enlaza y sin excepción escrita en EXCEPCIONES: {sin_alcanzar}",
        )

        # Fallar hacia rojo también por el otro lado: una excepción que ya no existe como
        # ruta, o que en realidad SÍ es alcanzable, es exactamente el agujero tapado que la
        # regla de esta casa prohíbe ("una excepción sin motivo escrito", y aquí además sin
        # motivo VÁLIDO).
        huerfanas = sorted(set(EXCEPCIONES) - set(universo))
        self.assertEqual(huerfanas, [], f"excepciones que apuntan a una ruta que ya no existe: {huerfanas}")

        de_mas = sorted(set(EXCEPCIONES) & alcanzadas)
        self.assertEqual(
            de_mas, [], f"excepciones que SÍ son alcanzables navegando y sobran en la lista: {de_mas}"
        )

    def test_el_recorrido_no_prueba_nada_vacio(self):
        """Guarda de rojo mudo: si `_recorrer_la_app` se rompiera y devolviera un conjunto
        vacío (por ejemplo, si "/" empezara a dar un código distinto de 200), el test de
        arriba compararía dos conjuntos vacíos contra las excepciones y podría colar en
        verde sin haber recorrido nada de verdad."""
        alcanzadas = _recorrer_la_app(self.client)
        self.assertGreater(len(alcanzadas), 10, f"el recorrido autenticado apenas alcanzó nada: {alcanzadas}")
        self.assertIn("paginas:inicio", alcanzadas)
        self.assertIn("planes:apuntar", alcanzadas)

        anonimas = _recorrer_la_app(Client())
        self.assertIn("paginas:inicio", anonimas)
        self.assertIn("account_login", anonimas)
        self.assertIn("account_signup", anonimas)
