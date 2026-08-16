"""
Tests de la unidad 026 (docs/05-trabajo/026-la-salida-del-borrado/especificacion.md) — R1 a R8:
las dos salidas de G-195 (pasarle la ficha a otra persona de la casa, o borrarla a conciencia)
y el cierre del callejón sin salida que dejó abierto la unidad 024.

Mismo montaje que `hogares/tests.py:PermisoDelResponsableTests` (unidad 025): tres personas del
mismo hogar — Alejandro (cuenta propia), Marta (a cargo de Alejandro, sin cuenta) y Euridice
(cuenta propia, a cargo de nadie) — y todo se recorre con el cliente de pruebas contra las URLs
reales, nunca llamando a las vistas o a los modelos directamente (salvo la clase que prueba la
puerta de `hogares/acceso.py` en aislamiento, igual que hace esa misma unidad 025).
"""

import re

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.http import Http404
from django.test import RequestFactory

from cierres.models import CierreDeDia
from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from entrenos.models import Entreno
from perfiles.models import MedicionPeso, Perfil
from planes.models import PlanDeDia

from .acceso import es_su_responsable, persona_a_cargo_o_404
from .models import Persona, SolicitudEntrada

Usuario = get_user_model()

# Mismos datos de Marta que usa la unidad 025 (hogares/tests.py:DATOS_DE_MARTA_A_CARGO):
# duplicados a propósito, igual que hace `hogares/tests_personas_de_la_casa.py` con los de
# Euridice — cada fichero de tests de esta app es autocontenido.
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

# Payload mínimo válido de perfiles/views.py:actualizar_perfil (mismo patrón que
# hogares/tests_personas_de_la_casa.py:R4_..._payload_edicion).
_PAYLOAD_EDICION_PERFIL = {
    "actividad": "activo",
    "objetivo": "mantener",
    "ajuste_pct": 0,
    "dieta": "",
    "alergias": "",
    "intolerancias": "",
    "no_le_gusta": "",
}


class _ConAlejandroMartaYEuridice(PruebaConRegistroAbierto):
    """Base: Alejandro (cuenta), Marta (a su cargo, sin cuenta) y Euridice (cuenta propia, del
    mismo hogar, a cargo de nadie) — las tres personas de los criterios de esta unidad. Mismo
    montaje que `hogares/tests.py:PermisoDelResponsableTests` (025)."""

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

    def _montar_historico_de_marta(self):
        """R1 — histórico real para el contrafactual: UNA pesada más (el alta de la 024 ya le
        crea la primera, con la fecha de HOY — `perfiles/logica.py:crear_perfil_desde_alta`),
        un entreno, un cierre de día y un plan. Sin esto, un borrado (o un pasar la ficha) que
        no llega a tener nada que mover "pasaría" sin probar nada (16ª cara de
        docs/conocimiento/tests-que-no-fallan-cuando-deben.md)."""
        MedicionPeso.objects.create(persona=self.marta, fecha="2026-08-01", peso_kg="35.2")
        Entreno.objects.create(
            persona=self.marta,
            fecha="2026-08-01",
            deporte="nadar",
            intensidad="media",
            minutos=30,
            calorias=150,
        )
        CierreDeDia.objects.create(
            persona=self.marta, fecha="2026-08-01", respuesta=CierreDeDia.LO_SEGUI
        )
        PlanDeDia.objects.create(persona=self.marta, hogar=self.marta.hogar, fecha="2026-08-01")

    @staticmethod
    def _recuento_de(persona_id):
        return {
            "pesadas": MedicionPeso.objects.filter(persona_id=persona_id).count(),
            "entrenos": Entreno.objects.filter(persona_id=persona_id).count(),
            "cierres": CierreDeDia.objects.filter(persona_id=persona_id).count(),
            "planes": PlanDeDia.objects.filter(persona_id=persona_id).count(),
            "perfiles": Perfil.objects.filter(persona_id=persona_id).count(),
        }


