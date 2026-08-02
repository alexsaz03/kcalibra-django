"""
Tests de la unidad 003, la parte de "cuentas": R2, R3, R4, R10, R12, R13, R14, R15.

Todos pasan por el cliente de pruebas de Django contra las URLs reales (nunca llamando a
`Usuario.objects.create(...)` a mano ni a las funciones internas): es la única forma de
demostrar que la APP se comporta así de punta a punta, tal como exige el AGENTS.md de esta
unidad y la lección de docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo.
"""

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto

Usuario = get_user_model()


class RegistroCerradoTests(TestCase):
    """R12 — con el registro CERRADO (la palanca en su posición de hoy), nadie se registra."""

    @override_settings(REGISTRO_ABIERTO=False)
    def test_con_registro_cerrado_no_se_crea_ninguna_cuenta(self):
        respuesta = self.client.post(
            "/cuentas/signup/",
            {
                "email": "nadie@example.com",
                "password1": CLAVE_VALIDA,
                "password2": CLAVE_VALIDA,
                "codigo_hogar": "",
            },
            follow=True,
        )
        self.assertFalse(Usuario.objects.filter(email="nadie@example.com").exists())
        # No debe colarse un 500 ni un error a medias: la pantalla de "registro cerrado" debe
        # responder con normalidad.
        self.assertEqual(respuesta.status_code, 200)

    @override_settings(REGISTRO_ABIERTO=True)
    def test_con_registro_abierto_si_se_crea_la_cuenta(self):
        """La misma palanca, la otra posición: control de que el test de arriba de verdad
        depende del ajuste, y no de otra cosa (p. ej. un formulario roto)."""
        self.client.post(
            "/cuentas/signup/",
            {
                "email": "alguien@example.com",
                "password1": CLAVE_VALIDA,
                "password2": CLAVE_VALIDA,
                "codigo_hogar": "",
            },
            follow=True,
        )
        self.assertTrue(Usuario.objects.filter(email="alguien@example.com").exists())


class CorreoDuplicadoTests(PruebaConRegistroAbierto):
    """R2 — registrarse con un correo que ya tiene cuenta avisa y no crea una segunda."""

    def test_avisa_y_no_crea_segunda_cuenta(self):
        self.registrar_y_verificar("alejandro@example.com")
        self.client.logout()

        respuesta = self.registrar("alejandro@example.com")

        self.assertEqual(
            Usuario.objects.filter(email="alejandro@example.com").count(),
            1,
            "no debe crearse una segunda cuenta con el mismo correo",
        )
        # H2 de la revisión (2ª ronda): "le lleva a la pantalla de iniciar sesión" significa
        # que la petición TERMINA ahí (una redirección real), no que el enlace de "inicia
        # sesión" aparezca mencionado en alguna parte — ese enlace está en TODAS las páginas
        # de alta (`templates/account/signup.html` lo pinta siempre, con o sin error), así
        # que buscarlo en el HTML no demuestra nada por sí solo. Lo que sí lo demuestra es la
        # cadena de redirecciones.
        self.assertTrue(
            respuesta.redirect_chain,
            "el alta con un correo duplicado debe REDIRIGIR (no quedarse en el formulario)",
        )
        url_final, status_intermedio = respuesta.redirect_chain[-1]
        self.assertEqual(url_final, "/cuentas/login/")
        self.assertEqual(status_intermedio, 302)
        # Y la página en la que se acaba viendo es de verdad la de iniciar sesión, con el
        # aviso puesto — no un 200 cualquiera que por casualidad contenga esa URL en un enlace.
        self.assertContains(respuesta, "Entrar en KCalibra")
        self.assertContains(respuesta, "Ya existe una cuenta")

    def test_un_correo_nuevo_NO_redirige_a_iniciar_sesion(self):
        """
        Control del test de arriba: sin el hueco de C-14, dar de alta un correo que NO existe
        todavía se queda en la pantalla de espera de verificación, nunca en la de iniciar
        sesión — así se sabe que la redirección de arriba depende de verdad del correo
        duplicado, y no es algo que pase siempre.
        """
        respuesta = self.registrar("nunca-registrado@example.com")

        self.assertFalse(respuesta.redirect_chain[-1][0] == "/cuentas/login/")
        self.assertContains(respuesta, "Revisa tu correo")


