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

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from perfiles.logica import calcular_objetivo_del_dia
from perfiles.models import MedicionPeso, Perfil

from .models import Persona, SolicitudEntrada

Usuario = get_user_model()

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
        self.assertEqual(respuesta.status_code, 200)  # control: el alta no falló
        self.euridice = Persona.objects.get(nombre="Euridice", hogar=self.alejandro.hogar)


class R1_SinCorreoEnNingunaPantallaTests(_ConAlejandroYEuridiceACargo):
    """
    R1 — en ninguna de las pantallas que antes enseñaban un correo (Inicio, Progreso, su peso,
    apuntar plan, sus datos, la barra de arriba, la pantalla de la casa) aparece ya ninguna
    dirección de correo — se lee el nombre.
    """

    def test_ninguna_pantalla_muestra_ningun_correo(self):
        rutas = [
            "/",  # Inicio
            f"/progreso/{self.alejandro.id}/",  # Progreso
            f"/perfiles/{self.alejandro.id}/peso/",  # su peso
            f"/planes/{self.alejandro.id}/apuntar/",  # apuntar plan
            f"/perfiles/{self.alejandro.id}/",  # sus datos
            "/hogares/mi-hogar/",  # la pantalla de la casa
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                self.assertNotIn(
                    "alejandro@example.com", respuesta.content.decode(),
                    f"{ruta} sigue enseñando el correo de Alejandro",
                )
                self.assertIn("Alejandro", respuesta.content.decode())

    def test_la_barra_de_arriba_enseña_el_nombre_no_el_correo(self):
        respuesta = self.client.get("/")
        contenido = respuesta.content.decode()
        self.assertNotIn("alejandro@example.com", contenido)
        self.assertIn("Alejandro", contenido)


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
        self.assertEqual(respuesta.status_code, 200)

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

    def test_ve_las_dos_fichas_marcadas_correctamente(self):
        respuesta = self.client.get("/hogares/mi-hogar/")
        contenido = respuesta.content.decode()

        self.assertIn("Alejandro", contenido)
        self.assertIn("Euridice", contenido)
        self.assertIn("Entra con su cuenta", contenido)
        self.assertIn("A cargo de Alejandro", contenido)


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
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
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

        self.registrar_y_verificar("preteleuri@gmail.com", sexo="mujer")
        Persona.objects.filter(usuario__email="preteleuri@gmail.com").update(nombre="")

        modulo.rellenar_nombres_provisionales(apps_reales, None)

        self.assertFalse(Persona.objects.filter(nombre="").exists())
