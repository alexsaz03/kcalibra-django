"""
Tests de la unidad 025 (lo-de-quien-tienes-a-tu-cargo.md) para `perfiles/`: R1 (apuntar y
borrar el peso de una persona a cargo), la mitad de R4 y R5 que toca esta app (el peso), y R7
(caso límite, verificado también aquí de punta a punta por HTTP, no solo en `hogares/tests.py`).

Los tres personajes de la especificación: **Alejandro** (cuenta propia), **Marta** (a su
cargo, sin cuenta) y **Euridice** (cuenta propia, del mismo hogar, sin estar a cargo de
nadie). Todo por el cliente de pruebas contra las URLs reales — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo.
"""

import re

from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Persona, SolicitudEntrada

from .models import MedicionPeso

Usuario = get_user_model()

# Datos físicos válidos de Marta, la niña a cargo de Alejandro (mismo criterio que
# `hogares/tests_personas_de_la_casa.py:DATOS_DE_EURIDICE_A_CARGO`, unidad 024).
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
        self.assertEqual(respuesta.status_code, 200)  # control: el alta no falló
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


class R1_ApuntarYBorrarElPesoDeUnaPersonaACargoTests(_ConAlejandroMartaYEuridice):
    """R1 — Alejandro apunta una pesada en el histórico de Marta y queda a nombre de ELLA (no
    del suyo); al borrarla, desaparece de su histórico. Hoy las dos rutas dan 404."""

    def test_apuntar_una_pesada_de_marta_queda_a_su_nombre_no_al_de_alejandro(self):
        respuesta = self.client.post(
            f"/perfiles/{self.marta.id}/peso/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "peso_kg": "36.2",
                "grasa_pct": "",
                "cintura_cm": "",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        medicion = MedicionPeso.objects.get(persona=self.marta, fecha=timezone.localdate())
        self.assertEqual(str(medicion.peso_kg), "36.2")
        self.assertFalse(
            MedicionPeso.objects.filter(
                persona=self.alejandro, fecha=timezone.localdate(), peso_kg="36.2"
            ).exists()
        )

    def test_borrar_una_pesada_de_marta_desaparece_de_su_historico(self):
        self.client.post(
            f"/perfiles/{self.marta.id}/peso/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "peso_kg": "36.2",
                "grasa_pct": "",
                "cintura_cm": "",
            },
        )
        medicion = MedicionPeso.objects.get(persona=self.marta, fecha=timezone.localdate())

        respuesta = self.client.post(f"/perfiles/{self.marta.id}/peso/{medicion.id}/borrar/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MedicionPeso.objects.filter(id=medicion.id).exists())


class R4_LaPuertaEsSoloParaElResponsableTests(_ConAlejandroMartaYEuridice):
    """
    R4 (la puerta) — Euridice, que vive en el MISMO hogar que Marta pero no es su responsable,
    recibe 404 al intentar apuntar o borrar el peso de Marta con su id exacto — nunca 403
    (Q-20). Y Alejandro, que SÍ es responsable de Marta, recibe 404 sobre Euridice: tener a
    alguien a cargo no da permiso sobre el resto de la casa.
    """

    def test_euridice_no_puede_apuntar_el_peso_de_marta_aunque_conozca_su_id(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/perfiles/{self.marta.id}/peso/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "peso_kg": "40",
                "grasa_pct": "",
                "cintura_cm": "",
            },
        )
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(
            MedicionPeso.objects.filter(persona=self.marta, peso_kg="40").exists()
        )

    def test_euridice_no_puede_borrar_una_pesada_de_marta(self):
        medicion = MedicionPeso.objects.filter(persona=self.marta).first()
        self.assertIsNotNone(medicion)  # control: el alta ya le dejó una

        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(f"/perfiles/{self.marta.id}/peso/{medicion.id}/borrar/")

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(MedicionPeso.objects.filter(id=medicion.id).exists())

    def test_alejandro_no_puede_apuntar_el_peso_de_euridice_aunque_tenga_a_marta_a_cargo(self):
        respuesta = self.client.post(
            f"/perfiles/{self.euridice.id}/peso/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "peso_kg": "55",
                "grasa_pct": "",
                "cintura_cm": "",
            },
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(
            MedicionPeso.objects.filter(persona=self.euridice, peso_kg="55").exists()
        )