class SesionNoCaducaTests(PruebaConRegistroAbierto):
    """R3/G-50 — una sesión no caduca por el mero paso del tiempo."""

    def test_la_edad_de_la_cookie_de_sesion_es_de_anhos_no_de_dias(self):
        self.registrar_y_verificar("alejandro@example.com")
        # No hay forma honesta de "esperar dos meses" en un test: lo que se comprueba es la
        # promesa concreta detrás del requisito — el plazo configurado para que la sesión siga
        # viva es de años, no el valor por defecto de Django (dos semanas). Si alguien lo
        # rebajara sin querer a algo corto, este test se entera.
        from django.conf import settings

        self.assertGreater(settings.SESSION_COOKIE_AGE, 60 * 60 * 24 * 365)

    def test_la_sesion_recien_creada_expira_dentro_de_anhos_no_de_dias(self):
        """
        No basta con leer el número en `settings.py` (el test de arriba): esto demuestra que
        una sesión CREADA DE VERDAD por un login real lleva ese plazo largo puesto, no uno
        corto que alguna otra pieza (allauth, un middleware) pudiera estar recortando por su
        cuenta sin que el ajuste de settings.py lo refleje.
        """
        from django.utils import timezone

        self.registrar_y_verificar("alejandro@example.com")
        expira = self.client.session.get_expiry_date()
        self.assertGreater(expira, timezone.now() + timezone.timedelta(days=365 * 5))

    def test_cada_peticion_alarga_la_sesion_hacia_ese_plazo_largo(self):
        """
        SESSION_SAVE_EVERY_REQUEST=True: la fecha de caducidad guardada en la base de datos se
        recalcula como "ahora + SESSION_COOKIE_AGE" en CADA petición, no solo al entrar. Aquí
        se deja la fila de sesión con una caducidad corta (como si quedara poco) escribiéndola
        directamente en la base (sin pasar por `set_expiry`, que fijaría un valor explícito y
        ya no dejaría ver el recálculo automático) y se comprueba que, tras UNA petición
        cualquiera, vuelve a quedar lejísimos — así es como alguien que abre la app de vez en
        cuando nunca se acerca al límite.
        """
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        self.registrar_y_verificar("alejandro@example.com")
        clave_sesion = self.client.session.session_key
        fila = Session.objects.get(session_key=clave_sesion)
        fila.expire_date = timezone.now() + timezone.timedelta(seconds=50)
        fila.save()

        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertTrue(respuesta.wsgi_request.user.is_authenticated)

        fila.refresh_from_db()
        self.assertGreater(fila.expire_date, timezone.now() + timezone.timedelta(days=365))

    def test_cerrar_sesion_si_termina_la_sesion(self):
        """Control: la sesión SÍ termina con un logout explícito (para que el test de arriba
        no esté vigilando "siempre autenticado pase lo que pase")."""
        self.registrar_y_verificar("alejandro@example.com")
        self.client.post("/cuentas/logout/")
        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_cambiar_la_contrasena_cierra_las_demas_sesiones(self):
        """R3/G-52 — cambiar la contraseña cierra las sesiones DE OTROS aparatos (aquí,
        simulados con un segundo cliente de pruebas), pero no la que se está usando."""
        from django.test import Client

        self.registrar_y_verificar("alejandro@example.com")

        otro_aparato = Client()
        otro_aparato.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        self.assertTrue(
            otro_aparato.get("/hogares/mi-hogar/").wsgi_request.user.is_authenticated
        )

        nueva_clave = "otra-clave-de-verdad-2026"
        self.client.post(
            "/cuentas/password/change/",
            {
                "oldpassword": CLAVE_VALIDA,
                "password1": nueva_clave,
                "password2": nueva_clave,
            },
        )

        # La sesión ACTUAL (la que cambió la contraseña) sigue dentro.
        self.assertTrue(
            self.client.get("/hogares/mi-hogar/").wsgi_request.user.is_authenticated
        )
        # La del OTRO aparato, no.
        self.assertFalse(
            otro_aparato.get("/hogares/mi-hogar/").wsgi_request.user.is_authenticated
        )


