"""
Tests de la unidad 025 (lo-de-quien-tienes-a-tu-cargo.md) para `cierres/`: R3 (responder,
saltar y cerrar el día de una persona a cargo), la mitad de R4 que toca esta app, y R7 (caso
límite, de punta a punta por HTTP: la puerta de `cierres/` tampoco depende de que exista un
`Perfil`).

Los tres personajes de la especificación: **Alejandro** (cuenta propia), **Marta** (a su
cargo, sin cuenta) y **Euridice** (cuenta propia, del mismo hogar, sin estar a cargo de
nadie). Todo por el cliente de pruebas contra las URLs reales.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Persona, SolicitudEntrada

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


class _ConAlejandroMartaYEuridice(PruebaConRegistroAbierto):
    """Alejandro (cuenta propia), Marta (a su cargo, sin cuenta) y Euridice (cuenta propia,
    del MISMO hogar, sin estar a cargo de nadie). La sesión queda en Alejandro al terminar."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", DATOS_DE_MARTA_A_CARGO, follow=True
        )
        # `follow=True` hace que este 200 sea el mismo tanto si el alta acierta como si el
        # formulario es inválido (bug 032): lo que de verdad prueba que el alta no falló es
        # que la Persona exista.
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

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)


class R3_ResponderSaltarYCerrarElDiaDeUnaPersonaACargoTests(_ConAlejandroMartaYEuridice):
    """R3 — Alejandro contesta el cierre del día de Marta (responder, saltar y cerrar): el
    cierre queda apuntado a nombre de ELLA."""

    def test_responder_cierra_el_dia_pendiente_de_marta_a_su_nombre(self):
        ayer = timezone.localdate() - timezone.timedelta(days=1)
        respuesta = self.client.post(
            f"/cierres/{self.marta.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertEqual(respuesta.status_code, 302)
        cierre = CierreDeDia.objects.get(persona=self.marta, fecha=ayer)
        self.assertEqual(cierre.respuesta, "lo_segui")

    def test_saltar_registra_que_marta_se_salto_el_dia_pendiente(self):
        ayer = timezone.localdate() - timezone.timedelta(days=1)
        respuesta = self.client.post(f"/cierres/{self.marta.id}/saltar/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            DiaSaltado.objects.filter(persona=self.marta, fecha=ayer).exists()
        )

    def test_cerrar_a_mano_desde_progreso_queda_a_nombre_de_marta(self):
        respuesta = self.client.get(f"/cierres/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.post(
            f"/cierres/{self.marta.id}/",
            {
                "fecha": timezone.localdate().isoformat(),
                "respuesta": "a_medias",
                "calorias_comidas": "",
                "nota": "",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            CierreDeDia.objects.filter(
                persona=self.marta, fecha=timezone.localdate(), respuesta="a_medias"
            ).exists()
        )
        self.assertFalse(
            CierreDeDia.objects.filter(
                persona=self.alejandro, fecha=timezone.localdate()
            ).exists()
        )


class R4_LaPuertaEsSoloParaElResponsableTests(_ConAlejandroMartaYEuridice):
    """R4 — Euridice (misma casa, sin ser responsable de Marta) recibe 404 en TODAS las rutas
    de R3 llamando con el id de Marta; nunca 403. Y Alejandro recibe 404 contra Euridice."""

    def test_euridice_no_puede_responder_por_marta(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.marta.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(CierreDeDia.objects.filter(persona=self.marta).exists())

    def test_euridice_no_puede_saltar_por_marta(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(f"/cierres/{self.marta.id}/saltar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(DiaSaltado.objects.filter(persona=self.marta).exists())

    def test_euridice_ve_pero_no_puede_cerrar_a_mano_el_dia_de_marta(self):
        """
        Actualizado por la unidad 036 (R4/R5/R7/R-23/G-43): antes de esa unidad, VER y
        CAMBIAR el día de otra persona eran la MISMA puerta, así que el GET daba 404. Desde
        la 036, todo el hogar VE el histórico de cualquiera de dentro; lo que sigue dando 404
        —con el guarda de SERVIDOR del POST, no solo escondiendo el formulario (ADR-019)— es
        CAMBIARLO.
        """
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta_ver = self.client.get(f"/cierres/{self.marta.id}/")
        self.assertEqual(respuesta_ver.status_code, 200)
        self.assertNotIn("Guardar", respuesta_ver.content.decode())

        respuesta_post = self.client.post(
            f"/cierres/{self.marta.id}/",
            {
                "fecha": timezone.localdate().isoformat(),
                "respuesta": "no_lo_segui",
                "calorias_comidas": "",
                "nota": "",
            },
        )
        self.assertEqual(respuesta_post.status_code, 404)
        self.assertFalse(CierreDeDia.objects.filter(persona=self.marta).exists())

    def test_alejandro_ve_pero_no_puede_cerrar_el_dia_de_euridice_aunque_tenga_a_marta_a_cargo(self):
        """Actualizado por la unidad 036 (R7, caso límite explícito del contrato): ser
        responsable de Marta no da mando sobre Euridice, pero sí la deja VER — antes de la
        036 esto daba 404 porque VER y CAMBIAR eran la misma puerta."""
        respuesta = self.client.get(f"/cierres/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("Guardar", respuesta.content.decode())

        respuesta_post = self.client.post(
            f"/cierres/{self.euridice.id}/",
            {
                "fecha": timezone.localdate().isoformat(),
                "respuesta": "lo_segui",
                "calorias_comidas": "",
                "nota": "",
            },
        )
        self.assertEqual(respuesta_post.status_code, 404)
        self.assertFalse(CierreDeDia.objects.filter(persona=self.euridice).exists())


class R7_LaPuertaMiraResponsableNoPerfilTests(_ConAlejandroMartaYEuridice):
    """R7 (caso límite) — una persona a cargo SIN `Perfil` no revienta la puerta de
    `cierres/`, que no depende en ningún punto de que exista un `Perfil`."""

    def setUp(self):
        super().setUp()
        self.sin_perfil = Persona.objects.create(
            hogar=self.alejandro.hogar, nombre="SinPerfil", responsable=self.alejandro
        )
        self.assertFalse(hasattr(self.sin_perfil, "perfil"))  # control

    def test_alejandro_puede_cerrar_el_dia_de_una_persona_a_cargo_sin_perfil(self):
        respuesta = self.client.post(
            f"/cierres/{self.sin_perfil.id}/",
            {
                "fecha": timezone.localdate().isoformat(),
                "respuesta": "lo_segui",
                "calorias_comidas": "",
                "nota": "",
            },
        )
        self.assertNotEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(CierreDeDia.objects.filter(persona=self.sin_perfil).exists())

    def test_euridice_ve_pero_no_puede_cerrar_el_dia_de_una_persona_a_cargo_de_otro_sin_perfil(
        self,
    ):
        """Actualizado por la unidad 036: `persona_visible_o_404` tampoco depende de que
        exista un `Perfil` (misma garantía que ya tenía la puerta de editar, R7 caso límite),
        así que Euridice VE la pantalla sin reventar, aunque no pueda cerrar nada."""
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/cierres/{self.sin_perfil.id}/")
        self.assertNotEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("Guardar", respuesta.content.decode())
