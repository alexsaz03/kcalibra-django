r"""
El guardián de la unidad 045: deja de leer la PROSA que `manage.py check --deploy` imprime
para humanos y le pregunta al registro de checks de Django por sus OBJETOS
(`django.core.checks.messages.CheckMessage`, cada uno con su `.id` y su `.level` reales).

Cuatro formas distintas de que la versión anterior (basada en `re.search` sobre el texto)
dijera verde con Django diciendo rojo, cada una destapada al tapar la anterior (ver
`especificacion.md` de esta unidad): mirar solo los códigos entre paréntesis y restar los
cuatro esperados (039); un aviso sin `id=` se imprime sin paréntesis y el filtro no ve nada que
restar (043); un aviso cuyo TEXTO imita el pie de página cuela un recuento falso porque
`re.search` coge la primera coincidencia (043, puerta 3); y un aviso ajeno que ocupa el hueco
de un esperado ya arreglado hace cuadrar la resta igual (043, puerta 4). Comparar objetos en
vez de prosa cierra la familia entera de una vez: el `id` y el `level` no dependen de cómo se
haya escrito el texto del mensaje, y un mensaje sin `id` es, sin más, un intruso sin nombre.

Dos piezas separadas a propósito:

- `evaluar()` — función PURA. Recibe una lista de `CheckMessage` y el conjunto de ids
  esperados, y devuelve un `Veredicto` con sus dos listas (intrusos y esperados que ya no
  aparecen). Sin Django configurado, sin entrada/salida: es lo que hace testeable R1-R7 con
  mensajes fabricados a mano.
- `comprobar()` — el envoltorio. Llama a `django.core.checks.run_checks(
  include_deployment_checks=True)`, descarta lo que el comando `check` descartaría por su
  cuenta (`CheckMessage.is_silenced()`, que mira `settings.SILENCED_SYSTEM_CHECKS`) y lo que
  quede por debajo de `WARNING`, imprime el veredicto en texto legible y devuelve 0 o 1.

**La diferencia que hay que reproducir a propósito:** el comando `check` filtra por su cuenta
`SILENCED_SYSTEM_CHECKS` y por `--fail-level`; la API `run_checks()` NO — devuelve TODOS los
mensajes, silenciados o no, de cualquier nivel. Si nadie reprodujera ese filtrado, el guion
pasaría a ser más estricto que Django sin que nadie lo hubiera pedido (un
`SILENCED_SYSTEM_CHECKS` dejaría de servir para nada, y un `DEBUG`/`INFO` informativo tumbaría
el CI). El filtrado se reparte entre las dos piezas, cada una responsable de lo suyo:
`comprobar()` filtra silenciados (`CheckMessage.is_silenced()`) ANTES de llamar a `evaluar()`;
el corte por nivel (R7) vive por completo dentro de `evaluar()`, no en `comprobar()`, así que
`evaluar()` sigue siendo correcta si se la llama directamente con una lista que no ha pasado
por ningún filtro.
"""

import sys
import traceback

from django.core.checks import WARNING

# Los cuatro avisos de HTTPS que hoy no se pueden cumplir: los aporta el servidor del
# despliegue (el proxy con TLS de verdad), que aún no existe. Heredado de scripts/ci/security
# (unidades 039/043). Cualquier otro aviso, o uno de estos subido a ERROR/CRITICAL, hace
# fallar el guion entero — no se silencia nada.
ESPERADOS = frozenset(
    {
        "security.W004",  # SECURE_HSTS_SECONDS sin valor
        "security.W008",  # SECURE_SSL_REDIRECT no está a True
        "security.W012",  # SESSION_COOKIE_SECURE no está a True
        "security.W016",  # CSRF_COOKIE_SECURE no está a True
    }
)


class Veredicto:
    """El resultado de comparar lo que Django ve contra lo que se tolera. `intrusos` son
    mensajes (`CheckMessage`) que no deberían estar: por id ajeno, por id ausente (R3, se
    imprime como `<sin id>`) o por nivel demasiado grave para un esperado (R7). `faltantes`
    son ids de `ESPERADOS` que ya no aparece ningún mensaje suyo (R6): una tolerancia caducada
    que nadie relee acaba tapando algo real."""

    def __init__(self, intrusos, faltantes):
        self.intrusos = intrusos
        self.faltantes = faltantes

    @property
    def ok(self):
        return not self.intrusos and not self.faltantes


def evaluar(mensajes, esperados=ESPERADOS):
    """Función pura (R1-R7): ni toca Django configurado, ni hace I/O. El número total de
    mensajes NO interviene en la decisión (R4, R5): cada mensaje se juzga por su propio `id` y
    `level`, nunca por el recuento ni por el contenido de su `msg`."""
    intrusos = []
    vistos = set()
    for mensaje in mensajes:
        if mensaje.level < WARNING:
            continue
        if mensaje.level > WARNING or mensaje.id not in esperados or mensaje.id in vistos:
            # `mensaje.id in vistos`: el id es una IDENTIDAD, no una etiqueta reutilizable. Sin
            # esta condición, un segundo mensaje —de otro problema real— que reutilice el id de
            # un esperado ya visto casaba igual que el primero (H1, segunda vuelta de la 045):
            # el guion viejo, que cuadraba el RECUENTO total contra los esperados vistos, sí lo
            # cazaba; comparar solo por conjunto de ids sin marcar "ya consumido" no.
            intrusos.append(mensaje)
        else:
            vistos.add(mensaje.id)
    faltantes = sorted(esperados - vistos)
    return Veredicto(intrusos, faltantes)


def _nombre_intruso(mensaje):
    return mensaje.id if mensaje.id else "<sin id>"


def _texto_legible(veredicto):
    if veredicto.ok:
        return "OK: los avisos de despliegue son exactamente los tolerados."
    lineas = ["ROJO: la configuración de despliegue no coincide con lo tolerado."]
    for mensaje in veredicto.intrusos:
        lineas.append(f"  - intruso: {_nombre_intruso(mensaje)} (nivel {mensaje.level}): {mensaje.msg}")
    for id_esperado in veredicto.faltantes:
        lineas.append(
            f"  - esperado que ya no aparece: {id_esperado} (¿se arregló? quítalo de ESPERADOS "
            "en kcalibra/avisos_de_despliegue.py)"
        )
    return "\n".join(lineas)


def comprobar():
    """El envoltorio (R8 incluido): llama a la API real de Django, reproduce a mano el
    filtrado de silenciados que el comando `check` hace por su cuenta
    (`CheckMessage.is_silenced()`) — el corte por nivel lo aplica `evaluar()`, no esta función
    — imprime el veredicto legible y devuelve el código de salida. Un check que revienta al
    ejecutarse nunca se da por bueno: se imprime la traza completa y se sale en rojo."""
    from django.core.checks import run_checks

    try:
        mensajes = run_checks(include_deployment_checks=True)
    except Exception:
        print("ROJO: al menos un check reventó al ejecutarse:")
        traceback.print_exc()
        return 1

    visibles = [mensaje for mensaje in mensajes if not mensaje.is_silenced()]
    veredicto = evaluar(visibles)
    print(_texto_legible(veredicto))
    return 0 if veredicto.ok else 1


if __name__ == "__main__":
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kcalibra.settings")
    import django

    django.setup()
    sys.exit(comprobar())
