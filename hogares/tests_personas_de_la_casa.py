"""
Tests de la unidad 024 (darle-cuenta-propia-a-los-de-casa.md, REC-4 1ª entrega) — R1 a R7 de su
especificación.

Vive en `hogares/` (que esta unidad posee entera) aunque varios criterios crucen otras apps
(perfiles/, progreso/, planes/, paginas/): mismo patrón que `hogares/tests_persona.py` de la
unidad 023 — se recorre la app entera por HTTP con el cliente de pruebas, sin tocar ni un
fichero de las apps que esta unidad NO posee (progreso/views.py, progreso/tests.py, etc. —
"progreso/templates/" es lo único que declara `ficheros:` en la especificación).

Convención de nombres de las clases: `R<n>_...Tests`, una por criterio de aceptación, igual
que `hogares/tests_persona.py`.
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from perfiles.logica import calcular_objetivo_del_dia
from perfiles.models import MedicionPeso, Perfil

from .models import Persona, SolicitudEntrada

Usuario = get_user_model()

# Bug 027 (misma familia que 016/018/019/026, cara de
# docs/conocimiento/tests-que-no-fallan-cuando-deben.md): `templates/base.html` pinta el nombre
# de quien tiene la sesión abierta en la barra de arriba de TODAS las páginas de la app. Un
# assertIn("Alejandro", <página entera>) hecho estando Alejandro logueado pasa SIEMPRE, viva o
# no viva "Alejandro" en el contenido propio de la pantalla — medido mutando cada plantilla
# para que no diga nada suyo en su cuerpo: la suite seguía en verde (ver
# docs/bugs/027-asserts-de-la-024-y-una-rama-de-progreso-sin-red.md, sección 2). Estas
# dos zonas se usan para acotar, nunca para aflojar lo que cada test comprueba.
#
# R10 de la unidad 053 (las-pantallas-del-dia-a-dia.md) — R1 de esa misma unidad mudó el
# título de cada pantalla (`{% block titulo_grande %}`) DENTRO de `<header>`
# (`templates/base.html`), para que salga en la cabecera de toda pantalla del marco. Eso
# rompió la red del bug 027 por los DOS lados a la vez: el `<h1>` del título —que es
# precisamente el texto que `_zona_de_cuerpo` necesita para las pantallas de esta unidad
# (`test_ninguna_pantalla_muestra_ningun_correo` busca "Tu progreso", "Tu peso", "Apuntar tu
# plan" ahí dentro)— se mudó a la zona que antes se descartaba por compartida; y la zona de
# la barra pasó a incluir ese título, así que `test_la_barra_de_arriba_enseña_el_nombre_no_el_
# correo` podía acertar por el título de pantalla en vez de por la línea de la barra que de
# verdad promete probar. Las plantillas que esta unidad NO toca (`perfiles/ver.html`,
# `hogares/mi_hogar.html`: no viven en su `ficheros:`) siguen sin llenar `titulo_grande`, así
# que su `<header>` no tiene ningún `<h1>` — de ahí que `_indices_del_h1_de_titulo` devuelva
# `None` para ellas y las dos zonas se comporten exactamente como antes de esta unidad.


def _indices_del_h1_de_titulo(contenido, inicio_header, fin_header):
    """Localiza el `<h1>` del título de pantalla (`{% block titulo_grande %}`, unidad 053)
    DENTRO de la zona de cabecera ya acotada — `None` si esta pantalla todavía no lo llena
    (las que la 053 no toca: R10 arriba)."""
    try:
        inicio_h1 = contenido.index("<h1", inicio_header, fin_header)
    except ValueError:
        return None
    fin_h1 = contenido.index("</h1>", inicio_h1, fin_header) + len("</h1>")
    return inicio_h1, fin_h1


def _zona_de_la_barra_de_arriba(contenido):
    """Aísla el `<header>` (`templates/base.html`) SIN el `<h1>` del título de pantalla
    (R10 de la unidad 053, nota de arriba): el ÚNICO sitio de la página donde esta unidad
    garantiza el nombre de quien mira, siempre, en toda pantalla autenticada — es exactamente
    lo que promete `test_la_barra_de_arriba_enseña_el_nombre_no_el_correo`, así que es lo
    único que ese test debe mirar, ahora sin colarse por el título de pantalla que vive en
    la misma etiqueta."""
    inicio = contenido.index("<header")
    fin = contenido.index("</header>", inicio) + len("</header>")
    limites_h1 = _indices_del_h1_de_titulo(contenido, inicio, fin)
    if limites_h1 is None:
        zona = contenido[inicio:fin]
    else:
        inicio_h1, fin_h1 = limites_h1
        zona = contenido[inicio:inicio_h1] + contenido[fin_h1:fin]
    # Guarda de rojo mudo (R10): una zona vacía no es "no encontró nada que probar", es la
    # señal de que `<header>` cambió de forma que este helper ya no sabe leer — el test tiene
    # que fallar diciéndolo, no pasar en falso por `assertIn` contra una cadena vacía.
    assert zona.strip(), "la zona de la barra de arriba salió vacía: ¿cambió <header>?"
    return zona


def _zona_de_cuerpo(contenido):
    """El `<h1>` del título de pantalla (R10 de la unidad 053, nota de arriba) más TODO lo
    que hay DESPUÉS de la barra de arriba: el contenido propio de cada pantalla, sin la parte
    de la barra que se repite igual en todas y que por eso no prueba nada específico de ESTA
    pantalla — pero SIN perder el título, que desde la 053 vive dentro de `<header>` y es
    precisamente lo que varios de estos tests usan para saber de quién es la pantalla."""
    inicio = contenido.index("<header")
    fin_header = contenido.index("</header>", inicio) + len("</header>")
    limites_h1 = _indices_del_h1_de_titulo(contenido, inicio, fin_header)
    resto_tras_header = contenido[fin_header:]
    if limites_h1 is None:
        zona = resto_tras_header
    else:
        inicio_h1, fin_h1 = limites_h1
        zona = contenido[inicio_h1:fin_h1] + resto_tras_header
    # Guarda de rojo mudo (R10): ver la de `_zona_de_la_barra_de_arriba`, mismo motivo.
    assert zona.strip(), "la zona de cuerpo salió vacía: ¿cambió <header> o el <h1> del título?"
    return zona


def _fragmento_esta_dentro_del_h1_de_titulo(contenido, fragmento):
    """Hueco 3 de la revisión (2ª vuelta), escape 2 de `_plantilla_llena_titulo_grande`: no
    basta con que HAYA un `<h1>` dentro de `<header>` — un `<h1>` señuelo vacío
    (`<h1 class="sr-only">Inicio</h1>`) con el título de verdad movido a un `<div>` a su lado
    también "hay un `<h1>`" y dejaba pasar exactamente el escape que este hueco vino a cerrar.
    Lo que `_zona_de_la_barra_de_arriba` necesita para acotar bien es que el fragmento que
    identifica la pantalla viva DENTRO de ese `<h1>`, no sólo en algún sitio de la cabecera."""
    inicio = contenido.index("<header")
    fin = contenido.index("</header>", inicio) + len("</header>")
    limites_h1 = _indices_del_h1_de_titulo(contenido, inicio, fin)
    if limites_h1 is None:
        return False
    inicio_h1, fin_h1 = limites_h1
    return fragmento in contenido[inicio_h1:fin_h1]


_BLOQUE_TITULO_GRANDE_DECLARADO_RE = re.compile(r"\{%\s*block\s+titulo_grande\s*%\}")


def _plantilla_llena_titulo_grande(ruta_de_plantilla):
    """Hueco 4 (revisión, 1ª vuelta) y Hueco 3 (revisión, 2ª vuelta): la guarda de rojo mudo de
    `_zona_de_la_barra_de_arriba`/`_zona_de_cuerpo` sólo dispara si la zona sale VACÍA — si el
    `<h1>` desaparece pero el resto de `<header>` sigue teniendo contenido (p. ej. el `<h1>`
    mudado a `<div>`, que R1 no cazaría porque su test sólo compara POSICIONES contra
    `<main>`), la zona nunca sale vacía y la guarda no ve nada raro: el título vuelve a colarse
    en la zona de la barra en silencio, exactamente el bug 027 otra vez.
    No hay forma de que `_indices_del_h1_de_titulo` distinga "esta pantalla nunca tuvo título"
    de "esta pantalla debería tener título y lo perdió" mirando sólo la respuesta HTTP — hace
    falta una segunda fuente que diga qué pantallas DEBEN traerlo. En vez de escribir esa lista
    a mano (se quedaría vieja el día que una pantalla gane o pierda su `{% block
    titulo_grande %}`, que es justo lo que pasó una vez para abrir R10), se deriva del propio
    fichero de plantilla: si su texto declara el bloque, el `<h1>` es obligatorio, y la
    lista de rutas de abajo sólo dice QUÉ plantilla mirar, no si tiene título.

    La 1ª versión de esto comparaba la cadena EXACTA `"{% block titulo_grande %}"` y devolvía
    `False` -"no lo declara"- ante cualquier otra forma, incluida `{%block titulo_grande%}`
    (sin espacios dentro de las llaves, que Django acepta igual): la guarda se apagaba en
    silencio sin que nada lo dijera (Hueco 3, 2ª revisión). Ahora sólo se reconocen DOS formas:
    declarado (la expresión de abajo, tolerante a los espacios que el propio Django tolera) o
    AUSENTE (ni siquiera aparece el nombre del bloque en el texto). Cualquier otra cosa -el
    nombre del bloque aparece pero en una forma que ninguna de las dos reconoce- es el mismo
    fallar-abierto que abrió este hueco la primera vez, así que revienta en vez de adivinar."""
    texto = (settings.BASE_DIR / ruta_de_plantilla).read_text()
    if _BLOQUE_TITULO_GRANDE_DECLARADO_RE.search(texto):
        return True
    if "titulo_grande" not in texto:
        return False
    raise AssertionError(
        f"{ruta_de_plantilla} menciona 'titulo_grande' pero no en una forma reconocible -ni "
        "declarado ni ausente-: la guarda no puede decidir en silencio"
    )


# Los mismos datos físicos de Euridice que usa el resto de la suite (R1 de crear-cuenta.md,
# C-112 de darle-cuenta-propia-a-los-de-casa.md): 167 cm, 62 kg, objetivo "adelgazar" (la
# clave real es "perder_grasa", ver perfiles/constantes.py) — 1.894 kcal es su cifra conocida.
DATOS_DE_EURIDICE_A_CARGO = {
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
}


class _ConAlejandroYEuridiceACargo(PruebaConRegistroAbierto):
    """Base común: Alejandro con su cuenta, y Euridice dada de alta a su cargo (R2). La usan
    R3, R4 y R5 — los tres criterios que presuponen exactamente este montaje."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", DATOS_DE_EURIDICE_A_CARGO, follow=True
        )
        # `follow=True` hace que este 200 sea el mismo tanto si el alta acierta como si el
        # formulario es inválido (bug 032): lo que de verdad prueba que el alta no falló es
        # que la Persona exista.
        self.assertTrue(
            Persona.objects.filter(nombre="Euridice", hogar=self.alejandro.hogar).exists()
        )  # control: el alta no falló
        self.euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)


