"""
Unidad 049 — la red que mira el HTML de `allauth`, no el formulario en abstracto.

Contexto (medido antes de escribir un solo test, con `django-allauth` 65.19.1): la 046 cazó
una versión MENOR de la librería metiendo un enlace de "recuperar contraseña" en el `help_text`
de `ChangePasswordForm.oldpassword`, y los 767 tests de entonces salieron VERDES con la
regresión puesta — ninguno miraba el HTML que de verdad llega al navegador. Lo cazó un
constructor leyendo el registro de cambios, y eso no escala.

Este fichero entra SIEMPRE por la puerta real (`self.client.get/post`), nunca instanciando un
formulario a mano: lo que se protege es lo que pinta la plantilla, no lo que devuelve una
clase de Python — un `{% for field in form.visible_fields %}` genérico protege de que
CAMBIEN los campos que hay, no de que la librería cambie algo DENTRO de un campo que ya
existía (etiqueta, help_text), que es justo por donde entró la regresión de la 046.

R1 — veredicto por ruta, medido renderizando cada una (no leyendo), con `django-allauth
65.19.1`. `kcalibra/urls.py` monta DIEZ rutas de la librería:

| ruta (`name=`)                          | plantilla                              | ¿expuesta? | motivo medido |
|------------------------------------------|-----------------------------------------|:---:|---|
| `account_login`                          | `login.html` (propia)                   | SÍ  | `LoginForm` decide `login`/`password`, con `help_text` en `password` (`show_reset_help`) |
| `account_signup`                         | `signup.html` (propia)                  | SÍ  | `allauth` construye `email`/`password1`/`password2` (`ACCOUNT_SIGNUP_FIELDS`) antes de mezclarlos con `FormularioAlta`; esos tres siguen siendo de la librería |
| `account_change_password`                | `password_change.html` (propia)         | SÍ  | `ChangePasswordForm` decide `oldpassword`/`password1`/`password2`; `oldpassword` trae `help_text` (`show_reset_help`) — la regresión exacta de la 046 |
| `account_reset_password`                 | `password_reset.html` (propia)          | SÍ  | `ResetPasswordForm` decide `email` |
| `account_reset_password_from_key`        | `password_reset_from_key.html` (propia) | SÍ  | `ResetPasswordKeyForm` decide `password1`/`password2` |
| `account_logout`                         | `logout.html` (propia)                  | NO  | Sin ningún campo de formulario: solo un botón y el CSRF. No hay nada que la librería pueda cambiarle por dentro |
| `account_inactive`                       | *(sin plantilla propia)*                | NO  | HTML de fábrica de `allauth` al 100 % (medido: `templates/account/` no trae `inactive.html`). No hay markup nuestro que proteger; si la librería cambia esa plantilla, es su propia responsabilidad, no la nuestra |
| `account_confirm_email`                  | `email_confirm.html` (propia)           | NO  | Sin formulario ni campos: solo un mensaje fijo (medido: `templates/account/email_confirm.html` no itera ningún `form.visible_fields`) |
| `account_reset_password_done`            | `password_reset_done.html` (propia)     | NO  | Página estática, sin formulario |
| `account_reset_password_from_key_done`   | `password_reset_from_key_done.html` (propia) | NO | Página estática, sin formulario |

Las cinco EXPUESTAS son exactamente las que "Diseño conversado" de la especificación mide como
las que pintan campos en bucle genérico. R2 pone red sobre las tres cosas que decide la
librería en cada una de esas cinco: qué campos, con qué etiqueta, y si su `help_text` sale o
no. R4 (el `aria-describedby` huérfano) se prueba aparte, sobre las dos pantallas donde vivía
el resto invisible que dejó la 046: `login` y `password_change`.
"""

import re

from django.test import TestCase
from django.urls import get_resolver, reverse

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto

# El veredicto de R1, en una sola estructura: nombre de ruta -> (¿expuesta?, motivo medido).
# Es la fuente de verdad que el test de abajo contrasta contra las rutas que existen DE
# VERDAD en `kcalibra/urls.py` — si alguien monta una ruta once, este fichero se entera solo.
VEREDICTOS_POR_RUTA = {
    "account_login": (True, "LoginForm decide login/password, con help_text en password"),
    "account_signup": (True, "allauth construye email/password1/password2 antes de mezclarlos con FormularioAlta"),
    "account_change_password": (True, "ChangePasswordForm decide oldpassword/password1/password2"),
    "account_reset_password": (True, "ResetPasswordForm decide email"),
    "account_reset_password_from_key": (True, "ResetPasswordKeyForm decide password1/password2"),
    "account_logout": (False, "sin ningún campo de formulario, solo un botón y el CSRF"),
    "account_inactive": (False, "HTML de fábrica de allauth al 100%: no hay plantilla propia ni markup nuestro"),
    "account_confirm_email": (False, "sin formulario: solo un mensaje fijo, no itera form.visible_fields"),
    "account_reset_password_done": (False, "página estática, sin formulario"),
    "account_reset_password_from_key_done": (False, "página estática, sin formulario"),
}


