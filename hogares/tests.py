"""
Tests de la unidad 003, la parte de "hogares": R1 (mitad del hogar), R5, R6, R7, R8, R9, R11.

Igual que en `cuentas/tests.py`: todo pasa por el cliente de pruebas contra las URLs reales.
Las pruebas de aislamiento (R9) son las más importantes de toda la unidad — llaman al
servidor directamente con el id exacto de una solicitud ajena, sin pasar por ningún botón.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Hogar, Persona, SolicitudEntrada

Usuario = get_user_model()


class CrearCuentaCreaHogarPropioTests(PruebaConRegistroAbierto):
    """R1 — registrarse sin código crea la cuenta Y el hogar, y enseña el código para
    invitar en cuanto verifica (sin tener que iniciar sesión aparte)."""

    def test_al_verificar_ya_esta_dentro_de_su_hogar_con_su_codigo_a_la_vista(self):
        respuesta = self.registrar_y_verificar("alejandro@example.com")

        persona = Persona.objects.get(usuario__email="alejandro@example.com")
        self.assertIsNotNone(persona.hogar_id)
        self.assertEqual(persona.hogar.miembros.count(), 1)

        # "sin pedirle iniciar sesión aparte": la propia respuesta de pulsar el enlace ya
        # lleva a una pantalla autenticada con el código a la vista, sin pasar por /login/.
        respuesta_mi_hogar = self.client.get("/hogares/mi-hogar/")
        self.assertContains(respuesta_mi_hogar, persona.hogar.codigo)
        self.assertContains(respuesta_mi_hogar, "alejandro@example.com")


class CodigoInvalidoTests(PruebaConRegistroAbierto):
    """R6/G-30 — un código que no existe avisa y crea igualmente un hogar propio."""

    def test_codigo_que_no_existe_avisa_y_crea_hogar_propio(self):
        self.assertFalse(Hogar.objects.filter(codigo="NOEXISTEESTE").exists())

        # El aviso ("ese código no vale") sale en la respuesta del ALTA (mensaje flash, se
        # consume al pintarse): se comprueba ahí, no en la página de después de verificar.
        respuesta_alta = self.registrar("euridice@example.com", codigo_hogar="NOEXISTEESTE")
        self.assertContains(respuesta_alta, "no existe")

        self.client.get(
            self.ultimo_enlace_de_verificacion(para_correo="euridice@example.com"),
            follow=True,
        )
        persona = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertIsNotNone(persona.hogar_id)
        self.assertNotEqual(persona.hogar.codigo, "NOEXISTEESTE")
        self.assertEqual(persona.hogar.miembros.count(), 1)


class PedirEntrarConCodigoValidoTests(PruebaConRegistroAbierto):
    """R5/G-30/G-37/C-104 — el camino completo de pedir entrar con un código que sí existe."""

    def _crear_hogar_de_alejandro(self):
        self.registrar_y_verificar("alejandro@example.com")
        alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.client.logout()
        return alejandro

    def test_antes_de_verificar_el_hogar_no_sabe_nada_de_ella(self):
        """C-104: mientras no verifica, ni existe la solicitud."""
        alejandro = self._crear_hogar_de_alejandro()

        self.registrar("euridice@example.com", codigo_hogar=alejandro.hogar.codigo)

        self.assertEqual(
            SolicitudEntrada.objects.filter(hogar=alejandro.hogar).count(),
            0,
            "la petición no debe existir hasta que euridice verifique su correo",
        )

    def test_al_verificar_no_ve_nada_del_hogar_y_alejandro_recibe_el_aviso(self):
        alejandro = self._crear_hogar_de_alejandro()

        respuesta = self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=alejandro.hogar.codigo
        )
        euridice = Persona.objects.get(usuario__email="euridice@example.com")

        # Está verificada y autenticada, pero SIN hogar: no ve nada del de alejandro.
        self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
        self.assertIsNone(euridice.hogar_id)
        self.assertContains(respuesta, "Esperando a que te acepten")
        self.assertNotContains(respuesta, alejandro.hogar.codigo)

        # A alejandro SÍ le ha llegado el aviso, justo ahora que ella verificó.
        self.assertEqual(
            SolicitudEntrada.objects.filter(
                hogar=alejandro.hogar, estado=SolicitudEntrada.PENDIENTE
            ).count(),
            1,
        )
        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        respuesta_hogar = self.client.get("/hogares/mi-hogar/")
        self.assertContains(respuesta_hogar, "euridice@example.com")

    def test_aceptar_la_mete_dentro_del_hogar_compartido(self):
        alejandro = self._crear_hogar_de_alejandro()
        self.registrar_y_verificar("euridice@example.com", codigo_hogar=alejandro.hogar.codigo)
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(hogar=alejandro.hogar)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")

        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertEqual(euridice.hogar_id, alejandro.hogar_id)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudEntrada.ACEPTADA)

        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertContains(respuesta, "alejandro@example.com")
        self.assertContains(respuesta, "euridice@example.com")

    def test_acepta_cualquiera_de_dentro_no_solo_quien_creo_el_hogar(self):
        """G-30: "Acepta cualquiera de dentro, no hace falta que sea quien lo creó"."""
        alejandro = self._crear_hogar_de_alejandro()
        # Una tercera persona se une primero al hogar de alejandro para poder comprobar que
        # ELLA (no alejandro) también puede aceptar.
        self.registrar_y_verificar(
            "tercera@example.com", codigo_hogar=alejandro.hogar.codigo
        )
        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        primera_solicitud = SolicitudEntrada.objects.get(usuario__email="tercera@example.com")
        self.client.post(f"/hogares/mi-hogar/solicitudes/{primera_solicitud.pk}/aceptar/")
        self.client.logout()

        self.registrar_y_verificar("euridice@example.com", codigo_hogar=alejandro.hogar.codigo)
        self.client.logout()

        # Quien acepta a euridice es la TERCERA persona, no alejandro.
        self.client.login(username="tercera@example.com", password=CLAVE_VALIDA)
        segunda_solicitud = SolicitudEntrada.objects.get(usuario__email="euridice@example.com")
        self.client.post(f"/hogares/mi-hogar/solicitudes/{segunda_solicitud.pk}/aceptar/")

        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertEqual(euridice.hogar_id, alejandro.hogar_id)

    def test_rechazar_la_deja_con_su_propio_hogar(self):
        """R8/G-30."""
        alejandro = self._crear_hogar_de_alejandro()
        self.registrar_y_verificar("euridice@example.com", codigo_hogar=alejandro.hogar.codigo)
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(hogar=alejandro.hogar)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/rechazar/")
        self.client.logout()

        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertIsNotNone(euridice.hogar_id)
        self.assertNotEqual(euridice.hogar_id, alejandro.hogar_id)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudEntrada.RECHAZADA)

        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertNotContains(respuesta, "alejandro@example.com")


class CaducidadDeSolicitudTests(PruebaConRegistroAbierto):
    """R7/Q-10/G-34 — pasada una hora sin respuesta, la petición queda denegada sola."""

    def _crear_solicitud_vieja(self):
        self.registrar_y_verificar("alejandro@example.com")
        alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.client.logout()
        self.registrar_y_verificar("euridice@example.com", codigo_hogar=alejandro.hogar.codigo)
        self.client.logout()

        solicitud = SolicitudEntrada.objects.get(hogar=alejandro.hogar)
        solicitud.creada_en = timezone.now() - timezone.timedelta(hours=1, minutes=1)
        solicitud.save(update_fields=["creada_en"])
        return alejandro, solicitud

    def test_una_hora_despues_la_persona_que_pidio_entrar_ya_tiene_su_propio_hogar(self):
        alejandro, solicitud = self._crear_solicitud_vieja()

        # Nadie ha mirado nada todavía: es EURIDICE, simplemente usando la app (aquí, pidiendo
        # su propia pantalla de "mi hogar"), quien dispara la resolución — el middleware de
        # hogares/middleware.py, no un proceso en segundo plano.
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        self.client.get("/hogares/mi-hogar/")

        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertIsNotNone(euridice.hogar_id)
        self.assertNotEqual(euridice.hogar_id, alejandro.hogar_id)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudEntrada.CADUCADA)

    def test_una_aceptacion_pasada_la_hora_no_revive_la_peticion(self):
        """Q-10: "una aceptación posterior a esa hora no revive la petición"."""
        alejandro, solicitud = self._crear_solicitud_vieja()

        # Nadie ha "cerrado" la solicitud todavía (sigue PENDIENTE en la base de datos): esto
        # comprueba que aceptar la mira en caliente, no que se fía del campo `estado`.
        self.assertEqual(solicitud.estado, SolicitudEntrada.PENDIENTE)

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")

        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertNotEqual(euridice.hogar_id, alejandro.hogar_id)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudEntrada.CADUCADA)

    def test_puede_volver_a_pedir_entrar_mas_adelante(self):
        """Nada impide una SEGUNDA solicitud de la misma persona al mismo hogar tras caducar
        la primera (sin restricción de unicidad entre usuario y hogar)."""
        alejandro, solicitud_vieja = self._crear_solicitud_vieja()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        self.client.get("/hogares/mi-hogar/")  # resuelve (y caduca) la primera

        nueva_solicitud = SolicitudEntrada.objects.create(
            hogar=alejandro.hogar,
            usuario=Usuario.objects.get(email="euridice@example.com"),
        )
        self.assertEqual(
            SolicitudEntrada.objects.filter(
                hogar=alejandro.hogar, usuario__email="euridice@example.com"
            ).count(),
            2,
        )
        self.assertEqual(nueva_solicitud.estado, SolicitudEntrada.PENDIENTE)


class AislamientoPorHogarTests(PruebaConRegistroAbierto):
    """
    R9/Q-20 — el más importante de la unidad. Llama al servidor DIRECTAMENTE, con el id
    exacto de una solicitud de un hogar ajeno, saltándose cualquier botón o enlace de la
    interfaz: quien está fuera de un hogar no puede ver ni cambiar nada de él.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.client.logout()

        self.registrar_y_verificar("berta@example.com")
        self.berta = Persona.objects.get(usuario__email="berta@example.com")
        self.client.logout()

        # Alguien pide entrar en el hogar de ALEJANDRO (no en el de berta).
        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.client.logout()
        self.solicitud_de_alejandro = SolicitudEntrada.objects.get(hogar=self.alejandro.hogar)

    def test_alguien_de_otro_hogar_no_puede_aceptar_una_solicitud_ajena(self):
        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{self.solicitud_de_alejandro.pk}/aceptar/"
        )

        self.assertEqual(respuesta.status_code, 404)
        self.solicitud_de_alejandro.refresh_from_db()
        self.assertEqual(self.solicitud_de_alejandro.estado, SolicitudEntrada.PENDIENTE)
        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertNotEqual(euridice.hogar_id, self.alejandro.hogar_id)

    def test_alguien_de_otro_hogar_no_puede_rechazar_una_solicitud_ajena(self):
        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{self.solicitud_de_alejandro.pk}/rechazar/"
        )

        self.assertEqual(respuesta.status_code, 404)
        self.solicitud_de_alejandro.refresh_from_db()
        self.assertEqual(self.solicitud_de_alejandro.estado, SolicitudEntrada.PENDIENTE)

    def test_quien_no_esta_en_ningun_hogar_tampoco_puede_tocar_nada(self):
        """Euridice, esperando aceptación (sin hogar propio todavía), tampoco puede colarse
        aceptando o rechazando SU PROPIA solicitud llamando a la URL directamente."""
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{self.solicitud_de_alejandro.pk}/aceptar/"
        )

        self.assertEqual(respuesta.status_code, 404)
        self.solicitud_de_alejandro.refresh_from_db()
        self.assertEqual(self.solicitud_de_alejandro.estado, SolicitudEntrada.PENDIENTE)

    def test_un_desconocido_sin_sesion_no_puede_tocar_nada(self):
        """Ni con sesión de otro hogar ni SIN sesión ninguna: @login_required lo manda a
        iniciar sesión, nunca deja pasar la acción."""
        respuesta = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{self.solicitud_de_alejandro.pk}/aceptar/"
        )

        self.assertEqual(respuesta.status_code, 302)
        self.solicitud_de_alejandro.refresh_from_db()
        self.assertEqual(self.solicitud_de_alejandro.estado, SolicitudEntrada.PENDIENTE)

    def test_pedir_una_solicitud_que_no_existe_da_el_mismo_404(self):
        """Q-20/Q-11: la respuesta no debe distinguir "existe pero no es tuyo" de "no existe
        en absoluto" — el mismo 404 en los dos casos."""
        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)

        respuesta_ajena = self.client.post("/hogares/mi-hogar/solicitudes/999999/aceptar/")
        respuesta_de_otro_hogar = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{self.solicitud_de_alejandro.pk}/aceptar/"
        )

        self.assertEqual(respuesta_ajena.status_code, respuesta_de_otro_hogar.status_code)

    def test_lo_del_hogar_lo_cambia_cualquiera_de_dentro_sin_pedir_permiso(self):
        """R9/R24/G-43, la otra mitad: DENTRO del hogar, no hace falta ser quien lo creó."""
        # berta NO pertenece al hogar de alejandro: control negativo ya cubierto arriba. Aquí
        # se prueba el positivo con una segunda persona QUE SÍ está en el hogar de alejandro.
        self.registrar_y_verificar(
            "segunda_persona@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud_segunda = SolicitudEntrada.objects.get(
            usuario__email="segunda_persona@example.com"
        )
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud_segunda.pk}/aceptar/")
        self.client.logout()

        # Ahora "segunda_persona" está DENTRO del hogar de alejandro, y sin ser quien lo creó
        # puede aceptar la solicitud de euridice sin que nadie le dé permiso expreso.
        self.client.login(username="segunda_persona@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/hogares/mi-hogar/solicitudes/{self.solicitud_de_alejandro.pk}/aceptar/"
        )
        self.assertEqual(respuesta.status_code, 302)
        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertEqual(euridice.hogar_id, self.alejandro.hogar_id)


