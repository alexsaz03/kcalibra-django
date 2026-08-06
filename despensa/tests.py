"""
Tests de la unidad 014 (R1-R12, llevar-la-despensa.md): añadir a mano sumando en vez de
duplicar (R-55, C-57, G-110, Q-92), corregir cantidad/unidad/categoría fundiendo líneas
cuando choque (R-56, R7, Q-92), quitar sin pedir explicaciones (C-62), y el aislamiento del
hogar (R9, R10, G-43).

Igual que en `planes/tests.py`, `entrenos/tests.py` y `progreso/tests.py`: todo pasa por el
cliente de pruebas de Django contra las URLs reales (nunca `ProductoDespensa.objects.
create(...)` a mano cuando lo que se prueba es un flujo completo) — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo: la petición tiene que
LLEGAR a lo que dice probar. La ÚNICA excepción a propósito es R4 (la restricción de la base
de datos): esa SÍ tiene que insertar saltándose la vista, porque lo que demuestra es que la
base de datos protege aunque la vista no exista o esté rota (verificación de la
especificación, mutación obligatoria nº4).
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

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


class R3_SumaPorProductoYUnidadTests(BaseDespensaTests):
    """R3 — la suma es por producto Y unidad: "arroz, 1 kg" y "arroz, 500 g" son dos líneas
    distintas, porque las unidades no son la misma (G-110)."""

    def test_arroz_en_kg_y_arroz_en_g_son_dos_lineas_distintas(self):
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        self.anadir(nombre="arroz", cantidad="500", unidad="g")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(lineas.count(), 2)
        unidades = set(lineas.values_list("unidad", flat=True))
        self.assertEqual(unidades, {"kg", "g"})


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
    """R5 — se puede corregir la cantidad, la unidad y la categoría de cualquier producto (son
    TRES cosas, cada una con su propio test)."""

    def _crear_producto(self):
        self.anadir(nombre="Leche", cantidad="1", unidad="l", categoria="lacteo")
        return ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="leche")

    def test_se_puede_corregir_la_cantidad(self):
        producto = self._crear_producto()
        self.corregir(producto.id, cantidad="3", unidad="l", categoria="lacteo")
        producto.refresh_from_db()
        self.assertEqual(producto.cantidad, Decimal("3"))

    def test_se_puede_corregir_la_unidad(self):
        producto = self._crear_producto()
        self.corregir(producto.id, cantidad="1000", unidad="ml", categoria="lacteo")
        producto.refresh_from_db()
        self.assertEqual(producto.unidad, "ml")

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
        """
        self.anadir(nombre="Aceite", cantidad="1.50", unidad="l", categoria="aceite_grasa")
        producto = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="aceite")
        respuesta = self.client.get("/despensa/")
        contenido = respuesta.content.decode()
        self.assertIn(f'id="cantidad-{producto.id}"', contenido)
        self.assertIn('value="1.50"', contenido)
        self.assertNotIn('value="1,50"', contenido)


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


class R7_CorregirLaUnidadFusionaSiChocaTests(BaseDespensaTests):
    """
    R7 (caso límite que el plano no resuelve) — hay "arroz 500 g" y "arroz 1 kg"; al
    corregir el de gramos y cambiarlo a kilos, las dos líneas se funden sumando (Q-92 es
    absoluta: nunca dos líneas del mismo producto con la misma unidad). No puede quedar un
    error a medias ni dos líneas iguales.
    """

    def test_corregir_la_unidad_y_chocar_con_otra_linea_las_funde_sumando(self):
        self.anadir(nombre="arroz", cantidad="500", unidad="g")
        self.anadir(nombre="arroz", cantidad="1", unidad="kg")
        arroz_g = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, unidad="g")
        id_del_gramos = arroz_g.id

        # Al pasar el "arroz, 500 g" a "kg" (con 0.5 kg, la conversión que haría la persona)
        # choca con la línea "arroz, 1 kg" que ya existía.
        self.corregir(arroz_g.id, cantidad="0.5", unidad="kg", categoria="cereal_pan")

        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="arroz"
        )
        self.assertEqual(lineas.count(), 1)  # nunca dos líneas iguales (Q-92)
        fundida = lineas.get()
        self.assertEqual(fundida.unidad, "kg")
        self.assertEqual(fundida.cantidad, Decimal("1.5"))  # 1 + 0.5, no un error a medias
        self.assertFalse(
            ProductoDespensa.objects.filter(id=id_del_gramos).exists()
        )  # la línea de origen no sobrevive duplicada

    def test_corregir_la_unidad_sin_chocar_no_funde_nada(self):
        # Control: si no hay ninguna línea gemela con la unidad nueva, corregir la unidad NO
        # fusiona nada raro — solo cambia esa línea.
        self.anadir(nombre="harina", cantidad="500", unidad="g")
        harina = ProductoDespensa.objects.get(hogar=self.alejandro.hogar, nombre_normalizado="harina")
        self.corregir(harina.id, cantidad="0.5", unidad="kg", categoria="cereal_pan")
        lineas = ProductoDespensa.objects.filter(
            hogar=self.alejandro.hogar, nombre_normalizado="harina"
        )
        self.assertEqual(lineas.count(), 1)
        self.assertEqual(lineas.get().unidad, "kg")
        self.assertEqual(lineas.get().cantidad, Decimal("0.5"))


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
        self.assertEqual(producto.cantidad, Decimal("1"))  # intacto


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
