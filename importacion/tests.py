"""
Tests de la unidad 022 (R1-R8, traer-los-datos-de-verdad): traer despensa, entrenos, recetas y
pesadas de la app Node a una cuenta que ya existe en Django, pasando por las puertas que ya
existen (R1), de forma repetible (R2), con `--dry-run` (R3), sin redondear (R4), traduciendo las
recetas (R5), sin salirse del hogar (R6), fallando en cristiano si el origen no vale (R7) y sin
un solo dato real dentro del repositorio (R8: toda la SQLite de Node que usan estos tests está
INVENTADA aquí mismo, nunca es `~/Desktop/proyectos/kcalibra/backend/data/kcalibra.db`).

Convención de esta unidad, distinta de la del resto de la app: NO hay ninguna vista ni URL que
probar (`especificacion.md`, "Fuera de alcance": "una pantalla para importar... es un comando de
terminal"), así que aquí no aplica la lección de "la petición tiene que LLEGAR a lo que dice
probar" vía `self.client` (`despensa/tests.py`, cabecera) — el "cliente" de este comando es
`django.core.management.call_command`, y ESE sí se usa siempre que se prueba el COMANDO entero
(nunca se llama a `_importar_despensa` etc. sin pasar por `handle()` cuando lo que se prueba es
el contrato de cara al usuario). Las funciones privadas del módulo del comando SÍ se llaman
directamente en un puñado de tests que necesitan aislar una tabla sin las otras tres — están
señaladas una a una con el motivo.
"""

import io
import json
import os
import sqlite3
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from despensa.models import ProductoDespensa
from entrenos.logica import apuntar_entreno
from entrenos.models import Entreno
from hogares.models import Hogar, Persona, crear_hogar_propio
from perfiles.models import MedicionPeso
from recetas.models import IngredienteDeReceta, Receta

from . import mapeo, origen

Usuario = get_user_model()


# ---------------------------------------------------------------------------------------------
# La SQLite de Node, INVENTADA (R8): el mismo esqueleto de columnas que lee `importacion/origen.
# py` (comprobado contra el schema real con `sqlite3 ... ".schema"`, nunca contra sus filas),
# pero con datos de mentira, creados aquí. Ningún test de este fichero abre jamás la ruta real
# de la base de Node.
# ---------------------------------------------------------------------------------------------


def _crear_sqlite_de_node(
    ruta,
    *,
    productos=None,
    entrenos=None,
    recetas=None,
    pesos=None,
    con_productos=True,
    con_entrenos=True,
    con_recetas=True,
    con_pesos=True,
    con_strava_cuentas=False,
):
    conexion = sqlite3.connect(ruta)
    try:
        if con_productos:
            conexion.execute(
                "CREATE TABLE productos_stock (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "usuario_id INTEGER NOT NULL, nombre TEXT NOT NULL, cantidad REAL NOT NULL, "
                "unidad TEXT NOT NULL, categoria TEXT NOT NULL)"
            )
            for p in productos or []:
                conexion.execute(
                    "INSERT INTO productos_stock (usuario_id, nombre, cantidad, unidad, categoria) "
                    "VALUES (1, ?, ?, ?, ?)",
                    (p["nombre"], p["cantidad"], p["unidad"], p["categoria"]),
                )
        if con_entrenos:
            conexion.execute(
                "CREATE TABLE entrenos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "usuario_id INTEGER NOT NULL, fecha TEXT NOT NULL, tipo TEXT NOT NULL, "
                "duracion_min INTEGER NOT NULL, intensidad TEXT NOT NULL, "
                "calorias INTEGER NOT NULL, origen TEXT NOT NULL DEFAULT 'manual', "
                # Bug 033 — `miembro_id` con el MISMO esqueleto que la real (comprobado con
                # `.schema` contra la SQLite real de la 022, ver la ficha del bug): NULL =
                # titular, un id = otro miembro de la casa. Se añade aquí, al fixture
                # COMPARTIDO por los ~50 tests de la 022, en vez de en uno aparte: así CUALQUIER
                # test que no lo declare (la inmensa mayoría) sigue significando "es del
                # titular" sin tener que saber que la columna existe.
                "strava_id TEXT, miembro_id INTEGER)"
            )
            for e in entrenos or []:
                conexion.execute(
                    "INSERT INTO entrenos "
                    "(usuario_id, fecha, tipo, duracion_min, intensidad, calorias, origen, "
                    "strava_id, miembro_id) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        e["fecha"],
                        e["tipo"],
                        e["duracion_min"],
                        e["intensidad"],
                        e["calorias"],
                        e.get("origen", "manual"),
                        e.get("strava_id"),
                        e.get("miembro_id"),
                    ),
                )
        if con_recetas:
            conexion.execute(
                "CREATE TABLE recetas (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "usuario_id INTEGER NOT NULL, nombre TEXT NOT NULL, "
                "raciones_base INTEGER NOT NULL, tipo_comida TEXT NOT NULL, "
                "ingredientes TEXT NOT NULL, preparacion TEXT NOT NULL DEFAULT '')"
            )
            for r in recetas or []:
                conexion.execute(
                    "INSERT INTO recetas "
                    "(usuario_id, nombre, raciones_base, tipo_comida, ingredientes, preparacion) "
                    "VALUES (1, ?, ?, ?, ?, ?)",
                    (
                        r["nombre"],
                        r["raciones_base"],
                        r["tipo_comida"],
                        json.dumps(r["ingredientes"]),
                        r.get("preparacion", ""),
                    ),
                )
        if con_pesos:
            conexion.execute(
                "CREATE TABLE pesos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "usuario_id INTEGER NOT NULL, fecha TEXT NOT NULL, peso_kg REAL NOT NULL, "
                # Bug 033 — mismo motivo que en `entrenos` de arriba: `miembro_id` en el
                # fixture compartido, NULL por defecto (titular) salvo que el test lo declare.
                "grasa_pct REAL, cintura_cm REAL, miembro_id INTEGER)"
            )
            for p in pesos or []:
                conexion.execute(
                    "INSERT INTO pesos (usuario_id, fecha, peso_kg, grasa_pct, cintura_cm, "
                    "miembro_id) VALUES (1, ?, ?, ?, ?, ?)",
                    (
                        p["fecha"],
                        p["peso_kg"],
                        p.get("grasa_pct"),
                        p.get("cintura_cm"),
                        p.get("miembro_id"),
                    ),
                )
        if con_strava_cuentas:
            # Trampa deliberada para R8/"Fuera de alcance": si algún día alguien tocara
            # `origen.py` para leer esta tabla, este fichero de tests ya trae un valor que
            # PARECE un secreto (nunca uno real, R8) y que ningún test de abajo debe ver salir
            # por ningún lado.
            conexion.execute(
                "CREATE TABLE strava_cuentas (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "usuario_id INTEGER NOT NULL, access_token TEXT NOT NULL)"
            )
            conexion.execute(
                "INSERT INTO strava_cuentas (usuario_id, access_token) VALUES "
                "(1, 'TOKEN-DE-MENTIRA-QUE-NO-DEBE-APARECER-NUNCA')"
            )
        conexion.commit()
    finally:
        conexion.close()