class R1_SinCorreoEnNingunaPantallaTests(_ConAlejandroYEuridiceACargo):
    """
    R1 — en ninguna de las pantallas que antes enseñaban un correo (Inicio, Progreso, su peso,
    apuntar plan, sus datos, la barra de arriba, la pantalla de la casa) aparece ya ninguna
    dirección de correo — se lee el nombre.
    """

    def test_ninguna_pantalla_muestra_ningun_correo(self):
        # Bug 027: en las CUATRO rutas donde Alejandro mira lo SUYO (es_propio=True en la
        # vista), sus propias plantillas dicen "tu"/"tus" en vez de repetir su nombre — un
        # diseño correcto, no un defecto (no hace falta que la pantalla te diga tu propio
        # nombre para saber que es tuya). Un assertIn("Alejandro", ...) en esas cuatro solo
        # podía estar pasando por la barra de arriba, medido mutando cada plantilla para que
        # no dijera nada suyo en su cuerpo — la suite seguía en verde (ficha del bug 027,
        # sección 2). El arreglo NO afloja el criterio ("sin correo, se sabe de quién es"):
        # en vez de un literal que solo la barra garantiza, comprueba en el CUERPO (fuera de
        # la barra) la frase que CADA pantalla usa de verdad para decirlo — la misma que ya
        # usan sus propias plantillas. En Inicio, el ancla es "Tú (Alejandro)", la frase EXACTA
        # que solo produce su propia tarjeta de la casa — no "Alejandro" a secas: desde la 053,
        # el `<h1>` de `{% block titulo_grande %}` ("Hola, Alejandro") también vive en la zona
        # de cuerpo, y un `assertIn("Alejandro", cuerpo)` colaría por ese saludo sin decir nada
        # del listado de la casa que este caso quiere probar (medido: quitándole el nombre a la
        # tarjeta de la casa, "Tú ({{ tarjeta.persona.nombre }})" → "Tú", este subtest seguía
        # verde hasta que se ató a la frase completa — hallazgos.md, Vuelta 2). En la pantalla
        # de la casa el ancla también es el nombre, pero OJO: este assert solo comprueba que
        # "Alejandro" aparece en algún sitio del cuerpo — puede colar por "A cargo de
        # Alejandro" en la ficha de Euridice, no necesariamente por la suya propia (medido). La
        # comprobación precisa de que CADA ficha dice su propio nombre, una a una, es la que
        # hace
        # `R3_LaPantallaDeLasPersonasDeLaCasaTests.test_ve_las_dos_fichas_marcadas_correctamente`
        # más abajo — este subtest solo cierra el hueco de R1 (correo vs. cuerpo), no
        # duplica esa precisión.
        # La tercera columna es la plantilla que responde a esa ruta — sólo para que
        # `_plantilla_llena_titulo_grande` sepa qué fichero mirar; si esa pantalla trae
        # `titulo_grande` o no lo decide el propio fichero, no esta lista (ver su docstring).
        # La cuarta es el fragmento que debe vivir DENTRO del propio `<h1>` de esa pantalla —
        # `None` donde `titulo_grande` no aplica. NO es la misma cadena que la segunda columna
        # a propósito: en Inicio el ancla del CUERPO es "Tú (Alejandro)" (la tarjeta de la
        # casa, R1 de esta unidad), pero el `<h1>` de `titulo_grande` dice "Hola, Alejandro"
        # (el saludo) — dos frases distintas de la misma pantalla que prueban dos cosas
        # distintas (Hueco 3, 2ª revisión).
        rutas_y_fragmento_de_identidad = [
            ("/", "Tú (Alejandro)", "paginas/templates/paginas/inicio.html", "Hola, Alejandro"),  # Inicio: solo la produce la tarjeta de la casa
            (f"/progreso/{self.alejandro.id}/", "Tu progreso", "progreso/templates/progreso/ver.html", "Tu progreso"),
            (f"/perfiles/{self.alejandro.id}/peso/", "Tu peso", "perfiles/templates/perfiles/peso.html", "Tu peso"),
            (f"/planes/{self.alejandro.id}/apuntar/", "Apuntar tu plan", "planes/templates/planes/apuntar.html", "Apuntar tu plan de hoy"),
            (f"/perfiles/{self.alejandro.id}/", "Tus datos", "perfiles/templates/perfiles/ver.html", "Tus datos"),
            ("/hogares/mi-hogar/", "Alejandro", "hogares/templates/hogares/mi_hogar.html", "Las personas de la casa"),  # su nombre en algún sitio del cuerpo (ver nota de arriba)
        ]
        for ruta, fragmento_de_identidad, ruta_de_plantilla, fragmento_del_h1 in rutas_y_fragmento_de_identidad:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                contenido = respuesta.content.decode()
                # El correo, en cambio, sí se comprueba sobre la página ENTERA a propósito:
                # R1 promete que no aparece en NINGÚN sitio, incluida la barra — acotar esta
                # mitad sería aflojarla, no acotarla.
                self.assertNotIn(
                    "alejandro@example.com", contenido,
                    f"{ruta} sigue enseñando el correo de Alejandro",
                )
                cuerpo = _zona_de_cuerpo(contenido)
                self.assertIn(
                    fragmento_de_identidad, cuerpo,
                    f"{ruta} no dice de quién es en su propio contenido "
                    "(fuera de la barra de arriba)",
                )
                # Hueco 4 (revisión, 1ª vuelta) y Hueco 3 (revisión, 2ª vuelta): con el `<h1>`
                # de titulo_grande mudado a otra etiqueta (algo que R1 no cazaría, su test
                # sólo compara POSICIONES), `_indices_del_h1_de_titulo` vuelve `None` en
                # silencio, la zona de la barra vuelve a incluir el título de pantalla y la
                # red del bug 027 queda otra vez rota sin que ningún test lo diga — medido:
                # `<h1>` de inicio.html mudado a `<div>` + barra de base.html sin el nombre,
                # las dos juntas, daban "Ran 40 tests — OK" antes de esta guarda. No basta con
                # que HAYA un `<h1>`: un `<h1>` señuelo vacío (`<h1 class="sr-only">Inicio</h1>`)
                # con el título de verdad movido a un `<div>` a su lado también "tiene un
                # `<h1>`" y colaba el mismo agujero (Hueco 3, escape 2) — de ahí que se exija
                # que el fragmento propio de esta pantalla viva DENTRO del `<h1>`, no que el
                # `<h1>` simplemente exista. Sólo se exige donde la propia plantilla declara el
                # bloque (ver `_plantilla_llena_titulo_grande`), así que "Tus datos" y
                # "mi-hogar" —que hoy no lo llenan— no se ven afectadas.
                if _plantilla_llena_titulo_grande(ruta_de_plantilla):
                    self.assertTrue(
                        _fragmento_esta_dentro_del_h1_de_titulo(contenido, fragmento_del_h1),
                        f"{ruta}: {ruta_de_plantilla} llena titulo_grande pero «{fragmento_del_h1}» "
                        "no está dentro de su <h1> — la guarda de rojo mudo de R10 se quedaría "
                        "ciega",
                    )

    def test_la_barra_de_arriba_enseña_el_nombre_no_el_correo(self):
        respuesta = self.client.get("/")
        contenido = respuesta.content.decode()
        self.assertNotIn("alejandro@example.com", contenido)
        # Bug 027: este test se llama "la barra de arriba enseña el nombre" pero miraba la
        # página ENTERA — y en Inicio, "Alejandro" TAMBIÉN aparece en el cuerpo (su propia
        # tarjeta, "Tú (Alejandro)"), así que el assert podía estar pasando por ahí y nunca
        # haber probado la barra en absoluto (medido: con la barra rota a propósito —
        # "Alejandro" sustituido por otra cosa en `templates/base.html`— este test seguía en
        # verde gracias al cuerpo; ver ficha del bug 027, sección 2). Acotado a la barra de
        # verdad.
        barra = _zona_de_la_barra_de_arriba(contenido)
        self.assertIn("Alejandro", barra)


