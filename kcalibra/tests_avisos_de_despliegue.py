r"""
La red que hoy no existe (unidad 045): antes de esta unidad, `scripts/ci/security` no tenía
NI UN test (guarda sin red, la 20ª cara de `docs/conocimiento/tests-que-no-fallan-cuando-deben.md`).
Un test por cada una de las cuatro maneras conocidas de engañar al guardián viejo (R2-R5),
más la lista caducada (R6), el corte por nivel (R7, con su reproducción manual de lo que el
comando `check` filtra solo) y el caso límite del check que revienta (R8). Más un test de
sistema que ejecuta `scripts/ci/security` de verdad.

Fabrica `django.core.checks.messages.CheckMessage` a mano — incluido el que se construye SIN
`id=` (R3) y el que lleva el pie de página de Django DENTRO del texto (R4) — porque
`evaluar()` es una función pura: no necesita levantar la app para juzgar un veredicto, solo
mensajes con `.id` y `.level` reales.
"""

import os
import subprocess

from django.core.checks import CRITICAL, DEBUG, ERROR, INFO, WARNING
from django.core.checks.messages import CheckMessage
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from kcalibra.avisos_de_despliegue import ESPERADOS, evaluar


def _msg(id, nivel=WARNING, texto="aviso de prueba"):
    return CheckMessage(nivel, texto, id=id)


def _genuino(id):
    """El objeto SINGLETON real de Django para uno de los cuatro esperados -- el mismo que
    `comprobar()` usa como referencia de identidad (R9, `_genuinos_de_django()`). Necesario en
    los tests que pasan por `comprobar()` (via `_comprobar_con`): desde que `comprobar()`
    inyecta el mapa de genuinos, un `_msg(id)` fabricado para uno de los ESPERADOS deja de
    contar como el aviso real y se vería (incorrectamente) como un impostor. Los tests que
    llaman a `evaluar()` a solas, sin pasar por `comprobar()`, no necesitan esto: por defecto
    `evaluar()` no exige identidad (`genuinos=None`)."""
    from kcalibra.avisos_de_despliegue import _genuinos_de_django

    return _genuinos_de_django()[id]


def _mensaje_fallo_guion(resultado, esperado):
    """Mensaje de fallo para los dos tests de sistema que ejecutan `scripts/ci/security` de
    verdad. `evaluar()`/`comprobar()` solo devuelven 0 o 1: cualquier OTRO código (127 "comando
    no encontrado", 126 "sin permiso de ejecución", 2 de un `set -e` que revienta antes de
    llegar al módulo...) significa que el guion NUNCA LLEGÓ A DICTAMINAR -- no es un veredicto
    de R1-R9 en desacuerdo con el test, es el guion muriendo por algo ajeno a la lógica que esta
    unidad prueba (ver hallazgos.md, "Cuarta vuelta": tres ejecuciones de este mismo test en el
    CI murieron así, por `pip-audit` ausente, sin que la falta de un contrato al que preguntar
    lo hiciera evidente en la cabecera del fallo)."""
    if resultado.returncode not in (0, 1):
        diagnostico = (
            f"el guion NO llegó a dictaminar (código {resultado.returncode}, fuera de "
            "{0, 1}): probablemente una herramienta que usa falta o falló antes de invocar a "
            "avisos_de_despliegue.comprobar(), no un veredicto real"
        )
    else:
        diagnostico = f"el guion SÍ dictaminó, pero en código {resultado.returncode}, no {esperado}"
    return (
        f"scripts/ci/security terminó con código {resultado.returncode} (se esperaba "
        f"{esperado}) -- {diagnostico}\n"
        f"--- stdout ---\n{resultado.stdout}\n--- stderr ---\n{resultado.stderr}"
    )