class BaseImportacionTests(TestCase):
    """Una cuenta con su hogar YA CREADO (R6: 'cuelga de una cuenta que ya existe'), y una ruta
    de SQLite temporal que cada test rellena con `_crear_sqlite_de_node`. Se crea con el ORM
    directamente (patrón ya usado en `planes/tests.py:519` y `perfiles/tests.py:1098` para
    pruebas que no son de una vista): este comando no es una pantalla, no hay HTTP que recorrer
    de camino a él."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ruta_db = os.path.join(self._tmp.name, "node-de-mentira.db")

        self.cuenta = Usuario.objects.create_user(email="prueba@example.com", password="x")
        self.usuario = Persona.objects.get(usuario=self.cuenta)
        crear_hogar_propio(self.usuario)
        self.hogar = self.usuario.hogar

    def _importar(self, *, dry_run=False, cuenta=None, ruta=None, miembro_node=None):
        # Bug 033 — `miembro_node` es opcional y por defecto `None` (== ninguno declarado, el
        # `[]` de fábrica de `add_arguments`): los ~50 tests de la 022 que NO lo pasan siguen
        # exactamente igual que antes, sin tener que saber que el parámetro existe.
        salida = io.StringIO()
        call_command(
            "importar_datos_node",
            ruta or self.ruta_db,
            cuenta=cuenta or self.cuenta.email,
            dry_run=dry_run,
            miembro_node=miembro_node if miembro_node is not None else [],
            stdout=salida,
        )
        return salida.getvalue()

    def _contar(self):
        return {
            "despensa": ProductoDespensa.objects.filter(hogar=self.hogar).count(),
            "entrenos": Entreno.objects.filter(persona=self.usuario).count(),
            "pesadas": MedicionPeso.objects.filter(persona=self.usuario).count(),
            "recetas": Receta.objects.filter(hogar=self.hogar).count(),
        }


# ---------------------------------------------------------------------------------------------
# R1 — la despensa pasa por `despensa.logica.anadir_producto`: convierte a canónica y funde.
# ---------------------------------------------------------------------------------------------


class R1_DespensaPorLaPuertaTests(BaseImportacionTests):
    def test_un_kilo_llega_como_mil_gramos_no_como_uno(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[{"nombre": "Arroz integral", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}],
        )
        self._importar()
        producto = ProductoDespensa.objects.get(hogar=self.hogar, nombre_normalizado="arroz integral")
        self.assertEqual(producto.cantidad, Decimal("1000.00"))
        self.assertEqual(producto.unidad, "g")

    def test_dos_lineas_del_mismo_producto_en_distinta_unidad_se_funden_sumando(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[
                {"nombre": "Lentejas", "cantidad": 1, "unidad": "kg", "categoria": "legumbre"},
                {"nombre": " lentejas ", "cantidad": 250, "unidad": "g", "categoria": "legumbre"},
            ],
        )
        self._importar()
        self.assertEqual(ProductoDespensa.objects.filter(hogar=self.hogar).count(), 1)
        producto = ProductoDespensa.objects.get(hogar=self.hogar)
        self.assertEqual(producto.cantidad, Decimal("1250.00"))
        self.assertEqual(producto.unidad, "g")

    def test_las_unidades_a_piezas_no_se_convierten_y_se_funden_entre_si(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[
                {"nombre": "Latas de tomate", "cantidad": 2, "unidad": "lata", "categoria": "verdura"},
                {"nombre": "Latas de tomate", "cantidad": 3, "unidad": "lata", "categoria": "verdura"},
            ],
        )
        self._importar()
        producto = ProductoDespensa.objects.get(hogar=self.hogar)
        self.assertEqual(producto.cantidad, Decimal("5.00"))
        self.assertEqual(producto.unidad, "lata")

    def test_litro_llega_como_mil_mililitros(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[{"nombre": "Leche de avena", "cantidad": 1.5, "unidad": "l", "categoria": "lacteo"}],
        )
        self._importar()
        producto = ProductoDespensa.objects.get(hogar=self.hogar)
        self.assertEqual(producto.cantidad, Decimal("1500.00"))
        self.assertEqual(producto.unidad, "ml")


# ---------------------------------------------------------------------------------------------
# R2 — idempotencia: dos pasadas seguidas dejan la base igual que una.
# ---------------------------------------------------------------------------------------------


class R2_IdempotenciaTests(BaseImportacionTests):
    def _fixture_completo(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[
                {"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"},
                {"nombre": "Aceite de oliva", "cantidad": 1, "unidad": "l", "categoria": "aceite_grasa"},
            ],
            entrenos=[
                {"fecha": "2026-03-01", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300},
            ],
            recetas=[
                {
                    "nombre": "Tortilla de patatas",
                    "raciones_base": 2,
                    "tipo_comida": "comida",
                    "ingredientes": [
                        {"alimento": "Huevo", "cantidad": 4, "unidad": "ud"},
                        {"alimento": "Patata", "cantidad": 500, "unidad": "g"},
                    ],
                    "preparacion": "Se pela, se fríe y se cuaja.",
                }
            ],
            pesos=[{"fecha": "2026-03-01", "peso_kg": 71.2, "grasa_pct": None, "cintura_cm": None}],
        )

    def test_segunda_pasada_no_duplica_nada_en_ninguna_tabla(self):
        self._fixture_completo()

        salida_1 = self._importar()
        tras_primera = self._contar()
        self.assertEqual(tras_primera, {"despensa": 2, "entrenos": 1, "pesadas": 1, "recetas": 1})
        self.assertIn("Despensa: 2 en Node -> 2 nuevos, 0 ya estaban.", salida_1)
        self.assertIn("Entrenos: 1 en Node -> 1 nuevos, 0 ya estaban.", salida_1)
        self.assertIn("Pesadas: 1 en Node -> 1 nuevos, 0 ya estaban.", salida_1)
        self.assertIn("Recetas: 1 en Node -> 1 nuevos, 0 ya estaban.", salida_1)

        salida_2 = self._importar()
        tras_segunda = self._contar()

        self.assertEqual(tras_primera, tras_segunda)
        self.assertIn("Despensa: 2 en Node -> 0 nuevos, 2 ya estaban.", salida_2)
        self.assertIn("Entrenos: 1 en Node -> 0 nuevos, 1 ya estaban.", salida_2)
        self.assertIn("Pesadas: 1 en Node -> 0 nuevos, 1 ya estaban.", salida_2)
        self.assertIn("Recetas: 1 en Node -> 0 nuevos, 1 ya estaban.", salida_2)

        # Los ingredientes tampoco se duplican (no solo la cabecera de la receta).
        receta = Receta.objects.get(hogar=self.hogar)
        self.assertEqual(receta.ingredientes.count(), 2)

    def test_entrenos_del_mismo_dia_y_deporte_pero_distintos_no_se_confunden_entre_si(self):
        """La clave de idempotencia elegida (R2, ver docstring de `mapeo.py`) es la tupla
        completa, no 'fecha+tipo': dos entrenos reales del mismo día y deporte, con minutos y
        calorías distintos, tienen que entrar los DOS (no es una repetición, son dos entrenos
        de verdad) — y una repetición exacta de una fila ya importada sí se reconoce."""
        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[
                {"fecha": "2026-03-01", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300},
                {"fecha": "2026-03-01", "tipo": "correr", "duracion_min": 45, "intensidad": "media", "calorias": 450},
            ],
        )
        self._importar()
        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 2)

        # Repetir la pasada: las DOS ya existen, ninguna se duplica.
        salida = self._importar()
        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 2)
        self.assertIn("Entrenos: 2 en Node -> 0 nuevos, 2 ya estaban.", salida)


# ---------------------------------------------------------------------------------------------
# R3 — `--dry-run`: cero escrituras, y aun así informa contando por tabla.
# ---------------------------------------------------------------------------------------------


class R3_DryRunTests(BaseImportacionTests):
    def test_dry_run_no_escribe_nada_e_informa_lo_que_haria(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}],
            entrenos=[{"fecha": "2026-03-01", "tipo": "bici", "duracion_min": 40, "intensidad": "baja", "calorias": 250}],
            recetas=[
                {
                    "nombre": "Ensalada",
                    "raciones_base": 1,
                    "tipo_comida": "cualquiera",
                    "ingredientes": [{"alimento": "Lechuga", "cantidad": 100, "unidad": "g"}],
                    "preparacion": "Se lava y se mezcla.",
                }
            ],
            pesos=[{"fecha": "2026-03-01", "peso_kg": 80.0, "grasa_pct": 20.5, "cintura_cm": 90.0}],
        )
        antes = self._contar()
        self.assertEqual(antes, {"despensa": 0, "entrenos": 0, "pesadas": 0, "recetas": 0})

        salida = self._importar(dry_run=True)
        despues = self._contar()

        self.assertEqual(antes, despues)
        self.assertIn("[DRY-RUN]", salida)
        self.assertIn("Despensa: 1 en Node -> 1 nuevos, 0 ya estaban.", salida)
        self.assertIn("Entrenos: 1 en Node -> 1 nuevos, 0 ya estaban.", salida)
        self.assertIn("Pesadas: 1 en Node -> 1 nuevos, 0 ya estaban.", salida)
        self.assertIn("Recetas: 1 en Node -> 1 nuevos, 0 ya estaban.", salida)

    def test_dry_run_repetido_no_escribe_nada_tampoco_la_segunda_vez(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}],
        )
        self._importar(dry_run=True)
        antes = self._contar()
        self._importar(dry_run=True)
        despues = self._contar()
        self.assertEqual(antes, despues)
        self.assertEqual(despues["despensa"], 0)


# ---------------------------------------------------------------------------------------------
# R4 — entrenos y pesadas llegan intactos (sin redondear), y una pesada que choca se salta.
# ---------------------------------------------------------------------------------------------


class R4_EntrenosYPesadasIntactosTests(BaseImportacionTests):
    def test_entreno_llega_con_fecha_calorias_y_valores_intactos(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[
                {"fecha": "2026-02-14", "tipo": "bici", "duracion_min": 47, "intensidad": "alta", "calorias": 611},
            ],
        )
        self._importar()
        entreno = Entreno.objects.get(persona=self.usuario)
        self.assertEqual(entreno.fecha, date(2026, 2, 14))
        self.assertEqual(entreno.deporte, "bici")
        self.assertEqual(entreno.intensidad, "fuerte")  # G-71: 'alta' de Node -> 'fuerte' del plano
        self.assertEqual(entreno.minutos, 47)
        self.assertEqual(entreno.calorias, 611)
        self.assertTrue(entreno.calorias_manuales)  # nunca se reestima: ya traía sus calorías

    def test_pesada_llega_sin_redondear_incluida_la_grasa_y_la_cintura(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[{"fecha": "2026-02-14", "peso_kg": 70.3, "grasa_pct": 18.2, "cintura_cm": 81.5}],
        )
        self._importar()
        pesada = MedicionPeso.objects.get(persona=self.usuario)
        self.assertEqual(pesada.peso_kg, Decimal("70.3"))
        self.assertEqual(pesada.grasa_pct, Decimal("18.2"))
        self.assertEqual(pesada.cintura_cm, Decimal("81.5"))

    def test_pesada_sin_grasa_ni_cintura_llega_con_esos_campos_vacios(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[{"fecha": "2026-02-14", "peso_kg": 65.0, "grasa_pct": None, "cintura_cm": None}],
        )
        self._importar()
        pesada = MedicionPeso.objects.get(persona=self.usuario)
        self.assertIsNone(pesada.grasa_pct)
        self.assertIsNone(pesada.cintura_cm)

    def test_una_pesada_que_choca_con_una_ya_existente_se_salta_y_no_revienta(self):
        """R4, caso límite: si la persona (o una pasada anterior) YA tiene una medición ese
        día, la fila de Node no se sobrescribe -- se salta, se cuenta como 'ya estaba' y el
        comando sigue sin reventar contra la restricción 'una_medicion_por_persona_y_dia'
        (unidad 006)."""
        MedicionPeso.objects.create(persona=self.usuario, fecha=date(2026, 2, 14), peso_kg=Decimal("99.9"))
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[{"fecha": "2026-02-14", "peso_kg": 70.3, "grasa_pct": None, "cintura_cm": None}],
        )
        salida = self._importar()
        # No revienta, y NO sobrescribe: sigue siendo la medición que ya había.
        pesada = MedicionPeso.objects.get(persona=self.usuario, fecha=date(2026, 2, 14))
        self.assertEqual(pesada.peso_kg, Decimal("99.9"))
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)
        self.assertIn("Pesadas: 1 en Node -> 0 nuevos, 1 ya estaban.", salida)

    def test_dos_pesadas_de_node_con_la_misma_fecha_se_salta_la_segunda_y_no_revienta(self):
        """H1 de la ronda 1 de revisión: el índice único de Node es
        `(usuario_id, COALESCE(miembro_id, 0), fecha)` -- permite DOS pesadas el mismo día si
        son de personas distintas de la misma casa (`miembro_id` no se lee, "Fuera de
        alcance"). Pero aquí las dos cuelgan del MISMO `usuario` de Django, y su restricción
        'una_medicion_por_persona_y_dia' (unidad 006) no admite dos filas del mismo día. Antes
        del arreglo, la foto `existentes_al_empezar` se tomaba una sola vez al principio de la
        pasada: la SEGUNDA fila de Node de ese día no estaba en esa foto (la primera solo se
        guarda en Django DURANTE esta misma pasada) y llegaba desnuda a
        `MedicionPeso.objects.create()`, que revienta con `IntegrityError` -- sin atrapar en
        `handle()`, así que el usuario veía una traza cruda de Python (R7) en vez del 'se
        salta y lo dice' que pide R4. No es un caso teórico: la base real de Node YA tiene dos
        pesadas de personas distintas con miembro_id (None, 4)."""
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[
                {"fecha": "2026-02-14", "peso_kg": 70.3, "grasa_pct": None, "cintura_cm": None},
                {"fecha": "2026-02-14", "peso_kg": 71.1, "grasa_pct": None, "cintura_cm": None},
            ],
        )
        salida = self._importar()  # no debe reventar con IntegrityError

        # Se queda con la PRIMERA fila de Node de ese día; la segunda se salta, no se sobrescribe.
        pesada = MedicionPeso.objects.get(persona=self.usuario, fecha=date(2026, 2, 14))
        self.assertEqual(pesada.peso_kg, Decimal("70.3"))
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)

        # Y lo dice: 1 nuevo, 0 "ya estaban" (ninguna existía antes de esta pasada) y la
        # colisión nombrada aparte, no disfrazada de "ya estaba".
        self.assertIn("Pesadas: 2 en Node -> 1 nuevos, 0 ya estaban.", salida)
        self.assertIn(
            "Pesadas: 1 más se ha saltado por chocar en fecha con otra fila de Node de esta "
            "misma pasada (una persona no puede tener dos pesadas el mismo día).",
            salida,
        )

    def test_dos_pesadas_de_node_con_la_misma_fecha_no_revientan_tampoco_con_dry_run(self):
        """El mismo caso límite que arriba, pero con `--dry-run` (R3): es el modo pensado para
        mirar ANTES de tocar la base, así que con más razón no puede reventar con una traza
        cruda. Antes del arreglo, `--dry-run` reventaba igual porque ejecuta el mismo código de
        escritura de verdad (ver el docstring del comando, "`--dry-run` no es una simulación
        paralela")."""
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[
                {"fecha": "2026-02-14", "peso_kg": 70.3, "grasa_pct": None, "cintura_cm": None},
                {"fecha": "2026-02-14", "peso_kg": 71.1, "grasa_pct": None, "cintura_cm": None},
            ],
        )
        salida = self._importar(dry_run=True)  # no debe reventar

        # No se escribió nada de verdad.
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 0)
        self.assertIn("Pesadas: 2 en Node -> 1 nuevos, 0 ya estaban.", salida)
        self.assertIn(
            "Pesadas: 1 más se ha saltado por chocar en fecha con otra fila de Node de esta "
            "misma pasada (una persona no puede tener dos pesadas el mismo día).",
            salida,
        )


