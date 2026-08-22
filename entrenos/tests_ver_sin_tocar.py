"""
Tests de la unidad 036 (ver-lo-de-los-demas-sin-tocarlo, R1-R9 de su especificación; R-23/G-43
del mapa) para `entrenos/`: la mitad de VER que faltaba — cualquiera del hogar ve los entrenos
de cualquiera de dentro, pero solo los CAMBIA su dueña o su responsable.

Cuatro personajes, el elenco completo que exige la matriz de Verificación de la especificación:
**Alejandro** (cuenta propia, responsable de Marta), **Marta** (a cargo de Alejandro, sin
cuenta), **Euridice** (cuenta propia, MISMO hogar que Alejandro, sin estar a cargo de nadie ni
tener a nadie a su cargo) y **Carlos** (cuenta propia, OTRO hogar — nunca se une a nadie). Todo
por el cliente de pruebas contra las URLs reales (ADR-019 / lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md: la petición tiene que LLEGAR a lo que
dice probar).
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.acceso import puede_cambiar_lo_de
from hogares.models import Persona, SolicitudEntrada

from .acceso import puede_editar_entrenos
from .models import Entreno

Usuario = get_user_model()

DATOS_DE_MARTA_A_CARGO = {
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


class _ConAlejandroMartaEuridiceYCarlos(PruebaConRegistroAbierto):
    """Alejandro (cuenta propia, responsable de Marta), Marta (a su cargo, sin cuenta),
    Euridice (cuenta propia, MISMO hogar, sin estar a cargo de nadie) y Carlos (cuenta propia,
    OTRO hogar — el "ajeno" que exige la octava cara de tests-que-no-fallan-cuando-deben.md: un
    permiso "propio / mismo hogar / de fuera" necesita un tercero que nunca se una a nadie). La
    sesión queda en Alejandro al terminar `setUp`."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre", peso_kg="93")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", DATOS_DE_MARTA_A_CARGO, follow=True
        )
        self.assertTrue(
            Persona.objects.filter(nombre="Marta", hogar=self.alejandro.hogar).exists()
        )  # control: el alta no falló
        self.marta = Persona.objects.get(nombre="Marta", hogar=self.alejandro.hogar)

        self.client.logout()
        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo, sexo="mujer"
        )
        self.euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice.usuario)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/", follow=True)
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control
        self.client.logout()

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): R8, la frontera del hogar.
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)


# ---------------------------------------------------------------------------------------- #
# Nivel unitario — Verificación, fila 1: los predicados nuevos DELEGAN, no reimplementan.
# ---------------------------------------------------------------------------------------- #


class PuedeEditarEntrenosDelegaEnLaPuertaUnicaTests(_ConAlejandroMartaEuridiceYCarlos):
    """
    `entrenos/acceso.py:puede_editar_entrenos` no decide nada por su cuenta: tiene que devolver
    EXACTAMENTE lo mismo que `hogares.acceso.puede_cambiar_lo_de` para dueña, responsable, otro
    del hogar con cuenta y alguien de otro hogar — la tentación clásica es copiar el `if` en vez
    de llamar (cita literal de la especificación). Mismo patrón que
    `hogares/tests.py:R6_R7_LaReglaVivaEnUnSoloSitioTests` (unidad 025): se llama DIRECTAMENTE,
    con un `RequestFactory`, porque `hogares.acceso.persona_actual` solo mira `request.user`.
    """

    @staticmethod
    def _peticion_de(email):
        peticion = RequestFactory().get("/")
        peticion.user = Usuario.objects.get(email=email)
        return peticion

    def test_dueña(self):
        peticion = self._peticion_de("alejandro@example.com")
        self.assertEqual(
            puede_editar_entrenos(peticion, self.alejandro.id),
            puede_cambiar_lo_de(peticion, self.alejandro.id),
        )
        self.assertTrue(puede_editar_entrenos(peticion, self.alejandro.id))

    def test_responsable(self):
        peticion = self._peticion_de("alejandro@example.com")
        self.assertEqual(
            puede_editar_entrenos(peticion, self.marta.id),
            puede_cambiar_lo_de(peticion, self.marta.id),
        )
        self.assertTrue(puede_editar_entrenos(peticion, self.marta.id))

    def test_otro_del_hogar_con_cuenta(self):
        peticion = self._peticion_de("euridice@example.com")
        self.assertEqual(
            puede_editar_entrenos(peticion, self.alejandro.id),
            puede_cambiar_lo_de(peticion, self.alejandro.id),
        )
        self.assertFalse(puede_editar_entrenos(peticion, self.alejandro.id))

    def test_ajeno_de_otro_hogar(self):
        peticion = self._peticion_de("carlos@example.com")
        self.assertEqual(
            puede_editar_entrenos(peticion, self.alejandro.id),
            puede_cambiar_lo_de(peticion, self.alejandro.id),
        )
        self.assertFalse(puede_editar_entrenos(peticion, self.alejandro.id))


