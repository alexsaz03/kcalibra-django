"""
El formulario de "he olvidado mi contraseña" (R2/R-22, R3), en un fichero SEPARADO de
`cuentas/forms.py` a propósito.

¿Por qué no fue a parar a `cuentas/forms.py`, con `FormularioAlta`? Porque `cuentas.forms` se
importa MUY pronto: `ACCOUNT_SIGNUP_FORM_CLASS = "cuentas.forms.FormularioAlta"` hace que
`allauth.account.forms` importe ese módulo DESDE DENTRO de su propia carga (en
`base_signup_form_class()`, llamada al definir `class BaseSignupForm(...)`, antes de que ese
mismo fichero de allauth llegue a definir `ResetPasswordForm`, más abajo). Si
`cuentas/forms.py` importara en su cabecera algo de `allauth.account.forms` (como
`ResetPasswordForm`), ese `import` caería en mitad de la carga de allauth y reventaría con
"cannot import name 'ResetPasswordForm' from partially initialized module" — la misma trampa
nº 3 que ya documentó la unidad 003 para `SignupForm`, solo que aplicada a OTRO nombre del
mismo fichero.

Este módulo, en cambio, nadie lo importa de forma temprana: `ACCOUNT_FORMS` (ver settings.py)
guarda su ruta como TEXTO, y allauth solo la resuelve (`import_attribute`) cuando de verdad
hace falta — al construir la vista de "recuperar contraseña", con `allauth.account.forms` ya
totalmente cargado. Para entonces, importar `ResetPasswordForm` de allí es seguro.
"""

from allauth.account.adapter import get_adapter
from allauth.account.forms import ResetPasswordForm
from allauth.account.utils import filter_users_by_email


class FormularioRecuperarContrasena(ResetPasswordForm):
    """
    R3 (R-22, caso límite): pedir el enlace de recuperación para un correo que NO existe en la
    app no puede revelar que no existe — la respuesta tiene que ser la MISMA que para un
    correo que sí tiene cuenta.

    El formulario de fábrica de allauth, `ResetPasswordForm.clean_email()`, decide esto
    mirando `ACCOUNT_PREVENT_ENUMERATION`:

        if not self.users and not app_settings.PREVENT_ENUMERATION:
            raise get_adapter().validation_error("unknown_email")

    Esa palanca es GLOBAL, y este proyecto la tiene en `False` A PROPÓSITO desde la unidad
    003, para el flujo CONTRARIO: R2 pide avisar explícitamente "ese correo ya tiene cuenta"
    al REGISTRARSE. Con `ACCOUNT_PREVENT_ENUMERATION = False` sin más, este mismo formulario
    heredaría ese comportamiento y reventaría el R3 de esta unidad: un formulario inválido (se
    queda en la pantalla con un error) revela justo lo que R3 prohíbe revelar.

    No se puede usar el mismo ajuste global para las dos cosas sin romper una de las dos. La
    solución es la misma que ya usa `ACCOUNT_SIGNUP_FORM_CLASS` para el alta: un punto de
    extensión propio de allauth (`ACCOUNT_FORMS = {"reset_password": ...}`, ver settings.py)
    que sustituye SOLO este formulario, sin tocar la palanca global.

    Quitar la comprobación no dice "vale, cualquier cosa": si el correo no tiene ninguna
    cuenta, `self.users` queda vacío, y es la propia `request_password_reset()` de allauth
    (`internal/flows/password_reset.py`) la que ya está preparada para ese caso — manda un
    correo distinto ("no hay cuenta con este correo, ¿quieres registrarte?", si
    `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS` lo permite) y de todas formas acaba en la MISMA pantalla
    de "hemos mandado un correo" que si la cuenta sí existiera. La respuesta HTTP nunca
    distingue los dos casos; solo el CONTENIDO del correo (que nadie fuera de esa bandeja
    puede ver) es distinto.
    """

    def clean_email(self):
        correo = self.cleaned_data["email"].lower()
        correo = get_adapter().clean_email(correo)
        self.users = filter_users_by_email(correo, is_active=True, prefer_verified=True)
        return self.cleaned_data["email"]