class R1_PasarleLaFichaTests(_ConAlejandroMartaYEuridice):
    """
    R1 — cuando Alejandro pasa a Marta a cargo de Euridice, Marta conserva su ficha entera y
    todo su histórico (contado ANTES y DESPUÉS, y son los mismos), y su responsable pasa a ser
    Euridice. Desde ese momento Euridice puede cambiarle sus datos y Alejandro ya no.
    """

    def test_marta_conserva_su_ficha_y_todo_su_historico(self):
        self._montar_historico_de_marta()
        recuento_antes = self._recuento_de(self.marta.id)
        # Control: el montaje puso de verdad lo que dice que puso (2 pesadas: la del alta,
        # con la fecha de hoy, más la que añade `_montar_historico_de_marta`).
        self.assertEqual(
            recuento_antes,
            {"pesadas": 2, "entrenos": 1, "cierres": 1, "planes": 1, "perfiles": 1},
        )

        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/",
            {"destino": self.euridice.id},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)

        self.marta.refresh_from_db()
        self.assertEqual(self.marta.responsable_id, self.euridice.id)
        self.assertEqual(recuento_antes, self._recuento_de(self.marta.id))  # el contrafactual

    def test_desde_ese_momento_euridice_puede_y_alejandro_no(self):
        self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/", {"destino": self.euridice.id}
        )

        # Alejandro ya NO es su responsable: 404 (la puerta de la unidad 025 leyendo el campo
        # que esta unidad acaba de escribir).
        respuesta = self.client.post(
            f"/perfiles/{self.marta.id}/actualizar/",
            {**_PAYLOAD_EDICION_PERFIL, "altura_cm": 141},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.marta.perfil.refresh_from_db()
        self.assertNotEqual(self.marta.perfil.altura_cm, 141)

        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/perfiles/{self.marta.id}/actualizar/",
            {**_PAYLOAD_EDICION_PERFIL, "altura_cm": 142},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.marta.perfil.refresh_from_db()
        self.assertEqual(self.marta.perfil.altura_cm, 142)


class R2_BorrarlaFichaAConcienciaTests(_ConAlejandroMartaYEuridice):
    """
    R2 — cuando Alejandro borra la ficha de Marta a conciencia, desaparecen Marta y su
    histórico entero. Antes de confirmar, la app le dice por su nombre a quién va a borrar y
    qué se lleva por delante (en HTML servido por el servidor, nunca en un `confirm()` de
    JavaScript — lección de la unidad 021: "lo que solo pinta el navegador, ningún test lo
    ve").
    """

    def test_el_aviso_dice_el_nombre_y_el_recuento_antes_de_confirmar(self):
        self._montar_historico_de_marta()

        respuesta = self.client.get(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/")
        self.assertEqual(respuesta.status_code, 200)

        # Acotado a la zona del aviso (17ª/12ª cara de tests-que-no-fallan-cuando-deben.md):
        # no basta con que "Marta" aparezca en algún sitio de la página.
        contenido = respuesta.content.decode()
        coincidencia = re.search(
            r'<section id="aviso-de-borrado".*?</section>', contenido, re.S
        )
        self.assertIsNotNone(coincidencia)
        aviso = coincidencia.group(0)

        self.assertIn("Marta", aviso)
        # 2 pesadas: la del alta (fecha de hoy) más la que añade _montar_historico_de_marta.
        self.assertIn("2 pesadas", aviso)
        self.assertIn("1 entreno", aviso)
        self.assertIn("1 día", aviso)

    def test_borrarla_se_lleva_la_ficha_y_todo_su_historico(self):
        self._montar_historico_de_marta()
        marta_id = self.marta.id

        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{marta_id}/borrar/", follow=True
        )
        self.assertEqual(respuesta.status_code, 200)

        self.assertFalse(Persona.objects.filter(pk=marta_id).exists())
        self.assertEqual(self._recuento_de(marta_id), {k: 0 for k in self._recuento_de(marta_id)})

    def test_no_toca_a_nadie_mas_de_la_casa(self):
        """Se borra "una por una": borrar a Marta no arrastra a Euridice ni a Alejandro."""
        self.client.post(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/")

        self.assertTrue(Persona.objects.filter(pk=self.alejandro.id).exists())
        self.assertTrue(Persona.objects.filter(pk=self.euridice.id).exists())


class R4_AQuienSePuedePasarTests(_ConAlejandroMartaYEuridice):
    """
    R4 — el destino tiene que ser alguien que entre con su cuenta y del mismo hogar: pasarle
    Marta a otra persona a cargo se rechaza, y a alguien de otro hogar, 404.
    """

    def test_a_otra_persona_a_cargo_se_rechaza(self):
        # Segunda persona a cargo de Alejandro, sin cuenta: no podría hacer nada por Marta.
        nino = Persona.objects.create(
            hogar=self.alejandro.hogar, nombre="Nino", responsable=self.alejandro
        )

        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/",
            {"destino": nino.id},
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)  # rechazo con mensaje, NUNCA 404
        self.marta.refresh_from_db()
        self.assertEqual(self.marta.responsable_id, self.alejandro.id)  # nada cambió

    def test_a_alguien_de_otro_hogar_da_404(self):
        self.client.logout()
        self.registrar_y_verificar("de-otra-casa@example.com", sexo="mujer")
        de_otra_casa = Persona.objects.get(usuario__email="de-otra-casa@example.com")
        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/",
            {"destino": de_otra_casa.id},
        )

        self.assertEqual(respuesta.status_code, 404)
        self.marta.refresh_from_db()
        self.assertEqual(self.marta.responsable_id, self.alejandro.id)  # nada cambió

    def test_a_si_mismo_tambien_se_rechaza(self):
        """"distintas de quien pide" ("Cómo" de la especificación): Alejandro no puede
        pasarse la ficha de Marta a sí mismo, ya es su responsable."""
        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/",
            {"destino": self.alejandro.id},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)  # rechazo, no 404
        self.marta.refresh_from_db()
        self.assertEqual(self.marta.responsable_id, self.alejandro.id)