# ---------------------------------------------------------------------------------------------
# R5 — las recetas: ingredientes de JSON a filas, preparación literal, comidas traducidas.
# ---------------------------------------------------------------------------------------------


class R5_RecetasTests(BaseImportacionTests):
    def test_ingredientes_de_json_llegan_como_filas_de_ingredientedereceta(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            recetas=[
                {
                    "nombre": "Crema de calabaza",
                    "raciones_base": 4,
                    "tipo_comida": "cena",
                    "ingredientes": [
                        {"alimento": "Calabaza", "cantidad": 800, "unidad": "g"},
                        {"alimento": "Caldo de verduras", "cantidad": 500, "unidad": "ml"},
                        {"alimento": "Cebolla", "cantidad": 1, "unidad": "ud"},
                    ],
                    "preparacion": "Se sofríe la cebolla, se añade la calabaza y el caldo, y se tritura.",
                }
            ],
        )
        self._importar()
        receta = Receta.objects.get(hogar=self.hogar, nombre="Crema de calabaza")
        self.assertEqual(receta.raciones, 4)
        ingredientes = list(receta.ingredientes.order_by("id"))
        self.assertEqual(len(ingredientes), 3)
        self.assertEqual(ingredientes[0].nombre, "Calabaza")
        self.assertEqual(ingredientes[0].cantidad, Decimal("800.00"))
        self.assertEqual(ingredientes[0].unidad, "g")
        self.assertEqual(ingredientes[1].unidad, "ml")
        self.assertEqual(ingredientes[2].unidad, "ud")

    def test_preparacion_llega_literal_caracter_por_caracter(self):
        texto = "Paso 1: pelar.\nPaso 2 (¡ojo!): no pasarse de sal — 100% al gusto.\n\tTip: usar aceite de oliva."
        _crear_sqlite_de_node(
            self.ruta_db,
            recetas=[
                {
                    "nombre": "Receta con texto raro",
                    "raciones_base": 1,
                    "tipo_comida": "snack",
                    "ingredientes": [{"alimento": "Algo", "cantidad": 1, "unidad": "ud"}],
                    "preparacion": texto,
                }
            ],
        )
        self._importar()
        receta = Receta.objects.get(hogar=self.hogar)
        self.assertEqual(receta.preparacion, texto)

    def test_tipo_comida_cualquiera_se_traduce_a_lista_vacia(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            recetas=[
                {
                    "nombre": "Vale para cualquier comida",
                    "raciones_base": 1,
                    "tipo_comida": "cualquiera",
                    "ingredientes": [{"alimento": "Algo", "cantidad": 1, "unidad": "ud"}],
                    "preparacion": "",
                }
            ],
        )
        self._importar()
        receta = Receta.objects.get(hogar=self.hogar)
        self.assertEqual(receta.comidas, [])

    def test_tipo_comida_concreto_se_traduce_a_lista_de_un_elemento(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            recetas=[
                {
                    "nombre": "Solo desayuno",
                    "raciones_base": 1,
                    "tipo_comida": "desayuno",
                    "ingredientes": [{"alimento": "Algo", "cantidad": 1, "unidad": "ud"}],
                    "preparacion": "",
                }
            ],
        )
        self._importar()
        receta = Receta.objects.get(hogar=self.hogar)
        self.assertEqual(receta.comidas, ["desayuno"])


