"""
Tests de la unidad 014 (R1-R12, llevar-la-despensa.md): añadir a mano sumando en vez de
duplicar (R-55, C-57, G-110, Q-92), corregir cantidad/unidad/categoría fundiendo líneas
cuando choque (R-56, R7, Q-92), quitar sin pedir explicaciones (C-62), y el aislamiento del
hogar (R9, R10, G-43).

**Unidad 017 (G-110 reescrita, G-194, R-96/R-97, C-105→C-110, aprobado 2026-08-09):** "arroz,
1 kg" y "arroz, 500 g" pasan a ser LA MISMA línea de 1,5 kg. Esto DEROGA la lectura literal de
lo que el R3 de la 014 comprobaba (que la unidad, sola, bastaba para distinguir dos líneas) —
`R3_UnidadesQueNoConvierteNuncaSeFundenTests` documenta el cambio con el mismo ejemplo que
antes probaba lo contrario, y las clases nuevas con prefijo `C1XX_` (nombradas por el
criterio de aceptación del plano que clavan, no por el número de requisito interno de la 014,
para no confundirlas con R1-R12 de aquí abajo) cubren el contrato completo de la 017.

Igual que en `planes/tests.py`, `entrenos/tests.py` y `progreso/tests.py`: todo pasa por el
cliente de pruebas de Django contra las URLs reales (nunca `ProductoDespensa.objects.
create(...)` a mano cuando lo que se prueba es un flujo completo) — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo: la petición tiene que
LLEGAR a lo que dice probar. Las ÚNICAS excepciones a propósito son R4 (la restricción de la
base de datos: esa SÍ tiene que insertar saltándose la vista, porque lo que demuestra es que
la base de datos protege aunque la vista no exista o esté rota — verificación de la
especificación de la 014, mutación obligatoria nº4) y R6 de la 017 (la migración de datos: se
prueba migrando de verdad con `MigrationExecutor`, no a través de ninguna vista, porque lo que
demuestra es que datos que YA existían antes de esta unidad se convierten sin romperse).
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Hogar, SolicitudEntrada

from .models import ProductoDespensa

Usuario = get_user_model()


class BaseDespensaTests(PruebaConRegistroAbierto):
    """
    Alejandro y Euridice, en el MISMO hogar; Carlos, en el SUYO propio (nunca se une a
    nadie) — el mismo montaje de tres personas que ya usan `progreso/tests.py` y
    `entrenos/tests.py`, necesario para R10 (octava cara de
    conocimiento/tests-que-no-fallan-cuando-deben.md: un permiso "propio / mismo hogar / de
    fuera" necesita un TERCERO que nunca se una a nadie, no solo dos personas del mismo
    hogar). La sesión queda en Alejandro al terminar `setUp`.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com")
        self.alejandro = Usuario.objects.get(email="alejandro@example.com")
        self.client.logout()

        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Usuario.objects.get(email="euridice@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control
        self.client.logout()

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el tercero de R10.
        self.registrar_y_verificar("carlos@example.com")
        self.carlos = Usuario.objects.get(email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

    def anadir(self, **campos):
        datos = {
            "nombre": "Tomate",
            "cantidad": "2",
            "unidad": "lata",
            "categoria": "verdura",
            **campos,
        }
        return self.client.post("/despensa/anadir/", datos)

    def corregir(self, producto_id, **campos):
        datos = {"cantidad": "1", "unidad": "lata", "categoria": "verdura", **campos}
        return self.client.post(f"/despensa/{producto_id}/corregir/", datos)

    def quitar(self, producto_id):
        return self.client.post(f"/despensa/{producto_id}/quitar/")

    def trozo_input_cantidad(self, contenido, producto_id):
        """
        Aísla el `<input id="cantidad-{id}" ...>` de UN producto, del atributo `id` hasta el
        `>` que cierra esa etiqueta — nunca el HTML entero. Lo pide la lección que dejó el bug
        016 (assert sobre la página ENTERA es frágil: el token CSRF de Django es una cadena
        aleatoria y por pura coincidencia puede contener la cifra que se busca) y la décima
        cara de conocimiento/tests-que-no-fallan-cuando-deben.md: "acota siempre al `id` de la
        pieza que el criterio nombra, antes de mirar si algo está o no está".
        """
        marcador = f'id="cantidad-{producto_id}"'
        return contenido.split(marcador, 1)[1].split(">", 1)[0]


class R1_C57_SumaEnVezDeDuplicarTests(BaseDespensaTests):
    """R1 (el episodio real de C-57, R-55, G-110, Q-92) — 2 latas de tomate + 2 latas de
    tomate más = una sola línea con 4 latas, no dos líneas de 2."""

    def test_anadir_el_mismo_producto_dos_veces_suma_en_una_sola_linea(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata")
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="tomate", unidad="lata"
        )
        self.assertEqual(lineas.count(), 1)
        self.assertEqual(lineas.get().cantidad, Decimal("4"))

    def test_la_pantalla_ensena_una_sola_linea_con_4_latas(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata")
        respuesta = self.anadir(nombre="Tomate", cantidad="2", unidad="lata")
        self.assertContains(respuesta, "Tomate")
        contenido = respuesta.content.decode()
        self.assertEqual(contenido.count("data-producto-id"), 1)


class R2_IgnoraMayusculasYEspaciosTests(BaseDespensaTests):
    """R2 — la suma ignora mayúsculas y espacios de sobra: "Tomate " sobre "tomate" suma en la
    misma línea (fuente: la app Node de referencia)."""

    def test_tomate_con_mayuscula_y_espacio_suma_sobre_tomate_en_minuscula(self):
        self.anadir(nombre="tomate", cantidad="2", unidad="lata")
        self.anadir(nombre="Tomate ", cantidad="3", unidad="lata")

        lineas = ProductoDespensa.objects.filter(hogar=self.alejandro.hogar, unidad="lata")
        self.assertEqual(lineas.count(), 1)
        self.assertEqual(lineas.get().cantidad, Decimal("5"))

    def test_el_nombre_guardado_es_el_que_escribio_la_primera_persona(self):
        # El "Cómo" de la especificación: se guarda y enseña el nombre tal cual lo escribió
        # la persona; lo normalizado es solo para comparar, nunca para mostrar.
        self.anadir(nombre="tomate", cantidad="2", unidad="lata")
        self.anadir(nombre="TOMATE", cantidad="1", unidad="lata")
        linea = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, unidad="lata")
        self.assertEqual(linea.nombre, "tomate")


class R3_UnidadesQueNoConvierteNuncaSeFundenTests(BaseDespensaTests):
    """
    Esta clase se llamaba `R3_SumaPorProductoYUnidadTests` y comprobaba que "arroz, 1 kg" y
    "arroz, 500 g" eran DOS líneas distintas porque la unidad, sola, bastaba para distinguir
    una línea de otra. La unidad 017 (G-110 reescrita, C-105, aprobado 2026-08-09) hace justo
    lo contrario A PROPÓSITO — ver `C105_C107_PesoYLiquidoSeFundenEnUnaSolaLineaTests` más
    abajo, que es donde vive ahora la cobertura completa de "cuándo se funde". Lo que sigue
    siendo cierto de la idea original de esta clase — "hay unidades que la app NO puede sumar
    sin inventar" — vive en la frontera correcta desde la 017: entre FAMILIAS (peso, líquido,
    paquete, lata, bote, ud), no entre unidades sueltas de la MISMA familia. Cobertura
    completa de esa frontera en `C108_PaquetesLatasBotesYPiezasNuncaSeFundenTests`; aquí queda
    un único test que documenta el cambio con el mismo ejemplo que antes probaba lo opuesto.
    """

    def test_arroz_en_kg_y_arroz_en_g_ya_no_son_dos_lineas_ahora_se_funden_en_una(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        self.anadir(nombre="arroz", cantidad="500", unidad="g")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(lineas.count(), 1)
        fundida = lineas.get()
        self.assertEqual(fundida.unidad, "g")
        self.assertEqual(fundida.cantidad, Decimal("1500"))


class C105_C107_PesoYLiquidoSeFundenEnUnaSolaLineaTests(BaseDespensaTests):
    """
    Unidad 017, R1/R2 (C-105, C-107, G-110 reescrita) — el peso (g, kg) se funde consigo mismo
    SIN IMPORTAR en qué unidad entró cada cantidad, y lo mismo con el líquido (ml, l). Guardar
    SIEMPRE en la unidad pequeña (g/ml) es lo que hace que el `UniqueConstraint` que ya existía
    en la base de datos (`una_linea_por_hogar_producto_y_unidad`) impida por sí solo las dos
    líneas de arroz, sin vigilancia nueva (el "Cómo" de la especificación, punto 0).
    """

    def test_1kg_de_arroz_mas_500g_de_arroz_es_una_sola_linea_de_1500_g(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        self.anadir(nombre="arroz", cantidad="500", unidad="g")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(lineas.count(), 1)
        fundida = lineas.get()
        self.assertEqual(fundida.unidad, "g")  # guardado SIEMPRE en la unidad pequeña
        self.assertEqual(fundida.cantidad, Decimal("1500"))  # 1000 + 500, exacto

    def test_1l_de_leche_mas_500ml_de_leche_es_una_sola_linea_de_1500_ml(self):
        self.anadir(nombre="leche", cantidad="1", unidad="l", categoria="lacteo")
        self.anadir(nombre="leche", cantidad="500", unidad="ml", categoria="lacteo")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="leche"
        )
        self.assertEqual(lineas.count(), 1)
        fundida = lineas.get()
        self.assertEqual(fundida.unidad, "ml")
        self.assertEqual(fundida.cantidad, Decimal("1500"))

    def test_el_orden_de_entrada_no_importa_gramos_primero_kilos_despues(self):
        # Control: da igual qué entre primero, el resultado es el mismo (la suma es
        # conmutativa) — la fusión no depende de "quién llegó antes".
        self.anadir(nombre="arroz", cantidad="500", unidad="g")
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        fundida = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(fundida.cantidad, Decimal("1500"))
        self.assertEqual(fundida.unidad, "g")


class C106_EnsenaEnGramosOKilosConElCorteEnElKiloTests(BaseDespensaTests):
    """
    Unidad 017, R3 (C-106, R-96, G-194) — por debajo de un kilo se enseña en gramos, de un
    kilo para arriba en kilos (igual con litros); el corte está EN el kilo: 1.000 g clavados
    se enseñan "1 kg", no "1.000 g". Lo que hay guardado por dentro NUNCA se toca (Q-174): el
    formateo vive solo en `despensa/logica.py:formatear_cantidad` y solo se ve en el `value`
    del `<input>` de corrección y en el `<select>` de unidad ("Cómo" punto 6).
    """

    def _trozos_mostrados(self, producto_id):
        """
        Devuelve `(trozo_input, trozo_select)`: el `<input>` de cantidad y el `<select>` de
        unidad de ESE producto, cada uno aislado a su propia etiqueta — nunca la página
        entera (lección del bug 016: un assert sobre el HTML completo puede colar por
        casualidad con el token CSRF aleatorio; y décima cara de
        conocimiento/tests-que-no-fallan-cuando-deben.md: acota siempre al `id` de la pieza).
        """
        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()
        trozo_input = self.trozo_input_cantidad(contenido, producto_id)
        trozo_select = contenido.split(f'id="unidad-{producto_id}"')[1].split("</select>")[0]
        return trozo_input, trozo_select

    def test_500_gramos_se_ensenan_en_gramos(self):
        self.anadir(nombre="arroz", cantidad="500", unidad="g")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        trozo_input, trozo_select = self._trozos_mostrados(producto.id)
        self.assertIn('value="500"', trozo_input)
        self.assertIn('<option value="g" selected>', trozo_select)

    def test_300_mas_200_gramos_se_ensenan_500_gramos_no_0_5_kg(self):
        self.anadir(nombre="arroz", cantidad="300", unidad="g")
        self.anadir(nombre="arroz", cantidad="200", unidad="g")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(producto.cantidad, Decimal("500"))
        trozo_input, trozo_select = self._trozos_mostrados(producto.id)
        self.assertIn('value="500"', trozo_input)
        self.assertNotIn('value="0.5"', trozo_input)
        self.assertIn('<option value="g" selected>', trozo_select)

    def test_1500_gramos_se_ensenan_en_kilos(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        self.anadir(nombre="arroz", cantidad="500", unidad="g")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        trozo_input, trozo_select = self._trozos_mostrados(producto.id)
        self.assertIn('value="1.5"', trozo_input)
        self.assertIn('<option value="kg" selected>', trozo_select)

    def test_1000_gramos_clavados_se_ensenan_1_kg_no_1000_g(self):
        self.anadir(nombre="harina", cantidad="1000", unidad="g")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="harina"
        )
        self.assertEqual(producto.cantidad, Decimal("1000"))  # guardado intacto, sin redondear
        trozo_input, trozo_select = self._trozos_mostrados(producto.id)
        self.assertIn('value="1"', trozo_input)
        self.assertNotIn('value="1000"', trozo_input)
        self.assertIn('<option value="kg" selected>', trozo_select)


class C108_PaquetesLatasBotesYPiezasNuncaSeFundenTests(BaseDespensaTests):
    """
    Unidad 017, R4 (C-108, R-97) — el caso límite que define la unidad: "arroz, 1 paquete" +
    "arroz, 500 g" son DOS líneas, siempre, y la app NUNCA estima cuánto pesa un paquete (ni
    una lata, ni un bote, ni una pieza) — ni siquiera al AÑADIR, que es justo la tentación de
    "mejorar" que esta unidad prohíbe a propósito (estimar es aceptable solo al DESCONTAR,
    R-57/G-111, y esa es otra promesa, de otra unidad, que aquí no se toca).
    """

    def test_arroz_en_paquete_mas_arroz_en_gramos_son_dos_lineas_y_nada_se_estima(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="paquete", categoria="cereal_pan")
        self.anadir(nombre="arroz", cantidad="500", unidad="g", categoria="cereal_pan")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(lineas.count(), 2)
        por_unidad = {p.unidad: p.cantidad for p in lineas}
        # Ni rastro de un peso estimado para el paquete: sigue siendo "1 paquete" clavado.
        self.assertEqual(por_unidad, {"paquete": Decimal("1"), "g": Decimal("500")})

    def test_latas_botes_y_unidades_sueltas_tampoco_se_funden_con_peso(self):
        for familia, cantidad_inicial in [("lata", "2"), ("bote", "3"), ("ud", "4")]:
            with self.subTest(familia=familia):
                nombre = f"producto-{familia}"
                self.anadir(nombre=nombre, cantidad=cantidad_inicial, unidad=familia)
                self.anadir(nombre=nombre, cantidad="200", unidad="g")
                lineas = ProductoDespensa.objects.filter(
                    hogar=self.alejandro.hogar, nombre_normalizado=nombre
                )
                self.assertEqual(lineas.count(), 2)


class C109_NoSePierdeNiUnGramoAlConvertirTests(BaseDespensaTests):
    """
    Unidad 017, R5 (C-109, Q-174) — sumar no pierde ni un gramo: 1 kg + 383 g se guarda como
    1.383 g EXACTOS (no 1,38 kg con 3 g evaporados — la lección de la 011, un número
    redondeado al guardarlo es un número muerto). La otra mitad de C-109 ("y al cocinar un
    plato que gasta 383 g queda 1 kg exacto") depende de R-57/"marcar como preparada", que
    esta unidad NO construye (Deltas al mapa: `llevar-la-despensa` sigue en obra) — se
    comprueba aquí simulando el descuento exacto con `corregir_producto` (vía la vista de
    corregir), que usa la MISMA aritmética exacta que usará el día que exista "cocinar".
    """

    def test_1kg_mas_383g_se_guarda_como_1383_gramos_exactos_y_se_ensena_1_383_kg(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        self.anadir(nombre="arroz", cantidad="383", unidad="g")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(producto.cantidad, Decimal("1383"))
        self.assertEqual(producto.unidad, "g")

        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()
        # Aislado al propio `<input>` de esta línea, nunca a la página entera (bug 016: un
        # assert sobre el HTML completo puede colar por casualidad con el token CSRF).
        trozo_input = self.trozo_input_cantidad(contenido, producto.id)
        self.assertIn('value="1.383"', trozo_input)  # se enseña 1,383 kg, no 1,38 (Q-174)

    def test_descontar_los_383g_exactos_deja_1_kg_clavado_sin_perder_nada(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        self.anadir(nombre="arroz", cantidad="383", unidad="g")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(producto.cantidad, Decimal("1383"))

        # Simula el descuento exacto que hará "marcar como preparada" el día que exista
        # (R-57, fuera de esta unidad): quedan exactamente 1.000 g, ni un gramo de más ni de
        # menos.
        self.corregir(producto.id, cantidad="1000", unidad="g", categoria="cereal_pan")
        producto.refresh_from_db()
        self.assertEqual(producto.cantidad, Decimal("1000"))
        self.assertEqual(producto.unidad, "g")


class R7_CorregirLaUnidadSigueFundiendoSinDuplicarTests(BaseDespensaTests):
    """
    Sustituye a `R7_CorregirLaUnidadFusionaSiChocaTests` de la 014, cuyo montaje ("arroz 500 g"
    + "arroz 1 kg" coexistiendo como DOS líneas para luego corregir una hacia la otra) ya no se
    puede dar: con la 017, esas dos líneas se habrían fundido en el propio `self.anadir()` de
    la segunda, antes de llegar a la corrección. Unidad 017, R7 — corregir la unidad de una
    línea existente sigue funcionando y sigue sin dejar duplicados (Q-92 es absoluta). Lo que
    CAMBIA respecto a la 014: para peso y líquido
    este choque ya no puede darse EN PRIMER LUGAR (nunca hay dos líneas de peso ni dos de
    líquido del mismo producto que corregir-hacia-otra pueda chocar, porque ya se habrían
    fundido al AÑADIR o en una corrección anterior — es la misma restricción de la base de
    datos, ahora blindando también esto). El choque real que sigue vivo, intacto, es cuando
    alguien corrige a mano una línea de una familia que NO se convierte (paquete/lata/bote/ud)
    hacia peso o líquido: una decisión de la PERSONA, no una estimación de la app (R4/G-110
    sigue sin tocarse — la app nunca lo hace sola).
    """

    def test_corregir_una_lata_a_gramos_choca_con_el_peso_existente_y_se_funden(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")  # -> 1000 g
        self.anadir(nombre="arroz", cantidad="1", unidad="lata", categoria="cereal_pan")
        lata = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, unidad="lata")

        # Alejandro decide que esa "lata" eran en realidad 300 g y lo corrige a mano.
        self.corregir(lata.id, cantidad="300", unidad="g", categoria="cereal_pan")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(lineas.count(), 1)  # nunca dos líneas iguales (Q-92)
        fundida = lineas.get()
        self.assertEqual(fundida.unidad, "g")
        self.assertEqual(fundida.cantidad, Decimal("1300"))  # 1000 + 300, sin error a medias
        self.assertFalse(ProductoDespensa.objects.filter(id=lata.id).exists())

    def test_corregir_la_unidad_sin_chocar_solo_reexpresa_en_la_unidad_pequena(self):
        # Control: sin ninguna línea gemela con la que chocar, corregir la unidad NO funde
        # nada raro — solo re-expresa la cantidad en la unidad canónica (R-96: se guarda
        # SIEMPRE en la pequeña, también al corregir, no solo al añadir).
        self.anadir(nombre="harina", cantidad="500", unidad="g")
        harina = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="harina"
        )
        self.corregir(harina.id, cantidad="0.5", unidad="kg", categoria="cereal_pan")
        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="harina"
        )
        self.assertEqual(lineas.count(), 1)
        self.assertEqual(lineas.get().unidad, "g")
        self.assertEqual(lineas.get().cantidad, Decimal("500"))

    def test_dos_familias_que_no_convierten_siguen_sin_fundirse_al_corregir(self):
        # R4 no se rompe por el camino de corregir: pasar de "paquete" a "lata" (dos familias
        # que NO se convierten entre sí) nunca funde nada.
        self.anadir(nombre="arroz", cantidad="1", unidad="paquete", categoria="cereal_pan")
        arroz = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.corregir(arroz.id, cantidad="2", unidad="lata", categoria="cereal_pan")
        arroz.refresh_from_db()
        self.assertEqual(arroz.unidad, "lata")
        self.assertEqual(arroz.cantidad, Decimal("2"))


class R6_MigracionFundeLoQueYaColisionaTests(TestCase):
    """
    Unidad 017, R6 (caso límite del arranque, no está en los planos) — los productos que YA
    existen se convierten sin perder nada, INCLUIDOS los que hoy están en dos líneas y a
    partir de ahora no pueden estarlo: un hogar con "arroz, 1 kg" y "arroz, 500 g" tiene que
    acabar con UNA sola línea de 1.500 g, no con un `IntegrityError` a mitad de camino ni con
    una borrada sin sumar.

    La migración 0002 (`despensa/migrations/0002_funde_pesos_y_liquidos_en_su_unidad_pequena.py`)
    NO CAMBIA el esquema, solo datos: la tabla es idéntica antes y después. Por eso esta clase
    no necesita retroceder el esquema de verdad con `MigrationExecutor` — monta el caso que YA
    colisiona insertando DIRECTAMENTE con el ORM real (misma técnica que
    `R4_RestriccionEnLaBaseDeDatosTests`: la restricción de la base, sobre la unidad EXACTA,
    seguía permitiendo "kg" y "g" como dos filas distintas antes de esta unidad, así que el
    montaje es legítimo) y llama a la función de la migración TAL CUAL — importada por su
    nombre de módulo real con `importlib` (los ficheros de migración empiezan por un número,
    así que no se pueden importar con `import` normal) — para que lo que se prueba sea el
    código de producción, no una copia.
    """

    def test_arroz_1kg_y_arroz_500g_que_ya_colisionaban_se_funden_en_una_linea_de_1500g(self):
        import importlib

        from django.apps import apps as registro_de_apps

        hogar = Hogar.objects.create()
        ProductoDespensa.objects.create(
            hogar=hogar, nombre="arroz", cantidad=Decimal("1"), unidad="kg",
            categoria="cereal_pan",
        )
        ProductoDespensa.objects.create(
            hogar=hogar, nombre="arroz", cantidad=Decimal("500"), unidad="g",
            categoria="cereal_pan",
        )
        antes = list(
            ProductoDespensa.objects.filter(hogar_id=hogar.id, nombre_normalizado="arroz")
            .order_by("unidad")
            .values("nombre", "cantidad", "unidad")
        )
        print("\n--- R6: ANTES de migrar (datos que YA colisionan) ---")
        for fila in antes:
            print(fila)
        self.assertEqual(len(antes), 2)  # control: de verdad hay dos líneas antes de migrar

        modulo = importlib.import_module(
            "despensa.migrations.0002_funde_pesos_y_liquidos_en_su_unidad_pequena"
        )
        modulo.fundir_pesos_y_liquidos_en_su_unidad_pequena(registro_de_apps, None)

        despues = list(
            ProductoDespensa.objects.filter(hogar_id=hogar.id, nombre_normalizado="arroz")
            .order_by("unidad")
            .values("nombre", "cantidad", "unidad")
        )
        print("--- R6: DESPUÉS de migrar ---")
        for fila in despues:
            print(fila)

        self.assertEqual(len(despues), 1)
        self.assertEqual(despues[0]["unidad"], "g")
        self.assertEqual(despues[0]["cantidad"], Decimal("1500.00"))

    def test_una_fila_suelta_en_l_sin_gemela_solo_se_convierte_a_ml(self):
        # Control: sin colisión, la migración simplemente convierte (no hay nada que fundir).
        import importlib

        from django.apps import apps as registro_de_apps

        hogar = Hogar.objects.create()
        ProductoDespensa.objects.create(
            hogar=hogar, nombre="leche", cantidad=Decimal("2"), unidad="l", categoria="lacteo",
        )
        modulo = importlib.import_module(
            "despensa.migrations.0002_funde_pesos_y_liquidos_en_su_unidad_pequena"
        )
        modulo.fundir_pesos_y_liquidos_en_su_unidad_pequena(registro_de_apps, None)

        producto = ProductoDespensa.objects.get(hogar_id=hogar.id, nombre_normalizado="leche")
        self.assertEqual(producto.unidad, "ml")
        self.assertEqual(producto.cantidad, Decimal("2000.00"))


class R6_RollbackDeLaMigracionEsIrreversibleAPropositoTests(TransactionTestCase):
    """
    Unidad 017, R6 — el rollback escrito y probado que pide la especificación. La migración
    0002 declara `reverse_code=_irreversible`: intentar `manage.py migrate despensa
    0001_initial` con ella ya aplicada tiene que fallar con un mensaje que EXPLICA por qué (no
    hay forma de deshacer una suma), en vez de fingir en silencio que separó lo que fundió.

    `TransactionTestCase`, no `TestCase`: aquí SÍ se llama a `MigrationExecutor.migrate()` de
    verdad (mueve el puntero de qué migraciones están aplicadas), y eso no puede ir envuelto en
    la transacción atómica que usa `TestCase`.
    """

    def tearDown(self):
        # El intento de retroceder debe abortar entero (el `IrreversibleError` se levanta
        # dentro del bloque atómico de la propia migración) y dejar todo tal cual estaba, pero
        # se comprueba y se repara aquí por si acaso, para no contaminar el resto de la suite.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_intentar_deshacer_la_migracion_falla_con_irreversibleerror(self):
        from django.db.migrations.exceptions import IrreversibleError

        executor = MigrationExecutor(connection)
        with self.assertRaises(IrreversibleError) as contexto:
            executor.migrate([("despensa", "0001_initial")])
        print("\n--- R6: intento de rollback (esperado: falla) ---")
        print(repr(contexto.exception))
        self.assertIn("no se puede deshacer", str(contexto.exception))

        # Control: tras el intento fallido, la migración de fusión SIGUE aplicada — no se ha
        # quedado a medias.
        self.assertIn(
            ("despensa", "0002_funde_pesos_y_liquidos_en_su_unidad_pequena"),
            executor.loader.applied_migrations,
        )


class R4_RestriccionEnLaBaseDeDatosTests(TestCase):
    """
    R4 — la regla vive en la BASE DE DATOS, no solo en la vista: es imposible que existan dos
    filas del mismo hogar con el mismo nombre (normalizado) y la misma unidad. Precedente:
    `MedicionPeso.una_medicion_por_persona_y_dia` (unidad 006). A propósito, este test
    INSERTA saltándose la vista (verificación de la especificación, mutación nº4): lo que
    demuestra es que la base de datos protege por sí sola, no que el formulario lo impida.
    """

    def test_la_base_de_datos_impide_dos_lineas_del_mismo_hogar_producto_y_unidad(self):
        hogar = Hogar.objects.create()
        ProductoDespensa.objects.create(
            hogar=hogar, nombre="Tomate", cantidad=Decimal("2"), unidad="lata",
            categoria="verdura",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductoDespensa.objects.create(
                    hogar=hogar, nombre="tomate", cantidad=Decimal("1"), unidad="lata",
                    categoria="verdura",
                )
        # Solo la primera fila sobrevive: la segunda petición no dejó ningún rastro.
        self.assertEqual(
            ProductoDespensa.objects.filter(hogar=hogar, nombre_normalizado="tomate").count(), 1
        )

    def test_hogares_distintos_si_pueden_tener_cada_uno_su_linea_de_tomate(self):
        # Control: la restricción es POR HOGAR, no global — dos hogares distintos pueden
        # tener cada uno su propia línea de "tomate, lata" sin chocar entre sí.
        hogar_1 = Hogar.objects.create()
        hogar_2 = Hogar.objects.create()
        ProductoDespensa.objects.create(
            hogar=hogar_1, nombre="Tomate", cantidad=Decimal("2"), unidad="lata",
            categoria="verdura",
        )
        ProductoDespensa.objects.create(
            hogar=hogar_2, nombre="Tomate", cantidad=Decimal("3"), unidad="lata",
            categoria="verdura",
        )
        self.assertEqual(ProductoDespensa.objects.count(), 2)


class R5_CorregirCantidadUnidadYCategoriaTests(BaseDespensaTests):
    """
    R5 — se puede corregir la cantidad, la unidad y la categoría de cualquier producto (son
    TRES cosas, cada una con su propio test). Unidad 017: `_crear_producto` añade "Leche, 1 l"
    y esa línea SE GUARDA como (1000, "ml") desde el instante en que se crea (R-96: siempre en
    la unidad pequeña) — los asserts de cantidad de esta clase están en mililitros, no en
    litros, por eso.
    """

    def _crear_producto(self):
        self.anadir(nombre="Leche", cantidad="1", unidad="l", categoria="lacteo")
        return ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="leche")

    def test_se_puede_corregir_la_cantidad(self):
        producto = self._crear_producto()
        self.corregir(producto.id, cantidad="3", unidad="l", categoria="lacteo")
        producto.refresh_from_db()
        self.assertEqual(producto.cantidad, Decimal("3000"))  # 3 l guardados como 3.000 ml
        self.assertEqual(producto.unidad, "ml")

    def test_se_puede_corregir_la_unidad(self):
        # Corrige de líquido (ml) a una familia que no convierte (paquete): demuestra que la
        # unidad SÍ cambia de verdad, cosa que un cambio "ml -> ml" no demostraría (ambos
        # canonicalizan a lo mismo y no se vería ninguna diferencia).
        producto = self._crear_producto()
        self.corregir(producto.id, cantidad="2", unidad="paquete", categoria="lacteo")
        producto.refresh_from_db()
        self.assertEqual(producto.unidad, "paquete")
        self.assertEqual(producto.cantidad, Decimal("2"))

    def test_se_puede_corregir_la_categoria(self):
        producto = self._crear_producto()
        self.corregir(producto.id, cantidad="1", unidad="l", categoria="bebida")
        producto.refresh_from_db()
        self.assertEqual(producto.categoria, "bebida")

    def test_el_campo_de_cantidad_no_sale_con_coma_decimal(self):
        """
        Séptima cara de conocimiento/tests-que-no-fallan-cuando-deben.md: con
        LANGUAGE_CODE="es", un Decimal puesto directamente en el atributo `value` de un
        `<input type="number">` sale con COMA ("1,50"), que el navegador no sabe leer y
        descarta EN SILENCIO — el campo se vería vacío al abrir la pantalla, aunque el valor
        SÍ esté en la respuesta (por eso hace falta mirar el HTML crudo, no un assertContains
        cualquiera). `despensa/templates/despensa/ver.html` usa `|unlocalize` para evitarlo.
        Unidad 017: el `value` ahora es `cantidad_mostrada` (R-96), que además quita los
        ceros decimales que sobran (1.50 -> 1.5) — se usa "ml" a propósito, para que esta
        cantidad no cruce el corte del kilo y el test siga aislando SOLO el problema de la
        coma, no el del formateo de escala (eso ya lo cubre `C106_...`).
        """
        self.anadir(nombre="Aceite", cantidad="1.50", unidad="ml", categoria="aceite_grasa")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="aceite")
        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()
        self.assertIn(f'id="cantidad-{producto.id}"', contenido)
        # Aislado al propio `<input>`, nunca a la página entera (bug 016: el token CSRF es
        # una cadena aleatoria y por pura coincidencia puede contener la cifra que se busca).
        trozo_input = self.trozo_input_cantidad(contenido, producto.id)
        self.assertIn('value="1.5"', trozo_input)
        self.assertNotIn('value="1,5"', trozo_input)


class R6_C62_QuitarSinExplicacionTests(BaseDespensaTests):
    """R6 (el caso de C-62) — se puede quitar un producto y la app no pide ninguna
    explicación: deja de contar y punto."""

    def test_quitar_borra_la_linea_definitivamente(self):
        self.anadir(nombre="Lechuga", cantidad="1", unidad="ud", categoria="verdura")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="lechuga"
        )
        respuesta = self.quitar(producto.id)
        self.assertEqual(respuesta.status_code, 200)  # misma pantalla, sin recargar (patrón
        # de planes/perfiles: no hay a dónde "volver", así que no hace falta redirect)
        self.assertFalse(ProductoDespensa.objects.filter(id=producto.id).exists())

    def test_quitar_no_pide_ningun_motivo_ni_campo_extra(self):
        # C-62: el POST de quitar no lleva ningún campo de motivo/confirmación — solo el
        # token CSRF de siempre — y aun así basta para borrar.
        self.anadir(nombre="Lechuga", cantidad="1", unidad="ud", categoria="verdura")
        producto = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="lechuga"
        )
        respuesta = self.client.post(f"/despensa/{producto.id}/quitar/", {})
        self.assertNotEqual(respuesta.status_code, 400)
        self.assertFalse(ProductoDespensa.objects.filter(id=producto.id).exists())