class R4_SinNadieMasConCuentaTests(PruebaConRegistroAbierto):
    """R4, última fila — si en la casa no queda nadie más con cuenta, la app lo dice claro: la
    única salida es borrar la ficha (no ofrece un desplegable de destinos vacío)."""

    def test_lo_dice_claro_en_la_pantalla(self):
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        respuesta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/", DATOS_DE_MARTA_A_CARGO, follow=True
        )
        self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertContains(respuesta, "la única salida es borrar su ficha")


class R5_SoloElResponsableActualTests(_ConAlejandroMartaYEuridice):
    """
    R5 — solo su responsable actual puede hacer las dos cosas. Euridice recibe 404 en las dos
    rutas contra Marta, con el id exacto, aunque viva en la misma casa: no es su responsable.
    Nunca un 403 (Q-20).
    """

    def setUp(self):
        super().setUp()
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

    def test_404_al_intentar_pasarla(self):
        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/", {"destino": self.euridice.id}
        )
        self.assertEqual(respuesta.status_code, 404)
        self.marta.refresh_from_db()
        self.assertEqual(self.marta.responsable_id, self.alejandro.id)

    def test_404_al_abrir_la_confirmacion_de_borrado(self):
        respuesta = self.client.get(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/")
        self.assertEqual(respuesta.status_code, 404)

    def test_404_al_confirmar_el_borrado(self):
        respuesta = self.client.post(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Persona.objects.filter(pk=self.marta.id).exists())

    def test_nunca_un_403(self):
        for respuesta in (
            self.client.post(
                f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/",
                {"destino": self.euridice.id},
            ),
            self.client.get(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/"),
            self.client.post(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/"),
        ):
            self.assertNotEqual(respuesta.status_code, 403)

    def test_solo_su_responsable_no_es_lo_mismo_que_ella_misma(self):
        """H3 (2ª ronda): "SOLO su responsable actual" (el "Cómo" §1 dice explícitamente que
        aquí "la propia dueña no cuenta") es una puerta MÁS ESTRECHA que `puede_cambiar_lo_de`
        de la 025 — esa otra deja pasar también a "la propia persona". Los tests de arriba
        prueban que la puerta IMPORTA (Euridice, que no es responsable de Marta, recibe 404 en
        las tres rutas), pero ninguno prueba que sea ESTRECHA: con `es_su_responsable`
        aflojada a `puede_cambiar_lo_de`, Alejandro —que es SU PROPIA persona, y por eso
        `puede_cambiar_lo_de` lo dejaría pasar— podría pedir pasarse a SÍ MISMO a cargo de
        Euridice contra su propio id, un estado que el modelo no debería admitir."""
        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.alejandro.id}/pasar/",
            {"destino": self.euridice.id},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.alejandro.refresh_from_db()
        self.assertIsNone(self.alejandro.responsable_id)  # nada cambió


class R6_ElCaminoExisteTests(_ConAlejandroMartaYEuridice):
    """
    R6 — el mensaje de "no puedes borrar tu cuenta" lleva al sitio donde están las dos
    salidas, nombrando a quien te lo impide.
    """

    def test_el_aviso_nombra_a_marta_y_aterriza_donde_estan_las_dos_salidas(self):
        respuesta = self.client.post("/cuentas/borrar/", follow=True)

        # Segunda ronda (H2): "Marta" ya la escribe la lista de "Quién vive en la casa" de
        # esa misma pantalla — el comentario decía "nombra a quien lo impide" pero el assert
        # no probaba eso (5ª/10ª/17ª cara). Se afirma sobre la frase completa del aviso, que
        # solo sale del mensaje real de `cuentas/views.py:borrar_cuenta`.
        self.assertContains(respuesta, "tienes a Marta a tu cargo")
        contenido = respuesta.content.decode()
        # Aterrizó en "Mi hogar", donde ahora viven las dos salidas de la fila de Marta.
        self.assertIn(f"/hogares/mi-hogar/personas/{self.marta.id}/pasar/", contenido)
        self.assertIn(f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/", contenido)


class R7_CasoLimiteDelProtectTests(_ConAlejandroMartaYEuridice):
    """
    R7 (caso límite) — borrar la ficha de alguien que a su vez es responsable de otra persona
    no revienta: la app lo impide con un mensaje en cristiano, nunca con un `ProtectedError`
    crudo ni un 500. Hoy no debería poder ocurrir por el flujo normal de la app (una persona a
    cargo no tiene cuenta, así que jamás da de alta a nadie) — se fuerza el estado directamente
    en la base, que es justo lo que R7 pide contemplar: "el campo lo permite en la base de
    datos, y esta unidad es la que borra fichas".
    """

    def test_no_revienta_y_da_un_mensaje_en_cristiano(self):
        nieta = Persona.objects.create(
            hogar=self.alejandro.hogar, nombre="Nieta", responsable=self.marta
        )

        respuesta = self.client.post(
            f"/hogares/mi-hogar/personas/{self.marta.id}/borrar/", follow=True
        )

        self.assertEqual(respuesta.status_code, 200)  # nunca un 500
        # Segunda ronda (H1): "Marta" ya la escribe la lista de "Quién vive en la casa" de
        # esa misma pantalla (5ª/10ª/17ª cara de tests-que-no-fallan-cuando-deben.md) — un
        # assertContains(respuesta, "Marta") pasa aunque el mensaje sea un ProtectedError
        # crudo. Se afirma sobre el texto distintivo del mensaje en cristiano, no sobre un
        # nombre que la página ya escribe por su cuenta.
        self.assertContains(respuesta, "a su vez tiene a alguien a su cargo")
        self.assertTrue(Persona.objects.filter(pk=self.marta.id).exists())
        self.assertTrue(Persona.objects.filter(pk=nieta.id).exists())

    def test_la_base_de_datos_lo_impide_directamente_tambien(self):
        """Igual que Q-175 para `borrar_cuenta` (unidad 024): el cinturón de verdad vive en
        `Persona.responsable` (`on_delete=PROTECT`), no solo en la vista."""
        Persona.objects.create(
            hogar=self.alejandro.hogar, nombre="Nieta", responsable=self.marta
        )
        with self.assertRaises(ProtectedError):
            self.marta.delete()


class LaPuertaDeLasDosSalidasTests(_ConAlejandroMartaYEuridice):
    """
    Prueba DIRECTA de `es_su_responsable`/`persona_a_cargo_o_404` (`hogares/acceso.py`), igual
    que `hogares/tests.py:PermisoDelResponsableTests` prueba `puede_cambiar_lo_de` (025): para
    que mutar estas funciones tumbe un test SIN tener que pasar por ninguna vista.
    """

    @staticmethod
    def _peticion_de(email):
        peticion = RequestFactory().get("/")
        peticion.user = Usuario.objects.get(email=email)
        return peticion

    def test_el_responsable_puede(self):
        self.assertTrue(
            es_su_responsable(self._peticion_de("alejandro@example.com"), self.marta.id)
        )

    def test_otra_persona_del_hogar_con_cuenta_no_puede(self):
        self.assertFalse(
            es_su_responsable(self._peticion_de("euridice@example.com"), self.marta.id)
        )

    def test_persona_a_cargo_o_404_da_404_para_quien_no_es_responsable(self):
        with self.assertRaises(Http404):
            persona_a_cargo_o_404(self._peticion_de("euridice@example.com"), self.marta.id)

    def test_persona_a_cargo_o_404_devuelve_la_persona_para_su_responsable(self):
        persona = persona_a_cargo_o_404(
            self._peticion_de("alejandro@example.com"), self.marta.id
        )
        self.assertEqual(persona.id, self.marta.id)
