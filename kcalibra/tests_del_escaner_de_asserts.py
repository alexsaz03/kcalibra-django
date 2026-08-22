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

import io
import os
import shutil
import subprocess
import tempfile
import unittest

from django.conf import settings
from django.test import SimpleTestCase

from kcalibra.tests_asserts_de_estado import descubrir_helpers, sitios_de_hoy


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


class ElDocstringDeDescubrirHelpersDiceLaVerdadTests(SimpleTestCase):
    """Hueco 2 de la revisión (R6), primera y segunda vuelta. El docstring de `descubrir_helpers`
    ha dicho, en distintos momentos, cosas que no eran ciertas: que NO reconoce una respuesta
    guardada en el atributo de un objeto que no sea `self` (falso, primera vuelta); que SÍ
    reconoce `self.<algo>.<verbo>(..., follow=True)` para cualquier `<algo>` (falso desde
    `bcb12a7`, segunda vuelta: el receptor tiene que ser `self.client`/algo que termine en
    `.client`/una variable `client`); y que NO reconoce un helper envuelto en un decorador
    (falso siempre: `descubrir_helpers` no mira el `decorator_list`). Cada test de esta clase
    fija UNA afirmación del docstring de hoy, con el fixture que la comprueba."""

    databases = set()

    def setUp(self):
        self.directorio = tempfile.mkdtemp(prefix="kcalibra_escaner_037_")
        self.addCleanup(shutil.rmtree, self.directorio, ignore_errors=True)

    def test_guardado_en_el_atributo_de_otro_objeto_que_no_es_self_si_se_reconoce(self):
        _escribir(
            self.directorio,
            "tests_otro_objeto.py",
            (
                "class Prueba:\n"
                "    def ayuda_en_caja(self, caja):\n"
                '        caja.resp = self.client.post("/algo/", {}, follow=True)\n'
                "        return caja.resp\n"
                "\n"
                "    def test_guardado_en_otro_objeto(self):\n"
                "        respuesta = self.ayuda_en_caja(self.objeto)\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertIn(("test_guardado_en_otro_objeto", "respuesta"), sitios)

    def test_el_desempaquetado_de_tupla_sigue_siendo_ciego(self):
        """La única forma de escribir la forma 4 que puede EJECUTARSE de verdad
        (`respuesta, extra = self.ayuda_tupla()`): límite escrito, no arreglado."""
        _escribir(
            self.directorio,
            "tests_desempaquetado.py",
            (
                "class Prueba:\n"
                "    def ayuda_tupla_desempaquetada(self):\n"
                '        return self.client.post("/algo/", {}, follow=True), "extra"\n'
                "\n"
                "    def test_desempaquetado_de_tupla(self):\n"
                "        respuesta, extra = self.ayuda_tupla_desempaquetada()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertNotIn(("test_desempaquetado_de_tupla", "respuesta"), sitios)

    def test_un_receptor_que_no_es_self_punto_client_no_se_cuenta(self):
        """La forma ciega nueva que nació con el arreglo del hueco 1 (R2, `_es_receptor_de_
        cliente`): `self.navegador` no termina en `.client`, así que aunque sea idéntico a
        `self.client.post(..., follow=True)` en todo lo demás, no se cuenta."""
        _escribir(
            self.directorio,
            "tests_receptor_no_client.py",
            (
                "class Prueba:\n"
                "    def ayuda_navegador(self):\n"
                '        return self.navegador.post("/algo/", {}, follow=True)\n'
                "\n"
                "    def test_receptor_no_client(self):\n"
                "        respuesta = self.ayuda_navegador()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertNotIn(("test_receptor_no_client", "respuesta"), sitios)

    def test_un_helper_envuelto_en_decorador_si_se_reconoce(self):
        """`descubrir_helpers` recorre los `FunctionDef` sin mirar el `decorator_list`: un
        decorador no le tapa el helper de debajo."""
        _escribir(
            self.directorio,
            "tests_helper_decorado.py",
            (
                "def mi_decorador(f):\n"
                "    return f\n"
                "\n"
                "class Prueba:\n"
                "    @mi_decorador\n"
                "    def ayuda_decorada(self):\n"
                '        return self.client.post("/algo/", {}, follow=True)\n'
                "\n"
                "    def test_helper_decorado(self):\n"
                "        respuesta = self.ayuda_decorada()\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertIn(("test_helper_decorado", "respuesta"), sitios)


class LaOrmConKwargsNoEsUnaLlamadaDeClienteTests(SimpleTestCase):
    """Hueco 1 de la revisión (R2): `_es_llamada_de_cliente` solo miraba el nombre del método
    (`get`/`post`/...) sin mirar el RECEPTOR, así que `Persona.objects.get(**filtros)` -- el
    idioma más común de la ORM de Django, sin cliente ni `follow` por ninguna parte -- se
    contaba como sitio, y de paso su helper contaminaba por nombre la FASE 2 en todo el repo.
    Fixture íntegro del revisor, pegado en `hallazgos.md`."""

    databases = set()

    def setUp(self):
        self.directorio = tempfile.mkdtemp(prefix="kcalibra_escaner_037_")
        self.addCleanup(shutil.rmtree, self.directorio, ignore_errors=True)

    def _escribir_fixture_del_revisor(self):
        _escribir(
            self.directorio,
            "tests_falso_positivo.py",
            (
                "def buscar_persona(**filtros):\n"
                "    return Persona.objects.get(**filtros)      # ni cliente, ni follow\n"
                "\n"
                "class PruebaDeAlgo:\n"
                "    def test_la_ficha_se_pinta(self):\n"
                "        respuesta = buscar_persona(id=1)\n"
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )

    def test_el_kwargs_de_la_orm_no_se_cuenta_como_sitio(self):
        self._escribir_fixture_del_revisor()
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertNotIn(("test_la_ficha_se_pinta", "respuesta"), sitios)

    def test_buscar_persona_no_contamina_el_diccionario_de_helpers(self):
        self._escribir_fixture_del_revisor()
        helpers = descubrir_helpers(self.directorio)
        self.assertNotIn("buscar_persona", helpers)


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

    def _escribir_sitio_bueno(self):
        _escribir(
            self.directorio,
            "bueno.py",
            (
                "class Prueba:\n"
                "    def test_sitio_bueno(self):\n"
                '        respuesta = self.client.post("/algo/", {}, follow=True)\n'
                "        self.assertEqual(respuesta.status_code, 200)\n"
            ),
        )

    def test_sintaxis_rota_no_tumba_el_escaneo(self):
        """No basta con que no lance: junto al fichero roto va uno bueno, y ese SÍ tiene que
        aparecer -- si no, "no encuentro nada" (por ejemplo, un escaneo que devolviera lista
        vacía) pasaría este test igual de verde (015)."""
        _escribir(self.directorio, "roto.py", "def test_algo(self:\n    pasa\n")
        self._escribir_sitio_bueno()
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertIn(("test_sitio_bueno", "respuesta"), sitios)

    def test_bytes_no_utf8_no_tumban_el_escaneo(self):
        ruta = os.path.join(self.directorio, "binario.py")
        with open(ruta, "wb") as f:
            f.write(b"\xff\xfe\x00\x01 esto no es utf-8 valido \x80\x81")
        self._escribir_sitio_bueno()
        sitios = {(test, variable) for (_f, _l, test, variable) in sitios_de_hoy(self.directorio)}
        self.assertIn(("test_sitio_bueno", "respuesta"), sitios)


class ElRepoNoCambiaAlCorrerEstaSuiteTests(SimpleTestCase):
    """R7: hueco 3 de la revisión. El test anterior (`assertNotEqual(commonpath(...), raiz)`)
    medía una propiedad de `tempfile`, no de esta suite: pasaría igual el día que un fixture se
    escribiera de verdad dentro del repo. R7 pide el observable literal del contrato --
    `git status` sin cambios TRAS CORRER la suite del escáner-- así que aquí se corren de
    verdad, en proceso, las clases de este fichero que escriben fixtures (todas menos esta
    misma, para no recursar), y se compara `git status --porcelain` de antes y de después."""

    databases = set()

    def _git_status_porcelain(self, raiz):
        return subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=raiz,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def test_correr_las_clases_que_escriben_fixtures_deja_el_repo_igual(self):
        raiz = str(settings.BASE_DIR)
        antes = self._git_status_porcelain(raiz)

        cargador = unittest.TestLoader()
        suite = unittest.TestSuite()
        for clase in (
            SeisFormasQueElEscanerDebeVerTests,
            ElDocstringDeDescubrirHelpersDiceLaVerdadTests,
            LaOrmConKwargsNoEsUnaLlamadaDeClienteTests,
            CarpetaConPyvenvCfgSeSaltaTests,
            FicheroIlegibleNoTumbaElEscaneoTests,
        ):
            suite.addTests(cargador.loadTestsFromTestCase(clase))
        resultado = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertTrue(
            resultado.wasSuccessful(),
            f"las clases de fixtures de esta suite deberían pasar limpiamente: "
            f"{len(resultado.failures)} fallo(s), {len(resultado.errors)} error(es)",
        )

        despues = self._git_status_porcelain(raiz)
        self.assertEqual(
            antes,
            despues,
            "el repo cambió tras correr la suite del escáner: algún fixture se escribió dentro "
            "de BASE_DIR en vez de en un temporal fuera del árbol",
        )