class LimiteDeIntentosTests(PruebaConRegistroAbierto):
    """R4/Q-12 — varios fallos de contraseña seguidos bloquean el acceso desde ahí, sin decir
    nunca si lo que falla es el correo o la contraseña."""

    def test_tras_varios_fallos_se_bloquea_sin_distinguir_el_motivo(self):
        self.registrar_y_verificar("alejandro@example.com")
        self.client.logout()

        # Los mismos mensajes de error, fallando por CONTRASEÑA incorrecta...
        respuesta_pass_mala = self.client.post(
            "/cuentas/login/", {"login": "alejandro@example.com", "password": "mala-clave"}
        )
        # ...y fallando por CORREO que no existe: el texto tiene que ser IDÉNTICO.
        respuesta_correo_malo = self.client.post(
            "/cuentas/login/", {"login": "no-existe@example.com", "password": "lo-que-sea"}
        )
        mensaje_pass_mala = respuesta_pass_mala.context["form"].non_field_errors()
        mensaje_correo_malo = respuesta_correo_malo.context["form"].non_field_errors()
        self.assertEqual(list(mensaje_pass_mala), list(mensaje_correo_malo))

        # Bastantes fallos seguidos MÁS, todos contra el mismo correo: en algún punto, la app
        # dejará de intentar autenticar y devolverá el mensaje de bloqueo.
        ultima_respuesta = None
        for _ in range(10):
            ultima_respuesta = self.client.post(
                "/cuentas/login/",
                {"login": "alejandro@example.com", "password": "sigue-mal"},
            )
        texto = ultima_respuesta.content.decode()
        self.assertIn("Demasiados intentos", texto)

        # Y aunque ahora se teclee la contraseña BUENA, sigue sin dejar entrar: el acceso
        # está cerrado "desde ahí" durante un rato, no solo mientras se falla.
        respuesta_con_clave_buena = self.client.post(
            "/cuentas/login/",
            {"login": "alejandro@example.com", "password": CLAVE_VALIDA},
        )
        self.assertFalse(respuesta_con_clave_buena.wsgi_request.user.is_authenticated)


class ContrasenasCifradasTests(PruebaConRegistroAbierto):
    """R10/Q-12 — las contraseñas se guardan cifradas: mirando la base de datos no aparece
    ninguna en claro."""

    def test_la_fila_de_la_base_de_datos_no_contiene_la_contrasena_en_claro(self):
        clave_en_claro = "correcaballo-manzana-2026"
        self.registrar_y_verificar("alejandro@example.com", password=clave_en_claro)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT password FROM cuentas_usuario WHERE email = %s",
                ["alejandro@example.com"],
            )
            (password_almacenada,) = cursor.fetchone()

        self.assertNotEqual(password_almacenada, clave_en_claro)
        self.assertNotIn(clave_en_claro, password_almacenada)
        # Con pinta de hash de Django (algoritmo$iteraciones$sal$hash), no de texto suelto.
        self.assertIn("$", password_almacenada)


