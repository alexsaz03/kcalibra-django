"""
Tests de la unidad 025 (lo-de-quien-tienes-a-tu-cargo.md) para `entrenos/`: R2 (ver, apuntar,
corregir y borrar entrenos de una persona a cargo), la mitad de R4 que toca esta app, y R7
(caso límite — aquí SÍ se puede probar de punta a punta por HTTP sin toparse con ningún 404
"ajeno a esta unidad": la puerta de `entrenos/` no depende de que exista un `Perfil`, a
diferencia de `perfiles/`).

Los tres personajes de la especificación: **Alejandro** (cuenta propia), **Marta** (a su
cargo, sin cuenta) y **Euridice** (cuenta propia, del mismo hogar, sin estar a cargo de
nadie). Todo por el cliente de pruebas contra las URLs reales.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Persona, SolicitudEntrada

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


class _ConAlejandroMartaYEuridice(PruebaConRegistroAbierto):
    """Alejandro (cuenta propia), Marta (a su cargo, sin cuenta) y Euridice (cuenta propia,
    del MISMO hogar, sin estar a cargo de nadie). La sesión queda en Alejandro al terminar."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre", peso_kg="93")
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


class R2_VerApuntarCorregirYBorrarEntrenosDeUnaPersonaACargoTests(_ConAlejandroMartaYEuridice):
    """R2 — Alejandro entra en los entrenos de Marta, VE la pantalla, y puede apuntar,
    corregir y borrar un entreno; el entreno queda colgando de ELLA. Hoy la pantalla da 404."""

    def test_alejandro_ve_la_pantalla_de_entrenos_de_marta(self):
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Marta", respuesta.content.decode())

    def test_alejandro_apunta_un_entreno_a_marta_y_queda_colgando_de_ella(self):
        respuesta = self.client.post(
            f"/entrenos/{self.marta.id}/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "deporte": "nadar",
                "intensidad": "media",
                "minutos": "30",
                "calorias": "",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        entreno = Entreno.objects.get(persona=self.marta, deporte="nadar")
        self.assertGreater(entreno.calorias, 0)  # estimado con EL PESO de Marta, no revienta
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro, deporte="nadar").exists())

    def test_alejandro_corrige_un_entreno_de_marta(self):
        entreno = Entreno.objects.create(
            persona=self.marta, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=20, calorias=100, calorias_manuales=True,
        )
        respuesta = self.client.post(
            f"/entrenos/{self.marta.id}/{entreno.id}/corregir/",
            {
                "fecha": timezone.localdate().isoformat(),
                "deporte": "correr",
                "intensidad": "media",
                "minutos": "25",
                "calorias": "100",
            },
        )
        self.assertEqual(respuesta.status_code, 302)  # redirect tras corregir, como a sí mismo
        entreno.refresh_from_db()
        self.assertEqual(entreno.minutos, 25)

    def test_alejandro_borra_un_entreno_de_marta(self):
        entreno = Entreno.objects.create(
            persona=self.marta, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=20, calorias=100, calorias_manuales=True,
        )
        respuesta = self.client.post(f"/entrenos/{self.marta.id}/{entreno.id}/borrar/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Entreno.objects.filter(id=entreno.id).exists())


class R4_LaPuertaEsSoloParaElResponsableTests(_ConAlejandroMartaYEuridice):
    """R4 — Euridice (misma casa, sin ser responsable de Marta) recibe 404 en TODAS las rutas
    de R2 llamando con el id de Marta; nunca 403. Y Alejandro recibe 404 contra Euridice, que
    tiene cuenta propia: tener a Marta a cargo no da permiso sobre el resto de la casa."""

    def setUp(self):
        super().setUp()
        self.entreno_de_marta = Entreno.objects.create(
            persona=self.marta, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=20, calorias=100, calorias_manuales=True,
        )

    def test_euridice_no_ve_la_pantalla_de_entrenos_de_marta(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.marta.id}/")
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)

    def test_euridice_no_puede_apuntar_un_entreno_a_marta(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/entrenos/{self.marta.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_euridice_no_puede_corregir_ni_borrar_un_entreno_de_marta(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta_corregir = self.client.post(
            f"/entrenos/{self.marta.id}/{self.entreno_de_marta.id}/corregir/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "99", "calorias": "100"},
        )
        self.assertEqual(respuesta_corregir.status_code, 404)

        respuesta_borrar = self.client.post(
            f"/entrenos/{self.marta.id}/{self.entreno_de_marta.id}/borrar/"
        )
        self.assertEqual(respuesta_borrar.status_code, 404)

        self.entreno_de_marta.refresh_from_db()
        self.assertEqual(self.entreno_de_marta.minutos, 20)  # intacto

    def test_alejandro_no_puede_tocar_los_entrenos_de_euridice_aunque_tenga_a_marta_a_cargo(self):
        respuesta = self.client.get(f"/entrenos/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 404)


class R7_LaPuertaMiraResponsableNoPerfilTests(_ConAlejandroMartaYEuridice):
    """
    R7 (caso límite) — una persona a cargo SIN `Perfil` no revienta la puerta: la puerta de
    `entrenos/` (delegada en `hogares.acceso.persona_editable_o_404`) se decide sobre
    `Persona.responsable`, nunca sobre `Perfil` (que aquí ni siquiera existe como concepto). A
    diferencia de `perfiles/`, esta ruta no depende en ningún punto de que exista un `Perfil`,
    así que demuestra el caso límite de punta a punta, sin ningún 404 "de otra puerta" de por
    medio.
    """

    def setUp(self):
        super().setUp()
        self.sin_perfil = Persona.objects.create(
            hogar=self.alejandro.hogar, nombre="SinPerfil", responsable=self.alejandro
        )
        self.assertFalse(hasattr(self.sin_perfil, "perfil"))  # control

    def test_alejandro_ve_la_pantalla_de_entrenos_de_una_persona_a_cargo_sin_perfil(self):
        respuesta = self.client.get(f"/entrenos/{self.sin_perfil.id}/")
        self.assertNotEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.status_code, 200)

    def test_alejandro_apunta_calorias_manuales_a_una_persona_sin_perfil_sin_reventar(self):
        """Sin `Perfil` no hay peso con el que ESTIMAR (G-70 necesita el peso de quien
        entrena); escribiendo las calorías a mano se evita esa dependencia y se demuestra que
        la puerta en sí no es el problema."""
        respuesta = self.client.post(
            f"/entrenos/{self.sin_perfil.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "10", "calorias": "50"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Entreno.objects.filter(persona=self.sin_perfil, calorias=50).exists())

    def test_euridice_no_puede_ver_la_pantalla_de_una_persona_a_cargo_de_otro_sin_perfil(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/entrenos/{self.sin_perfil.id}/")
        self.assertEqual(respuesta.status_code, 404)
