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
from entrenos.models import Entreno
from hogares.models import Hogar, crear_hogar_propio
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
                "strava_id TEXT)"
            )
            for e in entrenos or []:
                conexion.execute(
                    "INSERT INTO entrenos "
                    "(usuario_id, fecha, tipo, duracion_min, intensidad, calorias, origen, strava_id) "
                    "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        e["fecha"],
                        e["tipo"],
                        e["duracion_min"],
                        e["intensidad"],
                        e["calorias"],
                        e.get("origen", "manual"),
                        e.get("strava_id"),
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
                "grasa_pct REAL, cintura_cm REAL)"
            )
            for p in pesos or []:
                conexion.execute(
                    "INSERT INTO pesos (usuario_id, fecha, peso_kg, grasa_pct, cintura_cm) "
                    "VALUES (1, ?, ?, ?, ?)",
                    (p["fecha"], p["peso_kg"], p.get("grasa_pct"), p.get("cintura_cm")),
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

        self.usuario = Usuario.objects.create_user(email="prueba@example.com", password="x")
        crear_hogar_propio(self.usuario)
        self.hogar = self.usuario.hogar

    def _importar(self, *, dry_run=False, cuenta=None, ruta=None):
        salida = io.StringIO()
        call_command(
            "importar_datos_node",
            ruta or self.ruta_db,
            cuenta=cuenta or self.usuario.email,
            dry_run=dry_run,
            stdout=salida,
        )
        return salida.getvalue()

    def _contar(self):
        return {
            "despensa": ProductoDespensa.objects.filter(hogar=self.hogar).count(),
            "entrenos": Entreno.objects.filter(usuario=self.usuario).count(),
            "pesadas": MedicionPeso.objects.filter(usuario=self.usuario).count(),
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
        self.assertEqual(Entreno.objects.filter(usuario=self.usuario).count(), 2)

        # Repetir la pasada: las DOS ya existen, ninguna se duplica.
        salida = self._importar()
        self.assertEqual(Entreno.objects.filter(usuario=self.usuario).count(), 2)
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
        entreno = Entreno.objects.get(usuario=self.usuario)
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
        pesada = MedicionPeso.objects.get(usuario=self.usuario)
        self.assertEqual(pesada.peso_kg, Decimal("70.3"))
        self.assertEqual(pesada.grasa_pct, Decimal("18.2"))
        self.assertEqual(pesada.cintura_cm, Decimal("81.5"))

    def test_pesada_sin_grasa_ni_cintura_llega_con_esos_campos_vacios(self):
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[{"fecha": "2026-02-14", "peso_kg": 65.0, "grasa_pct": None, "cintura_cm": None}],
        )
        self._importar()
        pesada = MedicionPeso.objects.get(usuario=self.usuario)
        self.assertIsNone(pesada.grasa_pct)
        self.assertIsNone(pesada.cintura_cm)

    def test_una_pesada_que_choca_con_una_ya_existente_se_salta_y_no_revienta(self):
        """R4, caso límite: si la persona (o una pasada anterior) YA tiene una medición ese
        día, la fila de Node no se sobrescribe -- se salta, se cuenta como 'ya estaba' y el
        comando sigue sin reventar contra la restricción 'una_medicion_por_persona_y_dia'
        (unidad 006)."""
        MedicionPeso.objects.create(usuario=self.usuario, fecha=date(2026, 2, 14), peso_kg=Decimal("99.9"))
        _crear_sqlite_de_node(
            self.ruta_db,
            pesos=[{"fecha": "2026-02-14", "peso_kg": 70.3, "grasa_pct": None, "cintura_cm": None}],
        )
        salida = self._importar()
        # No revienta, y NO sobrescribe: sigue siendo la medición que ya había.
        pesada = MedicionPeso.objects.get(usuario=self.usuario, fecha=date(2026, 2, 14))
        self.assertEqual(pesada.peso_kg, Decimal("99.9"))
        self.assertEqual(MedicionPeso.objects.filter(usuario=self.usuario).count(), 1)
        self.assertIn("Pesadas: 1 en Node -> 0 nuevos, 1 ya estaban.", salida)


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
        otro_usuario = Usuario.objects.create_user(email="otra-cuenta@example.com", password="x")
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
        otro_usuario = Usuario.objects.create_user(email="otra-cuenta@example.com", password="x")
        crear_hogar_propio(otro_usuario)

        _crear_sqlite_de_node(
            self.ruta_db,
            entrenos=[{"fecha": "2026-03-01", "tipo": "correr", "duracion_min": 30, "intensidad": "media", "calorias": 300}],
            pesos=[{"fecha": "2026-03-01", "peso_kg": 70.0, "grasa_pct": None, "cintura_cm": None}],
        )
        self._importar()

        self.assertEqual(Entreno.objects.filter(usuario=self.usuario).count(), 1)
        self.assertEqual(Entreno.objects.filter(usuario=otro_usuario).count(), 0)
        self.assertEqual(MedicionPeso.objects.filter(usuario=self.usuario).count(), 1)
        self.assertEqual(MedicionPeso.objects.filter(usuario=otro_usuario).count(), 0)

    def test_una_cuenta_sin_hogar_todavia_no_deja_importar(self):
        """Caso límite de R6: mientras espera a que la acepten en un hogar (unidad 003), una
        cuenta no tiene ningún hogar propio todavía. El comando falla en cristiano, sin tocar
        nada, en vez de dejar algo colgado sin hogar."""
        huerfano = Usuario.objects.create_user(email="esperando@example.com", password="x")
        self.assertIsNone(huerfano.hogar)

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