class VerificacionDeCorreoTests(PruebaConRegistroAbierto):
    """R13, R14, R15 — la cuenta dormida, la pantalla de espera, y el enlace de 24h/un uso."""

    def test_antes_de_verificar_no_hay_sesion_ni_se_ve_nada(self):
        """R13/R14: recién registrada, la cuenta EXISTE pero no hay forma de entrar."""
        self.registrar("alejandro@example.com")
        self.assertTrue(Usuario.objects.filter(email="alejandro@example.com").exists())

        respuesta = self.client.get("/hogares/mi-hogar/", follow=True)
        # @login_required la manda a iniciar sesión: no hay sesión, no hay datos.
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)
        self.assertIn("/cuentas/login/", respuesta.redirect_chain[-1][0])

    def test_llamando_directamente_al_servidor_tampoco_ve_nada(self):
        """R14, la mitad "por detrás": ni siquiera pidiendo la URL exacta sin pasar por
        ningún botón se ve nada, antes de verificar."""
        self.registrar("alejandro@example.com")
        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertEqual(respuesta.status_code, 302)  # a login, nunca 200 con datos

    def test_pantalla_de_espera_dice_a_que_correo_se_mando(self):
        respuesta = self.registrar("alejandro@example.com")
        self.assertContains(respuesta, "alejandro@example.com")
        self.assertContains(respuesta, "24 horas")

    def test_al_pulsar_el_enlace_entra_sin_iniciar_sesion_aparte(self):
        respuesta = self.registrar_y_verificar("alejandro@example.com")
        self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
        self.assertEqual(
            respuesta.wsgi_request.user.email.lower(), "alejandro@example.com"
        )

    def test_el_enlace_caducado_no_da_acceso(self):
        """R15/Q-14: pasadas 24 horas, el enlace deja de valer."""
        import time
        from unittest import mock

        self.registrar("alejandro@example.com")
        enlace = self.ultimo_enlace_de_verificacion(para_correo="alejandro@example.com")

        dentro_de_25_horas = time.time() + 60 * 60 * 25
        with mock.patch("time.time", return_value=dentro_de_25_horas):
            respuesta = self.client.get(enlace, follow=True)

        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)
        self.assertContains(respuesta, "ya no vale")

    def test_el_enlace_usado_no_vuelve_a_dar_acceso(self):
        """R15/Q-14: "usado... no vuelve a dar acceso"."""
        self.registrar("alejandro@example.com")
        enlace = self.ultimo_enlace_de_verificacion(para_correo="alejandro@example.com")

        primera_vez = self.client.get(enlace, follow=True)
        self.assertTrue(primera_vez.wsgi_request.user.is_authenticated)

        self.client.logout()
        segunda_vez = self.client.get(enlace, follow=True)
        self.assertFalse(segunda_vez.wsgi_request.user.is_authenticated)
        self.assertContains(segunda_vez, "ya no vale")

    def test_pedir_otro_correo_manda_uno_nuevo_sin_rellenar_el_alta_otra_vez(self):
        from django.core import mail

        self.registrar("alejandro@example.com")
        num_correos_antes = len(mail.outbox)

        respuesta = self.client.post(
            "/cuentas/esperando-verificacion/reenviar/", follow=True
        )

        self.assertGreater(len(mail.outbox), num_correos_antes)
        self.assertContains(respuesta, "nuevo enlace")
        # Y ese correo nuevo también deja entrar (no es un enlace decorativo).
        nuevo_enlace = self.ultimo_enlace_de_verificacion(para_correo="alejandro@example.com")
        respuesta_confirmar = self.client.get(nuevo_enlace, follow=True)
        self.assertTrue(respuesta_confirmar.wsgi_request.user.is_authenticated)

    def test_corregir_la_direccion_sin_rellenar_el_alta_otra_vez(self):
        self.registrar("alejandro-con-un-typo@example.com")

        respuesta = self.client.post(
            "/cuentas/esperando-verificacion/corregir/",
            {"nuevo_correo": "alejandro@example.com"},
            follow=True,
        )

        self.assertFalse(
            Usuario.objects.filter(email="alejandro-con-un-typo@example.com").exists()
        )
        usuario = Usuario.objects.get(email="alejandro@example.com")
        self.assertFalse(usuario.is_active is False)  # sigue siendo la MISMA cuenta, corregida
        self.assertContains(respuesta, "alejandro@example.com")

        enlace = self.ultimo_enlace_de_verificacion(para_correo="alejandro@example.com")
        respuesta_confirmar = self.client.get(enlace, follow=True)
        self.assertTrue(respuesta_confirmar.wsgi_request.user.is_authenticated)

    def test_corregir_invalida_el_enlace_viejo(self):
        """
        H1 de la revisión (2ª ronda, el hueco GRAVE): el enlace de verificación firma el PK de
        la fila `EmailAddress`, no la dirección. Reproduce el ataque tal cual lo describió el
        revisor: alguien se da de alta con una dirección, NO pulsa el enlace, "corrige" la
        dirección a la de una víctima, y prueba el enlace VIEJO — que no debe verificar NADA
        ni dejar ninguna sesión abierta sobre la dirección corregida.
        """
        self.registrar("atacante@evil.com")
        enlace_viejo = self.ultimo_enlace_de_verificacion(para_correo="atacante@evil.com")

        self.client.post(
            "/cuentas/esperando-verificacion/corregir/",
            {"nuevo_correo": "victima@banco.com"},
        )

        respuesta = self.client.get(enlace_viejo, follow=True)

        self.assertFalse(
            respuesta.wsgi_request.user.is_authenticated,
            "el enlace viejo NO debe dejar ninguna sesión abierta",
        )
        victima = Usuario.objects.get(email="victima@banco.com")
        self.assertFalse(
            EmailAddress.objects.filter(user=victima, verified=True).exists(),
            "el enlace viejo NO debe haber verificado la dirección corregida",
        )
        # Y el enlace NUEVO (el que sí se manda a la dirección corregida) funciona con
        # normalidad — el arreglo no rompe el camino feliz de R15.
        enlace_nuevo = self.ultimo_enlace_de_verificacion(para_correo="victima@banco.com")
        respuesta_buena = self.client.get(enlace_nuevo, follow=True)
        self.assertTrue(respuesta_buena.wsgi_request.user.is_authenticated)

    def test_reenviar_y_corregir_tienen_limite_de_intentos(self):
        """
        H1 de la revisión: sin límite, estas dos vistas convierten la app en un relé que manda
        enlaces a cualquier dirección que alguien teclee. Se machaca "corregir" apuntando cada
        vez a una víctima distinta (así se comprueba que el límite es por IP, no solo por
        correo — si fuera solo por correo, cambiar de víctima en cada intento lo esquivaría).
        """
        self.registrar("atacante@evil.com")

        ultima_respuesta = None
        for numero in range(10):
            ultima_respuesta = self.client.post(
                "/cuentas/esperando-verificacion/corregir/",
                {"nuevo_correo": f"victima{numero}@banco.com"},
                follow=True,
            )

        self.assertContains(ultima_respuesta, "Demasiados intentos")

    def test_no_se_puede_corregir_a_un_correo_que_ya_tiene_cuenta(self):
        self.registrar_y_verificar("alejandro@example.com")
        self.client.logout()
        self.registrar("euridice@example.com")

        self.client.post(
            "/cuentas/esperando-verificacion/corregir/",
            {"nuevo_correo": "alejandro@example.com"},
        )

        # La corrección se rechaza: euridice se queda con SU dirección original...
        self.assertTrue(
            Usuario.objects.filter(email="euridice@example.com").exists()
        )
        # ...y la cuenta de alejandro sigue siendo UNA sola, no se ha tocado.
        self.assertEqual(
            Usuario.objects.filter(email="alejandro@example.com").count(), 1
        )