# ---------------------------------------------------------------------------------------------
# R6 — aislamiento: todo cuelga del hogar de la cuenta elegida, y de nadie más.
# ---------------------------------------------------------------------------------------------


class R6_AislamientoTests(BaseImportacionTests):
    def test_lo_importado_no_aparece_en_otro_hogar(self):
        otro_usuario = Persona.objects.get(
            usuario=Usuario.objects.create_user(email="otra-cuenta@example.com", password="x")
        )
        crear_hogar_propio(otro_usuario)

        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}],
            recetas=[
                {
                    "nombre": "Receta de la cuenta A",
                    "raciones_base": 1,
                    "tipo_comida": "cualquiera",
                    "ingredientes": [{"alimento": "Algo", "cantidad": 1, "unidad": "ud"}],
                    "preparacion": "",
                }
            ],
        )
        self._importar()

        self.assertEqual(ProductoDespensa.objects.filter(hogar=self.hogar).count(), 1)
        self.assertEqual(ProductoDespensa.objects.filter(hogar=otro_usuario.hogar).count(), 0)
        self.assertEqual(Receta.objects.filter(hogar=self.hogar).count(), 1)
        self.assertEqual(Receta.objects.filter(hogar=otro_usuario.hogar).count(), 0)

    def test_entrenos_y_pesadas_no_aparecen_en_otra_cuenta(self):
        otro_usuario = Persona.objects.get(
            usuario=Usuario.objects.create_user(email="otra-cuenta@example.com", password="x")
        )
        crear_hogar_propio(otro_usuario)

        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[{"fecha": "2026-03-01", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300}],
            pesos=[{"fecha": "2026-03-01", "peso_kg": 70.0, "grasa_pct": None, "cintura_cm": None}],
        )
        self._importar()

        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 1)
        self.assertEqual(Entreno.objects.filter(persona=otro_usuario).count(), 0)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(persona=otro_usuario).count(), 0)

    def test_una_cuenta_sin_hogar_todavia_no_deja_importar(self):
        """Caso límite de R6: mientras espera a que la acepten en un hogar (unidad 003), una
        cuenta no tiene ningún hogar propio todavía. El comando falla en cristiano, sin tocar
        nada, en vez de dejar algo colgado sin hogar."""
        huerfano = Usuario.objects.create_user(email="esperando@example.com", password="x")
        self.assertIsNone(huerfano.persona.hogar)

        _crear_sqlite_de_node(self.ruta_db, productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}])

        with self.assertRaises(CommandError) as cm:
            self._importar(cuenta=huerfano.email)
        self.assertIn("no tiene hogar", str(cm.exception))
        self.assertEqual(ProductoDespensa.objects.count(), 0)

    def test_kcalibra_tests_aislamiento_sigue_en_verde(self):
        """No repite el check de la 020 entero (vive en `kcalibra/tests_aislamiento.py`), pero
        deja constancia aquí de que esta unidad no le abre ningún agujero: `importacion/` no
        aparece nunca en la lista de infracciones que ese check calcula."""
        from kcalibra.tests_aislamiento import analizar_repositorio

        infracciones, _ = analizar_repositorio()
        de_importacion = [inf for inf in infracciones if inf[0].startswith("importacion" + os.sep)]
        self.assertEqual(de_importacion, [])


# ---------------------------------------------------------------------------------------------
# R7 — el origen no está: falla diciendo qué falta, sin trazas crudas, sin dejar nada a medias.
# ---------------------------------------------------------------------------------------------


class R7_OrigenInvalidoTests(BaseImportacionTests):
    def test_ruta_inexistente_falla_en_cristiano(self):
        ruta_que_no_existe = os.path.join(self._tmp.name, "no-existe.db")
        with self.assertRaises(CommandError) as cm:
            self._importar(ruta=ruta_que_no_existe)
        self.assertIn("No existe ninguna base de datos", str(cm.exception))

    def test_falta_una_tabla_falla_nombrandola(self):
        _crear_sqlite_de_node(self.ruta_db, con_pesos=False)
        with self.assertRaises(CommandError) as cm:
            self._importar()
        self.assertIn("pesos", str(cm.exception))

    def test_faltan_varias_tablas_las_nombra_todas(self):
        _crear_sqlite_de_node(self.ruta_db, con_pesos=False, con_recetas=False)
        with self.assertRaises(CommandError) as cm:
            self._importar()
        mensaje = str(cm.exception)
        self.assertIn("pesos", mensaje)
        self.assertIn("recetas", mensaje)

    def test_fichero_que_no_es_una_sqlite_falla_en_cristiano(self):
        ruta_basura = os.path.join(self._tmp.name, "no-es-una-db.db")
        with open(ruta_basura, "w", encoding="utf-8") as f:
            f.write("esto no es una base de datos SQLite")
        with self.assertRaises(CommandError):
            self._importar(ruta=ruta_basura)

    def test_cuenta_inexistente_falla_sin_tocar_nada(self):
        _crear_sqlite_de_node(self.ruta_db, productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}])
        with self.assertRaises(CommandError) as cm:
            self._importar(cuenta="no-existe@example.com")
        self.assertIn("No existe ninguna cuenta", str(cm.exception))
        self.assertEqual(ProductoDespensa.objects.count(), 0)

    def test_un_dato_que_no_se_sabe_traducir_deshace_todo_lo_escrito(self):
        """R7 generalizado: una unidad de despensa que no existe en la app nueva no deja
        media importación hecha -- el producto válido que iba ANTES en la misma pasada
        también se deshace (todo o nada, "sin dejar la base a medias")."""
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[
                {"nombre": "Producto válido", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"},
                {"nombre": "Producto raro", "cantidad": 1, "unidad": "toneladas", "categoria": "cereal_pan"},
            ],
        )
        with self.assertRaises(CommandError) as cm:
            self._importar()
        self.assertIn("toneladas", str(cm.exception))
        self.assertEqual(ProductoDespensa.objects.count(), 0)


# ---------------------------------------------------------------------------------------------
# R8 — ni un secreto ni un dato personal: nunca se lee `strava_cuentas`, y estos tests jamás
# tocan la base real de Node.
# ---------------------------------------------------------------------------------------------


