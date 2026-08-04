"""
Tests de la unidad 003, la parte de "cuentas": R2, R3, R4, R10, R12, R13, R14, R15.

Todos pasan por el cliente de pruebas de Django contra las URLs reales (nunca llamando a
`Usuario.objects.create(...)` a mano ni a las funciones internas): es la única forma de
demostrar que la APP se comporta así de punta a punta, tal como exige el AGENTS.md de esta
unidad y la lección de docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo.

Desde la unidad 008 (ver `EnvioDeCorreoTests` y `RecuperarContrasenaTests` más abajo) se
suman R2 (R-22), R3, R4, R5, R6 y R7: el correo sale de verdad y, si el envío falla, nadie se
queda atrapado.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from smtplib import SMTPException
from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings

from cuentas.ayuda_pruebas import CLAVE_VALIDA, DATOS_FISICOS_POR_DEFECTO, PruebaConRegistroAbierto
from kcalibra.settings import _booleano_desde_entorno, _entero_desde_entorno

Usuario = get_user_model()

# Igual que `_RE_ENLACE` de ayuda_pruebas.py, pero para el enlace de RECUPERAR CONTRASEÑA
# (unidad 008): otra ruta, otro correo, así que hace falta su propio patrón.
_RE_ENLACE_RECUPERAR = re.compile(r"(http\S+/cuentas/password/reset/key/\S+/)")


def _ultimo_enlace_de_recuperacion(para_correo=None):
    """Como `PruebaConRegistroAbierto.ultimo_enlace_de_verificacion`, pero para el enlace de
    "pon una contraseña nueva" del correo de recuperación."""
    mensajes = mail.outbox
    if para_correo:
        mensajes = [m for m in mensajes if para_correo in m.to]
    assert mensajes, f"no se mandó ningún correo a {para_correo!r}"
    cuerpo = mensajes[-1].body
    coincidencia = _RE_ENLACE_RECUPERAR.search(cuerpo)
    assert coincidencia, f"el correo no contiene un enlace de recuperación: {cuerpo!r}"
    return coincidencia.group(1)

# El punto único por el que sale CUALQUIER correo de la app, una vez que
# `AdaptadorDeCuentas.send_mail` ya ha construido el mensaje (ver cuentas/adapters.py): es lo
# que hay que hacer fallar para simular "el proveedor no contesta" sin tocar la red de
# verdad, tal como pide el plan de esta unidad ("el test SIMULA el fallo, no espera a que
# ocurra").
_RUTA_ENVIO_DE_MENSAJE = "django.core.mail.message.EmailMessage.send"


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
                # Unidad 004: el formulario de alta creció y ahora pide también los datos
                # físicos (cuentas/forms.py). Van aquí con valores válidos para que la ÚNICA
                # razón de que esta cuenta no se cree sea el registro cerrado (lo que este
                # test dice probar) y no un formulario incompleto por otro motivo.
                **DATOS_FISICOS_POR_DEFECTO,
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
                # Unidad 004: ver el comentario del test de arriba.
                **DATOS_FISICOS_POR_DEFECTO,
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

    def test_un_error_de_formulario_distinto_no_redirige_a_iniciar_sesion(self):
        """
        Segundo control, añadido en la 3ª revisión: el de arriba usa un correo NUEVO, que es
        un formulario VÁLIDO — nunca llega a pasar por `form_invalid`, así que no demuestra
        nada sobre ESE método (comprobado: con `form_invalid` redirigiendo SIEMPRE a
        `account_login`, pasara lo que pasara, este archivo seguía entero en verde). Lo que sí
        hace falta es un formulario INVÁLIDO por un motivo que NO sea el correo duplicado —
        aquí, una contraseña completamente numérica, que Django rechaza de fábrica
        (`NumericPasswordValidator`) — y comprobar que la persona se queda en el formulario de
        alta corrigiendo su contraseña, no que la manden a iniciar sesión sin haber creado
        nada.
        """
        respuesta = self.registrar("alguien-nuevo@example.com", password="12345678")

        self.assertFalse(
            respuesta.redirect_chain,
            "un error de CONTRASEÑA no debe redirigir a ninguna parte: se queda en el alta",
        )
        self.assertContains(respuesta, "Crea tu cuenta")
        self.assertFalse(Usuario.objects.filter(email="alguien-nuevo@example.com").exists())


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
        # `follow=True` es lo que importa aquí (H4 de la 3ª revisión): tras cambiarla, allauth
        # REDIRIGE de vuelta a `/cuentas/password/change/` (`get_password_change_redirect_url`
        # apunta ahí por defecto) — sin seguir esa redirección, el test se queda en el 302 y
        # jamás llega a RENDERIZAR esa plantilla. Fue justo eso lo que dejó pasar un `500` real
        # (la plantilla de fábrica de allauth enlaza a una URL que H3 quitó a propósito): la
        # ruta "existía" (302 sin sesión), pero renderizarla de verdad reventaba.
        respuesta = self.client.post(
            "/cuentas/password/change/",
            {
                "oldpassword": CLAVE_VALIDA,
                "password1": nueva_clave,
                "password2": nueva_clave,
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)

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

    def test_corregir_no_deja_a_nadie_a_medias_si_falla_por_el_camino(self):
        """
        3ª revisión, "menor" 1: el disparador realista no es que el proceso muera, es que
        lleguen DOS peticiones a la vez sobre el mismo correo (dos pestañas, un doble clic).
        Sin `transaction.atomic()`, si el `create()` de la `EmailAddress` nueva fallara
        DESPUÉS de que el `delete()` de la vieja ya se hubiera confirmado en la base, la
        persona se quedaría sin NINGUNA fila `EmailAddress` — fuera de su propia cuenta: la
        pantalla de espera le diría "no hay ninguna verificación pendiente", no podría ni
        reenviar ni corregir, y R2 le impediría volver a registrarse con ese correo.

        Se simula el fallo a mano (un `create()` que revienta) y se comprueba que la fila
        ORIGINAL sigue intacta: con `transaction.atomic()`, o se confirman las tres escrituras
        juntas, o no se confirma ninguna.
        """
        from unittest import mock

        self.registrar("alejandro@example.com")

        with mock.patch(
            "cuentas.views.EmailAddress.objects.create",
            side_effect=RuntimeError("fallo simulado, a medio camino"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    "/cuentas/esperando-verificacion/corregir/",
                    {"nuevo_correo": "otra-direccion@example.com"},
                )

        # La fila ORIGINAL sigue ahí, sin verificar, tal cual estaba: nada se quedó a medias.
        self.assertTrue(
            EmailAddress.objects.filter(
                email="alejandro@example.com", verified=False
            ).exists(),
            "sin la fila original, la persona se queda sin ninguna EmailAddress pendiente",
        )
        usuario = Usuario.objects.get(email="alejandro@example.com")
        self.assertEqual(usuario.email, "alejandro@example.com")
        self.assertFalse(
            Usuario.objects.filter(email="otra-direccion@example.com").exists()
        )

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


class EnvioDeCorreoTests(PruebaConRegistroAbierto):
    """
    Unidad 008 — R5 (LO IMPORTANTE), R6 y R7: si el envío de un correo falla, nadie se queda
    atrapado y queda constancia en el log.

    Los tres tests que importan (`test_fallo_al_dar_de_alta...`,
    `test_fallo_al_reenviar...`, `test_fallo_al_corregir...`) SIMULAN el fallo del proveedor
    haciendo que `EmailMessage.send()` lance `SMTPException` — nunca esperan a que un envío de
    verdad falle, ni tocan la red (R8).
    """

    def test_fallo_al_dar_de_alta_no_deja_una_cuenta_atrapada(self):
        """
        R5 — el criterio que da sentido a la unidad. Antes del arreglo, este fallo tumbaba la
        petición con un 500 (allauth no captura nada, Django no lo permite en silencio) sobre
        una cuenta que YA estaba guardada (no hay ATOMIC_REQUESTS): la persona se quedaba sin
        ver la pantalla de espera y, al reintentar, R2 le decía "ya existe una cuenta con ese
        correo" — sin salida.
        """
        with mock.patch(_RUTA_ENVIO_DE_MENSAJE, side_effect=SMTPException("el proveedor no contesta")):
            respuesta = self.registrar("alejandro@example.com")

        # No sale un 500: si `send_mail` no hubiera capturado el fallo, esta misma línea del
        # test habría reventado con la SMTPException sin capturar (el cliente de pruebas de
        # Django deja subir las excepciones no manejadas por la vista, no las convierte en un
        # 500 silencioso) — el hecho de llegar hasta aquí con una respuesta normal YA es la
        # prueba.
        self.assertEqual(respuesta.status_code, 200)

        # La cuenta se creó (a medias, sin verificar: eso es aceptable y esperado), pero NO es
        # una cuenta "a medio crear que le impida volver a intentarlo": le queda la pantalla
        # de espera, con su camino de vuelta.
        self.assertTrue(Usuario.objects.filter(email="alejandro@example.com").exists())
        self.assertContains(respuesta, "Revisa tu correo")
        self.assertContains(respuesta, "alejandro@example.com")

        # Camino de vuelta 1: pedir otro enlace desde esa misma pantalla, sin rellenar el alta
        # de nuevo. Sigue fallando el envío (mismo mock), pero eso NO puede volver a tumbar la
        # petición.
        with mock.patch(_RUTA_ENVIO_DE_MENSAJE, side_effect=SMTPException("sigue caído")):
            respuesta_reenvio = self.client.post(
                "/cuentas/esperando-verificacion/reenviar/", follow=True
            )
        self.assertEqual(respuesta_reenvio.status_code, 200)

        # Camino de vuelta 2: si el proveedor se recupera, un reenvío de verdad SÍ deja
        # entrar — la cuenta nunca quedó en un estado del que no se pudiera salir.
        respuesta_reenvio_bueno = self.client.post(
            "/cuentas/esperando-verificacion/reenviar/", follow=True
        )
        self.assertEqual(respuesta_reenvio_bueno.status_code, 200)
        enlace = self.ultimo_enlace_de_verificacion(para_correo="alejandro@example.com")
        respuesta_confirmar = self.client.get(enlace, follow=True)
        self.assertTrue(respuesta_confirmar.wsgi_request.user.is_authenticated)

    def test_fallo_de_red_generico_tampoco_tumba_el_alta(self):
        """
        R5, caso límite: no todos los fallos de un proveedor SMTP son `SMTPException` — un
        DNS que no resuelve o una conexión rechazada son `OSError` (y el `TimeoutError` que
        dispara `EMAIL_TIMEOUT` en cuanto el proveedor no contesta a tiempo, también). Sin
        `OSError` en la captura, precisamente el timeout que esta unidad añade para no colgar
        la petición seguiría colgándola con una excepción sin capturar.
        """
        with mock.patch(_RUTA_ENVIO_DE_MENSAJE, side_effect=TimeoutError("tiempo agotado")):
            respuesta = self.registrar("timeout@example.com")

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Usuario.objects.filter(email="timeout@example.com").exists())
        self.assertContains(respuesta, "Revisa tu correo")

    def test_fallo_al_reenviar_no_da_un_500(self):
        """R6, primera de las "otras dos puertas": reenviar la verificación."""
        self.registrar("alejandro@example.com")

        with mock.patch(_RUTA_ENVIO_DE_MENSAJE, side_effect=SMTPException("caído")):
            respuesta = self.client.post(
                "/cuentas/esperando-verificacion/reenviar/", follow=True
            )

        self.assertEqual(respuesta.status_code, 200)
        # Sigue en la pantalla de espera, con su camino de vuelta intacto — no la echa a
        # ningún sitio raro ni la deja sin nada que hacer.
        self.assertContains(respuesta, "Revisa tu correo")

    def test_fallo_al_corregir_no_da_un_500(self):
        """R6, segunda puerta: corregir la dirección de correo."""
        self.registrar("con-un-typo@example.com")

        with mock.patch(_RUTA_ENVIO_DE_MENSAJE, side_effect=SMTPException("caído")):
            respuesta = self.client.post(
                "/cuentas/esperando-verificacion/corregir/",
                {"nuevo_correo": "corregido@example.com"},
                follow=True,
            )

        self.assertEqual(respuesta.status_code, 200)
        # La corrección en sí (cambiar de fila EmailAddress, ver H1 de la 003) no depende del
        # envío: se aplicó igual, y la pantalla de espera sigue ahí para reintentar.
        self.assertTrue(
            Usuario.objects.filter(email="corregido@example.com").exists()
        )
        self.assertContains(respuesta, "Revisa tu correo")

    def test_el_fallo_de_envio_queda_registrado_en_el_log(self):
        """
        R7 — "si un envío falla, queda registrado donde se pueda ver". Hoy nadie se entera de
        nada: se comprueba que el logger de `cuentas.adapters` (el que usa `send_mail`) emite
        un registro de error cuando el envío revienta.
        """
        with mock.patch(_RUTA_ENVIO_DE_MENSAJE, side_effect=SMTPException("boom")):
            with self.assertLogs("cuentas.adapters", level="ERROR") as registro:
                self.registrar("se-queda-en-el-log@example.com")

        self.assertTrue(
            any("No se pudo enviar el correo" in mensaje for mensaje in registro.output),
            registro.output,
        )

    def test_sin_ningun_fallo_no_se_registra_nada_de_error(self):
        """Control del test de arriba: con el envío yendo bien (el caso normal de toda la
        suite), el logger de `cuentas.adapters` no tiene por qué decir nada."""
        with self.assertRaises(AssertionError):
            # `assertLogs` FALLA con AssertionError si NINGÚN mensaje se emitió en ese
            # logger/nivel durante el bloque — que es justo lo que se espera aquí: ningún
            # error, porque el envío (al backend de memoria de los tests) no falla.
            with self.assertLogs("cuentas.adapters", level="ERROR"):
                self.registrar("sin-fallos@example.com")


class ConfiguracionDeCorreoTests(TestCase):
    """
    Unidad 009 — R1-R11: una variable de entorno del bloque de correo definida pero VACÍA (lo
    más fácil del mundo al copiar `.env.example` a medias) no puede tumbar el arranque de la
    app (R1, R2) ni desactivar el cifrado en silencio (R3, R4); sin definir en absoluto, el
    comportamiento sigue siendo el de siempre (R5, caso límite de no regresión).

    Ampliación de la 2ª ronda (R8-R11), con el principio que decidió el usuario: ante un valor
    que no se entiende, la app falla RUIDOSAMENTE y nombrando la variable — nunca cae del lado
    inseguro. `USE_TLS` acepta las formas habituales de sí/no (R8); un valor irreconocible en
    `USE_TLS`, o uno no numérico en `PORT`/`TIMEOUT`, hace que la app NO arranque y el error
    nombre la variable (R9, R10); y los ayudantes respetan de verdad el valor cuando SÍ lo hay,
    no solo cuando falta (R11 — la sexta cara de "un test que no falla cuando debe": la 1ª
    ronda solo clavó la rama "ausente o vacía", nunca la de "hay un valor y se usa").

    Dos formas de ejercitar la lectura REAL de la configuración (nunca una copia de la regla
    escrita aquí, que pasaría siempre y no probaría nada — 1ª cara del mismo error):

    - Cuando lo que importa es que Django ARRANQUE (o se niegue a hacerlo) con esa
      configuración de verdad cargada, cada test lanza un PROCESO APARTE (mismo motivo que
      `ArranqueSinConfiguracionTests` de `paginas/tests.py`: una vez que ESTE proceso de test
      ya importó `kcalibra.settings`, no hay forma limpia de "desconfigurarlo").
    - Cuando lo que importa es el propio ayudante (`_entero_desde_entorno`,
      `_booleano_desde_entorno`) — R5, R11 — se importa la función de producción DIRECTAMENTE
      y se llama con `mock.patch.dict(os.environ, ..., clear=True)`: ejercita el código real
      sin lanzar un subproceso ni tocar el disco. Corregido en la 2ª ronda (bloqueante del
      revisor): la versión anterior de R5 renombraba el `.env` real del disco para simular
      "no está definida en absoluto", y eso significaba mover un fichero con la `SECRET_KEY` y
      las credenciales de la base de datos — un `kill -9` a mitad de esa ventana podía dejarlo
      escondido bajo un nombre temporal sin que `git status` avisara (lo tapa `.gitignore`), y
      además petaba con `FileNotFoundError` en cualquier máquina sin `.env` en disco (el día
      del despliegue, que es justo lo que esta unidad protege). El cableado función ->
      `EMAIL_PORT`/`EMAIL_TIMEOUT`/`EMAIL_USE_TLS` ya lo demuestran de sobra los subprocesos de
      R1-R4 de aquí abajo: no hace falta repetirlo para probar el ayudante en sí.
    """

    _RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

    def _leer_configuracion_de_correo(self, entorno):
        """Lanza `manage.py shell -c` en un subproceso con el entorno dado y devuelve
        (EMAIL_PORT, EMAIL_TIMEOUT, EMAIL_USE_TLS) tal como Django los cargó de verdad."""
        resultado = subprocess.run(
            [
                sys.executable,
                "manage.py",
                "shell",
                "-c",
                "from django.conf import settings\n"
                "print(settings.EMAIL_PORT)\n"
                "print(settings.EMAIL_TIMEOUT)\n"
                "print(settings.EMAIL_USE_TLS)\n",
            ],
            cwd=str(self._RAIZ_PROYECTO),
            env=entorno,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            resultado.returncode,
            0,
            "la app debe arrancar con esta configuración de correo, y no lo hizo:\n"
            f"stdout: {resultado.stdout}\nstderr: {resultado.stderr}",
        )
        lineas = [linea for linea in resultado.stdout.strip().splitlines() if linea.strip()]
        # El comando de shell puede imprimir avisos antes de nuestras tres líneas (p. ej. los
        # objetos que autoimporta django-extensions) — solo las tres últimas son las nuestras.
        puerto, tiempo_espera, usa_tls = lineas[-3:]
        return int(puerto), int(tiempo_espera), usa_tls == "True"

    def test_puerto_vacio_arranca_con_el_puerto_por_defecto(self):
        """R1 — hoy revienta con ValueError; debe arrancar y usar 587."""
        entorno = os.environ.copy()
        entorno["DJANGO_EMAIL_PORT"] = ""
        puerto, _tiempo_espera, _usa_tls = self._leer_configuracion_de_correo(entorno)
        self.assertEqual(puerto, 587)

    def test_tiempo_de_espera_vacio_arranca_con_el_por_defecto(self):
        """R2 — hoy revienta con ValueError; debe arrancar y usar 10 segundos."""
        entorno = os.environ.copy()
        entorno["DJANGO_EMAIL_TIMEOUT"] = ""
        _puerto, tiempo_espera, _usa_tls = self._leer_configuracion_de_correo(entorno)
        self.assertEqual(tiempo_espera, 10)

    def test_use_tls_vacio_deja_el_cifrado_activado(self):
        """R3 — hoy queda desactivado en silencio; debe quedar ACTIVADO (el valor seguro)."""
        entorno = os.environ.copy()
        entorno["DJANGO_EMAIL_USE_TLS"] = ""
        _puerto, _tiempo_espera, usa_tls = self._leer_configuracion_de_correo(entorno)
        self.assertTrue(usa_tls, "una variable vacía nunca puede apagar el cifrado")

    def test_use_tls_acepta_formas_habituales_de_decir_si(self):
        """R4/R8 — variantes de "sí" (incluidas las de la 1ª ronda), sin mirar mayúsculas ni
        espacios, activan el cifrado."""
        for valor in ["true", "TRUE", " True ", "1", "yes", "YES", "on", "On", "si", "sí", "Sí"]:
            with self.subTest(valor=valor):
                entorno = os.environ.copy()
                entorno["DJANGO_EMAIL_USE_TLS"] = valor
                _puerto, _tiempo_espera, usa_tls = self._leer_configuracion_de_correo(entorno)
                self.assertTrue(usa_tls, f"{valor!r} debe activar el cifrado")

    def test_use_tls_acepta_formas_habituales_de_decir_no(self):
        """
        R8 — "false", "0", "no", "off" desactivan el cifrado EXPLÍCITAMENTE (a diferencia de
        una variable vacía, que lo deja ACTIVADO por R3: aquí SÍ hay un valor, y ese valor dice
        que no). Sin mirar mayúsculas ni espacios, igual que la lista de "sí".
        """
        for valor in ["false", "FALSE", " False ", "0", "no", "NO", "off", "OFF"]:
            with self.subTest(valor=valor):
                entorno = os.environ.copy()
                entorno["DJANGO_EMAIL_USE_TLS"] = valor
                _puerto, _tiempo_espera, usa_tls = self._leer_configuracion_de_correo(entorno)
                self.assertFalse(usa_tls, f"{valor!r} debe desactivar el cifrado")

    def test_use_tls_valor_irreconocible_no_arranca_y_nombra_la_variable(self):
        """
        R9 — un valor que no está en NINGUNA de las dos listas de R8 (un typo como "ture", o
        "xyz") no puede resolverse como "desactivado": eso sería exactamente el mismo fallo del
        lado inseguro que R3 cerró para la variable vacía. La app se niega a arrancar, y el
        mensaje nombra la variable — se comprueba con la frase exacta del mensaje, no solo con
        que algo fallara, porque un `ValueError` en bruto (el error críptico de antes) también
        tumbaría el arranque sin decir nada útil.
        """
        for valor in ["ture", "xyz"]:
            with self.subTest(valor=valor):
                entorno = os.environ.copy()
                entorno["DJANGO_EMAIL_USE_TLS"] = valor
                resultado = subprocess.run(
                    [sys.executable, "manage.py", "check"],
                    cwd=str(self._RAIZ_PROYECTO),
                    env=entorno,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                salida_completa = resultado.stdout + resultado.stderr
                self.assertNotEqual(
                    resultado.returncode,
                    0,
                    f"la app NO debe arrancar con DJANGO_EMAIL_USE_TLS={valor!r}",
                )
                self.assertIn("DJANGO_EMAIL_USE_TLS", salida_completa)
                self.assertIn(
                    "no se entiende como sí/no",
                    salida_completa,
                    "el mensaje debe ser el nuestro, no un ValueError en bruto",
                )

    def test_puerto_y_tiempo_de_espera_no_numericos_no_arrancan_y_nombran_la_variable(self):
        """
        R10 — hoy un valor no numérico en PORT o TIMEOUT revienta con un `ValueError` críptico
        que no dice cuál de las dos variables falló (la queja con la que nació R1, resuelta en
        la 1ª ronda solo para el caso vacío). Mismo patrón que `variable_obligatoria()`, diez
        líneas más arriba en `settings.py`: la app no arranca y el mensaje nombra la variable.
        """
        for variable in ("DJANGO_EMAIL_PORT", "DJANGO_EMAIL_TIMEOUT"):
            with self.subTest(variable=variable):
                entorno = os.environ.copy()
                entorno[variable] = "abc"
                resultado = subprocess.run(
                    [sys.executable, "manage.py", "check"],
                    cwd=str(self._RAIZ_PROYECTO),
                    env=entorno,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                salida_completa = resultado.stdout + resultado.stderr
                self.assertNotEqual(
                    resultado.returncode, 0, f"la app NO debe arrancar con {variable}='abc'"
                )
                self.assertIn(variable, salida_completa)
                self.assertIn(
                    "no es un número",
                    salida_completa,
                    "el mensaje debe ser el nuestro, no un ValueError en bruto",
                )

    def test_el_tiempo_de_espera_del_correo_queda_clavado(self):
        """
        R7 — hoy `EMAIL_TIMEOUT` se puede borrar entero de `settings.py` y la suite sigue en
        verde (nada afirma sobre su valor). Este test lee la configuración YA cargada en este
        mismo proceso (la real, la del `.env` de esta rama) y exige el valor concreto: si la
        línea desaparece, `EMAIL_TIMEOUT` cae al default de Django (`None`) y esto se rompe.
        """
        from django.conf import settings

        self.assertEqual(settings.EMAIL_TIMEOUT, 10)

    def test_sin_definir_en_absoluto_se_comporta_como_siempre(self):
        """
        R5 (caso límite, no regresión) — con las tres variables AUSENTES de verdad, el
        resultado tiene que ser el de siempre: 587, 10 segundos, cifrado activado. Se llama a
        los ayudantes de producción DIRECTAMENTE con `mock.patch.dict(os.environ, {},
        clear=True)` — ver el porqué en el docstring de la clase (bloqueante corregido en la
        2ª ronda: la versión anterior tocaba el `.env` real del disco).
        """
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_entero_desde_entorno("DJANGO_EMAIL_PORT", 587), 587)
            self.assertEqual(_entero_desde_entorno("DJANGO_EMAIL_TIMEOUT", 10), 10)
            self.assertTrue(_booleano_desde_entorno("DJANGO_EMAIL_USE_TLS", True))

    def test_los_ayudantes_respetan_el_valor_cuando_si_lo_hay(self):
        """
        R11 (la sexta cara de "un test que no falla cuando debe") — la 1ª ronda solo clavó la
        rama "ausente o vacía -> por defecto" de los dos ayudantes; ninguno de sus tests
        distinguía un ayudante que LEE el entorno de uno que ignora todo y siempre devuelve el
        valor por defecto (así se coló: 196 tests en verde con los dos ayudantes ciegos). Se
        llama a la función de producción DIRECTAMENTE, con un valor DISTINTO del por defecto en
        cada caso, para que no cuele un ayudante que solo reconozca el valor por defecto mismo.
        """
        with mock.patch.dict(os.environ, {"DJANGO_EMAIL_PORT": "2525"}, clear=True):
            self.assertEqual(_entero_desde_entorno("DJANGO_EMAIL_PORT", 587), 2525)

        with mock.patch.dict(os.environ, {"DJANGO_EMAIL_TIMEOUT": "30"}, clear=True):
            self.assertEqual(_entero_desde_entorno("DJANGO_EMAIL_TIMEOUT", 10), 30)

        with mock.patch.dict(os.environ, {"DJANGO_EMAIL_USE_TLS": "false"}, clear=True):
            self.assertFalse(_booleano_desde_entorno("DJANGO_EMAIL_USE_TLS", True))


class RecuperarContrasenaTests(PruebaConRegistroAbierto):
    """
    Unidad 008 — R2 (R-22), R3 y R4: recuperar la contraseña por correo, sin enseñar nunca la
    anterior, sin revelar si un correo existe, y con un enlace que caduca y se gasta.
    """

    NUEVA_CLAVE = "una-clave-nueva-de-verdad-2026"

    def test_pedir_recuperacion_y_usarla_deja_entrar_con_la_nueva(self):
        """R2: el camino feliz completo, de punta a punta."""
        self.registrar_y_verificar("alejandro@example.com")
        self.client.logout()

        respuesta = self.client.post(
            "/cuentas/password/reset/",
            {"email": "alejandro@example.com"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Revisa tu correo")

        enlace = _ultimo_enlace_de_recuperacion(para_correo="alejandro@example.com")
        respuesta_formulario = self.client.get(enlace, follow=True)
        self.assertNotContains(respuesta_formulario, "ya no vale")

        respuesta_cambio = self.client.post(
            respuesta_formulario.wsgi_request.path,
            {"password1": self.NUEVA_CLAVE, "password2": self.NUEVA_CLAVE},
            follow=True,
        )
        self.assertEqual(respuesta_cambio.status_code, 200)

        # Entra con la NUEVA, nunca vio la anterior en ningún sitio.
        self.client.logout()
        entrada = self.client.post(
            "/cuentas/login/",
            {"login": "alejandro@example.com", "password": self.NUEVA_CLAVE},
        )
        self.assertTrue(entrada.wsgi_request.user.is_authenticated)

    def test_la_contrasena_vieja_deja_de_servir(self):
        """R2, la otra mitad: "sin enseñarle nunca la anterior" implica que deja de valer."""
        self.registrar_y_verificar("alejandro@example.com", password=CLAVE_VALIDA)
        self.client.logout()

        self.client.post("/cuentas/password/reset/", {"email": "alejandro@example.com"})
        enlace = _ultimo_enlace_de_recuperacion(para_correo="alejandro@example.com")
        # `follow=True`: la primera visita al enlace REDIRIGE (allauth mueve el token de la
        # URL a la sesión, para no dejarlo en la cabecera Referer) a la URL de verdad del
        # formulario — hay que POSTear ahí, no a la URL original del correo.
        respuesta_formulario = self.client.get(enlace, follow=True)
        self.client.post(
            respuesta_formulario.wsgi_request.path,
            {"password1": self.NUEVA_CLAVE, "password2": self.NUEVA_CLAVE},
        )

        respuesta = self.client.post(
            "/cuentas/login/",
            {"login": "alejandro@example.com", "password": CLAVE_VALIDA},
        )
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_la_contrasena_nunca_se_manda_ni_se_ensena_en_ningun_sitio(self):
        """
        R2 en negativo: en ninguna de las respuestas del camino de recuperación aparece la
        contraseña ANTERIOR en claro — ni en el correo, ni en ninguna pantalla.
        """
        clave_vieja = "la-vieja-clave-de-verdad-2026"
        self.registrar_y_verificar("alejandro@example.com", password=clave_vieja)
        self.client.logout()

        respuesta = self.client.post(
            "/cuentas/password/reset/",
            {"email": "alejandro@example.com"},
            follow=True,
        )
        self.assertNotContains(respuesta, clave_vieja)

        mensaje = mail.outbox[-1]
        self.assertNotIn(clave_vieja, mensaje.body)
        self.assertNotIn(clave_vieja, mensaje.subject)

    def test_correo_que_no_existe_da_la_misma_respuesta_que_uno_que_si_existe(self):
        """
        R3, el caso límite: pedir el enlace para un correo SIN cuenta no puede decir "ese
        correo no existe" — la respuesta (status, redirección, contenido) tiene que ser
        IDÉNTICA a la de un correo que sí tiene cuenta. Solo el contenido del correo —que
        nadie fuera de esa bandeja puede ver— es distinto, y eso no lo mide un test contra la
        respuesta HTTP.
        """
        self.registrar_y_verificar("existe@example.com")
        self.client.logout()

        respuesta_existe = self.client.post(
            "/cuentas/password/reset/",
            {"email": "existe@example.com"},
            follow=True,
        )
        respuesta_no_existe = self.client.post(
            "/cuentas/password/reset/",
            {"email": "nunca-registrado@example.com"},
            follow=True,
        )

        self.assertEqual(respuesta_existe.status_code, respuesta_no_existe.status_code)
        self.assertEqual(
            [url for url, _ in respuesta_existe.redirect_chain],
            [url for url, _ in respuesta_no_existe.redirect_chain],
        )
        self.assertEqual(
            respuesta_existe.content.decode(), respuesta_no_existe.content.decode()
        )
        # Y no queda ninguna cuenta fantasma: pedir la recuperación no crea nada.
        self.assertFalse(
            Usuario.objects.filter(email="nunca-registrado@example.com").exists()
        )

    def test_correo_que_no_existe_no_da_un_error_de_formulario(self):
        """
        Control del test de arriba, más explícito: sin `FormularioRecuperarContrasena` (ver
        cuentas/forms_recuperacion.py), `ResetPasswordForm.clean_email()` de allauth mira
        `ACCOUNT_PREVENT_ENUMERATION` —que este proyecto tiene en `False` A PROPÓSITO para
        R2— y el formulario queda INVÁLIDO para un correo desconocido: la petición NO
        redirige, se queda en la pantalla con un error "unknown_email". Este test se enteraría
        de que alguien quitó el arreglo.
        """
        respuesta = self.client.post(
            "/cuentas/password/reset/",
            {"email": "nunca-registrado@example.com"},
            follow=True,
        )
        self.assertTrue(
            respuesta.redirect_chain,
            "un correo desconocido NO debe dejar a la persona en el formulario con un error",
        )

    def test_el_enlace_caducado_no_deja_cambiar_la_contrasena(self):
        """R4, primer caso: un enlace caducado."""
        self.registrar_y_verificar("alejandro@example.com")
        self.client.logout()
        self.client.post("/cuentas/password/reset/", {"email": "alejandro@example.com"})
        enlace = _ultimo_enlace_de_recuperacion(para_correo="alejandro@example.com")

        # `PASSWORD_RESET_TIMEOUT=-1`: cualquier token, por reciente que sea, queda fuera del
        # plazo permitido (Django compara "segundos transcurridos > PASSWORD_RESET_TIMEOUT").
        # No hace falta esperar de verdad ni mockear el reloj: es la MISMA comprobación que
        # usaría un enlace de hace días, solo que forzada a fallar ya. Las DOS peticiones (la
        # que sigue el enlace y la que intenta mandar la contraseña nueva) van DENTRO del
        # mismo `override_settings`, para que las dos vean el token igual de caducado — si la
        # segunda se hiciera ya fuera del bloque, el mismo enlace volvería a parecer válido
        # bajo el plazo normal y el test dejaría de probar lo que dice probar.
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            respuesta = self.client.get(enlace, follow=True)
            self.assertContains(respuesta, "ya no vale")

            respuesta_cambio = self.client.post(
                respuesta.wsgi_request.path,
                {"password1": self.NUEVA_CLAVE, "password2": self.NUEVA_CLAVE},
                follow=True,
            )
            self.assertContains(respuesta_cambio, "ya no vale")

        # Sigue sin dejar cambiarla: la persona no entra con la clave nueva.
        self.client.logout()
        entrada = self.client.post(
            "/cuentas/login/",
            {"login": "alejandro@example.com", "password": self.NUEVA_CLAVE},
        )
        self.assertFalse(entrada.wsgi_request.user.is_authenticated)

    def test_el_enlace_ya_usado_no_vuelve_a_dar_acceso(self):
        """R4, segundo caso: "caducado O YA USADO" — un enlace que ya sirvió una vez no sirve
        una segunda."""
        self.registrar_y_verificar("alejandro@example.com")
        self.client.logout()
        self.client.post("/cuentas/password/reset/", {"email": "alejandro@example.com"})
        enlace = _ultimo_enlace_de_recuperacion(para_correo="alejandro@example.com")

        primera_vez = self.client.get(enlace, follow=True)
        self.client.post(
            primera_vez.wsgi_request.path,
            {"password1": self.NUEVA_CLAVE, "password2": self.NUEVA_CLAVE},
        )

        # El MISMO enlace, otra vez: cambiar la contraseña cambia el hash que el token firma
        # (allauth/Django lo hacen así a propósito, ver EmailAwarePasswordResetTokenGenerator),
        # así que el enlace usado deja de resolver, igual que uno caducado.
        segunda_vez = self.client.get(enlace, follow=True)
        self.assertContains(segunda_vez, "ya no vale")

    def test_pedir_recuperacion_no_manda_ni_un_correo_de_verdad(self):
        """R8: control de que este flujo, como todos, usa el backend de memoria en tests."""
        self.registrar_y_verificar("alejandro@example.com")
        num_correos_antes = len(mail.outbox)

        self.client.post("/cuentas/password/reset/", {"email": "alejandro@example.com"})

        self.assertGreater(len(mail.outbox), num_correos_antes)
        # `mail.outbox` SOLO existe con el backend de memoria (locmem) — si algo cambiara el
        # backend a uno real dentro de los tests, esta lista ni se llenaría así.
        from django.conf import settings

        self.assertIn("locmem", settings.EMAIL_BACKEND)


class RutasFueraDeAlcanceTests(PruebaConRegistroAbierto):
    """
    H3 de la revisión (2ª ronda, unidad 003): `include("allauth.urls")` montaba de más — la
    recuperación de contraseña (R-22) y la gestión de direcciones de correo (`account_email`,
    la misma superficie que H1), ninguna de las dos especificada ni probada en la unidad 003.
    "Fuera de alcance" significa que ese comportamiento no se entrega: estas rutas tenían que
    devolver 404, para que si alguien las montaba sin querer, un test se enterase.

    La unidad 008 saca a `account_reset_password` (y las que encadena) de esa lista A
    PROPÓSITO: ver `RecuperarContrasenaTests` más abajo, donde esas mismas rutas ahora sí
    tienen especificación y tests — dejar aquí un 404 sería contradecir el propio contrato de
    esta unidad, no protegerlo. `account_email` (la gestión de direcciones: añadir, cambiar,
    quitar) SIGUE fuera de alcance — la unidad 008 es explícita en que no la toca — así que
    ese 404 se queda.
    """

    def test_gestion_de_direcciones_de_correo_no_esta_montado(self):
        self.registrar_y_verificar("alejandro@example.com")
        respuesta = self.client.get("/cuentas/email/")
        self.assertEqual(respuesta.status_code, 404)

    def test_las_siete_rutas_explicitas_renderizan_de_verdad(self):
        """
        Control corregido en la 3ª revisión (H4): la versión anterior solo comprobaba que
        estas rutas EXISTÍAN (`status_code != 404`), y así se coló un `500` real —
        `/cuentas/password/change/` "existía" (302 sin sesión, que es lo único que este test
        miraba), pero en cuanto alguien CON sesión la abría de verdad, su plantilla de fábrica
        reventaba con `NoReverseMatch`: enlazaba a `account_reset_password`, la ruta que H3
        quitó a propósito. Que una URL resuelva no significa que su plantilla renderice.

        Renombrado en la unidad 009 (R6): decía "seis" pero `kcalibra/urls.py` monta DIEZ
        rutas de `allauth`. De las diez, SIETE se ejercitan aquí una a una (con sesión si la
        necesitan, con una clave si la necesitan), comprobando el CONTENIDO de lo que
        devuelven, no solo que no sea 404. Las otras tres —`account_reset_password_done`,
        `account_reset_password_from_key` y `account_reset_password_from_key_done`— YA se
        pintan de refilón en `RecuperarContrasenaTests` (los `follow=True` del camino feliz
        las atraviesan de verdad): repetirlas aquí sería duplicar cobertura, no añadirla. La
        única que se quedó huérfana —ninguna prueba la dibujaba, solo la usaban como destino
        de un POST— era `password_reset.html`, la pantalla de "¿Has olvidado tu contraseña?":
        esa es la que se añade abajo.
        """
        # signup y login: SIN sesión, GET, 200 con su formulario pintado. (Con sesión,
        # `RedirectAuthenticatedUserMixin` de allauth las salta — por eso van ANTES de
        # autenticar más abajo, no da igual el orden.)
        self.assertContains(self.client.get("/cuentas/signup/"), "Crea tu cuenta")
        self.assertContains(self.client.get("/cuentas/login/"), "Entrar en KCalibra")

        # inactive: página informativa de allauth (plantilla de fábrica, pero sin ningún
        # {% url %} sin blindar — a diferencia de la de password_change, esta no reventaba).
        self.assertEqual(self.client.get("/cuentas/inactive/").status_code, 200)

        # logout: allauth solo RENDERIZA la confirmación si hay sesión que cerrar (sin ella,
        # `LogoutView.get()` redirige sin más, R28 nunca llega a pintar la plantilla) — por
        # eso esta comprobación va DESPUÉS de autenticar, no antes.
        self.registrar_y_verificar("con-sesion@example.com")
        self.assertContains(self.client.get("/cuentas/logout/"), "Salir de KCalibra")

        # password/change/: la que reventaba. Hacía falta sesión para toparse con el 500 (por
        # eso se coló: nadie la pedía ya autenticado en la ronda anterior). Un GET no cierra
        # la sesión (solo el POST del formulario de logout de arriba lo haría), así que sigue
        # autenticada aquí.
        respuesta_cambiar = self.client.get("/cuentas/password/change/")
        self.assertEqual(respuesta_cambiar.status_code, 200)
        self.assertContains(respuesta_cambiar, "Cambiar tu contraseña")
        # Y, a propósito, SIN el enlace roto que traía la plantilla de fábrica.
        self.assertNotContains(respuesta_cambiar, "Forgot Password")

        # confirm-email/<key>/: con un enlace inválido, SÍ renderiza su plantilla (con uno
        # válido, redirige — eso ya lo cubre de sobra VerificacionDeCorreoTests).
        respuesta_confirmar = self.client.get("/cuentas/confirm-email/una-clave-inventada/")
        self.assertEqual(respuesta_confirmar.status_code, 200)
        self.assertContains(respuesta_confirmar, "ya no vale")

        # password/reset/: la ruta huérfana (R6, unidad 009) — "la primera pantalla que ve
        # alguien que NO puede entrar", así que se pide SIN sesión de verdad: la de arriba
        # (`registrar_y_verificar` en la comprobación de logout) sigue abierta en el cliente de
        # pruebas, así que hay que cerrarla aquí antes del GET. Un GET, 200 con su propio
        # formulario pintado — hasta ahora ningún test la pedía así: los once tests de
        # `RecuperarContrasenaTests` solo hacen POST contra ella, así que `password_reset.html`
        # nunca se había renderizado de verdad en la suite.
        self.client.logout()
        respuesta_reset = self.client.get("/cuentas/password/reset/")
        self.assertEqual(respuesta_reset.status_code, 200)
        self.assertContains(respuesta_reset, "¿Has olvidado tu contraseña?")