class RutasFueraDeAlcanceTests(PruebaConRegistroAbierto):
    """
    H3 de la revisión (2ª ronda): `include("allauth.urls")` montaba de más — la recuperación
    de contraseña (R-22) y la gestión de direcciones de correo (`account_email`, la misma
    superficie que H1), ninguna de las dos especificada ni probada en esta unidad. "Fuera de
    alcance" significa que ese comportamiento no se entrega: estas rutas tienen que devolver
    404, para que si alguien las vuelve a montar sin querer (por ejemplo, al integrar R-21 o
    R-22 de verdad) este test se entere.
    """

    def test_recuperar_contrasena_no_esta_montado(self):
        respuesta = self.client.get("/cuentas/password/reset/")
        self.assertEqual(respuesta.status_code, 404)

    def test_gestion_de_direcciones_de_correo_no_esta_montado(self):
        self.registrar_y_verificar("alejandro@example.com")
        respuesta = self.client.get("/cuentas/email/")
        self.assertEqual(respuesta.status_code, 404)

    def test_las_rutas_que_si_hacen_falta_siguen_ahi(self):
        """Control: la poda de arriba no se llevó por delante nada que sí haga falta."""
        for ruta in ["/cuentas/signup/", "/cuentas/login/", "/cuentas/logout/"]:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertNotEqual(respuesta.status_code, 404)