# ---------------------------------------------------------------------------------------- #
# R1/R6/R7/R8 — la matriz de VER por HTTP.
# ---------------------------------------------------------------------------------------- #


class R1_R6_R7_R8_VerLosEntrenosDeCualquieraDelHogarTests(_ConAlejandroMartaEuridiceYCarlos):
    """200 para los cuatro roles del hogar (dueña, responsable de la persona, otro del hogar
    con cuenta, responsable de un tercero mirando a alguien de quien NO es responsable), 404
    para alguien de otro hogar."""

    def setUp(self):
        super().setUp()
        self.entreno_de_alejandro = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="hyrox",
            intensidad="fuerte", minutos=60, calorias=1302, calorias_manuales=False,
        )

    def test_r1_dueña_ve_sus_propios_entrenos(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'id="entreno-{self.entreno_de_alejandro.id}"')
        self.assertContains(respuesta, "1302")

    def test_r6_responsable_ve_los_entrenos_de_su_persona_a_cargo(self):
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)

    def test_r1_otro_del_hogar_con_cuenta_ve_los_entrenos_de_la_dueña(self):
        """El ESTRENO de esta unidad: antes de ella, esto daba 404 (mutación #2 de
        Verificación). R1, el episodio del contrato: Euridice ve fecha, tipo y calorías —
        aquí la fecha se ancla por su `id="entreno-N"` (elemento único), no por el texto:
        con `LANGUAGE_CODE="es"` la plantilla pinta la fecha localizada ("21 de agosto de
        2026"), no el ISO de `str(fecha)`."""
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn(f'id="entreno-{self.entreno_de_alejandro.id}"', contenido)
        self.assertIn("Hyrox", contenido)
        self.assertIn("1302", contenido)

    def test_r7_responsable_de_marta_ve_los_entrenos_de_euridice_sin_ser_su_responsable(self):
        """R7, caso límite — ser responsable de Marta no da mando sobre Euridice, pero SÍ la
        deja verla: ver y cambiar son preguntas distintas."""
        entreno_de_euridice = Entreno.objects.create(
            persona=self.euridice, fecha=timezone.localdate(), deporte="nadar",
            intensidad="media", minutos=30, calorias=200, calorias_manuales=True,
        )
        respuesta = self.client.get(f"/entrenos/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'id="entreno-{entreno_de_euridice.id}"')

    def test_r7_al_reves_euridice_ve_los_entrenos_de_marta_sin_ser_su_responsable(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)

    def test_r8_alguien_de_otro_hogar_no_ve_los_entrenos_de_la_dueña(self):
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)


# ---------------------------------------------------------------------------------------- #
# R3/R6/R7/R8 — la matriz de CAMBIAR por HTTP, con el dato contado y comparado antes y después.
# ---------------------------------------------------------------------------------------- #