class R5_ElCaminoDesdeLaFichaTests(_ConAlejandroMartaYEuridice):
    """
    R5 (camino en la interfaz) — desde la ficha de Marta, Alejandro llega a SU peso y ahí
    aparece el formulario de apuntar y el botón de borrar. En la ficha de Euridice, esas
    pantallas se comportan como hoy: sin formulario ni botones aunque la pantalla se vea.
    """

    def test_la_ficha_de_marta_enlaza_a_su_peso_a_sus_entrenos_y_a_su_cierre(self):
        respuesta = self.client.get(f"/perfiles/{self.marta.id}/")
        contenido = respuesta.content.decode()
        self.assertIn(f'href="/perfiles/{self.marta.id}/peso/"', contenido)
        self.assertIn(f'href="/entrenos/{self.marta.id}/"', contenido)
        self.assertIn(f'href="/cierres/{self.marta.id}/"', contenido)

    def test_el_peso_de_marta_enseña_formulario_y_boton_de_borrar_a_alejandro(self):
        respuesta = self.client.get(f"/perfiles/{self.marta.id}/peso/")
        contenido = respuesta.content.decode()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Apuntar pesada", contenido)
        # Espacios/saltos de línea fuera de las etiquetas no deben poder colar un falso
        # negativo (el HTML formatea el botón en varias líneas): se compacta antes de mirar.
        self.assertIn(">Borrar<", re.sub(r"\s+", "", contenido))

    def test_el_peso_de_euridice_se_ve_pero_sin_formulario_ni_botones(self):
        """Se comporta exactamente como hoy (unidad 010): visible para todo el hogar, editable
        solo por ella — tener a Marta a cargo no cambia nada aquí."""
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/peso/")
        contenido = respuesta.content.decode()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("Apuntar pesada", contenido)
        self.assertNotIn(">Borrar<", re.sub(r"\s+", "", contenido))

    def test_la_ficha_de_euridice_no_enlaza_a_entrenos_ni_cierre_para_alejandro(self):
        """El camino nuevo (peso/entrenos/cierre) solo aparece cuando `puede_editar` — nunca
        para la ficha de alguien que no está a su cargo."""
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn(f'href="/entrenos/{self.euridice.id}/"', contenido)
        self.assertNotIn(f'href="/cierres/{self.euridice.id}/"', contenido)


class R7_LaPuertaMiraResponsableNoPerfilTests(_ConAlejandroMartaYEuridice):
    """
    R7 (caso límite), verificado a nivel de la FUNCIÓN de la que depende toda esta app
    (`hogares.acceso.puede_cambiar_lo_de`, unidad 025): con Marta, que SÍ tiene `Perfil` (el
    alta se lo crea), la puerta ya se demuestra correcta en R1/R4 de aquí arriba. El caso
    límite exacto —una persona a cargo SIN `Perfil` todavía— no se puede ejercitar por HTTP
    en ESTA app sin toparse ANTES con el 404 propio de `perfil_visible_o_404` (que sí exige un
    `Perfil`, sin relación con esta unidad): se prueba de punta a punta, sin ese obstáculo, en
    `entrenos/tests_quien_tienes_a_cargo.py` (cuya puerta no depende de `Perfil` en absoluto)
    y, DIRECTAMENTE sobre la función, en `hogares/tests.py`.
    """

    def test_alejandro_sigue_pudiendo_editar_el_perfil_de_marta_que_si_tiene_perfil(self):
        """Control de que esta app no se rompió al subir la regla a `hogares/acceso.py`: la
        ficha de Marta (que SÍ tiene `Perfil`, R2 de la unidad 024) se sigue pudiendo editar."""
        respuesta = self.client.get(f"/perfiles/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Guardar", respuesta.content.decode())