class R8_AgrupadoPorCategoriasTests(BaseDespensaTests):
    """R8 (§8 del plano, "Qué ve nada más entrar") — la pantalla enseña lo que hay agrupado
    por categorías."""

    def test_dos_categorias_distintas_aparecen_cada_una_con_su_cabecera(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        self.anadir(nombre="Leche", cantidad="1", unidad="l", categoria="lacteo")

        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()
        self.assertIn("Verdura", contenido)
        self.assertIn("Lácteo", contenido)
        # El tomate aparece DEBAJO de la cabecera de Verdura, la leche debajo de Lácteo.
        self.assertLess(contenido.index("Verdura"), contenido.index("Tomate"))
        self.assertLess(contenido.index("Lácteo"), contenido.index("Leche"))

    def test_una_categoria_sin_ningun_producto_no_ensena_su_cabecera(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()
        # "Pescado" SÍ aparece en la página (como opción de los desplegables de categoría de
        # cada formulario): lo que R8 prohíbe es su CABECERA de sección — comprobar solo
        # "no está en ningún sitio" sería la quinta cara de
        # conocimiento/tests-que-no-fallan-cuando-deben.md (busca en todo el HTML, no en el
        # sitio correcto). Se aísla el `<h2>` de cabecera, que solo se pinta una vez por
        # categoría con productos.
        self.assertNotIn(">Pescado</h2>", contenido)
        self.assertIn(">Verdura</h2>", contenido)  # control: si la sí tiene, sí sale


class R9_CualquieraDelHogarVeAnadeCorrigeYQuitaTests(BaseDespensaTests):
    """
    R9 (G-43, R-24) — cualquiera del hogar puede VER, AÑADIR, CORREGIR y QUITAR sin pedir
    permiso ni confirmación a nadie (nombra CUATRO acciones: cuatro tests). La despensa es del
    hogar entero, no de una persona: lo que añade Alejandro lo puede corregir Euridice sin
    que nadie se lo autorice.
    """

    def test_euridice_ve_lo_que_anadio_alejandro(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/despensa/")
        self.assertContains(respuesta, "Tomate")

    def test_euridice_puede_anadir_sin_pedir_permiso(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.anadir(nombre="Pan", cantidad="1", unidad="paquete", categoria="cereal_pan")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            ProductoDespensa.objects.filter(
                hogar=self.alejandro.hogar, nombre_normalizado="pan"
            ).exists()
        )

    def test_euridice_puede_corregir_lo_que_anadio_alejandro_sin_pedir_permiso(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="tomate")
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.corregir(producto.id, cantidad="9", unidad="lata", categoria="verdura")
        self.assertEqual(respuesta.status_code, 200)
        producto.refresh_from_db()
        self.assertEqual(producto.cantidad, Decimal("9"))

    def test_euridice_puede_quitar_lo_que_anadio_alejandro_sin_pedir_permiso(self):
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="tomate")
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.quitar(producto.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(id=producto.id).exists())


class R10_OtroHogarSiempre404Tests(BaseDespensaTests):
    """
    R10 (§8: "Qué NO debe poder jamás: ver la despensa de otro hogar") — alguien de OTRO
    hogar (Carlos, que nunca se une a nadie) recibe 404, nunca 403, al intentar corregir o
    quitar un producto ajeno; y su propia pantalla nunca enseña productos de la despensa de
    Alejandro.
    """

    def setUp(self):
        super().setUp()
        self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        self.producto_de_alejandro = ProductoDespensa.objects.get(
            hogar=self.alejandro.hogar, nombre_normalizado="tomate"
        )
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)

    def test_la_despensa_de_carlos_no_ensena_el_tomate_de_alejandro(self):
        respuesta = self.client.get("/despensa/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Tomate")

    def test_carlos_no_puede_corregir_un_producto_de_otro_hogar(self):
        respuesta = self.corregir(self.producto_de_alejandro.id, cantidad="99", unidad="lata", categoria="verdura")
        self.assertEqual(respuesta.status_code, 404)
        self.producto_de_alejandro.refresh_from_db()
        self.assertEqual(self.producto_de_alejandro.cantidad, Decimal("2"))  # intacto

    def test_carlos_no_puede_quitar_un_producto_de_otro_hogar(self):
        respuesta = self.quitar(self.producto_de_alejandro.id)
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(ProductoDespensa.objects.filter(id=self.producto_de_alejandro.id).exists())

    def test_nunca_403_siempre_404(self):
        respuesta = self.quitar(self.producto_de_alejandro.id)
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)