class R2_AltaDeUnaPersonaACargoTests(PruebaConRegistroAbierto):
    """
    R2 — Alejandro da de alta a Euridice, sin cuenta, con nombre, datos físicos y objetivo:
    queda creada su ficha con Alejandro como responsable, y su objetivo diario se calcula
    igual que a cualquiera.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

    def test_el_alta_crea_la_ficha_de_euridice_con_alejandro_de_responsable(self):
        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", DATOS_DE_EURIDICE_A_CARGO, follow=True
        )
        # `follow=True` hace que este 200 sea el mismo tanto si el alta acierta como si el
        # formulario es inválido (bug 032): lo que de verdad prueba el criterio (R2, "queda
        # creada su ficha") es que la Persona exista.
        self.assertTrue(
            Persona.objects.filter(nombre="Euridice", hogar=self.alejandro.hogar).exists()
        )

        euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)
        self.assertIsNone(euridice.usuario_id)  # no tiene ni tendrá cuenta
        self.assertEqual(euridice.responsable_id, self.alejandro.id)
        self.assertEqual(euridice.hogar_id, self.alejandro.hogar_id)

    def test_el_objetivo_diario_se_calcula_igual_que_a_cualquiera(self):
        self.client.post("/hogares/mi-hogar/dar-de-alta/", DATOS_DE_EURIDICE_A_CARGO)
        euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)

        self.assertTrue(Perfil.objects.filter(persona=euridice).exists())
        self.assertTrue(MedicionPeso.objects.filter(persona=euridice).exists())

        resultado = calcular_objetivo_del_dia(euridice)
        self.assertIsNotNone(resultado)
        # El mismo episodio real que R1 de crear-cuenta.md / unidad 004: 1.894 kcal.
        self.assertEqual(resultado["calorias"], 1894)

    def test_sin_hogar_todavia_no_se_puede_dar_de_alta_a_nadie(self):
        """R14 de la unidad 003, aplicado aquí: mientras se espera a que le acepten en OTRO
        hogar, no hay una casa propia a la que dar de alta a nadie."""
        self.client.logout()
        self.registrar("berta@example.com", codigo_hogar=self.alejandro.hogar.codigo)
        # Berta se registró CON el código de Alejandro: queda "esperando que le acepten",
        # sin hogar propio. Sin verificar, ni siquiera tiene sesión — se comprueba la puerta
        # de todos modos, forzando el login para aislar exactamente lo que R14 protege.
        berta_cuenta = Usuario.objects.get(email="berta@example.com")
        self.client.force_login(berta_cuenta)

        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", DATOS_DE_EURIDICE_A_CARGO
        )
        self.assertEqual(respuesta.status_code, 404)


class R3_LaPantallaDeLasPersonasDeLaCasaTests(_ConAlejandroYEuridiceACargo):
    """
    R3 — la pantalla de las personas de la casa enseña las dos fichas por su nombre: la
    propia marcada como la que entra con su cuenta, y la de Euridice indicando que está a
    cargo de Alejandro.
    """

    @staticmethod
    def _zona_de_quien_vive_en_la_casa(contenido):
        """Aísla la sección `id="quien-vive-en-la-casa"`
        (`hogares/templates/hogares/mi_hogar.html`): el listado de fichas por nombre que R3
        promete. Bug 027: el `assertIn("Alejandro", ...)` original, sobre la página ENTERA,
        pasaba aunque la propia ficha de Alejandro dejara de decir su nombre — colaba por la
        barra de arriba (medido mutando `mi_hogar.html` para que su fila NO dijera
        "Alejandro", dejando intacto el resto; la suite seguía en verde — ver ficha del bug
        027, sección 2)."""
        inicio = contenido.index('id="quien-vive-en-la-casa"')
        fin = contenido.index("</section>", inicio)
        return contenido[inicio:fin]

    def test_ve_las_dos_fichas_marcadas_correctamente(self):
        respuesta = self.client.get("/hogares/mi-hogar/")
        contenido = respuesta.content.decode()
        zona = self._zona_de_quien_vive_en_la_casa(contenido)

        # Bug 027, segunda vuelta de la medición: acotar a la ZONA no basta por sí solo —
        # "Alejandro" aparece DOS VECES ahí dentro por dos motivos distintos: su propio
        # nombre, y "A cargo de Alejandro" en la ficha de Euridice. Un assertIn("Alejandro",
        # zona) seguía pasando con la ficha de Alejandro mutada para no decir su nombre,
        # porque la SEGUNDA aparición (la de Euridice) lo colaba igual (medido: misma
        # mutación de arriba, sobre la zona ya acotada, seguía en verde). El criterio real de
        # R3 es por FICHA ("la propia marcada como la que entra con su cuenta, y la de
        # Euridice...") — así que se comprueba ficha a ficha, no la zona entera de un tirón.
        fichas = re.findall(r"<li\b.*?</li>", zona, re.DOTALL)
        self.assertTrue(fichas, "no casó ninguna ficha: ¿cambió mi_hogar.html?")

        ficha_con_cuenta = next((f for f in fichas if "Entra con su cuenta" in f), None)
        self.assertIsNotNone(ficha_con_cuenta, "ninguna ficha dice 'Entra con su cuenta'")
        self.assertIn("Alejandro", ficha_con_cuenta)

        ficha_a_cargo = next((f for f in fichas if "A cargo de Alejandro" in f), None)
        self.assertIsNotNone(ficha_a_cargo, "ninguna ficha dice 'A cargo de Alejandro'")
        self.assertIn("Euridice", ficha_a_cargo)


class R4_SoloElResponsablePuedeEditarLosDatosDeACargoTests(_ConAlejandroYEuridiceACargo):
    """
    R4 — Alejandro (responsable) puede editar los datos de Euridice; otra persona CON cuenta
    del mismo hogar, llamando directamente al servidor (saltándose la pantalla), no puede
    (Q-20, Q-175).
    """

    def _payload_edicion(self, altura_cm):
        return {
            "altura_cm": altura_cm,
            "actividad": "activo",
            "objetivo": "ganar_musculo",
            "ajuste_pct": 15,
            "dieta": "",
            "alergias": "",
            "intolerancias": "",
            "no_le_gusta": "",
        }

    def test_alejandro_como_responsable_edita_los_datos_de_euridice(self):
        respuesta = self.client.post(
            f"/perfiles/{self.euridice.id}/actualizar/", self._payload_edicion(170)
        )
        self.assertEqual(respuesta.status_code, 200)
        self.euridice.perfil.refresh_from_db()
        self.assertEqual(self.euridice.perfil.altura_cm, 170)

    def test_alejandro_ve_el_formulario_al_abrir_la_ficha_de_euridice(self):
        """El formulario aparece (R4) aunque el TÍTULO siga diciendo "Datos de Euridice", no
        "Tus datos" (es_propio sigue siendo falso: solo cambia quién puede editar)."""
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/")
        contenido = respuesta.content.decode()
        self.assertIn("Datos de Euridice", contenido)
        self.assertIn("Guardar", contenido)  # el botón del formulario de edición

    def test_otra_persona_con_cuenta_del_hogar_no_puede_editar_a_euridice_saltandose_la_pantalla(
        self,
    ):
        # Berta entra en el MISMO hogar que Alejandro (con su propia cuenta), pero no es
        # responsable de Euridice.
        self.client.logout()
        self.registrar_y_verificar(
            "berta@example.com", codigo_hogar=self.alejandro.hogar.codigo, sexo="mujer"
        )
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario__email="berta@example.com")
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.client.logout()

        altura_original = self.euridice.perfil.altura_cm
        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/perfiles/{self.euridice.id}/actualizar/", self._payload_edicion(199)
        )

        self.assertEqual(respuesta.status_code, 404)
        self.euridice.perfil.refresh_from_db()
        self.assertEqual(self.euridice.perfil.altura_cm, altura_original)


class R5_NoSePuedeBorrarLaCuentaConAlguienACargoTests(_ConAlejandroYEuridiceACargo):
    """
    R5 (caso límite) — borrar la cuenta teniendo a alguien a cargo no se deja: ni la ficha de
    Euridice ni su histórico se pierden. Sin nadie a cargo, se borra sin más preguntas.
    """

    def test_no_se_borra_la_cuenta_ni_se_pierde_nada_de_euridice(self):
        self.assertTrue(MedicionPeso.objects.filter(persona=self.euridice).exists())

        respuesta = self.client.post("/cuentas/borrar/", follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Usuario.objects.filter(email="alejandro@example.com").exists())
        self.assertTrue(Persona.objects.filter(pk=self.euridice.id).exists())
        self.assertTrue(MedicionPeso.objects.filter(persona=self.euridice).exists())
        self.assertTrue(Perfil.objects.filter(persona=self.euridice).exists())
        # Sigue siendo SU responsable: nada se reasignó por su cuenta ni en silencio (G-195).
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.responsable_id, self.alejandro.id)

    def test_el_aviso_explica_que_hay_que_decidir_que_pasa_con_ella_antes(self):
        respuesta = self.client.post("/cuentas/borrar/", follow=True)
        # Unidad 026, 2ª ronda (H2, deuda heredada de la 024): "Euridice" ya la escribe la
        # lista de "Quién vive en la casa", y "a tu cargo" también lo escribe, estático, el
        # formulario de alta de esa misma pantalla ("Quedará a tu cargo:") — los dos asserts
        # por separado pasan aunque el mensaje real cambie de texto (misma cara que H1/H2 de
        # esta unidad). Se afirma sobre la frase completa del mensaje real.
        self.assertContains(respuesta, "tienes a Euridice a tu cargo")

    def test_la_base_de_datos_lo_impide_tambien_si_alguien_se_salta_la_vista(self):
        """Q-175: la protección no vive SOLO en `cuentas/views.py:borrar_cuenta` — está
        también en `Persona.responsable` (`on_delete=PROTECT`). Se demuestra llamando al ORM
        directamente, sin pasar por la vista, como haría cualquier otro camino futuro que se
        saltara la comprobación de la vista."""
        with self.assertRaises(ProtectedError):
            self.alejandro.usuario.delete()

        # Nada se perdió con el intento fallido.
        self.assertTrue(Usuario.objects.filter(email="alejandro@example.com").exists())
        self.assertTrue(Persona.objects.filter(pk=self.euridice.id).exists())

    def test_sin_nadie_a_cargo_se_borra_sin_mas_preguntas(self):
        self.client.logout()
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")

        respuesta = self.client.post("/cuentas/borrar/", follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(email="carlos@example.com").exists())


class R6_ElSelectorDeProgresoConDosPersonasTests(PruebaConRegistroAbierto):
    """
    R6 (caso límite, bug vivo destapado al especificar) — con dos o más personas en el hogar,
    el selector de Progreso enseña el nombre de cada una y marca "Tú" en la suya. Antes del
    arreglo, ese botón salía en blanco (comparaba id de persona con id de CUENTA, y pintaba
    `miembro.email`, que `Persona` no tiene) — ver hallazgos.md para el contrafactual pegado
    contra el código de antes del arreglo.
    """

    def setUp(self):
        super().setUp()
        # Desincroniza a propósito el id de `Persona` del id de `Usuario` ANTES de que
        # Alejandro exista (mismo hallazgo que en
        # progreso.tests.EsperandoAceptacionEnElHogarTests, revisión del bug 027): en una
        # tanda aislada las dos secuencias avanzan 1 a 1, así que la mutación histórica que R6
        # existe para cazar (comparar `request.user.id`, la CUENTA de quien mira, en vez de
        # `request.user.persona.id`) da el mismo resultado que compararlo bien, por pura
        # coincidencia numérica — medido: sin este paso, esa mutación pasaba en verde
        # corriendo esta clase sola. Dar de alta a una persona a cargo (una `Persona` SIN
        # `Usuario`) antes de que Alejandro se registre adelanta la secuencia de `Persona` un
        # paso por delante de la de `Usuario` — y ese desfase queda para siempre (nada lo
        # recompone), así que ni el id de Alejandro ni el de Euridice volverán a coincidir con
        # el de su propia cuenta.
        self.registrar_y_verificar("relleno@example.com", sexo="mujer")
        respuesta_alta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/",
            {
                "nombre": "Marta",
                "sexo": "mujer",
                "fecha_nacimiento": "2015-01-01",
                "altura_cm": "120",
                "peso_kg": "25",
                "actividad": "moderado",
                "objetivo": "mantener",
                "ajuste_pct": "",
                "dieta": "",
                "alergias": "",
                "intolerancias": "",
                "no_le_gusta": "",
            },
        )
        # El montaje se afirma, no se supone (19ª cara): un alta que falla en silencio (form
        # inválido, redirect distinto) dejaría el desfase sin crear.
        self.assertEqual(respuesta_alta.status_code, 302)
        self.assertTrue(
            Persona.objects.filter(nombre="Marta", usuario__isnull=True).exists()
        )
        self.client.logout()

        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        # Control estructural del desfase (no por el orden numérico: a escala de suite otros
        # tests ya pueden haber desalineado las secuencias por su cuenta, y entonces comparar
        # ids por casualidad deja de decir nada — 18ª cara operando sobre la red
        # anti-19ª-cara). Marta existe SIN Usuario y se creó ANTES que Alejandro: si el alta
        # falla o alguien la borra junto con sus asserts, este `.get()` revienta él solo, sin
        # depender de qué id le tocara a nadie.
        marta = Persona.objects.get(nombre="Marta", usuario__isnull=True)
        self.assertLess(marta.id, self.alejandro.id)  # control del desfase, estructural
        self.client.logout()

        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario__email="euridice@example.com")
        # `follow=True`: sin esto, el aviso flash ("Euridice ya está dentro del hogar")
        # queda en la cola de mensajes y se pinta en la SIGUIENTE petición cualquiera —
        # colando el nombre de Euridice en la página por una vía que no es el selector, y
        # dejando pasar en falso una aserción que debía depender solo del arreglo de R6.
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/", follow=True)

    @staticmethod
    def _zona_del_selector(contenido):
        """Aísla el `<div>` del selector de persona (decimotercera/decimosexta cara de
        docs/conocimiento/tests-que-no-fallan-cuando-deben.md: un assert sobre la página
        ENTERA puede colar por una vía que no es la que el criterio dice probar — aquí, un
        aviso flash con el nombre de Euridice que no tiene nada que ver con el selector)."""
        inicio = contenido.index('flex flex-wrap gap-2">')
        fin = contenido.index("</div>", inicio)
        return contenido[inicio:fin]

    def test_el_selector_muestra_el_nombre_de_cada_persona_y_marca_tu_en_la_suya(self):
        respuesta = self.client.get(f"/progreso/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        zona = self._zona_del_selector(respuesta.content.decode())

        # El botón del propio Alejandro dice "Tú" — antes del arreglo, este botón salía
        # EN BLANCO (ni "Tú" ni su correo): el `if` comparaba id de persona con id de cuenta,
        # que con dos personas en el hogar nunca coinciden.
        self.assertIn(">Tú<", re.sub(r"\s+", "", zona))
        self.assertIn("Euridice", zona)
        self.assertNotIn("@example.com", zona)

    def test_el_selector_tambien_marca_tu_cuando_lo_abre_euridice(self):
        """El contrafactual completo: el bug original comparaba SIEMPRE contra
        `request.user.id` (la cuenta de quien mira), así que daba igual desde qué persona se
        mirase — con el arreglo, cada quien ve "Tú" en la SUYA, no en la de Alejandro."""
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        zona = self._zona_del_selector(respuesta.content.decode())

        # Extrae el texto de cada botón del selector (un <a>...</a> por persona, DENTRO de la
        # zona aislada): "Tú" tiene que caer EXACTAMENTE una vez, y "Alejandro" tiene que
        # seguir apareciendo tal cual — si el bug reapareciera (comparando contra la cuenta en
        # vez de la persona), "Tú" saldría en el botón de Alejandro en vez del de Euridice, o
        # en los dos, o en ninguno.
        botones = re.findall(r">\s*([^<>]+?)\s*</a>", zona)
        self.assertEqual(botones.count("Tú"), 1)
        self.assertIn("Alejandro", botones)


class R7_LaMigracionDejaNombresProvisionalesTests(PruebaConRegistroAbierto):
    """
    R7 (caso límite) — las personas que ya existían salen de la migración CON nombre (la
    parte del correo antes de la "@", capitalizada), nunca en blanco. La demostración
    PRINCIPAL (obligatoria, R7/paso 3b del plan) es sobre una copia de la base con datos
    reales — ver hallazgos.md. Este test cubre la MISMA lógica pero de forma reproducible en
    la suite, llamando a la función de la migración directamente (lección de
    docs/conocimiento/migraciones-de-datos-en-django.md, punto 2: "no retrocedas el esquema,
    llama a la función de la migración directamente").
    """

    def test_rellenar_nombres_provisionales_deriva_el_nombre_del_correo(self):
        import importlib

        modulo = importlib.import_module(
            "hogares.migrations.0005_rellena_y_exige_el_nombre"
        )

        # Simula el estado ANTERIOR a esta unidad: una cuenta cuyo alta pasó por el `signup()`
        # de siempre (nombre relleno por el formulario) se le vuelve a dejar el nombre en
        # blanco a mano, como estaría cualquier fila creada antes de esta unidad.
        self.registrar_y_verificar("alexsaz03@gmail.com", sexo="hombre")
        persona = Persona.objects.get(usuario__email="alexsaz03@gmail.com")
        persona.nombre = ""
        persona.save(update_fields=["nombre"])

        from django.apps import apps as apps_reales

        modulo.rellenar_nombres_provisionales(apps_reales, None)

        persona.refresh_from_db()
        # El ejemplo LITERAL de la especificación: "alexsaz03" -> "Alexsaz03".
        self.assertEqual(persona.nombre, "Alexsaz03")

    def test_ninguna_persona_migrada_queda_con_el_nombre_en_blanco(self):
        import importlib

        modulo = importlib.import_module(
            "hogares.migrations.0005_rellena_y_exige_el_nombre"
        )
        from django.apps import apps as apps_reales

        self.registrar_y_verificar("pretel@example.com", sexo="mujer")
        Persona.objects.filter(usuario__email="pretel@example.com").update(nombre="")

        modulo.rellenar_nombres_provisionales(apps_reales, None)

        self.assertFalse(Persona.objects.filter(nombre="").exists())
