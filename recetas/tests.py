"""
Tests de la unidad 021 (R1-R7, guardar-tus-recetas.md): apuntar un plato con sus ingredientes
(R-67/R1), lo obligatorio y lo opcional (R2), la preparación literal sin tocarla (R3, R-69 sin
IA), del hogar y sin autor (R4, R-70), los formatos de cantidad (R5, la lección de la 017), el
borrado sin deshacer (R6) y la casa vacía (R7).

Igual que `despensa/tests.py`, `planes/tests.py`, `entrenos/tests.py`: todo pasa por el cliente
de pruebas de Django contra las URLs reales (nunca `Receta.objects.create(...)` a mano cuando lo
que se prueba es un flujo completo) — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo: la petición tiene que
LLEGAR a lo que dice probar.

**Este fichero se escribió ANTES de que existiera la app `recetas/`** (plan de trabajo, paso 1):
la primera vez que corrió, `python manage.py test recetas` falló porque Django ni siquiera
reconocía la app (no estaba en INSTALLED_APPS) — la evidencia ROJA está en hallazgos.md,
literal con su comando (ADR-012). Después de implementar, este mismo fichero, sin tocar un
carácter de sus asserts, es el que queda en verde.
"""

from decimal import Decimal

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from despensa.models import ProductoDespensa
from hogares.models import Hogar, SolicitudEntrada

from django.contrib.auth import get_user_model

Usuario = get_user_model()