def _bloque_de_campo(html, field_id):
    """
    Recorta el `<div>` que envuelve un campo concreto (por su `id_for_label`), para que los
    asserts de etiqueta/ayuda miren SOLO ese campo y no la página entera (24ª/12ª cara de
    tests-que-no-fallan-cuando-deben.md: un assert sobre todo el HTML puede colar por el
    sitio equivocado). Las cinco plantillas expuestas envuelven cada campo en un único nivel
    de `<div>` sin anidar otro dentro, así que cortar hasta el primer `</div>` tras la
    etiqueta es exacto, no una aproximación.
    """
    patron = r'<div>\s*<label for="' + re.escape(field_id) + r'"[^>]*>.*?</div>'
    coincidencia = re.search(patron, html, re.DOTALL)
    assert coincidencia, f"no se encontró el bloque del campo {field_id!r} en el HTML"
    return coincidencia.group(0)


def _campos_del_formulario(html, accion_url):
    """Todos los `name=` dentro del `<form action="accion_url">`, salvo el CSRF — para fijar
    QUÉ campos pinta la pantalla, no solo cómo se ve uno en concreto."""
    patron = r'<form method="post" action="' + re.escape(accion_url) + r'".*?</form>'
    coincidencia = re.search(patron, html, re.DOTALL)
    assert coincidencia, f"no se encontró el formulario con action={accion_url!r}"
    bloque = coincidencia.group(0)
    return set(re.findall(r'\bname="([^"]+)"', bloque)) - {"csrfmiddlewaretoken"}


def _ids_referenciados_por_aria_describedby(html):
    return set(re.findall(r'aria-describedby="([^"]+)"', html))


def _ids_presentes(html):
    return set(re.findall(r'\bid="([^"]+)"', html))


class ClasificacionDeRutasDeAllauthTests(TestCase):
    """R1: toda la superficie de allauth montada en kcalibra/urls.py tiene un veredicto
    escrito arriba, y ninguna ruta se queda sin clasificar."""

    def test_las_diez_rutas_de_allauth_estan_clasificadas(self):
        resolver = get_resolver()
        rutas_de_verdad = {
            patron.name
            for patron in resolver.url_patterns
            if getattr(patron, "name", None) and patron.name.startswith("account_")
        }
        self.assertEqual(
            rutas_de_verdad,
            set(VEREDICTOS_POR_RUTA.keys()),
            "kcalibra/urls.py monta una ruta de allauth sin veredicto (o el veredicto nombra "
            "una que ya no existe): revisa VEREDICTOS_POR_RUTA arriba.",
        )
        self.assertEqual(len(VEREDICTOS_POR_RUTA), 10)


class PantallaDeEntrarTests(PruebaConRegistroAbierto):
    """R2 sobre `account_login`: LoginForm decide login/password, y password trae help_text
    (show_reset_help) que ESTA pantalla nunca pinta — es la pantalla de quien no ha entrado
    todavía, y el enlace de "¿Has olvidado tu contraseña?" ya vive fuera del formulario."""

    def test_pinta_login_y_password_con_sus_etiquetas_y_sin_ayuda(self):
        respuesta = self.client.get("/cuentas/login/")
        html = respuesta.content.decode()

        self.assertEqual(_campos_del_formulario(html, reverse("account_login")), {"login", "password"})

        bloque_login = _bloque_de_campo(html, "id_login")
        self.assertIn("Correo electrónico", bloque_login)

        bloque_password = _bloque_de_campo(html, "id_password")
        self.assertIn("Contraseña", bloque_password)
        # El help_text de `password` (el enlace "¿Ha olvidado tu contraseña?" que allauth
        # construye vía show_reset_help) NUNCA se pinta aquí: login.html no lo renderiza en
        # ningún { % if % } — el enlace bueno vive fuera del formulario, ver más abajo.
        self.assertNotIn("<a ", bloque_password)
        self.assertNotIn("olvidado", bloque_password.lower())

    def test_el_enlace_de_recuperar_sigue_fuera_del_formulario(self):
        respuesta = self.client.get("/cuentas/login/")
        self.assertContains(respuesta, "¿Has olvidado tu contraseña?")
        self.assertContains(respuesta, reverse("account_reset_password"))

    def test_ningun_aria_describedby_apunta_a_un_id_que_no_existe(self):
        """R4: el mismo resto invisible que en password_change, aquí sobre `password` (login
        NUNCA pinta ningún help_text, así que el `id_password_helptext` que allauth referencia
        vía aria-describedby —porque el campo SÍ tiene help_text, show_reset_help— no existe
        en la página)."""
        respuesta = self.client.get("/cuentas/login/")
        html = respuesta.content.decode()
        ids_presentes = _ids_presentes(html)
        for id_referenciado in _ids_referenciados_por_aria_describedby(html):
            self.assertIn(
                id_referenciado,
                ids_presentes,
                f"aria-describedby apunta a {id_referenciado!r}, que no existe en la página",
            )


