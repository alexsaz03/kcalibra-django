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


def evaluar(mensajes, esperados=ESPERADOS, genuinos=None):
    """Función pura (R1-R7, R9): ni toca Django configurado, ni hace I/O. El número total de
    mensajes NO interviene en la decisión (R4, R5): cada mensaje se juzga por su propio `id` y
    `level`, nunca por el recuento ni por el contenido de su `msg`.

    `genuinos` (R9, la sexta puerta): mapa OPCIONAL `id -> objeto SINGLETON genuino`, con
    valor por defecto `None` — exactamente igual que `esperados` es un parámetro con su propio
    valor por defecto, para que los tests puedan seguir inyectando el suyo sin tocar Django. Sin
    él (el caso de todos los tests de R1-R8 y H1, que no lo pasan), el comportamiento es
    idéntico al de antes de esta vuelta: un mensaje se acepta por `id` y `level` solos. Con él
    (el caso de `comprobar()`, que inyecta los singletons reales de Django), un mensaje cuyo
    `id` tiene entrada en el mapa además debe SER, por identidad (`is`), ese objeto — si no lo
    es, es un impostor que reutiliza el id de un tolerado, aunque su `id` y su `level` sean
    indistinguibles del genuino."""
    genuinos = genuinos or {}
    intrusos = []
    vistos = set()
    for mensaje in mensajes:
        if mensaje.level < WARNING:
            continue
        # `mensaje.id in vistos`: el id es una IDENTIDAD, no una etiqueta reutilizable. Sin
        # esta condición, un segundo mensaje —de otro problema real— que reutilice el id de
        # un esperado ya visto casaba igual que el primero (H1, segunda vuelta de la 045):
        # el guion viejo, que cuadraba el RECUENTO total contra los esperados vistos, sí lo
        # cazaba; comparar solo por conjunto de ids sin marcar "ya consumido" no.
        #
        # `es_impostor` (R9, tercera vuelta): un id y un nivel iguales no bastan si el hueco de
        # un tolerado que se arregló de verdad lo ocupa OTRO problema, de otra causa, que
        # reutiliza justo ese id — el guion viejo (68895d2) y la versión de H1 pasan este caso
        # en verde por igual (medido por el revisor: 75/33649 divergencias laxas, todas esta
        # forma). El id y el level de los cuatro tolerados son indistinguibles del impostor por
        # construcción; solo la identidad del OBJETO los separa, porque Django devuelve siempre
        # el mismo singleton de módulo para cada uno (`security/base.py`, `csrf.py`,
        # `sessions.py`) y nunca fabrica una copia.
        es_impostor = mensaje.id in genuinos and mensaje is not genuinos[mensaje.id]
        if (
            mensaje.level > WARNING
            or mensaje.id not in esperados
            or mensaje.id in vistos
            or es_impostor
        ):
            intrusos.append(mensaje)
        else:
            vistos.add(mensaje.id)
    faltantes = sorted(esperados - vistos)
    return Veredicto(intrusos, faltantes)


def _genuinos_de_django():
    """El mapa `id -> objeto SINGLETON real de Django` para los cuatro esperados (R9): la
    identidad que separa un aviso genuino de un impostor que reutiliza su id. Comprobado, no
    supuesto: Django declara cada uno de los cuatro como una única instancia a nivel de MÓDULO
    (`django/core/checks/security/base.py` para W004 y W008, `.../sessions.py` para W012,
    `.../csrf.py` para W016) y los checks correspondientes devuelven siempre esa misma
    instancia, nunca una copia — verificado contra `run_checks()` real (`mensaje is
    django.core.checks.security.base.W004`, etc., las cuatro `True`)."""
    from django.core.checks.security import base, csrf, sessions

    return {
        "security.W004": base.W004,
        "security.W008": base.W008,
        "security.W012": sessions.W012,
        "security.W016": csrf.W016,
    }


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
    — inyecta los objetos SINGLETON genuinos de Django (R9, `_genuinos_de_django()`) para que
    un impostor que reutilice el id de un tolerado no pase por identidad, imprime el veredicto
    legible y devuelve el código de salida. Un check que revienta al ejecutarse **o que se mata
    con `sys.exit()`** nunca se da por bueno: se imprime la traza completa y se sale en rojo
    (bug 047 — `except Exception` no atrapaba la `SystemExit`, y el guion salía en verde)."""
    from django.core.checks import run_checks

    try:
        mensajes = run_checks(include_deployment_checks=True)
    except BaseException:
        # `BaseException` y no `Exception`, a propósito (bug 047, la SÉPTIMA puerta). Un check
        # no solo puede REVENTAR: puede MATARSE. `sys.exit()` levanta `SystemExit`, que cuelga
        # directamente de `BaseException` y NO de `Exception` -- es el mecanismo con el que
        # Python deja que una salida deliberada atraviese los `except` genéricos de en medio.
        # Aquí ese mecanismo jugaba en contra: la `SystemExit` se escapaba de esta función,
        # `sys.exit(comprobar())` no llegaba a ejecutarse jamás y el proceso moría con el
        # código que traía puesto -- 0 ante un `sys.exit(0)`, o sea VERDE, con la configuración
        # de despliegue SIN comprobar y sin imprimir una sola línea. Medido antes del arreglo:
        # el guion completo con un check que hace `sys.exit(0)` salía en código 0 y mudo.
        # `KeyboardInterrupt` entra por la misma puerta y con la misma razón: un Ctrl-C a mitad
        # tampoco es un veredicto. El proceso termina igual, pero termina diciendo la verdad.
        print("ROJO: al menos un check reventó o se mató al ejecutarse:")
        traceback.print_exc()
        return 1

    visibles = [mensaje for mensaje in mensajes if not mensaje.is_silenced()]
    veredicto = evaluar(visibles, genuinos=_genuinos_de_django())
    print(_texto_legible(veredicto))
    return 0 if veredicto.ok else 1


if __name__ == "__main__":
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kcalibra.settings")
    import django

    django.setup()
    sys.exit(comprobar())