class R11_EntradasInvalidasSeRechazanTests(BaseDespensaTests):
    """R11 (caso límite de entrada) — cantidad cero o negativa, nombre vacío, o una unidad o
    categoría que no están en la lista: la app no lo guarda y lo dice, sin romper la
    pantalla."""

    def test_cantidad_cero_no_se_guarda(self):
        respuesta = self.anadir(cantidad="0")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_cantidad_negativa_no_se_guarda(self):
        respuesta = self.anadir(cantidad="-3")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_nombre_vacio_no_se_guarda(self):
        respuesta = self.anadir(nombre="")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_unidad_que_no_esta_en_la_lista_no_se_guarda(self):
        respuesta = self.anadir(unidad="tonelada")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_categoria_que_no_esta_en_la_lista_no_se_guarda(self):
        respuesta = self.anadir(categoria="electronica")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_corregir_con_cantidad_cero_no_se_guarda_y_no_rompe_la_pantalla(self):
        self.anadir(nombre="Leche", cantidad="1", unidad="l", categoria="lacteo")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="leche")
        respuesta = self.corregir(producto.id, cantidad="0", unidad="l", categoria="lacteo")
        self.assertEqual(respuesta.status_code, 200)
        producto.refresh_from_db()
        # Unidad 017: "Leche, 1 l" se guarda como (1000, "ml") desde que se crea (R-96).
        self.assertEqual(producto.cantidad, Decimal("1000"))  # intacto


