"""
Tests de la unidad 036 (ver-lo-de-los-demas-sin-tocarlo, R1-R9 de su especificación; R-23/G-43
del mapa) para `cierres/`: la mitad de VER que faltaba — cualquiera del hogar ve el histórico
de días cerrados de cualquiera de dentro, pero solo lo CAMBIA su dueña o su responsable, y el
GET/POST comparten pantalla y URL (decisión (1) de la especificación): el guarda del POST es de
SERVIDOR y se prueba llamándolo directamente (decisión (2), ADR-019).

Mismo elenco que `entrenos/tests_ver_sin_tocar.py`: **Alejandro** (cuenta propia, responsable de
Marta), **Marta** (a cargo de Alejandro, sin cuenta), **Euridice** (cuenta propia, MISMO hogar,
sin estar a cargo de nadie ni tener a nadie a su cargo) y **Carlos** (cuenta propia, OTRO hogar).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.acceso import puede_cambiar_lo_de
from hogares.models import Persona, SolicitudEntrada

from .acceso import puede_editar_cierres
from .models import CierreDeDia, DiaSaltado

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
    """Mismo montaje que `entrenos/tests_ver_sin_tocar.py`. La sesión queda en Alejandro al
    terminar `setUp`."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
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

        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

    def _como(self, email):
        self.client.logout()
        self.client.login(username=email, password=CLAVE_VALIDA)
        return self.client


# ---------------------------------------------------------------------------------------- #
# Nivel unitario — Verificación, fila 1.
# ---------------------------------------------------------------------------------------- #


class PuedeEditarCierresDelegaEnLaPuertaUnicaTests(_ConAlejandroMartaEuridiceYCarlos):
    """`cierres/acceso.py:puede_editar_cierres` delega ENTERO en
    `hogares.acceso.puede_cambiar_lo_de`, sin reimplementar la regla. Mismo patrón que
    `hogares/tests.py:R6_R7_LaReglaVivaEnUnSoloSitioTests`."""

    @staticmethod
    def _peticion_de(email):
        peticion = RequestFactory().get("/")
        peticion.user = Usuario.objects.get(email=email)
        return peticion

    def test_dueña(self):
        peticion = self._peticion_de("alejandro@example.com")
        self.assertEqual(
            puede_editar_cierres(peticion, self.alejandro.id),
            puede_cambiar_lo_de(peticion, self.alejandro.id),
        )
        self.assertTrue(puede_editar_cierres(peticion, self.alejandro.id))

    def test_responsable(self):
        peticion = self._peticion_de("alejandro@example.com")
        self.assertEqual(
            puede_editar_cierres(peticion, self.marta.id),
            puede_cambiar_lo_de(peticion, self.marta.id),
        )
        self.assertTrue(puede_editar_cierres(peticion, self.marta.id))

    def test_otro_del_hogar_con_cuenta(self):
        peticion = self._peticion_de("euridice@example.com")
        self.assertEqual(
            puede_editar_cierres(peticion, self.alejandro.id),
            puede_cambiar_lo_de(peticion, self.alejandro.id),
        )
        self.assertFalse(puede_editar_cierres(peticion, self.alejandro.id))

    def test_ajeno_de_otro_hogar(self):
        peticion = self._peticion_de("carlos@example.com")
        self.assertEqual(
            puede_editar_cierres(peticion, self.alejandro.id),
            puede_cambiar_lo_de(peticion, self.alejandro.id),
        )
        self.assertFalse(puede_editar_cierres(peticion, self.alejandro.id))


# ---------------------------------------------------------------------------------------- #
# R4/R6/R7/R8 — la matriz de VER por HTTP.
# ---------------------------------------------------------------------------------------- #