def _comprobar_con(mensajes):
    """Llama a `avisos_de_despliegue.comprobar()` DE VERDAD (no a `evaluar()` a solas),
    parcheando `django.core.checks.run_checks` para que devuelva `mensajes` fabricados en vez
    de ejecutar los checks reales del proyecto. Devuelve (código de salida, todo lo impreso).
    Es la única manera de probar el código de retorno y el texto de `comprobar()` -- las
    mutaciones M6 (`_texto_legible()` siempre "OK: ...") y M8 (`comprobar()` siempre
    `return 0`) no tumbaban ni un test porque nada llamaba a `comprobar()` con un veredicto en
    rojo (H3, segunda vuelta de la 045)."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    import django.core.checks as checks_module
    from kcalibra import avisos_de_despliegue

    def run_checks_falso(*args, **kwargs):
        return mensajes

    original = checks_module.run_checks
    checks_module.run_checks = run_checks_falso
    try:
        salida = io.StringIO()
        with redirect_stdout(salida), redirect_stderr(salida):
            codigo = avisos_de_despliegue.comprobar()
    finally:
        checks_module.run_checks = original
    return codigo, salida.getvalue()


class LosCuatroEsperadosYNadaMasTests(SimpleTestCase):
    """R1: el estado de hoy. Si esto falla, el CI se pone rojo permanente y nadie lo mira."""

    databases = set()

    def test_los_cuatro_esperados_dan_verde(self):
        mensajes = [_msg(id) for id in ESPERADOS]
        veredicto = evaluar(mensajes)
        self.assertTrue(veredicto.ok)
        self.assertEqual(veredicto.intrusos, [])
        self.assertEqual(veredicto.faltantes, [])


class IntrusoConIdTests(SimpleTestCase):
    """R2 (puerta 1, la 039): un aviso ajeno CON id hace fallar el veredicto, y su id sale
    nombrado en la lista de intrusos — nombrar al intruso es lo que hace accionable el rojo."""

    databases = set()

    def test_intruso_con_id_pone_rojo_y_lo_nombra(self):
        mensajes = [_msg(id) for id in ESPERADOS] + [_msg("otraapp.W099", texto="algo ajeno")]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertEqual([m.id for m in veredicto.intrusos], ["otraapp.W099"])


class IntrusoSinIdTests(SimpleTestCase):
    """R3 (puerta 2, la 043): el `id` es opcional en Django. Un aviso construido sin `id=`
    no puede ser ninguno de los cuatro esperados, así que cuenta como intruso."""

    databases = set()

    def test_intruso_sin_id_pone_rojo(self):
        mensajes = [_msg(id) for id in ESPERADOS] + [
            CheckMessage(WARNING, "aviso sin identificador")
        ]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertEqual(len(veredicto.intrusos), 1)
        self.assertIsNone(veredicto.intrusos[0].id)


class MensajeQueImitaElPieDePaginaTests(SimpleTestCase):
    """R4 (puerta 3, medida y hoy ABIERTA en el guion viejo): un intruso cuyo TEXTO contiene
    el pie de página de Django ('System check identified 4 issues (0 silenced).') sigue
    siendo intruso -- el contenido del mensaje no influye en absoluto en el veredicto, porque
    `evaluar()` nunca mira `.msg`, solo `.id` y `.level`."""

    databases = set()

    def test_mensaje_que_imita_el_resumen_final_sigue_siendo_rojo(self):
        intruso = CheckMessage(
            WARNING,
            "Un aviso ajeno de verdad, sin id, cuyo texto imita el resumen final de Django: "
            "System check identified 4 issues (0 silenced).",
        )
        mensajes = [_msg(id) for id in ESPERADOS] + [intruso]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertIn(intruso, veredicto.intrusos)


class EsperadoArregladoConAjenoEnSuHuecoTests(SimpleTestCase):
    """R5 (puerta 4, medida y hoy ABIERTA en el guion viejo): uno de los cuatro esperados
    desaparece porque se arregló de verdad, y un aviso ajeno (con SU PROPIO id, distinto)
    aparece en su lugar. El total de avisos (cuatro, igual que siempre) no interviene: el
    veredicto es rojo por el ajeno, nombrándolo, sin importar que el recuento cuadre."""

    databases = set()

    def test_el_ajeno_se_senala_aunque_el_total_cuadre(self):
        esperados_restantes = sorted(ESPERADOS)[:-1]
        arreglado = sorted(ESPERADOS)[-1]
        ajeno = _msg("otraapp.W050", texto="un aviso ajeno que ocupa el hueco")
        mensajes = [_msg(id) for id in esperados_restantes] + [ajeno]
        self.assertEqual(len(mensajes), len(ESPERADOS))  # el total cuadra, y no debe importar

        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertEqual([m.id for m in veredicto.intrusos], ["otraapp.W050"])
        self.assertEqual(veredicto.faltantes, [arreglado])


class IntrusoQueReutilizaIdEsperadoTests(SimpleTestCase):
    """H1 (segunda vuelta de la 045, revisión sobre el PR #49): un aviso ajeno que REUTILIZA
    el id de uno de los cuatro esperados es la quinta puerta de la familia, y una REGRESIÓN
    contra el guion viejo (68895d2), que sí la cazaba porque cuadraba el RECUENTO total contra
    los esperados vistos (5 mensajes != 4 esperados). `evaluar()` debe tratar el id como una
    identidad que se consume la primera vez que casa, no como una etiqueta reutilizable:
    cualquier mensaje posterior con el mismo id -- por muy distinto que sea su texto o su
    causa real -- sigue siendo un intruso."""

    databases = set()

    def test_id_esperado_duplicado_por_un_intruso_pone_rojo_y_lo_nombra(self):
        esperado_reutilizado = sorted(ESPERADOS)[0]
        intruso = CheckMessage(
            WARNING,
            "otro problema real, distinto del que ya justificaba este id",
            id=esperado_reutilizado,
        )
        # El original de este id va PRIMERO en la lista, para que "vistos" ya lo tenga cuando
        # se llegue al intruso -- así se ejercita justo la rama `mensaje.id in vistos`.
        mensajes = [_msg(id) for id in sorted(ESPERADOS)] + [intruso]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertIn(intruso, veredicto.intrusos)
        self.assertEqual(veredicto.faltantes, [])


class ImpostorQueReutilizaElObjetoDeUnGenuinoTests(SimpleTestCase):
    """R9 (la sexta puerta; tercera vuelta de la 045, sobre `especificacion.md` y el hallazgo
    [revisor-1] de `hallazgos.md`): a diferencia de H1 (un intruso que DUPLICA un id ya visto
    EN LA MISMA LISTA, dos mensajes con ese id), aquí el tolerado se ARREGLA DE VERDAD -- su
    objeto genuino no aparece nunca -- y en su hueco aparece UN SOLO mensaje que reutiliza su
    id, con su mismo nivel, pero de otra causa. Por `id` y `level` los dos son indistinguibles
    (medido por el revisor: 75 de 33 649 combinaciones, todas esta misma forma) y ni H1 ni el
    guion viejo (68895d2) cazan este caso -- ambos dan verde. Solo la identidad del OBJETO
    (parámetro `genuinos` de `evaluar()`, que `comprobar()` rellena con los singletons reales de
    Django, R9) distingue al impostor."""

    databases = set()

    def test_impostor_con_mismo_id_y_nivel_que_el_arreglado_pone_rojo(self):
        arreglado = sorted(ESPERADOS)[-1]
        otros_tres = sorted(ESPERADOS)[:-1]
        genuino_real = _genuino(arreglado)
        impostor = CheckMessage(
            WARNING,
            "otro problema real, de otra causa, que reutiliza el id de un tolerado ya arreglado",
            id=arreglado,
        )
        # El genuino real de "arreglado" NUNCA aparece en la lista -- se arregló de verdad --,
        # solo su id vuelve, en un objeto distinto. `genuinos` solo tiene entrada para ESE id:
        # los otros tres siguen sin exigir identidad, igual que antes de esta vuelta.
        mensajes = [_msg(id) for id in otros_tres] + [impostor]
        veredicto = evaluar(mensajes, genuinos={arreglado: genuino_real})
        self.assertFalse(veredicto.ok)
        self.assertIn(impostor, veredicto.intrusos)
        # El id del impostor nunca llega a "vistos" (fue rechazado, no aceptado), así que
        # también sale en `faltantes` -- el mismo doble nombrado, ya documentado como ruido
        # inofensivo y no un hueco, que R7 produce con un esperado subido a ERROR.
        self.assertEqual(veredicto.faltantes, [arreglado])

    def test_el_genuino_de_verdad_sigue_pasando_con_el_mapa_de_identidad_puesto(self):
        """Control: el mapa de identidad no debe producir falsos positivos contra el propio
        genuino -- si esto fallara, R9 pondría en rojo el camino verde real (R1)."""
        genuinos = {id: _genuino(id) for id in ESPERADOS}
        mensajes = [_genuino(id) for id in ESPERADOS]
        veredicto = evaluar(mensajes, genuinos=genuinos)
        self.assertTrue(veredicto.ok)


class EsperadoQueDesaparaceSinSustitutoTests(SimpleTestCase):
    """R6 (lista caducada): si uno de los cuatro esperados desaparece y nadie lo sustituye,
    el veredicto es rojo nombrando cuál esperado sobra en la lista -- la misma regla que la
    043 aplicó al `--ignore-vuln` de `pip-audit`: un permiso que ya no protege de nada se
    quita, no se hereda."""

    databases = set()

    def test_el_esperado_que_falta_se_nombra(self):
        esperados_restantes = sorted(ESPERADOS)[:-1]
        que_sobra = sorted(ESPERADOS)[-1]
        mensajes = [_msg(id) for id in esperados_restantes]

        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertEqual(veredicto.intrusos, [])
        self.assertEqual(veredicto.faltantes, [que_sobra])


class CorteExactoPorNivelTests(SimpleTestCase):
    """R7 (nivel): ERROR/CRITICAL pone rojo aunque el id esté entre los esperados; INFO/DEBUG
    no lo pone en rojo. El corte es el mismo WARNING que hoy aplica `--fail-level WARNING`,
    pero la API de Django (a diferencia del comando `check`) devuelve TODOS los niveles sin
    filtrar -- si `evaluar()` no reprodujera ese corte, el guion cambiaría de estrictez sin
    que nadie lo hubiera pedido."""

    databases = set()

    def test_un_esperado_subido_a_error_pone_rojo(self):
        esperados_restantes = sorted(ESPERADOS)[1:]
        subido = sorted(ESPERADOS)[0]
        mensajes = [_msg(id) for id in esperados_restantes] + [_msg(subido, nivel=ERROR)]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertEqual([m.id for m in veredicto.intrusos], [subido])

    def test_un_esperado_subido_a_critical_pone_rojo(self):
        esperados_restantes = sorted(ESPERADOS)[1:]
        subido = sorted(ESPERADOS)[0]
        mensajes = [_msg(id) for id in esperados_restantes] + [_msg(subido, nivel=CRITICAL)]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)
        self.assertEqual([m.id for m in veredicto.intrusos], [subido])

    def test_un_mensaje_ajeno_en_info_no_pone_rojo(self):
        mensajes = [_msg(id) for id in ESPERADOS] + [
            _msg("otraapp.I001", nivel=INFO, texto="informativo, no cuenta")
        ]
        veredicto = evaluar(mensajes)
        self.assertTrue(veredicto.ok)

    def test_un_mensaje_ajeno_en_debug_no_pone_rojo(self):
        mensajes = [_msg(id) for id in ESPERADOS] + [
            _msg("otraapp.D001", nivel=DEBUG, texto="depuración, no cuenta")
        ]
        veredicto = evaluar(mensajes)
        self.assertTrue(veredicto.ok)


class SilencedSystemChecksSeRespetaTests(SimpleTestCase):
    """H2 (segunda vuelta de la 045): la diferencia real entre los dos caminos es que el
    comando `check` filtra `SILENCED_SYSTEM_CHECKS` por su cuenta y `run_checks()` no --
    filtrado que vive en la línea `visibles = [... if not mensaje.is_silenced()]` de
    `comprobar()`. La primera vuelta probaba esto reimplementando el filtro DENTRO del test y
    llamando a `evaluar()`: eso prueba el `is_silenced()` de Django, no la línea de
    `comprobar()` que lo usa (mutación M7 -- borrar ese filtro -- no tumbaba ni un test). Aquí
    se llama a `comprobar()` de verdad, con `run_checks` parcheado y `override_settings`, y se
    mira el CÓDIGO DE RETORNO."""

    databases = set()

    def test_un_id_silenciado_no_cuenta_como_intruso_tras_filtrar(self):
        ajeno_silenciado = _msg("otraapp.W099", texto="silenciado en settings")
        mensajes = [_genuino(id) for id in ESPERADOS] + [ajeno_silenciado]
        with override_settings(SILENCED_SYSTEM_CHECKS=["otraapp.W099"]):
            self.assertTrue(ajeno_silenciado.is_silenced())
            codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 0)
        self.assertIn("OK", salida)

    def test_sin_silenciar_el_mismo_id_si_cuenta_como_intruso(self):
        ajeno = _msg("otraapp.W099", texto="sin silenciar")
        self.assertFalse(ajeno.is_silenced())
        mensajes = [_genuino(id) for id in ESPERADOS] + [ajeno]
        codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 1)
        self.assertIn("otraapp.W099", salida)


class ElVerdeNombraLoQueToleroTests(SimpleTestCase):
    """R1 (unidad 048): en VERDE, el guion decía UNA línea sin ids —"OK: los avisos de
    despliegue son exactamente los tolerados"— mientras que el guion viejo, el que leía la
    prosa de `manage.py check --deploy`, volcaba al log del CI los cuatro avisos con su id y su
    texto. No incumplía nada (R1 de la 045 solo exige verde), pero el día que la lista de
    tolerados caduque no habrá en el log ni una pista que lo delate: se verá el rojo de golpe.

    Nombrar en verde no cambia el veredicto: el código de salida sigue siendo 0. Eso es la
    mitad del criterio y por eso se afirma aquí, no solo el texto."""

    databases = set()

    def test_el_verde_nombra_los_cuatro_tolerados_y_sigue_siendo_verde(self):
        codigo, salida = _comprobar_con([_genuino(id) for id in ESPERADOS])

        self.assertEqual(codigo, 0, salida)
        for id_esperado in sorted(ESPERADOS):
            self.assertIn(id_esperado, salida)

    def test_nombrar_no_convierte_el_verde_en_rojo_ni_al_reves(self):
        """El gemelo que impide el arreglo perezoso: imprimir los cuatro ids SIEMPRE, también
        en rojo, haría pasar el test de arriba sin haber entendido nada — R1 dice "cuando el
        veredicto es verde", no "siempre". Aquí se exige que en ROJO se siga señalando al
        intruso, que el verde no se cuele en su salida, y que la lista de tolerados **no
        aparezca**.

        El `assertNotIn` de la lista lo añadió la REVISIÓN de la 048, y su historia es la
        lección: el constructor declaró haber medido este atajo por mutación y haber visto caer
        este test. Lo que mutó en realidad fue otra cosa (meter `"OK:"` dentro de la línea
        roja), que sí cae por el `assertNotIn("OK:")` de abajo. El atajo DE VERDAD —mover el
        bucle de `veredicto.tolerados` fuera del `if veredicto.ok`— pasaba los **30 tests en
        verde**: ninguno miraba esa lista en el camino rojo. Describir una mutación y medir
        otra es la tercera forma de "pegado ≠ literal", y aquí la cometió quien construía."""
        ajeno = _msg("otraapp.W099", texto="un intruso cualquiera")
        codigo, salida = _comprobar_con([_genuino(id) for id in ESPERADOS] + [ajeno])

        self.assertEqual(codigo, 1, salida)
        self.assertIn("otraapp.W099", salida)
        self.assertNotIn("OK:", salida)
        self.assertNotIn(
            "tolerado, y visto",
            salida,
            "R1 nombra los tolerados SOLO en verde: en rojo, esa lista entierra el intruso "
            "entre cuatro líneas de ruido, que es justo lo contrario de hacer accionable el rojo",
        )


class SilenciarUnToleradoLoDiceConSuNombreTests(SimpleTestCase):
    """R2 (unidad 048): silenciar uno de los cuatro tolerados con `SILENCED_SYSTEM_CHECKS` ya
    ponía el guion en ROJO antes de esta unidad, y así se queda **por decisión del usuario del
    2026-08-24**: es MÁS estricto que Django, y es lo correcto — silenciar a escondidas un aviso
    que el guardián vigila es justo lo que el guardián existe para impedir. Lo que estaba mal
    era lo que DECÍA: el tolerado silenciado desaparecía de `visibles`, caía en `faltantes` y se
    imprimía con el consejo de R6 —"¿se arregló? quítalo de ESPERADOS"— que es **el consejo
    contrario** al que necesita quien acaba de silenciarlo. Seguirlo empeora las cosas: quitas
    de la lista un aviso que sigue vivo y solo estaba tapado.

    Aquí se exige que el rojo diga la verdad: que está **silenciado**."""

    databases = set()

    def test_un_tolerado_silenciado_pone_rojo_diciendo_que_esta_silenciado(self):
        with override_settings(SILENCED_SYSTEM_CHECKS=["security.W004"]):
            codigo, salida = _comprobar_con([_genuino(id) for id in ESPERADOS])

        self.assertEqual(codigo, 1, salida)
        self.assertIn("security.W004", salida)
        self.assertIn("silenciado", salida.lower())
        self.assertNotIn(
            "¿se arregló?",
            salida,
            "un tolerado SILENCIADO no es un tolerado arreglado: aconsejar quitarlo de "
            "ESPERADOS es el consejo contrario, y seguirlo deja el aviso vivo y sin vigilar",
        )

    def test_un_tolerado_que_de_verdad_desaparece_sigue_dando_el_consejo_de_R6(self):
        """El gemelo, y es el que impide curar R2 rompiendo R6: cuando un tolerado desaparece
        porque se ARREGLÓ de verdad (nadie lo silenció), el consejo bueno sigue siendo el de
        siempre — quítalo de ESPERADOS. Sin este test, cambiar el mensaje de faltantes a
        "silenciado" para todos pasaría el test de arriba y mentiría en el caso normal."""
        tres = [_genuino(id) for id in sorted(ESPERADOS) if id != "security.W004"]
        codigo, salida = _comprobar_con(tres)

        self.assertEqual(codigo, 1, salida)
        self.assertIn("security.W004", salida)
        self.assertIn("¿se arregló?", salida)
        self.assertNotIn("silenciado", salida.lower())


class ChequeQueRevientaTests(SimpleTestCase):
    """R8 (caso límite): un check que revienta al ejecutarse nunca se da por bueno. Se
    comprueba en `comprobar()` (el envoltorio), no en `evaluar()`: `run_checks()` es quien
    puede reventar, la función pura ni siquiera llega a ejecutarse."""

    databases = set()

    def test_un_check_que_revienta_devuelve_rojo_con_traza(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        from kcalibra import avisos_de_despliegue
        import django.core.checks as checks_module

        def run_checks_que_revienta(*args, **kwargs):
            raise RuntimeError("un check roto de mentira, para R8")

        original_run_checks = checks_module.run_checks
        checks_module.run_checks = run_checks_que_revienta
        try:
            salida_out, salida_err = io.StringIO(), io.StringIO()
            with redirect_stdout(salida_out), redirect_stderr(salida_err):
                codigo = avisos_de_despliegue.comprobar()
        finally:
            checks_module.run_checks = original_run_checks

        self.assertEqual(codigo, 1)
        traza_completa = salida_out.getvalue() + salida_err.getvalue()
        self.assertIn("RuntimeError", traza_completa)
        self.assertIn("un check roto de mentira, para R8", traza_completa)


class ChequeQueSeMataConSysExitTests(SimpleTestCase):
    """Bug 047 (séptima puerta): R8 promete que un check que revienta al ejecutarse termina en
    ROJO — «nunca se da por bueno lo que no se pudo comprobar». Pero un check no solo puede
    reventar: puede MATARSE. `sys.exit()` levanta `SystemExit`, que NO hereda de `Exception`
    sino directamente de `BaseException`, así que el `except Exception` de `comprobar()` la
    dejaba pasar de largo: `sys.exit(comprobar())` no llegaba a ejecutarse nunca y el proceso
    moría con el código que traía la `SystemExit` — **0**, o sea VERDE, con la configuración de
    despliegue sin comprobar y `scripts/ci/security` (que corre bajo `set -e`) tan contento.

    Lo encontró el revisor de la 045 en la vuelta de confirmación; el usuario lo dejó fuera de
    aquella unidad a propósito y pidió cerrarlo el 2026-08-24. No era regresión —el guion viejo,
    `manage.py check --deploy`, también salía 0 ante un check que hacía `sys.exit(0)`— pero sí
    incumplía R8 tal como está escrito.

    Los tres tests de aquí cubren las tres formas de `BaseException` que pueden llegar a este
    `try`, y por eso el arreglo es `except BaseException` y no `except (Exception, SystemExit)`:
    lo que se está tapando no es «`SystemExit` en concreto», es **cualquier cosa que atraviese
    el try sin que nadie dictamine**."""

    databases = set()

    def _comprobar_con_un_run_checks_que(self, funcion):
        """Igual que `_comprobar_con()`, pero parchea `run_checks` con una función que hace
        algo (matarse, reventar) en vez de devolver mensajes. Devuelve (código, todo lo
        impreso).

        **La fuga se ATRAPA aquí a propósito.** Si `comprobar()` deja escapar lo que levante
        `funcion`, este helper lo recoge y devuelve `codigo=None`, para que el test falle por
        su `assertEqual` con un mensaje que se entiende. Sin esto, el test del Ctrl-C **abortaba
        la ejecución entera** en vez de fallar: `unittest` re-lanza `KeyboardInterrupt` a
        propósito (es como se interrumpe una suite a mano), así que una fuga se llevaba por
        delante los otros 25 tests y no dejaba ni el resumen. Medido: con el arreglo deshecho,
        la orden de test no imprimía NI UNA línea de veredicto. Un rojo que no dice qué
        comprobación falló no es un rojo útil (regla 16), y además hacía imposible medir esta
        red por mutación."""
        import io
        from contextlib import redirect_stderr, redirect_stdout

        import django.core.checks as checks_module
        from kcalibra import avisos_de_despliegue

        original = checks_module.run_checks
        checks_module.run_checks = funcion
        fuga = None
        codigo = None
        try:
            salida_out, salida_err = io.StringIO(), io.StringIO()
            with redirect_stdout(salida_out), redirect_stderr(salida_err):
                try:
                    codigo = avisos_de_despliegue.comprobar()
                except BaseException as escapada:  # noqa: BLE001 -- ver docstring
                    fuga = escapada
        finally:
            checks_module.run_checks = original

        impreso = salida_out.getvalue() + salida_err.getvalue()
        if fuga is not None:
            impreso += (
                f"\n[el test atrapó una fuga: comprobar() dejó escapar "
                f"{type(fuga).__name__}({fuga!r}) en vez de dictaminar]"
            )
        return codigo, impreso

    def test_un_check_que_se_mata_con_sys_exit_0_pone_el_guion_en_rojo(self):
        """EL test del bug 047. Antes del arreglo no falla por el assert: falla porque la
        `SystemExit` **atraviesa** `comprobar()` y llega hasta aquí — que es justo lo que en el
        guion de verdad se traducía en un proceso muerto en 0 y un CI en verde."""

        def run_checks_que_se_mata(*args, **kwargs):
            import sys as _sys

            _sys.exit(0)

        codigo, impreso = self._comprobar_con_un_run_checks_que(run_checks_que_se_mata)

        self.assertEqual(
            codigo,
            1,
            "un check que se mata con sys.exit(0) tiene que dejar el guion en ROJO: la "
            "configuración de despliegue NO se comprobó, y R8 dice que lo que no se pudo "
            "comprobar nunca se da por bueno",
        )
        self.assertIn("SystemExit", impreso)

    def test_un_check_que_se_mata_con_sys_exit_1_tambien_pone_el_guion_en_rojo(self):
        """El hermano peligroso del anterior: con `sys.exit(1)` el proceso ya moría en 1, así
        que el guion salía ROJO **por accidente** — no porque hubiera dictaminado, sino porque
        el código de la `SystemExit` coincidía con el del rojo. Un rojo así no se distingue de
        uno bueno, y el día que el check se matara con 0 volvía el verde mentiroso. Aquí se
        exige que el 1 venga de `comprobar()` DEVOLVIÉNDOLO, con su traza impresa."""

        def run_checks_que_se_mata_en_1(*args, **kwargs):
            import sys as _sys

            _sys.exit(1)

        codigo, impreso = self._comprobar_con_un_run_checks_que(run_checks_que_se_mata_en_1)

        self.assertEqual(codigo, 1, impreso)
        self.assertIn("SystemExit", impreso)

    def test_un_ctrl_c_durante_los_checks_pone_el_guion_en_rojo(self):
        """`KeyboardInterrupt` es la otra `BaseException` que puede llegar a este `try`. Se
        decide capturarla y salir en ROJO, no dejarla pasar: el proceso termina igual (el
        guion devuelve 1 y `sys.exit(1)` lo remata), pero termina **diciendo la verdad** — los
        checks no se llegaron a ejecutar. Un Ctrl-C que dejara el guion en verde sería el mismo
        agujero con otro nombre. Es más estricto que la costumbre de Python (donde un Ctrl-C se
        deja subir) y falla del lado seguro, que es lo que se le pide a un guardián."""

        def run_checks_interrumpido(*args, **kwargs):
            raise KeyboardInterrupt

        codigo, impreso = self._comprobar_con_un_run_checks_que(run_checks_interrumpido)

        self.assertEqual(codigo, 1, impreso)
        self.assertIn("KeyboardInterrupt", impreso)


class ComprobarNombraAlCulpableEnRojoTests(SimpleTestCase):
    """H3 (segunda vuelta de la 045): ningún assert de la primera vuelta miraba nunca la
    salida impresa de `comprobar()` ni su código de retorno por el camino normal (el único
    `assertEqual(codigo, 1)` de toda la red era el de R8, que sale por el `except`). Las
    mutaciones M6 (`_texto_legible()` siempre "OK: ...") y M8 (`comprobar()` siempre
    `return 0`) no tumbaban ni un test. Aquí se ejercita `comprobar()` de verdad -- R2 exige
    que el rojo NOMBRE al intruso, R6 que diga qué esperado sobra -- con `run_checks`
    parcheado, sin pasar por `scripts/ci/security`."""

    databases = set()

    def test_los_cuatro_esperados_ponen_comprobar_en_verde_de_verdad(self):
        mensajes = [_genuino(id) for id in ESPERADOS]
        codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 0)
        self.assertIn("OK: los avisos de despliegue son exactamente los tolerados.", salida)

    def test_intruso_con_id_pone_comprobar_en_rojo_y_lo_nombra_en_la_salida(self):
        intruso = _msg("otraapp.W099", texto="un aviso ajeno de verdad")
        mensajes = [_genuino(id) for id in ESPERADOS] + [intruso]
        codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 1)
        self.assertIn("ROJO", salida)
        self.assertIn("otraapp.W099", salida)

    def test_intruso_sin_id_pone_comprobar_en_rojo_con_el_marcador_sin_id(self):
        mensajes = [_genuino(id) for id in ESPERADOS] + [
            CheckMessage(WARNING, "aviso sin identificador")
        ]
        codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 1)
        self.assertIn("<sin id>", salida)

    def test_esperado_que_falta_se_nombra_en_la_salida_de_comprobar(self):
        esperados_restantes = sorted(ESPERADOS)[:-1]
        que_sobra = sorted(ESPERADOS)[-1]
        mensajes = [_genuino(id) for id in esperados_restantes]
        codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 1)
        self.assertIn("ROJO", salida)
        self.assertIn(que_sobra, salida)


class ComprobarCazaAlImpostorQueReutilizaUnIdTests(SimpleTestCase):
    """R9 a través de `comprobar()` DE VERDAD, no solo de `evaluar()` a solas -- el caso medido
    por el revisor ([revisor-1] de `hallazgos.md`, tercera vuelta): tres tolerados GENUINOS (los
    singletons reales de Django, via `_genuino()`) más un CUARTO mensaje que reutiliza el id del
    tolerado que se arregló, con otro texto y otra causa. Antes de esta vuelta, `comprobar()` no
    inyectaba ningún mapa de identidad a `evaluar()` y este caso pasaba en verde -- la sexta
    puerta. Ahora inyecta `_genuinos_de_django()` y lo caza."""

    databases = set()

    def test_impostor_que_ocupa_el_hueco_de_un_arreglado_pone_comprobar_en_rojo(self):
        arreglado = sorted(ESPERADOS)[-1]
        otros_tres = sorted(ESPERADOS)[:-1]
        impostor = CheckMessage(
            WARNING,
            "OTRO problema real, con otra causa y otro texto, que reutiliza el id de un "
            "tolerado que ya se arregló",
            id=arreglado,
        )
        mensajes = [_genuino(id) for id in otros_tres] + [impostor]
        codigo, salida = _comprobar_con(mensajes)
        self.assertEqual(codigo, 1)
        self.assertIn("ROJO", salida)
        self.assertIn(arreglado, salida)


class ElGuionCompletoTerminaEnRojoAnteUnAvisoRealTests(SimpleTestCase):
    """H3, nivel sistema: la costura completa (`scripts/ci/security`) tampoco tenía ni un
    test que la ejercitara en rojo -- `ElGuionCompletoTerminaEnVerdeTests` solo prueba el
    camino verde, y "probar la pieza no prueba la costura" (lección de la 017) es exactamente
    lo que se dejó fuera. Provoca un aviso REAL de Django (`DEBUG=True` en un despliegue,
    `security.W018`), sin fabricar ni un `CheckMessage`, y comprueba que el guion de bash
    completo -- `pip-audit` incluido -- termina en rojo nombrando al intruso."""

    databases = set()

    def test_scripts_ci_security_sale_en_rojo_con_debug_true(self):
        raiz = str(settings.BASE_DIR)
        entorno = {**os.environ, "DJANGO_DEBUG": "True"}
        resultado = subprocess.run(
            ["scripts/ci/security"],
            cwd=raiz,
            env=entorno,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(
            resultado.returncode,
            1,
            _mensaje_fallo_guion(resultado, esperado=1),
        )
        self.assertIn("security.W018", resultado.stdout)


class ElGuionCompletoTerminaEnVerdeTests(SimpleTestCase):
    """R1, nivel de sistema: probar la pieza no prueba la costura (lección de la 017). Este
    test ejecuta `scripts/ci/security` de verdad, tal y como lo hace el CI (con
    `DJANGO_DEBUG=False`, igual que `.github/workflows/quality-security.yml`), y comprueba
    que sale con código 0."""

    databases = set()

    def test_scripts_ci_security_sale_en_verde(self):
        raiz = str(settings.BASE_DIR)
        entorno = {**os.environ, "DJANGO_DEBUG": "False"}
        resultado = subprocess.run(
            ["scripts/ci/security"],
            cwd=raiz,
            env=entorno,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(
            resultado.returncode,
            0,
            _mensaje_fallo_guion(resultado, esperado=0),
        )