class PantallaDeCrearCuentaTests(PruebaConRegistroAbierto):
    """R2 sobre `account_signup`, acotado a los TRES campos que construye la librería antes
    de mezclarlos con `FormularioAlta` (`ACCOUNT_SIGNUP_FIELDS`): los demás campos son
    nuestros (cuentas/forms.py) y no los decide ninguna versión de allauth."""

    def test_pinta_email_y_las_dos_contrasenas_de_la_libreria(self):
        respuesta = self.client.get("/cuentas/signup/")
        html = respuesta.content.decode()
        campos = _campos_del_formulario(html, reverse("account_signup"))
        self.assertTrue({"email", "password1", "password2"} <= campos)

        bloque_email = _bloque_de_campo(html, "id_email")
        self.assertIn("Correo electrónico", bloque_email)

        bloque_password1 = _bloque_de_campo(html, "id_password1")
        self.assertIn("Contraseña", bloque_password1)
        # password1 aquí es un SetPasswordField: su help_text son los validadores de Django,
        # no show_reset_help, y SÍ se quiere pintado (es la explicación de qué contraseñas
        # valen).
        self.assertIn("8 caracteres", bloque_password1)

        bloque_password2 = _bloque_de_campo(html, "id_password2")
        self.assertIn("Contraseña (de nuevo)", bloque_password2)
        self.assertNotIn("8 caracteres", bloque_password2)