class R3_R6_R7_R8_CambiarLosEntrenosDeOtroSigueBloqueadoTests(_ConAlejandroMartaEuridiceYCarlos):
    """Ver más no compra tocar más: apuntar/corregir/borrar dan 404 para quien SOLO puede
    mirar, y los entrenos de la persona objetivo quedan exactamente como estaban."""

    def setUp(self):
        super().setUp()
        self.entreno_de_alejandro = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=20, calorias=100, calorias_manuales=True,
        )

    def _entrenos_de_alejandro(self):
        return list(
            Entreno.objects.filter(persona=self.alejandro).values(
                "id", "fecha", "deporte", "minutos", "calorias"
            )
        )

    def test_r3_euridice_no_puede_apuntar_un_entreno_a_alejandro(self):
        antes = self._entrenos_de_alejandro()
        respuesta = self._como("euridice@example.com").post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._entrenos_de_alejandro(), antes)

    def test_r3_euridice_no_puede_corregir_un_entreno_de_alejandro(self):
        antes = self._entrenos_de_alejandro()
        respuesta = self._como("euridice@example.com").post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/corregir/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "99", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._entrenos_de_alejandro(), antes)

    def test_r3_euridice_no_puede_borrar_un_entreno_de_alejandro(self):
        antes = self._entrenos_de_alejandro()
        respuesta = self._como("euridice@example.com").post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/borrar/"
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._entrenos_de_alejandro(), antes)

    def test_r7_responsable_de_marta_no_puede_tocar_los_entrenos_de_euridice(self):
        entreno_de_euridice = Entreno.objects.create(
            persona=self.euridice, fecha=timezone.localdate(), deporte="nadar",
            intensidad="media", minutos=30, calorias=200, calorias_manuales=True,
        )
        antes = list(
            Entreno.objects.filter(persona=self.euridice).values("id", "minutos")
        )
        respuesta_corregir = self.client.post(
            f"/entrenos/{self.euridice.id}/{entreno_de_euridice.id}/corregir/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "nadar",
             "intensidad": "media", "minutos": "5", "calorias": ""},
        )
        self.assertEqual(respuesta_corregir.status_code, 404)
        respuesta_apuntar = self.client.post(
            f"/entrenos/{self.euridice.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "10", "calorias": ""},
        )
        self.assertEqual(respuesta_apuntar.status_code, 404)
        self.assertEqual(
            list(Entreno.objects.filter(persona=self.euridice).values("id", "minutos")), antes
        )

    def test_r8_alguien_de_otro_hogar_no_puede_apuntar_ni_borrar(self):
        antes = self._entrenos_de_alejandro()
        cliente = self._como("carlos@example.com")
        respuesta_apuntar = cliente.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta_apuntar.status_code, 404)
        respuesta_borrar = cliente.post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/borrar/"
        )
        self.assertEqual(respuesta_borrar.status_code, 404)
        self.assertEqual(self._entrenos_de_alejandro(), antes)

    def _como(self, email):
        self.client.logout()
        self.client.login(username=email, password=CLAVE_VALIDA)
        return self.client


# ---------------------------------------------------------------------------------------- #
# R2/R6 — lo que la pantalla ofrece: presente para quien manda, ausente para quien mira.
# ---------------------------------------------------------------------------------------- #