class R8_NiSecretosNiDatosRealesTests(BaseImportacionTests):
    def test_strava_cuentas_no_se_lee_aunque_este_presente_en_el_origen(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}],
            con_strava_cuentas=True,
        )
        salida = self._importar()
        self.assertNotIn("TOKEN-DE-MENTIRA", salida)
        self.assertNotIn("access_token", salida)
        self.assertNotIn("strava", salida.lower())

    def test_origen_requeridas_no_incluye_ninguna_tabla_de_identidad_ni_de_strava(self):
        self.assertNotIn("usuarios", origen.TABLAS_REQUERIDAS)
        self.assertNotIn("miembros_hogar", origen.TABLAS_REQUERIDAS)
        self.assertNotIn("strava_cuentas", origen.TABLAS_REQUERIDAS)
        self.assertNotIn("memoria", origen.TABLAS_REQUERIDAS)

    def test_ningun_test_de_este_fichero_abre_la_base_real_de_node(self):
        """Contraprueba estructural, barata y explícita: ninguna clase de test de este módulo
        pasa una ruta que no sea `self.ruta_db` (la SQLite de mentira de `setUp`) a `_importar`
        -- todas construyen su propia SQLite con `_crear_sqlite_de_node`. Se comprueba mirando
        el CUERPO de cada `test_*` (no el docstring del módulo, que sí puede nombrar la ruta
        real en prosa al explicar la regla) en busca de la única otra forma de pasar una ruta:
        el argumento con nombre `ruta=` de `_importar`, que en TODOS los tests reales apunta a
        un fichero dentro de `self._tmp` (el `TemporaryDirectory` de `setUp`)."""
        import ast

        with open(__file__, encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "_importar":
                for kw in nodo.keywords:
                    if kw.arg == "ruta" and isinstance(kw.value, ast.Constant):
                        self.fail(
                            "un test pasa una ruta LITERAL a `_importar(ruta=...)`: tiene que "
                            "ser siempre una ruta calculada dentro de un directorio temporal"
                        )


# ---------------------------------------------------------------------------------------------
# `importacion/mapeo.py` — funciones puras, probadas sin base de datos (salvo las que validan
# contra catálogos de modelos, que Django ya tiene cargados aunque el test no toque ninguna fila).
# ---------------------------------------------------------------------------------------------


class MapeoTests(TestCase):
    def test_traducir_intensidad_las_tres_formas(self):
        self.assertEqual(mapeo.traducir_intensidad("baja"), "suave")
        self.assertEqual(mapeo.traducir_intensidad("media"), "media")
        self.assertEqual(mapeo.traducir_intensidad("alta"), "fuerte")

    def test_traducir_intensidad_desconocida_revienta_en_cristiano(self):
        with self.assertRaises(mapeo.DatosNodeInvalidos):
            mapeo.traducir_intensidad("extrema")

    def test_traducir_comidas_cualquiera_es_lista_vacia(self):
        self.assertEqual(mapeo.traducir_comidas("cualquiera"), [])

    def test_traducir_comidas_valor_concreto(self):
        self.assertEqual(mapeo.traducir_comidas("cena"), ["cena"])

    def test_traducir_comidas_desconocida_revienta(self):
        with self.assertRaises(mapeo.DatosNodeInvalidos):
            mapeo.traducir_comidas("brunch")

    def test_decimal_desde_float_no_arrastra_ruido_binario(self):
        # 0.1 + 0.2 en coma flotante binaria no da 0.3 exacto; Decimal(str(...)) sí.
        self.assertEqual(mapeo._decimal(0.1), Decimal("0.1"))
        self.assertEqual(mapeo._decimal(0.429), Decimal("0.429"))

    def test_clave_producto_normaliza_nombre_e_ignora_mayusculas_y_espacios(self):
        clave_1 = mapeo.clave_producto("  Arroz  ", "kg")
        clave_2 = mapeo.clave_producto("ARROZ", "g")
        self.assertEqual(clave_1, clave_2)
        self.assertEqual(clave_1, ("arroz", "g"))

    def test_clave_producto_unidad_desconocida_revienta(self):
        with self.assertRaises(mapeo.DatosNodeInvalidos):
            mapeo.clave_producto("Arroz", "toneladas")

    def test_clave_entreno_es_la_tupla_completa_sin_el_usuario(self):
        datos = {"fecha": date(2026, 1, 1), "deporte": "correr", "intensidad": "suave", "minutos": 30, "calorias": 300}
        self.assertEqual(mapeo.clave_entreno(datos), (date(2026, 1, 1), "correr", "suave", 30, 300))

    def test_mapear_ingredientes_json_valido(self):
        texto = json.dumps([{"alimento": "Huevo", "cantidad": 3, "unidad": "ud"}])
        ingredientes = mapeo.mapear_ingredientes(texto)
        self.assertEqual(ingredientes, [{"nombre": "Huevo", "cantidad": Decimal("3"), "unidad": "ud"}])

    def test_mapear_ingredientes_json_invalido_revienta_en_cristiano(self):
        with self.assertRaises(mapeo.DatosNodeInvalidos):
            mapeo.mapear_ingredientes("esto no es json")

    def test_mapear_ingredientes_lista_vacia_revienta(self):
        with self.assertRaises(mapeo.DatosNodeInvalidos):
            mapeo.mapear_ingredientes("[]")

    def test_mapear_ingredientes_unidad_desconocida_revienta(self):
        texto = json.dumps([{"alimento": "Algo", "cantidad": 1, "unidad": "toneladas"}])
        with self.assertRaises(mapeo.DatosNodeInvalidos):
            mapeo.mapear_ingredientes(texto)

    def test_nombre_normalizado_recorta_y_pone_en_minusculas(self):
        self.assertEqual(mapeo.nombre_normalizado("  Tortilla De Patatas  "), "tortilla de patatas")


class OrigenTests(TestCase):
    """`importacion/origen.py`: abrir la SQLite de Node (siempre inventada aquí) y validar que
    trae lo necesario (R7)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ruta_db = os.path.join(self._tmp.name, "node-de-mentira.db")

    def test_abrir_ruta_inexistente_revienta_en_cristiano(self):
        with self.assertRaises(origen.OrigenNodeInvalido):
            origen.abrir(os.path.join(self._tmp.name, "no-existe.db"))

    def test_abrir_sin_ruta_revienta(self):
        with self.assertRaises(origen.OrigenNodeInvalido):
            origen.abrir("")

    def test_abrir_con_las_cuatro_tablas_funciona_y_es_de_solo_lectura(self):
        _crear_sqlite_de_node(self.ruta_db, productos=[{"nombre": "Arroz", "cantidad": 1, "unidad": "kg", "categoria": "cereal_pan"}])
        conexion = origen.abrir(self.ruta_db)
        try:
            filas = origen.productos_despensa(conexion)
            self.assertEqual(len(filas), 1)
            with self.assertRaises(sqlite3.OperationalError):
                conexion.execute("INSERT INTO productos_stock (usuario_id, nombre, cantidad, unidad, categoria) VALUES (1,'x',1,'kg','otro')")
        finally:
            conexion.close()

    def test_falta_la_tabla_de_entrenos_revienta_nombrandola(self):
        _crear_sqlite_de_node(self.ruta_db, con_entrenos=False)
        with self.assertRaises(origen.OrigenNodeInvalido) as cm:
            origen.abrir(self.ruta_db)
        self.assertIn("entrenos", str(cm.exception))


# ---------------------------------------------------------------------------------------------
# BUG 033 — `entrenos`/`pesos` de Node traen `miembro_id` (NULL = titular, un id = otro
# miembro de la casa) y antes de esta unidad esa columna no se leía: TODO colgaba del titular,
# sin importar de quién fuera. El arreglo (decisión 1, RESUELTA): un parámetro EXPLÍCITO,
# `--miembro-node <id-de-node>:<correo-o-id-de-persona>` — nunca un emparejamiento por nombre
# (medido en la ficha: `Persona.nombre` no es único) y nunca cuelga del titular por defecto
# (una fila con un `miembro_id` sin declarar hace fallar el comando ANTES de escribir nada).
# La decisión 2 (RESUELTA: mover, no borrar y reimportar) y la 3 (un comando de gestión propio,
# con `--dry-run` e idempotente, en vez de un `UPDATE` a mano) viven en
# `mover_filas_de_miembro.py`, probado más abajo.
# ---------------------------------------------------------------------------------------------


class Bug033_ImportacionPorMiembroTests(BaseImportacionTests):
    """El arreglo de la decisión 1: `importar_datos_node` traduce `miembro_id` a la `Persona`
    correcta vía `--miembro-node`, y falla en cristiano si a una fila le falta declarar el suyo."""

    MIEMBRO_ID_NODE = 4  # el mismo id que usa Node de verdad para Euridice (ver la ficha)

    def setUp(self):
        super().setUp()
        # Una "persona a cargo" (unidad 024, sin cuenta propia) de la misma casa que el
        # titular — el patrón real de `hogares/views.py:dar_de_alta_persona_a_cargo`. Esta
        # unidad no crea personas nuevas (fuera de alcance): en el arreglo de verdad esta
        # persona ya existiría ANTES de importar, aquí se crea porque el test la necesita de
        # antemano.
        self.miembro = Persona.objects.create(
            hogar=self.hogar, nombre="Miembro de la casa", responsable=self.usuario
        )
        self.spec_miembro = f"{self.MIEMBRO_ID_NODE}:{self.miembro.id}"

    def test_un_entreno_con_miembro_id_cuelga_del_miembro_no_del_titular(self):
        """Antes del arreglo este test estaba en ROJO (era
        `test_un_entreno_con_miembro_id_no_debe_colgar_del_titular` de la sección 2 de la
        ficha): 0 entrenos bajo el miembro, 2 bajo el titular. Con `--miembro-node` declarado,
        VERDE — sin haber tocado el test, solo el comando."""
        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[
                {"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": None},
                {"fecha": "2026-01-06", "tipo": "nadar", "duracion_min": 40, "intensidad": "alta", "calorias": 400, "miembro_id": self.MIEMBRO_ID_NODE},
            ],
        )
        self._importar(miembro_node=[self.spec_miembro])
        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 1)
        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 1)

    def test_una_pesada_con_miembro_id_cuelga_del_miembro_no_del_titular(self):
        """Misma reproducción que el test anterior, para `pesos` (la otra mitad del bug)."""
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[
                {"fecha": "2026-01-05", "peso_kg": 80.0, "miembro_id": None},
                {"fecha": "2026-01-05", "peso_kg": 60.0, "miembro_id": self.MIEMBRO_ID_NODE},
            ],
        )
        self._importar(miembro_node=[self.spec_miembro])
        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)

    def test_pesadas_del_titular_y_del_miembro_el_mismo_dia_no_colisionan(self):
        """El fallo que `existentes_al_empezar`/`vistas_en_esta_pasada` COMPARTIDOS habrían
        introducido: una pesada del titular y una del miembro el MISMO día no son una colisión
        (el índice único de Node ya las distingue por persona, `COALESCE(miembro_id, 0)`) — las
        dos tienen que crearse. Con el código de ANTES del arreglo (todo cuelga del titular sin
        mirar miembro_id) esto daba: 1 pesada bajo el titular y 0 bajo el miembro (la segunda se
        contaba como colisión consigo misma) — ROJO. Contraprobado: revertir `_importar_pesadas`
        a un solo `existentes_al_empezar`/`vistas_en_esta_pasada` (sin miembro_id) reproduce el
        rojo; con los dos por persona, VERDE."""
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[
                {"fecha": "2026-01-05", "peso_kg": 80.0, "miembro_id": None},
                {"fecha": "2026-01-05", "peso_kg": 60.0, "miembro_id": self.MIEMBRO_ID_NODE},
            ],
        )
        salida = self._importar(miembro_node=[self.spec_miembro])
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 1)
        self.assertNotIn("chocar en fecha", salida)

    def test_miembro_id_sin_correspondencia_revienta_antes_de_escribir_nada(self):
        """La parte de la decisión 1 que la ficha pidió explícitamente: sin `--miembro-node`
        declarado para un `miembro_id` que aparece en Node, el comando REVIENTA, dice CUÁL id
        falta, y no cuelga esa fila del titular por defecto ni la descarta callada — no escribe
        NADA, ni siquiera el entreno del titular que sí venía limpio."""
        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[
                {"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": None},
                {"fecha": "2026-01-06", "tipo": "nadar", "duracion_min": 40, "intensidad": "alta", "calorias": 400, "miembro_id": self.MIEMBRO_ID_NODE},
            ],
        )
        with self.assertRaises(CommandError) as cm:
            self._importar()  # sin --miembro-node: nadie declaró el id 4
        self.assertIn(str(self.MIEMBRO_ID_NODE), str(cm.exception))
        self.assertEqual(Entreno.objects.count(), 0, "No se ha escrito NADA, ni el entreno limpio del titular.")

    def test_miembro_node_formato_invalido_sin_dos_puntos_revienta(self):
        _crear_sqlite_de_node(self.ruta_db)
        with self.assertRaises(CommandError) as cm:
            self._importar(miembro_node=["formato-sin-dos-puntos"])
        self.assertIn("formato-sin-dos-puntos", str(cm.exception))

    def test_miembro_node_id_no_numerico_revienta(self):
        _crear_sqlite_de_node(self.ruta_db)
        with self.assertRaises(CommandError) as cm:
            self._importar(miembro_node=[f"cuatro:{self.miembro.id}"])
        self.assertIn("cuatro", str(cm.exception))

    def test_miembro_node_correo_inexistente_revienta(self):
        _crear_sqlite_de_node(
            self.ruta_db, entrenos=[{"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": self.MIEMBRO_ID_NODE}],
        )
        with self.assertRaises(CommandError) as cm:
            self._importar(miembro_node=[f"{self.MIEMBRO_ID_NODE}:no-existe@example.com"])
        self.assertIn("no-existe@example.com", str(cm.exception))

    def test_miembro_node_id_de_persona_inexistente_revienta(self):
        _crear_sqlite_de_node(
            self.ruta_db, entrenos=[{"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": self.MIEMBRO_ID_NODE}],
        )
        with self.assertRaises(CommandError) as cm:
            self._importar(miembro_node=[f"{self.MIEMBRO_ID_NODE}:999999"])
        self.assertIn("999999", str(cm.exception))

    def test_miembro_node_persona_de_otra_casa_revienta(self):
        """R6, generalizado: `--miembro-node` no puede colgar una fila de una persona que no
        vive en la casa del titular — la misma frontera que el resto del comando respeta."""
        otro_hogar = Hogar.objects.create()
        de_otra_casa = Persona.objects.create(hogar=otro_hogar, nombre="De otra casa")
        _crear_sqlite_de_node(
            self.ruta_db, entrenos=[{"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": self.MIEMBRO_ID_NODE}],
        )
        with self.assertRaises(CommandError) as cm:
            self._importar(miembro_node=[f"{self.MIEMBRO_ID_NODE}:{de_otra_casa.id}"])
        self.assertIn("misma casa", str(cm.exception))
        self.assertEqual(Entreno.objects.count(), 0)

    def test_miembro_node_repetido_revienta(self):
        _crear_sqlite_de_node(
            self.ruta_db, entrenos=[{"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": self.MIEMBRO_ID_NODE}],
        )
        otro_miembro = Persona.objects.create(hogar=self.hogar, nombre="Otro", responsable=self.usuario)
        with self.assertRaises(CommandError) as cm:
            self._importar(miembro_node=[self.spec_miembro, f"{self.MIEMBRO_ID_NODE}:{otro_miembro.id}"])
        self.assertIn(str(self.MIEMBRO_ID_NODE), str(cm.exception))

    def test_miembro_node_con_correo_de_cuenta_propia(self):
        """La otra forma de `--miembro-node` (la real, para Euridice: SÍ tiene cuenta propia,
        medido en la ficha): un correo, resuelto igual que `--cuenta`."""
        cuenta_miembro = Usuario.objects.create_user(email="miembro@example.com", password="x")
        persona_con_cuenta = Persona.objects.get(usuario=cuenta_miembro)
        persona_con_cuenta.hogar = self.hogar
        persona_con_cuenta.save(update_fields=["hogar"])

        _crear_sqlite_de_node(
            self.ruta_db, entrenos=[{"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": self.MIEMBRO_ID_NODE}],
        )
        self._importar(miembro_node=[f"{self.MIEMBRO_ID_NODE}:miembro@example.com"])
        self.assertEqual(Entreno.objects.filter(persona=persona_con_cuenta).count(), 1)

    def test_segunda_pasada_no_duplica_ni_al_titular_ni_al_miembro(self):
        """R2, generalizado a más de una persona: repetir el comando NO duplica nada, ni lo del
        titular ni lo del miembro — el criterio de aceptación del contrato (sección 1 de la
        ficha: '16 y 2 siguen siendo 16 y 2')."""
        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[
                {"fecha": "2026-01-05", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300, "miembro_id": None},
                {"fecha": "2026-01-06", "tipo": "nadar", "duracion_min": 40, "intensidad": "alta", "calorias": 400, "miembro_id": self.MIEMBRO_ID_NODE},
            ],
            pesos=[
                {"fecha": "2026-01-05", "peso_kg": 80.0, "miembro_id": None},
                {"fecha": "2026-01-06", "peso_kg": 60.0, "miembro_id": self.MIEMBRO_ID_NODE},
            ],
        )
        self._importar(miembro_node=[self.spec_miembro])
        self._importar(miembro_node=[self.spec_miembro])
        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 1)
        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 1)

    def test_H3_no_duplica_un_entreno_que_ya_existe_bajo_otra_persona_del_hogar(self):
        """H3 de la revisión (ronda 1): si este importador (ya arreglado) corre ANTES de
        `mover_filas_de_miembro` sobre una fila que el comando VIEJO dejó mal colgada del
        titular, NO debe crear un duplicado bajo la persona correcta — tiene que saltarla y
        avisarlo (nunca en silencio, R7)."""
        fila = {
            "fecha": "2026-02-15", "tipo": "correr", "duracion_min": 25,
            "intensidad": "baja", "calorias": 150, "miembro_id": self.MIEMBRO_ID_NODE,
        }
        # Simula el estado "recién detectado el bug, todavía sin mover": ya está, mal
        # colgado, bajo el titular — como lo dejó el comando VIEJO.
        apuntar_entreno(self.usuario, mapeo.datos_entreno(fila))
        _crear_sqlite_de_node(self.ruta_db, entrenos=[fila])

        salida = self._importar(miembro_node=[self.spec_miembro])

        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 0, "No se ha creado un duplicado.")
        self.assertEqual(Entreno.objects.count(), 1, "Sigue habiendo solo la fila vieja, mal colgada.")
        self.assertIn("mover_filas_de_miembro", salida)

    def test_H3_no_duplica_una_pesada_que_ya_existe_bajo_otra_persona_del_hogar(self):
        """Misma reproducción que el test anterior, para `pesos` — usa la tupla COMPLETA
        (fecha+peso+grasa+cintura), no solo la fecha: dos personas de la misma casa SÍ pueden
        tener, legítimamente, cada una su propia pesada el mismo día (eso no es un bug)."""
        fila = {"fecha": "2026-02-16", "peso_kg": 72.0, "grasa_pct": None, "cintura_cm": None, "miembro_id": self.MIEMBRO_ID_NODE}
        datos = mapeo.datos_pesada(fila)
        MedicionPeso.objects.create(persona=self.usuario, **datos)
        _crear_sqlite_de_node(self.ruta_db, pesos=[fila])

        salida = self._importar(miembro_node=[self.spec_miembro])

        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 0)
        self.assertEqual(MedicionPeso.objects.count(), 1)
        self.assertIn("mover_filas_de_miembro", salida)


# ---------------------------------------------------------------------------------------------
# BUG 033, decisiones 2 y 3 (RESUELTAS) — `mover_filas_de_miembro`: mueve las filas de
# `entrenos`/`pesos` que se importaron ANTES del arreglo (todas colgadas del titular) a la
# `Persona` correcta, identificándolas por su tupla completa (nunca por `id`), con `--dry-run`,
# de forma idempotente, y sin inventar si algo no está donde se espera.
# ---------------------------------------------------------------------------------------------


class Bug033_MoverFilasDeMiembroTests(BaseImportacionTests):
    MIEMBRO_ID_NODE = 4

    def setUp(self):
        super().setUp()
        self.miembro = Persona.objects.create(
            hogar=self.hogar, nombre="Miembro de la casa", responsable=self.usuario
        )
        self.spec_miembro = f"{self.MIEMBRO_ID_NODE}:{self.miembro.id}"
        # R8 ("sin un solo dato real dentro del repositorio"): fecha, deporte y peso
        # INVENTADOS aquí — ninguno coincide con los de la SQLite real de Node citada en la
        # ficha (id, fecha ni valores). La fila de Node "de mentira" que simula la que el
        # titular importó mal, en su día, con el comando de ANTES del arreglo.
        self.fila_entreno_miembro = {
            "fecha": "2026-02-10", "tipo": "bici", "duracion_min": 55,
            "intensidad": "baja", "calorias": 210, "miembro_id": self.MIEMBRO_ID_NODE,
        }
        self.fila_pesada_miembro = {
            "fecha": "2026-03-03", "peso_kg": 70.5, "grasa_pct": None, "cintura_cm": None,
            "miembro_id": self.MIEMBRO_ID_NODE,
        }

    def _sembrar_entreno_mal_colgado(self):
        """Simula el estado de la base ANTES del arreglo: este entreno de Euridice/miembro,
        importado por el comando VIEJO, cuelga hoy del titular. Se crea por la MISMA puerta que
        usaba el importador (`apuntar_entreno`), no por `create()` a pelo."""
        datos = mapeo.datos_entreno(self.fila_entreno_miembro)
        return apuntar_entreno(self.usuario, datos)

    def _sembrar_pesada_mal_colgada(self):
        datos = mapeo.datos_pesada(self.fila_pesada_miembro)
        return MedicionPeso.objects.create(persona=self.usuario, **datos)

    def _mover(self, *, dry_run=False, miembro_node=None, cuenta=None, ruta=None):
        salida = io.StringIO()
        call_command(
            "mover_filas_de_miembro",
            ruta or self.ruta_db,
            cuenta=cuenta or self.cuenta.email,
            miembro_node=miembro_node if miembro_node is not None else [self.spec_miembro],
            dry_run=dry_run,
            stdout=salida,
        )
        return salida.getvalue()

    def test_mueve_un_entreno_mal_colgado_del_titular_al_miembro(self):
        self._sembrar_entreno_mal_colgado()
        _crear_sqlite_de_node(self.ruta_db, entrenos=[self.fila_entreno_miembro])

        self._mover()

        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 0)
        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 1)

    def test_mueve_una_pesada_mal_colgada_del_titular_al_miembro(self):
        self._sembrar_pesada_mal_colgada()
        _crear_sqlite_de_node(self.ruta_db, pesos=[self.fila_pesada_miembro])

        self._mover()

        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 0)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 1)

    def test_dry_run_no_mueve_nada_pero_informa(self):
        self._sembrar_entreno_mal_colgado()
        _crear_sqlite_de_node(self.ruta_db, entrenos=[self.fila_entreno_miembro])

        salida = self._mover(dry_run=True)

        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 1, "Con --dry-run no se mueve NADA.")
        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 0)
        self.assertIn("1 movida", salida)

    def test_segunda_pasada_es_idempotente_no_mueve_nada(self):
        self._sembrar_entreno_mal_colgado()
        self._sembrar_pesada_mal_colgada()
        _crear_sqlite_de_node(
            self.ruta_db, entrenos=[self.fila_entreno_miembro], pesos=[self.fila_pesada_miembro],
        )

        self._mover()  # primera pasada: mueve de verdad
        salida_segunda = self._mover()  # segunda pasada: nada que mover

        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 1, "Sigue movido, no se duplicó.")
        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 1)
        self.assertIn("0 movida(s), 1 ya estaba(n) movida(s)", salida_segunda)

    def test_fila_duplicada_en_origen_y_destino_revienta_y_deshace_lo_ya_movido(self):
        """El riesgo medido en la ficha (sección 4): si alguien reejecuta el importador VIEJO
        tras mover, una fila queda EN LOS DOS SITIOS. El comando no adivina cuál es la buena:
        para, lo dice, y deshace TODO lo de esta pasada — incluida otra fila limpia que ya
        hubiera movido antes de toparse con la anómala (misma `transaction.atomic()`)."""
        fila_limpia = {
            "fecha": "2026-02-11", "tipo": "nadar", "duracion_min": 20,
            "intensidad": "alta", "calorias": 180, "miembro_id": self.MIEMBRO_ID_NODE,
        }
        apuntar_entreno(self.usuario, mapeo.datos_entreno(fila_limpia))  # limpia: solo bajo el titular

        self._sembrar_entreno_mal_colgado()  # bajo el titular...
        Entreno.objects.create(  # ...Y ya bajo el miembro (la duplicación medida)
            persona=self.miembro, **mapeo.datos_entreno(self.fila_entreno_miembro)
        )

        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[fila_limpia, self.fila_entreno_miembro],  # la limpia va primero
        )

        with self.assertRaises(CommandError) as cm:
            self._mover()
        self.assertIn("no están en un estado que el comando pueda explicar", str(cm.exception))
        # La fila LIMPIA, aunque hubiera sido segura por sí sola (va primero en Node), NO se
        # mueve: H1 de la revisión exige que el LOTE ENTERO del miembro esté íntegro para
        # tocar cualquiera de sus filas, y este lote no lo está (una de sus dos filas aparece
        # en los dos sitios a la vez).
        self.assertEqual(Entreno.objects.filter(persona=self.usuario, fecha="2026-02-11").count(), 1)
        self.assertEqual(Entreno.objects.filter(persona=self.miembro, fecha="2026-02-11").count(), 0)

    def test_fila_no_encontrada_en_ningun_sitio_revienta_sin_mover_nada(self):
        """Ni bajo el titular ni bajo el destino: el comando no la inventa, para y lo dice."""
        _crear_sqlite_de_node(self.ruta_db, entrenos=[self.fila_entreno_miembro])

        with self.assertRaises(CommandError) as cm:
            self._mover()
        self.assertIn("no están en un estado que el comando pueda explicar", str(cm.exception))
        self.assertIn("0 bajo el titular, 0 bajo el destino", str(cm.exception))

    def test_sin_ningun_miembro_node_revienta(self):
        _crear_sqlite_de_node(self.ruta_db, entrenos=[self.fila_entreno_miembro])
        with self.assertRaises(CommandError) as cm:
            self._mover(miembro_node=[])
        self.assertIn("No se ha declarado ningún --miembro-node", str(cm.exception))

    def test_miembro_id_sin_mapear_revienta_antes_de_mover_nada(self):
        """Reusa la misma validación que el importador (`miembros.miembros_sin_mapear`): un
        `miembro_id` de Node sin declarar hace fallar el comando sin mover NADA, ni siquiera
        las filas de otro miembro que sí estaban bien declaradas."""
        self._sembrar_entreno_mal_colgado()
        otro_miembro_id = 7
        otra_fila = {
            "fecha": "2026-08-01", "tipo": "bici", "duracion_min": 20,
            "intensidad": "baja", "calorias": 150, "miembro_id": otro_miembro_id,
        }
        _crear_sqlite_de_node(self.ruta_db, entrenos=[self.fila_entreno_miembro, otra_fila])

        with self.assertRaises(CommandError) as cm:
            self._mover(miembro_node=[self.spec_miembro])  # falta declarar otro_miembro_id=7
        self.assertIn(str(otro_miembro_id), str(cm.exception))
        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 0, "No se movió NADA.")

    def test_H1_no_mueve_una_fila_ajena_que_coincide_por_casualidad(self):
        """Reproducción EXACTA del hueco de la revisión (ronda 1, H1): mover de verdad; Euridice
        borra su entreno movido (acción normal); Alejandro apunta un entreno SUYO nuevo con la
        MISMA tupla exacta; al reejecutar el mover, el comando NO tiene que mover ese entreno
        nuevo de Alejandro — tiene que parar, porque el lote del miembro (dos filas) ya no está
        íntegro (una encaja, la otra no)."""
        otra_fila = {
            "fecha": "2026-02-12", "tipo": "fuerza", "duracion_min": 30,
            "intensidad": "media", "calorias": 220, "miembro_id": self.MIEMBRO_ID_NODE,
        }
        self._sembrar_entreno_mal_colgado()  # self.fila_entreno_miembro, bajo el titular
        apuntar_entreno(self.usuario, mapeo.datos_entreno(otra_fila))  # también bajo el titular
        _crear_sqlite_de_node(self.ruta_db, entrenos=[self.fila_entreno_miembro, otra_fila])

        # 1. Mover de verdad: lote íntegro de 2, las dos se mueven.
        self._mover()
        self.assertEqual(Entreno.objects.filter(persona=self.miembro).count(), 2)
        self.assertEqual(Entreno.objects.filter(persona=self.usuario).count(), 0)

        # 2. Euridice borra SU entreno movido (self.fila_entreno_miembro) — acción normal.
        Entreno.objects.filter(persona=self.miembro, fecha=self.fila_entreno_miembro["fecha"]).delete()

        # 3. Alejandro apunta un entreno NUEVO, SUYO, con la MISMA tupla que el que Euridice
        #    acaba de borrar — coincidencia real de valores, no la misma fila.
        apuntar_entreno(self.usuario, mapeo.datos_entreno(self.fila_entreno_miembro))

        # 4. Reejecutar el mover: NO debe tocar el entreno nuevo de Alejandro.
        with self.assertRaises(CommandError) as cm:
            self._mover()
        self.assertIn("no están en un estado que el comando pueda explicar", str(cm.exception))
        # El entreno NUEVO de Alejandro sigue siendo SUYO.
        self.assertEqual(
            Entreno.objects.filter(persona=self.usuario, fecha=self.fila_entreno_miembro["fecha"]).count(), 1,
            "El entreno nuevo de Alejandro NO debe haberse movido a Euridice.",
        )
        self.assertEqual(
            Entreno.objects.filter(persona=self.miembro, fecha=self.fila_entreno_miembro["fecha"]).count(), 0,
        )
        # La otra fila del lote, que SÍ seguía correctamente movida, tampoco se toca: el lote
        # entero se para junto, nunca se separa fila a fila (H1: "todo o nada").
        self.assertEqual(Entreno.objects.filter(persona=self.miembro, fecha=otra_fila["fecha"]).count(), 1)

    def test_H2_choque_de_persona_y_fecha_para_con_commanderror_no_integrityerror(self):
        """La restricción real de la base (`una_medicion_por_persona_y_dia`, persona+fecha) es
        MÁS CORTA que la tupla que usa este comando para identificar una fila. Si el destino ya
        tiene una pesada esa fecha con OTROS valores (la suya propia, autoapuntada), mover no
        debe reventar con un IntegrityError crudo: tiene que pararse con un CommandError en
        cristiano, sin mover nada, y SIN imprimir el peso real de nadie (H4/PII de la revisión)."""
        self._sembrar_pesada_mal_colgada()  # bajo el titular, la del miembro, mal colgada
        # El miembro YA tiene SU PROPIA pesada esa misma fecha, con otro peso — el choque real
        # que la restricción de la base impediría.
        MedicionPeso.objects.create(
            persona=self.miembro, fecha=self.fila_pesada_miembro["fecha"],
            peso_kg=Decimal("55.5"), grasa_pct=None, cintura_cm=None,
        )
        _crear_sqlite_de_node(self.ruta_db, pesos=[self.fila_pesada_miembro])

        with self.assertRaises(CommandError) as cm:
            self._mover()
        mensaje = str(cm.exception)
        self.assertIn("no están en un estado que el comando pueda explicar", mensaje)
        # H4/PII de la revisión: el mensaje NUNCA lleva ningún peso, propio ni ajeno.
        self.assertNotIn("70.5", mensaje)
        self.assertNotIn("55.5", mensaje)
        self.assertNotIn("peso_kg", mensaje)
        # Nada se movió.
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(persona=self.miembro).count(), 1)
        self.assertEqual(MedicionPeso.objects.get(persona=self.miembro).peso_kg, Decimal("55.5"))