class PantallaDeCambiarContrasenaTests(PruebaConRegistroAbierto):
    """R2 y R4 sobre `account_change_password`: la pantalla exacta donde mordió la 046.
    ChangePasswordForm decide oldpassword/password1/password2; oldpassword trae help_text
    (show_reset_help) que esta pantalla, a propósito, no pinta — ya está dentro y ya sabe su
    contraseña actual."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com")

    def test_pinta_las_tres_contrasenas_con_sus_etiquetas(self):
        respuesta = self.client.get("/cuentas/password/change/")
        html = respuesta.content.decode()

        self.assertEqual(
            _campos_del_formulario(html, reverse("account_change_password")),
            {"oldpassword", "password1", "password2"},
        )

        bloque_old = _bloque_de_campo(html, "id_oldpassword")
        self.assertIn("Contraseña actual", bloque_old)

        bloque_p1 = _bloque_de_campo(html, "id_password1")
        self.assertIn("Nueva contraseña", bloque_p1)

        bloque_p2 = _bloque_de_campo(html, "id_password2")
        self.assertIn("Nueva contraseña (de nuevo)", bloque_p2)

    def test_oldpassword_no_pinta_su_texto_de_ayuda(self):
        """La mitad de R2 que R6 vuelve a comprobar por mutación (ver hallazgos.md): si
        `oldpassword` volviera a pintar su help_text, este test se pone en rojo — es
        exactamente la regresión de la 046, repuesta a mano."""
        respuesta = self.client.get("/cuentas/password/change/")
        html = respuesta.content.decode()
        bloque_old = _bloque_de_campo(html, "id_oldpassword")
        self.assertNotIn("<a ", bloque_old)
        self.assertNotIn("olvidado", bloque_old.lower())
        self.assertNotContains(respuesta, reverse("account_reset_password"))

    def test_password1_SIGUE_pintando_su_texto_de_ayuda(self):
        """R4, la trampa que nombra el propio contrato: la cura del aria-describedby huérfano
        de oldpassword NO puede llevarse por delante el help_text de password1 (los
        validadores), que es un SetPasswordField y no pasa por show_reset_help."""
        respuesta = self.client.get("/cuentas/password/change/")
        html = respuesta.content.decode()
        bloque_p1 = _bloque_de_campo(html, "id_password1")
        self.assertIn("8 caracteres", bloque_p1)

    def test_ningun_aria_describedby_apunta_a_un_id_que_no_existe(self):
        """R4: markup muerto. `oldpassword` tiene help_text (show_reset_help) aunque esta
        plantilla no lo pinte, y Django añade `aria-describedby` al widget con solo que
        `field.help_text` sea verdadero — sin mirar si la plantilla lo usa. Comprobación
        genérica sobre TODA la página, no solo sobre oldpassword: cualquier id huérfano futuro
        cae aquí igual."""
        respuesta = self.client.get("/cuentas/password/change/")
        html = respuesta.content.decode()
        ids_presentes = _ids_presentes(html)
        for id_referenciado in _ids_referenciados_por_aria_describedby(html):
            self.assertIn(
                id_referenciado,
                ids_presentes,
                f"aria-describedby apunta a {id_referenciado!r}, que no existe en la página",
            )


class PantallaDeRecuperarContrasenaTests(PruebaConRegistroAbierto):
    """R2 sobre `account_reset_password`: ResetPasswordForm decide un único campo, email."""

    def test_pinta_email_con_su_etiqueta(self):
        respuesta = self.client.get("/cuentas/password/reset/")
        html = respuesta.content.decode()
        self.assertEqual(_campos_del_formulario(html, reverse("account_reset_password")), {"email"})
        bloque_email = _bloque_de_campo(html, "id_email")
        self.assertIn("Correo electrónico", bloque_email)


class PantallaDePonerContrasenaNuevaTests(PruebaConRegistroAbierto):
    """R2 sobre `account_reset_password_from_key`: ResetPasswordKeyForm decide
    password1/password2. Medido (no supuesto): a diferencia de `signup.html` y
    `password_change.html`, `password_reset_from_key.html` NO pinta `field.help_text` para
    NINGÚN campo de su `{% for %}` — ni siquiera lo pregunta con un `{% if %}` — así que los
    validadores de `password1` no salen aquí. Es un comportamiento previo a esta unidad, fuera
    de los criterios de aceptación (R4 solo habla de *Entrar* y *Cambiar tu contraseña*): se
    deja constancia en hallazgos.md como hallazgo, no se arregla en esta unidad."""

    _RE_ENLACE_RECUPERAR = re.compile(r"(http\S+/cuentas/password/reset/key/\S+/)")

    def _enlace_de_recuperacion_valido(self, email):
        from django.core import mail

        self.registrar_y_verificar(email)
        self.client.logout()
        self.client.post("/cuentas/password/reset/", {"email": email})
        mensajes = [m for m in mail.outbox if email in m.to]
        self.assertTrue(mensajes, f"no se mandó ningún correo de recuperación a {email!r}")
        coincidencia = self._RE_ENLACE_RECUPERAR.search(mensajes[-1].body)
        self.assertIsNotNone(coincidencia, "el correo no trae un enlace de recuperación")
        return coincidencia.group(1)

    def test_pinta_las_dos_contrasenas_con_sus_etiquetas_y_sin_ayuda(self):
        enlace = self._enlace_de_recuperacion_valido("alejandro@example.com")
        # La primera visita REDIRIGE (allauth mueve el token de la URL a la sesión): hay que
        # seguirla para llegar al formulario de verdad, con token_fail=False.
        respuesta = self.client.get(enlace, follow=True)
        html = respuesta.content.decode()
        self.assertNotContains(respuesta, "ya no vale")

        self.assertEqual(
            _campos_del_formulario(html, respuesta.wsgi_request.path),
            {"password1", "password2"},
        )

        bloque_p1 = _bloque_de_campo(html, "id_password1")
        self.assertIn("Nueva contraseña", bloque_p1)
        # Medido: esta plantilla no pinta help_text de ningún campo (ver docstring de la
        # clase) — si algún día empezara a hacerlo, este assert avisa del cambio de contrato.
        self.assertNotIn("8 caracteres", bloque_p1)

        bloque_p2 = _bloque_de_campo(html, "id_password2")
        self.assertIn("Nueva contraseña (de nuevo)", bloque_p2)