class R2_R6_LoQueLaPantallaOfreceTests(_ConAlejandroMartaEuridiceYCarlos):
    def setUp(self):
        super().setUp()
        self.entreno_de_alejandro = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=20, calorias=100, calorias_manuales=True,
        )

    def test_r2_euridice_no_ve_el_formulario_de_apuntar_en_los_entrenos_de_alejandro(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn(f'/entrenos/{self.alejandro.id}/apuntar/', contenido)
        self.assertNotIn("Apuntar entreno", contenido)

    def test_r2_euridice_no_ve_los_enlaces_de_corregir_ni_borrar(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn(
            f'/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/corregir/', contenido
        )
        self.assertNotIn(
            f'/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/borrar/', contenido
        )
        # Pero el DATO sigue ahí: solo desaparecen las acciones, no la información (R1).
        self.assertIn(f'id="entreno-{self.entreno_de_alejandro.id}"', contenido)

    def test_r6_la_dueña_sigue_viendo_su_propio_formulario_y_sus_enlaces(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        self.assertIn(f'/entrenos/{self.alejandro.id}/apuntar/', contenido)
        self.assertIn(
            f'/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/corregir/', contenido
        )
        self.assertIn(
            f'/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/borrar/', contenido
        )

    def test_r6_el_responsable_sigue_viendo_el_formulario_y_los_enlaces_de_su_cargo(self):
        entreno_de_marta = Entreno.objects.create(
            persona=self.marta, fecha=timezone.localdate(), deporte="nadar",
            intensidad="suave", minutos=15, calorias=80, calorias_manuales=True,
        )
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        contenido = respuesta.content.decode()
        self.assertIn(f'/entrenos/{self.marta.id}/apuntar/', contenido)
        self.assertIn(f'/entrenos/{self.marta.id}/{entreno_de_marta.id}/corregir/', contenido)
        self.assertIn(f'/entrenos/{self.marta.id}/{entreno_de_marta.id}/borrar/', contenido)


# ---------------------------------------------------------------------------------------- #
# Unidad 038, R1/R2/R3 — el subtítulo (`entrenos/ver.html:30-37`) pasa de dos ramas a tres,
# calcadas del patrón de `perfiles/templates/perfiles/peso.html:30-41`: propio (segunda
# persona), responsable (invita a apuntar, nombrando a la persona) y solo lectura (dice que es
# de esa persona y que solo ella o su responsable puede apuntarlo — nunca invita a mirar).
# ---------------------------------------------------------------------------------------- #


class R1_R2_R3_ElSubtituloHablaSegunQuienMiraTests(_ConAlejandroMartaEuridiceYCarlos):
    """Cada assert de texto lleva su negativo: lo que SÍ sale y los otros dos textos, que NO.
    Se compara sobre el HTML con los espacios normalizados: la plantilla parte las frases
    largas en varias líneas fuente (indentación incluida), y esa indentación sobrevive tal
    cual al render — comparar contra el texto SIN normalizar rompería por un salto de línea
    que no tiene nada que ver con lo que el criterio promete."""

    def _como(self, email):
        self.client.logout()
        self.client.login(username=email, password=CLAVE_VALIDA)
        return self.client

    @staticmethod
    def _normalizado(respuesta):
        return " ".join(respuesta.content.decode().split())

    def test_r1_quien_solo_mira_no_recibe_ninguna_invitacion_a_apuntar(self):
        """Euridice: mismo hogar que Alejandro, sin ser su responsable — solo mira."""
        respuesta = self._como("euridice@example.com").get(f"/entrenos/{self.alejandro.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn(
            "Solo lectura: el resto del hogar ve los entrenos de Alejandro, pero solo "
            "Alejandro (o su responsable) puede apuntarlos, corregirlos o borrarlos.",
            contenido,
        )
        self.assertNotIn("Apunta lo que entrenó Alejandro", contenido)
        self.assertNotIn("Apunta lo que has entrenado", contenido)

    def test_r2_el_responsable_si_es_invitado_a_apuntar_nombrando_a_su_cargo(self):
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn(
            "Apunta lo que entrenó Marta y cuenta en las calorías que le tocan hoy.", contenido
        )
        self.assertNotIn("Solo lectura", contenido)
        self.assertNotIn("Apunta lo que has entrenado", contenido)

    def test_r3_uno_mismo_sigue_hablandole_de_tu(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn(
            "Apunta lo que has entrenado y cuenta en las calorías que te tocan hoy.", contenido
        )
        self.assertNotIn("Solo lectura", contenido)
        self.assertNotIn("Apunta lo que entrenó Alejandro", contenido)


# ---------------------------------------------------------------------------------------- #
# Unidad 038, R7 — caso límite: la pantalla SIN ningún entreno apuntado (`entrenos/ver.html:
# 125-135`) respeta los mismos tres estados. A quien solo mira no se le invita a apuntar el
# primero.
# ---------------------------------------------------------------------------------------- #


class R7_CasoVacioLosTresEstadosTests(_ConAlejandroMartaEuridiceYCarlos):
    """Ningún entreno se crea en `setUp`: los tres estados se miran sobre la lista vacía."""

    def _como(self, email):
        self.client.logout()
        self.client.login(username=email, password=CLAVE_VALIDA)
        return self.client

    @staticmethod
    def _normalizado(respuesta):
        return " ".join(respuesta.content.decode().split())

    def test_quien_solo_mira_no_es_invitado_a_apuntar_el_primero(self):
        respuesta = self._como("euridice@example.com").get(f"/entrenos/{self.alejandro.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn("Alejandro todavía no tiene ningún entreno apuntado.", contenido)
        self.assertNotIn("Apúntale el primero aquí abajo", contenido)
        self.assertNotIn("Todavía no has apuntado ningún entreno", contenido)

    def test_el_responsable_si_es_invitado_a_apuntar_el_primero(self):
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn(
            "Marta todavía no tiene ningún entreno apuntado. Apúntale el primero aquí abajo.",
            contenido,
        )
        self.assertNotIn("Todavía no has apuntado ningún entreno", contenido)

    def test_uno_mismo_sigue_viendo_su_propio_texto(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn(
            "Todavía no has apuntado ningún entreno. En cuanto apuntes el primero, aparecerá "
            "aquí y sus calorías se sumarán a lo que te toca comer hoy.",
            contenido,
        )
        self.assertNotIn("Apúntale el primero aquí abajo", contenido)


# ---------------------------------------------------------------------------------------- #
# Unidad 038, R6 — el `help_text` de `calorias` (`entrenos/forms.py`) ya no dice "tu peso": la
# redacción es neutra, para que valga igual rellenando lo propio o lo de un cargo.
# ---------------------------------------------------------------------------------------- #


class R6_ElHelpTextDeCaloriasEsNeutroTests(_ConAlejandroMartaEuridiceYCarlos):
    @staticmethod
    def _normalizado(respuesta):
        return " ".join(respuesta.content.decode().split())

    def test_el_help_text_no_tutea_ni_rellenando_lo_propio(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn("y el peso de esa persona.", contenido)
        self.assertNotIn("y tu peso.", contenido)

    def test_el_help_text_no_tutea_rellenando_lo_de_un_cargo(self):
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        contenido = self._normalizado(respuesta)
        self.assertIn("y el peso de esa persona.", contenido)
        self.assertNotIn("y tu peso.", contenido)