class R12_PantallaVaciaTests(BaseDespensaTests):
    """R12 — cuando la despensa está vacía, la pantalla lo dice con naturalidad y no parece
    rota ni da error."""

    def test_sin_ningun_producto_no_da_error_y_lo_dice(self):
        respuesta = self.client.get("/despensa/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no hay nada apuntado en la despensa")

    def test_una_persona_recien_llegada_al_hogar_tambien_ve_la_pantalla_vacia_sin_reventar(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/despensa/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no hay nada apuntado en la despensa")


class HTMXRespondeSoloElTrozoTests(BaseDespensaTests):
    """
    Novena cara de conocimiento/tests-que-no-fallan-cuando-deben.md: si la plantilla manda
    algo por HTMX, la vista tiene que responder el TROZO, no un `redirect` — y el test tiene
    que mandar la cabecera `HX-Request`, la que manda el navegador de verdad, no la petición
    "limpia" que ningún botón real produce.
    """

    def test_anadir_con_hx_request_responde_solo_el_trozo(self):
        respuesta = self.anadir_con_hx()
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn('id="despensa-del-hogar"', contenido)

    def anadir_con_hx(self):
        return self.client.post(
            "/despensa/anadir/",
            {"nombre": "Tomate", "cantidad": "2", "unidad": "lata", "categoria": "verdura"},
            HTTP_HX_REQUEST="true",
        )

    def test_corregir_con_hx_request_responde_solo_el_trozo(self):
        self.anadir(nombre="Leche", cantidad="1", unidad="l", categoria="lacteo")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="leche")
        respuesta = self.client.post(
            f"/despensa/{producto.id}/corregir/",
            {"cantidad": "2", "unidad": "l", "categoria": "lacteo"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn('id="despensa-del-hogar"', contenido)

    def test_quitar_con_hx_request_responde_solo_el_trozo(self):
        self.anadir(nombre="Lechuga", cantidad="1", unidad="ud", categoria="verdura")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="lechuga")
        respuesta = self.client.post(
            f"/despensa/{producto.id}/quitar/", {}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ProductoDespensa.objects.filter(id=producto.id).exists())
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn('id="despensa-del-hogar"', contenido)

    def test_sin_hx_request_anadir_devuelve_la_pagina_completa(self):
        # Control del lado contrario: sin la cabecera (nadie navegando con JS deshabilitado
        # lleva HX-Request), la vista sirve la página COMPLETA — mismo patrón que
        # `planes/views.py:apuntar_plan` y `perfiles/views.py:apuntar_peso` (sin redirect: no
        # hay ninguna otra pantalla a la que "volver", así que renderizar de nuevo esta misma
        # basta).
        respuesta = self.anadir(nombre="Tomate", cantidad="2", unidad="lata", categoria="verdura")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn("<html", contenido)
        self.assertIn("</html>", contenido)