class CodigoDeHogarTests(PruebaConRegistroAbierto):
    """
    R11 — "el código de un hogar no se puede adivinar: es aleatorio y largo, nunca
    correlativo, y acertar uno no da acceso por sí solo — sigue haciendo falta que alguien de
    dentro acepte." (Redacción corregida por el padre tras la 1ª revisión: la versión anterior
    exigía además que la respuesta no distinguiera "ese hogar existe" de "no existe", y eso
    era incompatible con R6, que obliga a avisar de que el código no vale.)

    Que "acertar uno no da acceso por sí solo" ya está probado por otro lado: es exactamente
    lo que comprueba `PedirEntrarConCodigoValidoTests` (meter un código que SÍ existe dejaentra
    "sola", sin ver nada, hasta que alguien de dentro acepta).
    """

    def test_codigos_de_hogares_seguidos_no_se_parecen_entre_si(self):
        """
        R11: "aleatorio y largo, nunca correlativo". La versión anterior de este test
        (señalada en la 2ª revisión) solo comprobaba que la lista completa de códigos, tal
        cual salió, no coincidiera EXACTAMENTE con la misma lista ordenada alfabéticamente —
        una única pareja fuera de orden ya lo hacía pasar, así que un generador casi
        correlativo (un contador con un empujón al final, por ejemplo) lo habría colado igual.
        Aquí se mide algo más terco: con un generador correlativo, el orden de CREACIÓN y el
        orden ALFABÉTICO casi siempre coinciden (o casi siempre se invierten, si el contador
        fuera descendente) — con códigos de verdad aleatorios, ninguna de las dos cosas pasa:
        el porcentaje de pares consecutivos "en orden" tiene que quedarse a media tabla, ni
        casi 0% ni casi 100%.
        """
        codigos = [Hogar.objects.create().codigo for _ in range(60)]

        self.assertEqual(len(codigos), len(set(codigos)), "no puede haber dos iguales")
        for codigo in codigos:
            self.assertGreaterEqual(len(codigo), 10, "un código corto sí se puede fuerza bruta")

        pares_en_orden_ascendente = sum(
            1 for actual, siguiente in zip(codigos, codigos[1:]) if actual < siguiente
        )
        total_de_pares = len(codigos) - 1
        proporcion = pares_en_orden_ascendente / total_de_pares

        self.assertGreater(
            proporcion,
            0.2,
            "casi todos los pares van 'hacia abajo': parece un contador descendente disfrazado",
        )
        self.assertLess(
            proporcion,
            0.8,
            "casi todos los pares van 'hacia arriba': parece un contador ascendente disfrazado",
        )

    def test_probar_un_codigo_que_no_existe_no_distingue_nada_de_otro(self):
        """
        Nicety más allá de lo que R11 exige ya (no es parte de su redacción corregida, pero
        sigue siendo cierto y barato de mantener): probar dos códigos que NO existen da
        siempre la misma respuesta, sea cual sea el código — no hay manera de aprender, a
        base de probar, cuál "se acerca más" a uno real.
        """
        Hogar.objects.create()  # un hogar real de verdad, para que exista ALGO en la base

        respuesta_1 = self.registrar("persona1@example.com", codigo_hogar="AAAAAAAAAAAA")
        self.client.logout()
        respuesta_2 = self.registrar("persona2@example.com", codigo_hogar="ZZZZZZZZZZZZ")

        # Mismo status, mismo texto de aviso: no hay pistas de cuál código "se acerca más".
        self.assertEqual(respuesta_1.status_code, respuesta_2.status_code)
        self.assertIn("no existe", respuesta_1.content.decode())
        self.assertIn("no existe", respuesta_2.content.decode())
