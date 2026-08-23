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
    """La diferencia real entre los dos caminos: el comando `check` filtra
    `SILENCED_SYSTEM_CHECKS` por su cuenta; `run_checks()` no. `comprobar()` reproduce ese
    filtrado a mano con `CheckMessage.is_silenced()` ANTES de llamar a `evaluar()` -- se
    prueba aquí llamando a `is_silenced()` directamente (lo que usa `comprobar()`), sin
    necesidad de montar toda la app."""

    databases = set()

    def test_un_id_silenciado_no_cuenta_como_intruso_tras_filtrar(self):
        ajeno_silenciado = _msg("otraapp.W099", texto="silenciado en settings")
        with override_settings(SILENCED_SYSTEM_CHECKS=["otraapp.W099"]):
            self.assertTrue(ajeno_silenciado.is_silenced())
            mensajes = [_msg(id) for id in ESPERADOS] + [ajeno_silenciado]
            visibles = [m for m in mensajes if not m.is_silenced()]
            veredicto = evaluar(visibles)
        self.assertTrue(veredicto.ok)

    def test_sin_silenciar_el_mismo_id_si_cuenta_como_intruso(self):
        ajeno = _msg("otraapp.W099", texto="sin silenciar")
        self.assertFalse(ajeno.is_silenced())
        mensajes = [_msg(id) for id in ESPERADOS] + [ajeno]
        veredicto = evaluar(mensajes)
        self.assertFalse(veredicto.ok)


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
            f"scripts/ci/security terminó con código {resultado.returncode}\n"
            f"--- stdout ---\n{resultado.stdout}\n--- stderr ---\n{resultado.stderr}",
        )