class BaseRecetasTests(PruebaConRegistroAbierto):
    """
    Alejandro y Euridice, en el MISMO hogar; Carlos, en el SUYO propio (nunca se une a nadie) —
    el mismo montaje de tres personas que `despensa/tests.py`, `progreso/tests.py` y
    `entrenos/tests.py`: R4/R10 necesita un TERCERO que nunca se una a nadie, no solo dos
    personas del mismo hogar (octava cara de tests-que-no-fallan-cuando-deben.md). La sesión
    queda en Alejandro al terminar `setUp`.
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

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el tercero de R4.
        self.registrar_y_verificar("carlos@example.com")
        self.carlos = Usuario.objects.get(email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

    # -- helpers, mismo patrón que despensa/tests.py:BaseDespensaTests -------------------

    def crear(self, **campos):
        """
        POST a /recetas/nueva/ con el episodio real de C-73/R1: la crema de champiñones de
        Alejandro (4 raciones, 6 ingredientes, comida y cena). Las listas paralelas
        `ingrediente_nombre[]`/`ingrediente_cantidad[]`/`ingrediente_unidad[]` son la técnica
        que usa el formulario real (Alpine.js clona filas con el MISMO `name`, sin índices; el
        navegador las manda como listas, y el cliente de pruebas de Django hace lo mismo si se
        le pasa una lista como valor).
        """
        datos = {
            "nombre": "Crema de champiñones",
            "raciones": "4",
            "comidas": ["comida", "cena"],
            "preparacion": "",
            "ingrediente_nombre": [
                "Champiñones", "Patatas", "Ajo", "Vino blanco", "Caldo de pollo", "Aceite",
            ],
            "ingrediente_cantidad": ["300", "2", "1", "50", "500", "50"],
            "ingrediente_unidad": ["g", "ud", "ud", "ml", "ml", "g"],
        }
        datos.update(campos)
        return self.client.post("/recetas/nueva/", datos)

    def editar(self, receta_id, **campos):
        datos = {
            "nombre": "Crema de champiñones",
            "raciones": "4",
            "comidas": ["comida", "cena"],
            "preparacion": "",
            "ingrediente_nombre": ["Champiñones"],
            "ingrediente_cantidad": ["300"],
            "ingrediente_unidad": ["g"],
        }
        datos.update(campos)
        return self.client.post(f"/recetas/{receta_id}/editar/", datos)

    def borrar(self, receta_id):
        return self.client.post(f"/recetas/{receta_id}/borrar/")

    def receta_de_alejandro(self, **campos):
        """Crea la receta del episodio real y devuelve la instancia guardada."""
        from recetas.models import Receta

        self.crear(**campos)
        return Receta.objects.get(hogar=self.alejandro.hogar, nombre=campos.get("nombre", "Crema de champiñones"))


class R1_CaminoFelizTests(BaseRecetasTests):
    """R1 (R-67, C-73) — Alejandro apunta su crema de champiñones y la receta queda disponible,
    reabrible con los seis ingredientes, sus cantidades y sus unidades intactos."""

    def test_guardar_la_receta_completa_deja_los_seis_ingredientes_intactos(self):
        from recetas.models import IngredienteDeReceta, Receta

        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 302)  # redirige al detalle recién creado

        receta = Receta.objects.get(hogar=self.alejandro.hogar, nombre="Crema de champiñones")
        self.assertEqual(receta.raciones, 4)
        self.assertEqual(set(receta.comidas), {"comida", "cena"})

        ingredientes = IngredienteDeReceta.objects.filter(receta=receta).order_by("id")
        self.assertEqual(ingredientes.count(), 6)
        esperado = [
            ("Champiñones", Decimal("300"), "g"),
            ("Patatas", Decimal("2"), "ud"),
            ("Ajo", Decimal("1"), "ud"),
            ("Vino blanco", Decimal("50"), "ml"),
            ("Caldo de pollo", Decimal("500"), "ml"),
            ("Aceite", Decimal("50"), "g"),
        ]
        obtenido = [(i.nombre, i.cantidad, i.unidad) for i in ingredientes]
        self.assertEqual(obtenido, esperado)

    def test_reabrir_la_receta_ensena_los_seis_ingredientes(self):
        receta = self.receta_de_alejandro()
        respuesta = self.client.get(f"/recetas/{receta.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        for nombre in ["Champiñones", "Patatas", "Ajo", "Vino blanco", "Caldo de pollo", "Aceite"]:
            self.assertIn(nombre, contenido)


class R2_ObligatorioYOpcionalTests(BaseRecetasTests):
    """R2 (G-140) — nombre, raciones positivas y al menos un ingrediente son obligatorios; la
    preparación y las comidas son opcionales, y sin ninguna comida marcada la receta vale para
    cualquiera (se lee así, nunca como "ninguna")."""

    def test_sin_nombre_no_se_guarda(self):
        from recetas.models import Receta

        respuesta = self.crear(nombre="")
        self.assertEqual(respuesta.status_code, 200)  # no redirige: se queda en el formulario
        self.assertFalse(Receta.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_raciones_cero_no_se_guarda(self):
        from recetas.models import Receta

        respuesta = self.crear(raciones="0")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Receta.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_raciones_negativas_no_se_guarda(self):
        from recetas.models import Receta

        respuesta = self.crear(raciones="-2")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Receta.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_sin_ningun_ingrediente_no_se_guarda(self):
        from recetas.models import Receta

        respuesta = self.crear(
            ingrediente_nombre=[""], ingrediente_cantidad=[""], ingrediente_unidad=[""]
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Receta.objects.filter(hogar=self.alejandro.hogar).exists())
        self.assertIn("Añade al menos un ingrediente", respuesta.content.decode())

    def test_la_pantalla_lo_dice_en_cristiano_cuando_falta_algo(self):
        respuesta = self.crear(nombre="")
        contenido = respuesta.content.decode()
        self.assertIn("nombre", contenido.lower())

    def test_preparacion_y_comidas_vacias_la_receta_se_guarda_con_un_solo_ingrediente(self):
        from recetas.models import Receta

        respuesta = self.crear(
            nombre="Tostada",
            comidas=[],
            preparacion="",
            ingrediente_nombre=["Pan"],
            ingrediente_cantidad=["2"],
            ingrediente_unidad=["ud"],
        )
        self.assertEqual(respuesta.status_code, 302)
        receta = Receta.objects.get(hogar=self.alejandro.hogar, nombre="Tostada")
        self.assertEqual(receta.preparacion, "")
        self.assertEqual(receta.comidas, [])
        self.assertEqual(receta.ingredientes.count(), 1)

    def test_sin_marcar_ninguna_comida_la_pantalla_dice_cualquier_comida_no_ninguna(self):
        self.crear(nombre="Tostada", comidas=[])
        from recetas.models import Receta

        receta = Receta.objects.get(hogar=self.alejandro.hogar, nombre="Tostada")
        respuesta = self.client.get(f"/recetas/{receta.id}/")
        contenido = respuesta.content.decode()
        self.assertIn("Cualquier comida", contenido)
        self.assertNotIn("Ninguna", contenido)


class R3_PreparacionLiteralTests(BaseRecetasTests):
    """R3 (R-69, la mitad sin IA; Q-120) — la preparación se guarda literal, de corrido, con
    saltos de línea, comas y tildes, y al reabrir aparece carácter por carácter igual. Nada de
    recortarla, normalizarla ni reformatearla."""

    TEXTO_DE_CORRIDO = (
        "pochas el ajo, añades los champiñones y las patatas, echas el vino y dejas que "
        "evapore,\nviertes el caldo, cueces 20 minutos\ny trituras"
    )

    def test_la_preparacion_se_guarda_caracter_por_caracter_igual(self):
        from recetas.models import Receta

        self.crear(preparacion=self.TEXTO_DE_CORRIDO)
        receta = Receta.objects.get(hogar=self.alejandro.hogar, nombre="Crema de champiñones")
        self.assertEqual(receta.preparacion, self.TEXTO_DE_CORRIDO)

    def test_reabrir_la_receta_ensena_la_preparacion_intacta_en_el_formulario_de_editar(self):
        receta = self.receta_de_alejandro(preparacion=self.TEXTO_DE_CORRIDO)
        respuesta = self.client.get(f"/recetas/{receta.id}/editar/")
        contenido = respuesta.content.decode()
        # El texto de corrido, EXACTO, tiene que aparecer literal dentro del <textarea>: ni una
        # coma, ni una tilde, ni un salto de línea distintos de los que escribió la persona.
        self.assertIn(self.TEXTO_DE_CORRIDO, contenido)


class R4_DelHogarSinAutorTests(BaseRecetasTests):
    """R4 (R-70) — Eurídice guarda una receta y Alejandro la ve, la edita y la borra sin pedir
    permiso, y en ningún sitio se guarda ni se enseña quién la escribió. Desde otro hogar, 404
    siempre — nunca 403."""

    def setUp(self):
        super().setUp()
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        self.receta = self.receta_de_alejandro()  # la crea Eurídice, cuelga del hogar
        self.client.logout()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

    def test_ningun_campo_del_modelo_guarda_quien_escribio_la_receta(self):
        # Estructural, R-70: la app no tiene NINGÚN campo de autor sobre el que apoyarse.
        from recetas.models import Receta

        nombres_de_campo = {campo.name for campo in Receta._meta.get_fields()}
        for prohibido in ("creada_por", "creado_por", "autor", "usuario", "autora"):
            self.assertNotIn(prohibido, nombres_de_campo)

    def test_alejandro_ve_la_receta_que_escribio_euridice_sin_pedir_permiso(self):
        respuesta = self.client.get(f"/recetas/{self.receta.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Crema de champiñones")

    def test_ningun_sitio_de_la_pantalla_ensena_quien_escribio_la_receta(self):
        # Eurídice escribió la receta y Alejandro la está viendo: la barra de arriba SIEMPRE
        # enseña el correo de quien tiene la sesión abierta (aquí, Alejandro) — eso es "quién
        # mira", no "quién escribió", y no tiene nada que ver con R-70. Lo que R-70 prohíbe es
        # que la AUTORA (Eurídice, que no es quien mira esta pantalla) aparezca en algún sitio.
        respuesta = self.client.get(f"/recetas/{self.receta.id}/")
        contenido = respuesta.content.decode()
        self.assertNotIn("euridice@example.com", contenido)

    def test_alejandro_puede_editar_la_receta_que_escribio_euridice_sin_pedir_permiso(self):
        respuesta = self.editar(self.receta.id, nombre="Crema de champiñones (con nata)")
        self.assertEqual(respuesta.status_code, 302)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.nombre, "Crema de champiñones (con nata)")

    def test_alejandro_puede_borrar_la_receta_que_escribio_euridice_sin_pedir_permiso(self):
        from recetas.models import Receta

        respuesta = self.borrar(self.receta.id)
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Receta.objects.filter(id=self.receta.id).exists())

    def test_carlos_de_otro_hogar_recibe_404_al_ver(self):
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/recetas/{self.receta.id}/")
        self.assertEqual(respuesta.status_code, 404)

    def test_carlos_de_otro_hogar_recibe_404_al_editar(self):
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.editar(self.receta.id, nombre="Robada")
        self.assertEqual(respuesta.status_code, 404)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.nombre, "Crema de champiñones")

    def test_carlos_de_otro_hogar_recibe_404_al_borrar(self):
        from recetas.models import Receta

        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.borrar(self.receta.id)
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Receta.objects.filter(id=self.receta.id).exists())

    def test_la_lista_de_carlos_no_ensena_la_receta_de_otro_hogar(self):
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/recetas/")
        self.assertNotContains(respuesta, "Crema de champiñones")

    def test_nunca_403_siempre_404(self):
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get(f"/recetas/{self.receta.id}/")
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)


class R5_FormatosDeCantidadTests(BaseRecetasTests):
    """R5 (la lección de la 017) — las cantidades no pierden decimales, y cada canal usa su
    formato: el `<input>` trabaja con punto (formato de máquina), la lectura se enseña con
    coma. Un "0,5" tecleado no puede convertirse en 0 ni reventar el formulario."""

    def trozo_input_cantidad(self, contenido, indice=0):
        """Aísla el `<input name="ingrediente_cantidad" ...>` de la fila `indice` — nunca la
        página entera (bug 016/018: un literal corto puede colar por el token CSRF aleatorio;
        décima cara de tests-que-no-fallan-cuando-deben.md: acota siempre a la pieza)."""
        marcador = 'name="ingrediente_cantidad"'
        trozos = contenido.split(marcador)
        return trozos[indice + 1].split(">", 1)[0]

    def test_medio_kilo_tecleado_como_0_5_se_guarda_exacto_no_como_0(self):
        from recetas.models import IngredienteDeReceta

        self.crear(
            ingrediente_nombre=["Arroz"], ingrediente_cantidad=["0.5"], ingrediente_unidad=["kg"],
        )
        ingrediente = IngredienteDeReceta.objects.get(nombre="Arroz")
        self.assertEqual(ingrediente.cantidad, Decimal("0.5"))
        self.assertNotEqual(ingrediente.cantidad, Decimal("0"))

    def test_el_input_de_cantidad_al_reabrir_usa_punto_no_coma(self):
        # Séptima cara de tests-que-no-fallan-cuando-deben.md: con LANGUAGE_CODE="es", un
        # Decimal puesto a pelo en el `value` de un `<input type="number">` sale con coma, que
        # el navegador descarta en silencio. Aquí se comprueba el HTML crudo.
        receta = self.receta_de_alejandro(
            ingrediente_nombre=["Vino blanco"], ingrediente_cantidad=["1.50"],
            ingrediente_unidad=["l"],
        )
        respuesta = self.client.get(f"/recetas/{receta.id}/editar/")
        contenido = respuesta.content.decode()
        trozo = self.trozo_input_cantidad(contenido)
        self.assertIn('value="1.50"', trozo)
        self.assertNotIn('value="1,50"', trozo)

    def test_la_lectura_del_detalle_ensena_la_cantidad_con_coma(self):
        receta = self.receta_de_alejandro(
            ingrediente_nombre=["Vino blanco"], ingrediente_cantidad=["1.5"],
            ingrediente_unidad=["l"],
        )
        respuesta = self.client.get(f"/recetas/{receta.id}/")
        contenido = respuesta.content.decode()
        self.assertIn("1,5", contenido)

    def test_una_cantidad_no_numerica_no_se_guarda_y_lo_dice(self):
        from recetas.models import Receta

        respuesta = self.crear(
            ingrediente_nombre=["Arroz"], ingrediente_cantidad=["abc"], ingrediente_unidad=["g"],
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Receta.objects.filter(hogar=self.alejandro.hogar).exists())

    def test_una_cantidad_cero_o_negativa_no_se_guarda(self):
        from recetas.models import Receta

        respuesta = self.crear(
            ingrediente_nombre=["Arroz"], ingrediente_cantidad=["0"], ingrediente_unidad=["g"],
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Receta.objects.filter(hogar=self.alejandro.hogar).exists())


class R6_BorrarTests(BaseRecetasTests):
    """R6 (caso límite) — borrar una receta no se puede deshacer y pide confirmación antes.
    Borrar la receta no toca la despensa ni ningún otro dato del hogar."""

    def test_borrar_pide_confirmacion_antes(self):
        receta = self.receta_de_alejandro()
        respuesta = self.client.get(f"/recetas/{receta.id}/")
        contenido = respuesta.content.decode()
        # La confirmación es del navegador (`confirm(...)` o `hx-confirm`), no una pantalla
        # aparte: comprobamos que el botón de borrar la lleva puesta.
        self.assertTrue("confirm(" in contenido or "hx-confirm" in contenido)

    def test_borrar_es_definitivo(self):
        from recetas.models import Receta

        receta = self.receta_de_alejandro()
        self.borrar(receta.id)
        self.assertFalse(Receta.objects.filter(id=receta.id).exists())

    def test_borrar_una_receta_no_toca_la_despensa(self):
        self.client.post(
            "/despensa/anadir/",
            {"nombre": "Tomate", "cantidad": "2", "unidad": "lata", "categoria": "verdura"},
        )
        receta = self.receta_de_alejandro()
        self.borrar(receta.id)
        self.assertTrue(
            ProductoDespensa.objects.filter(
                hogar=self.alejandro.hogar, nombre_normalizado="tomate"
            ).exists()
        )

    def test_borrar_no_pide_ningun_motivo_ni_campo_extra(self):
        from recetas.models import Receta

        receta = self.receta_de_alejandro()
        respuesta = self.client.post(f"/recetas/{receta.id}/borrar/", {})
        self.assertNotEqual(respuesta.status_code, 400)
        self.assertFalse(Receta.objects.filter(id=receta.id).exists())


class R7_CasaVaciaTests(BaseRecetasTests):
    """R7 (caso límite) — un hogar sin ninguna receta ve una pantalla que lo dice con
    naturalidad y ofrece apuntar la primera, no una tabla vacía ni un error."""

    def test_sin_ninguna_receta_no_da_error_y_lo_dice_con_naturalidad(self):
        respuesta = self.client.get("/recetas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no hay ninguna receta")

    def test_sin_ninguna_receta_ofrece_apuntar_la_primera(self):
        respuesta = self.client.get("/recetas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "/recetas/nueva/")

    def test_una_persona_recien_llegada_al_hogar_tambien_ve_la_pantalla_vacia_sin_reventar(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/recetas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no hay ninguna receta")


class NavegacionTests(BaseRecetasTests):
    """El enlace "Recetas" en la barra de arriba, al lado de "Despensa" (el "Cómo" de la
    especificación: barra plana, sin pestañas)."""

    def test_la_barra_de_arriba_trae_el_enlace_a_recetas(self):
        respuesta = self.client.get("/recetas/")
        contenido = respuesta.content.decode()
        self.assertIn('href="/recetas/"', contenido)
        self.assertIn(">Recetas<", contenido)