class R4_R6_R7_R8_VerElDiaDeCualquieraDelHogarTests(_ConAlejandroMartaEuridiceYCarlos):
    def setUp(self):
        super().setUp()
        self.cierre_de_alejandro = CierreDeDia.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), respuesta=CierreDeDia.LO_SEGUI
        )

    def test_r4_dueña_ve_su_propio_historico(self):
        respuesta = self.client.get(f"/cierres/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'id="cierre-{self.cierre_de_alejandro.id}"')

    def test_r6_responsable_ve_el_historico_de_su_persona_a_cargo(self):
        respuesta = self.client.get(f"/cierres/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)

    def test_r4_otro_del_hogar_con_cuenta_ve_el_historico_de_la_dueña(self):
        """El ESTRENO de esta unidad: antes daba 404 (mutación #2 de Verificación). Se ancla
        por `id="cierre-N"` (elemento único), no por el texto de la fecha: con
        `LANGUAGE_CODE="es"` la plantilla la pinta localizada ("21 de agosto de 2026"), no el
        ISO de `str(fecha)`."""
        cliente = self._como("euridice@example.com")
        respuesta = cliente.get(f"/cierres/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'id="cierre-{self.cierre_de_alejandro.id}"')

    def test_r7_responsable_de_marta_ve_el_historico_de_euridice_sin_ser_su_responsable(self):
        cierre_de_euridice = CierreDeDia.objects.create(
            persona=self.euridice, fecha=timezone.localdate(), respuesta=CierreDeDia.A_MEDIAS
        )
        respuesta = self.client.get(f"/cierres/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'id="cierre-{cierre_de_euridice.id}"')

    def test_r7_al_reves_euridice_ve_el_historico_de_marta_sin_ser_su_responsable(self):
        cliente = self._como("euridice@example.com")
        respuesta = cliente.get(f"/cierres/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)

    def test_r8_alguien_de_otro_hogar_no_ve_el_historico_de_la_dueña(self):
        cliente = self._como("carlos@example.com")
        respuesta = cliente.get(f"/cierres/{self.alejandro.id}/")
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)


# ---------------------------------------------------------------------------------------- #
# R5/R6/R7/R8 — la matriz de CAMBIAR por HTTP: cerrar, responder, saltar. El guarda del POST
# es de SERVIDOR (decisión (2)) y se prueba llamándolo directamente, con el dato contado y
# comparado antes y después.
# ---------------------------------------------------------------------------------------- #


class R5_R6_R7_R8_CambiarElDiaDeOtroSigueBloqueadoTests(_ConAlejandroMartaEuridiceYCarlos):
    def setUp(self):
        super().setUp()
        self.cierre_de_alejandro = CierreDeDia.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), respuesta=CierreDeDia.LO_SEGUI
        )

    def _cierres_de_alejandro(self):
        return list(
            CierreDeDia.objects.filter(persona=self.alejandro).values("id", "fecha", "respuesta")
        )

    def test_r5_euridice_no_puede_cerrar_un_dia_nuevo_de_alejandro(self):
        antes = self._cierres_de_alejandro()
        cliente = self._como("euridice@example.com")
        respuesta = cliente.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": (timezone.localdate() - timedelta(days=1)).isoformat(),
             "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._cierres_de_alejandro(), antes)

    def test_r5_euridice_no_puede_cambiar_un_cierre_ya_existente_de_alejandro(self):
        antes = self._cierres_de_alejandro()
        cliente = self._como("euridice@example.com")
        respuesta = cliente.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "no_lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._cierres_de_alejandro(), antes)

    def test_r5_euridice_no_puede_responder_la_pregunta_rapida_de_alejandro(self):
        respuesta = self._como("euridice@example.com").post(
            f"/cierres/{self.alejandro.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(
            CierreDeDia.objects.filter(persona=self.alejandro).count(), 1
        )  # solo el que ya había

    def test_r5_euridice_no_puede_saltar_el_dia_de_alejandro(self):
        respuesta = self._como("euridice@example.com").post(
            f"/cierres/{self.alejandro.id}/saltar/"
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(DiaSaltado.objects.filter(persona=self.alejandro).exists())

    def test_r7_responsable_de_marta_no_puede_cerrar_el_dia_de_euridice(self):
        cierre_de_euridice = CierreDeDia.objects.create(
            persona=self.euridice, fecha=timezone.localdate(), respuesta=CierreDeDia.A_MEDIAS
        )
        respuesta = self.client.post(
            f"/cierres/{self.euridice.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        cierre_de_euridice.refresh_from_db()
        self.assertEqual(cierre_de_euridice.respuesta, CierreDeDia.A_MEDIAS)

    def test_r8_alguien_de_otro_hogar_no_puede_cerrar_ni_responder_ni_saltar(self):
        antes = self._cierres_de_alejandro()
        cliente = self._como("carlos@example.com")
        respuesta_cerrar = cliente.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": (timezone.localdate() - timedelta(days=1)).isoformat(),
             "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta_cerrar.status_code, 404)
        respuesta_responder = cliente.post(
            f"/cierres/{self.alejandro.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertEqual(respuesta_responder.status_code, 404)
        respuesta_saltar = cliente.post(f"/cierres/{self.alejandro.id}/saltar/")
        self.assertEqual(respuesta_saltar.status_code, 404)
        self.assertEqual(self._cierres_de_alejandro(), antes)


# ---------------------------------------------------------------------------------------- #
# R4/R6 — lo que la pantalla ofrece.
# ---------------------------------------------------------------------------------------- #


class R4_R6_LoQueLaPantallaOfreceTests(_ConAlejandroMartaEuridiceYCarlos):
    def setUp(self):
        super().setUp()
        self.cierre_de_alejandro = CierreDeDia.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), respuesta=CierreDeDia.LO_SEGUI
        )

    def test_r4_euridice_no_ve_el_formulario_de_cerrar_en_el_dia_de_alejandro(self):
        cliente = self._como("euridice@example.com")
        respuesta = cliente.get(f"/cierres/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn("Guardar", contenido)

    def test_r4_euridice_no_ve_el_enlace_cambiar_de_ningun_cierre(self):
        cliente = self._como("euridice@example.com")
        respuesta = cliente.get(f"/cierres/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn(
            f"/cierres/{self.alejandro.id}/?fecha={self.cierre_de_alejandro.fecha:%Y-%m-%d}",
            contenido,
        )
        # El DATO sigue presente: solo desaparece la acción, no la información.
        self.assertIn(f'id="cierre-{self.cierre_de_alejandro.id}"', contenido)

    def test_r4_euridice_no_ve_la_pregunta_pendiente_de_alejandro_en_su_pantalla_de_dia(self):
        """R4, el hueco explícito del contrato: la pregunta pendiente de OTRA persona nunca se
        pinta en `/cierres/<id>/` — hoy esa pregunta solo vive en el Inicio de quien pregunta
        (`paginas/templates/paginas/inicio.html`), y solo sobre SU PROPIO día pendiente
        (`paginas/views.py:inicio` la calcula siempre para `persona_actual`, nunca para la
        persona que se está mirando): este test deja el comportamiento afirmado, no supuesto."""
        cliente = self._como("euridice@example.com")
        respuesta = cliente.get(f"/cierres/{self.alejandro.id}/")
        self.assertNotContains(respuesta, 'id="pregunta-cierre"')
        self.assertNotContains(respuesta, "¿Cumpliste el plan de ayer")
        self.assertNotContains(respuesta, f"/cierres/{self.alejandro.id}/responder/")

    def test_r6_la_dueña_sigue_viendo_su_propio_formulario_y_sus_cambiar(self):
        respuesta = self.client.get(f"/cierres/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        self.assertIn("Guardar", contenido)
        self.assertIn(
            f"/cierres/{self.alejandro.id}/?fecha={self.cierre_de_alejandro.fecha:%Y-%m-%d}",
            contenido,
        )

    def test_r6_el_responsable_sigue_viendo_el_formulario_de_su_cargo(self):
        respuesta = self.client.get(f"/cierres/{self.marta.id}/")
        self.assertContains(respuesta, "Guardar")
