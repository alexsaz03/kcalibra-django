r"""
La red que la unidad 037 le pone por primera vez al escáner de `tests_asserts_de_estado.py`
(035). Sus dos tests de hoy corren contra el repo real: solo comprueban que lo que ya se ve
siga viéndose, nunca que el escáner sepa ver algo nuevo. Un escáner sin fixtures propios es
exactamente "la herramienta se prueba rompiéndola" (21ª cara) sin cumplir.

Por cada una de las seis formas que el revisor de la 035 midió como ciegas, hay aquí un
fichero `.py` sintético (uno por forma) y su gemelo negativo (misma escritura, sin
`follow=True`). Los fixtures se escriben con `tempfile.mkdtemp()` y se borran al terminar cada
test (R7): si se escribieran dentro del repo, el propio escáner los contaría como sitios nuevos
y fallaría él solo.
"""

import os
import shutil
import tempfile

from django.conf import settings
from django.test import SimpleTestCase

from kcalibra.tests_asserts_de_estado import sitios_de_hoy


def _escribir(directorio, nombre, contenido):
    ruta = os.path.join(directorio, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    return ruta


class SeisFormasQueElEscanerDebeVerTests(SimpleTestCase):
    """R1/R2: cada forma ciega, contada cuando aparece (R1) y callada cuando no (R2)."""

    databases = set()

    def setUp(self):
        self.directorio = tempfile.mkdtemp(prefix="kcalibra_escaner_037_")
        self.addCleanup(shutil.rmtree, self.directorio, ignore_errors=True)

    def _sitios(self):
        return {(test, variable) for (_fichero, _linea, test, variable) in sitios_de_hoy(self.directorio)}

    # --- Forma 1: follow por variable -----------------------------------------------------

    def test_forma_1_follow_por_variable_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_1.py",
            (
                "class Prueba:\n"
                "    def test_variable_follow(self):\n"
                "        seguir = True\n"
                '        respuesta = self.client.post("/algo/", {}, follow=seguir)\n'
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertIn(("test_variable_follow", "respuesta"), self._sitios())

    def test_forma_1_gemelo_negativo_sin_follow_no_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_1_negativo.py",
            (
                "class Prueba:\n"
                "    def test_variable_sin_follow(self):\n"
                '        respuesta = self.client.post("/algo/", {})\n'
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertNotIn(("test_variable_sin_follow", "respuesta"), self._sitios())

    # --- Forma 2: follow por **kwargs ------------------------------------------------------

    def test_forma_2_follow_por_kwargs_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_2.py",
            (
                "class Prueba:\n"
                "    def test_kwargs_follow(self):\n"
                '        extra = {"follow": True}\n'
                '        respuesta = self.client.post("/algo/", {}, **extra)\n'
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertIn(("test_kwargs_follow", "respuesta"), self._sitios())

    def test_forma_2_gemelo_negativo_sin_kwargs_no_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_2_negativo.py",
            (
                "class Prueba:\n"
                "    def test_kwargs_sin_follow(self):\n"
                '        respuesta = self.client.post("/algo/", {})\n'
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertNotIn(("test_kwargs_sin_follow", "respuesta"), self._sitios())

    # --- Forma 3: return con IfExp ----------------------------------------------------------

    def test_forma_3_return_ifexp_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_3.py",
            (
                "class Prueba:\n"
                "    def ayuda_ifexp(self, cond):\n"
                '        return self.client.post("/a/", {}, follow=True) if cond else self.client.get("/b/")\n'
                "\n"
                "    def test_ifexp(self):\n"
                "        respuesta = self.ayuda_ifexp(True)\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertIn(("test_ifexp", "respuesta"), self._sitios())

    def test_forma_3_gemelo_negativo_ifexp_sin_follow_no_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_3_negativo.py",
            (
                "class Prueba:\n"
                "    def ayuda_ifexp_sin_follow(self, cond):\n"
                '        return self.client.post("/a/", {}) if cond else self.client.get("/b/")\n'
                "\n"
                "    def test_ifexp_sin_follow(self):\n"
                "        respuesta = self.ayuda_ifexp_sin_follow(True)\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertNotIn(("test_ifexp_sin_follow", "respuesta"), self._sitios())

    # --- Forma 4: return de una tupla -------------------------------------------------------

    def test_forma_4_return_tupla_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_4.py",
            (
                "class Prueba:\n"
                "    def ayuda_tupla(self):\n"
                '        return self.client.post("/algo/", {}, follow=True), "extra"\n'
                "\n"
                "    def test_tupla(self):\n"
                "        respuesta = self.ayuda_tupla()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertIn(("test_tupla", "respuesta"), self._sitios())

    def test_forma_4_gemelo_negativo_tupla_sin_follow_no_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_4_negativo.py",
            (
                "class Prueba:\n"
                "    def ayuda_tupla_sin_follow(self):\n"
                '        return self.client.post("/algo/", {}), "extra"\n'
                "\n"
                "    def test_tupla_sin_follow(self):\n"
                "        respuesta = self.ayuda_tupla_sin_follow()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertNotIn(("test_tupla_sin_follow", "respuesta"), self._sitios())

    # --- Forma 5: respuesta guardada en self.algo -------------------------------------------

    def test_forma_5_guardado_en_self_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_5.py",
            (
                "class Prueba:\n"
                "    def test_guardado_en_self(self):\n"
                '        self.resultado = self.client.post("/algo/", {}, follow=True)\n'
                "        self.assertEqual(self.resultado.status_code, 200)\n"
            ),
        )
        self.assertIn(("test_guardado_en_self", "self.resultado"), self._sitios())

    def test_forma_5_gemelo_negativo_guardado_en_self_sin_follow_no_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_5_negativo.py",
            (
                "class Prueba:\n"
                "    def test_guardado_en_self_sin_follow(self):\n"
                '        self.resultado = self.client.post("/algo/", {})\n'
                "        self.assertEqual(self.resultado.status_code, 200)\n"
            ),
        )
        self.assertNotIn(("test_guardado_en_self_sin_follow", "self.resultado"), self._sitios())

    # --- Forma 6: indirección de dos saltos -------------------------------------------------

    def test_forma_6_indireccion_de_dos_saltos_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_6.py",
            (
                "class Prueba:\n"
                "    def ayuda_nivel_uno(self):\n"
                '        return self.client.post("/algo/", {}, follow=True)\n'
                "\n"
                "    def ayuda_nivel_dos(self):\n"
                "        return self.ayuda_nivel_uno()\n"
                "\n"
                "    def test_dos_saltos(self):\n"
                "        respuesta = self.ayuda_nivel_dos()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertIn(("test_dos_saltos", "respuesta"), self._sitios())

    def test_forma_6_gemelo_negativo_dos_saltos_sin_follow_no_se_cuenta(self):
        _escribir(
            self.directorio,
            "tests_forma_6_negativo.py",
            (
                "class Prueba:\n"
                "    def ayuda_nivel_uno_sin_follow(self):\n"
                '        return self.client.post("/algo/", {})\n'
                "\n"
                "    def ayuda_nivel_dos_sin_follow(self):\n"
                "        return self.ayuda_nivel_uno_sin_follow()\n"
                "\n"
                "    def test_dos_saltos_sin_follow(self):\n"
                "        respuesta = self.ayuda_nivel_dos_sin_follow()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        self.assertNotIn(("test_dos_saltos_sin_follow", "respuesta"), self._sitios())


class CarpetaConPyvenvCfgSeSaltaTests(SimpleTestCase):
    """R4: la marca canónica de un entorno virtual es el `pyvenv.cfg`, se llame la carpeta como
    se llame -- no una lista de nombres adivinados."""

    databases = set()

    def setUp(self):
        self.directorio = tempfile.mkdtemp(prefix="kcalibra_escaner_037_")
        self.addCleanup(shutil.rmtree, self.directorio, ignore_errors=True)

    def test_carpeta_con_pyvenv_cfg_se_salta_aunque_el_nombre_no_delate_nada(self):
        entorno = os.path.join(self.directorio, "env")  # sin punto: la regla "empieza por `.`" no lo salva
        os.makedirs(entorno)
        _escribir(entorno, "pyvenv.cfg", "home = /usr/bin\n")
        _escribir(
            entorno,
            "tests_dentro_del_entorno.py",
            (
                "class Prueba:\n"
                "    def test_dentro_del_entorno(self):\n"
                '        respuesta = self.client.post("/algo/", {}, follow=True)\n'
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertNotIn(("test_dentro_del_entorno", "respuesta"), sitios)


class FicheroIlegibleNoTumbaElEscaneoTests(SimpleTestCase):
    """R5, caso límite que ya funcionaba: un fichero con sintaxis rota o bytes no-UTF-8 se
    salta, no revienta el escaneo entero."""

    databases = set()

    def setUp(self):
        self.directorio = tempfile.mkdtemp(prefix="kcalibra_escaner_037_")
        self.addCleanup(shutil.rmtree, self.directorio, ignore_errors=True)

    def test_sintaxis_rota_no_tumba_el_escaneo(self):
        _escribir(self.directorio, "roto.py", "def test_algo(self:\n    pasa\n")
        sitios_de_hoy(self.directorio)  # no debe lanzar excepción

    def test_bytes_no_utf8_no_tumban_el_escaneo(self):
        ruta = os.path.join(self.directorio, "binario.py")
        with open(ruta, "wb") as f:
            f.write(b"\xff\xfe\x00\x01 esto no es utf-8 valido \x80\x81")
        sitios_de_hoy(self.directorio)  # no debe lanzar excepción


class ElRepoNoCambiaAlCorrerEstaSuiteTests(SimpleTestCase):
    """R7: los fixtures de este fichero nunca se escriben dentro del repo -- si se escribieran,
    el propio guardián de la unidad 035/037 los contaría como sitios nuevos y fallaría. Aquí se
    demuestra que cualquier directorio temporal que usa esta suite cae FUERA de `BASE_DIR`."""

    databases = set()

    def test_los_fixtures_temporales_quedan_fuera_del_repo(self):
        raiz = str(settings.BASE_DIR)
        directorio = tempfile.mkdtemp(prefix="kcalibra_escaner_037_")
        try:
            self.assertNotEqual(os.path.commonpath([directorio, raiz]), raiz)
        finally:
            shutil.rmtree(directorio, ignore_errors=True)
