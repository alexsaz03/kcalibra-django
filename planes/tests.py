"""
Tests de la unidad 005: R1, R6, R7, R9, R10, R11.

Como en `hogares/tests.py` y `perfiles/tests.py`, todo pasa por el cliente de pruebas de
Django contra las URLs reales (nunca `PlanDeDia.objects.create(...)` a mano cuando lo que se
prueba es un flujo completo) — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo: la petición tiene que
LLEGAR a lo que dice probar. R8 (el cálculo puro) ya está probado sin base de datos ni vista
en `servicios/tests.py` — aquí se prueba el CABLEADO: modelo → lógica → vista → puerta de
acceso.

R6 y R7 (la asimetría de G-43, el corazón de esta unidad) se comprueban SIEMPRE llamando al
servidor con `self.client`, nunca mirando si un botón se pinta o no (regla del constructor).
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import SolicitudEntrada
from planes.models import ComidaDelPlan, PlanDeDia

Usuario = get_user_model()

# El mismo "hoy" congelado que usa perfiles/tests.py, y por la misma razón: la edad (y por
# tanto las calorías objetivo de 3.006/1.894 que citan los criterios) depende de la fecha de
# nacimiento frente a HOY. Sin fijarlo, estos tests se volverían frágiles el día del
# cumpleaños de Alejandro o Euridice — aunque hoy (al escribir esto) dé el mismo resultado.
HOY_DE_REFERENCIA = date(2026, 8, 2)


class _FechaFija(date):
    @classmethod
    def today(cls):
        return HOY_DE_REFERENCIA


def _con_hoy_fijo():
    return mock.patch("servicios.metabolismo.date", _FechaFija)


class BaseConHogarDeDosPersonas(PruebaConRegistroAbierto):
    """
    Monta un hogar con Alejandro y Euridice DENTRO (registro, verificación y aceptación de
    verdad por HTTP, igual que `hogares/tests.py:AislamientoPorHogarTests`), y un tercer hogar
    aparte con Berta, para los tests de aislamiento (R7). No se toca `cuentas/` ni `hogares/`:
    solo se llaman sus URLs ya existentes.
    """

    def setUp(self):
        super().setUp()
        # "Hoy" congelado (ver el docstring de HOY_DE_REFERENCIA) durante TODO el test: así
        # cualquier `self.client.get("/")` o `self.apuntar(...)` de las subclases ve siempre
        # las mismas 3.006/1.894 kcal de objetivo, sin tener que envolver cada llamada.
        parche_de_hoy = _con_hoy_fijo()
        parche_de_hoy.start()
        self.addCleanup(parche_de_hoy.stop)

        # Alejandro: primero, se monta su propio hogar (datos que dan 3.006 kcal de objetivo,
        # el episodio de C-79/R2 de la unidad 004, para poder reutilizarlo en R2 de esta).
        self.registrar_y_verificar(
            "alejandro@example.com",
            sexo="hombre",
            fecha_nacimiento="1998-11-03",
            altura_cm="190",
            peso_kg="93",
            actividad="ligero",
            objetivo="recomposicion_corporal",
        )
        self.alejandro = Usuario.objects.get(email="alejandro@example.com")
        self.client.logout()

        # Euridice pide entrar en el hogar de Alejandro con su código, y él la acepta.
        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Usuario.objects.get(email="euridice@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.client.logout()
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control

        # Berta: un hogar totalmente aparte, para los tests de aislamiento (R7).
        self.registrar_y_verificar("berta@example.com")
        self.berta = Usuario.objects.get(email="berta@example.com")
        self.client.logout()

    def apuntar(self, usuario_objetivo, **campos):
        """Envía el formulario de apuntar una comida a `usuario_objetivo`, con el cliente ya
        logueado como quien corresponda en cada test."""
        datos = {
            "nombre": "Pechuga con arroz",
            "momento_del_dia": "comida",
            "calorias": "500",
            "proteina_g": "40",
            "grasa_g": "10",
            "carbos_g": "50",
            **campos,
        }
        return self.client.post(f"/planes/{usuario_objetivo.id}/apuntar/", datos, follow=True)


class R1_ApuntarComidaApareceEnLaTarjetaTests(BaseConHogarDeDosPersonas):
    """R1 — apuntar a mano una comida (nombre, momento, calorías y macros) la deja guardada Y
    la enseña en la tarjeta del Inicio de esa persona."""

    def test_la_comida_apuntada_se_guarda_con_todos_sus_datos(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        self.apuntar(
            self.alejandro,
            nombre="Tortilla de claras",
            momento_del_dia="desayuno",
            calorias="450",
            proteina_g="35",
            grasa_g="12",
            carbos_g="20",
        )

        plan = PlanDeDia.objects.get(usuario=self.alejandro, fecha=timezone.localdate())
        comida = plan.comidas.get()
        self.assertEqual(comida.nombre, "Tortilla de claras")
        self.assertEqual(comida.momento_del_dia, "desayuno")
        self.assertEqual(comida.calorias, 450)
        self.assertEqual(comida.proteina_g, 35)
        self.assertEqual(comida.grasa_g, 12)
        self.assertEqual(comida.carbos_g, 20)

    def test_la_comida_apuntada_aparece_en_el_inicio(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        self.apuntar(self.alejandro, nombre="Tortilla de claras")

        respuesta = self.client.get("/")

        self.assertContains(respuesta, "Tortilla de claras")

    def test_una_segunda_comida_el_mismo_dia_se_suma_al_mismo_plan_no_crea_otro(self):
        """"Cómo" de la especificación — "una persona, un plan por día": sustitución (se sigue
        completando el MISMO plan), no acumulación de planes distintos."""
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        self.apuntar(self.alejandro, nombre="Desayuno", momento_del_dia="desayuno")
        self.apuntar(self.alejandro, nombre="Cena", momento_del_dia="cena")

        self.assertEqual(PlanDeDia.objects.filter(usuario=self.alejandro).count(), 1)
        plan = PlanDeDia.objects.get(usuario=self.alejandro)
        self.assertEqual(plan.comidas.count(), 2)


class R2_AnilloComparaElPlanConElObjetivoTests(BaseConHogarDeDosPersonas):
    """R2/C-79 — Alejandro, con 3.006 kcal de objetivo, y un plan que suma 2.800, ve el
    anillo en torno al 93%."""

    def test_el_inicio_ensena_el_93_por_ciento(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        self.apuntar(
            self.alejandro,
            nombre="Comida grande",
            calorias="2800",
            proteina_g="0",
            grasa_g="0",
            carbos_g="0",
        )

        respuesta = self.client.get("/")

        self.assertContains(respuesta, "3006 kcal")  # su objetivo del día (unidad 004)
        self.assertContains(respuesta, "93%")


class R4_TarjetaPropiaPrimeraTests(BaseConHogarDeDosPersonas):
    """
    R4/C-78/G-152 — una tarjeta por persona del hogar, y la de quien abre la app va SIEMPRE
    la primera.

    H1 de la revisión: buscar el email a pelo en TODA la página no vale para comprobar el
    orden — `templates/base.html` imprime `{{ user.email }}` en la barra de arriba de
    CUALQUIER pantalla, así que el email de quien mira aparece SIEMPRE antes que cualquier
    tarjeta, pase lo que pase con el orden real (la aserción daba verde incluso con las
    tarjetas invertidas a propósito). Se compara en su lugar la posición del `id="tarjeta-N"`
    que pinta `paginas/templates/paginas/inicio.html` en cada `<section>`, que solo existe
    dentro del contenedor de tarjetas.
    """

    def test_alejandro_ve_la_suya_primero_y_la_de_euridice_debajo(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        contenido = respuesta.content.decode()
        posicion_alejandro = contenido.index(f'id="tarjeta-{self.alejandro.id}"')
        posicion_euridice = contenido.index(f'id="tarjeta-{self.euridice.id}"')
        self.assertLess(posicion_alejandro, posicion_euridice)

    def test_euridice_ve_la_suya_primero_y_la_de_alejandro_debajo(self):
        """Mismo hogar, misma pantalla: el orden depende de QUIÉN mira, no de quién se
        registró antes (C-78)."""
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        contenido = respuesta.content.decode()
        posicion_euridice = contenido.index(f'id="tarjeta-{self.euridice.id}"')
        posicion_alejandro = contenido.index(f'id="tarjeta-{self.alejandro.id}"')
        self.assertLess(posicion_euridice, posicion_alejandro)


class R5_SinPlanElInicioSigueSirviendoTests(BaseConHogarDeDosPersonas):
    """R5/C-80/G-153 — sin plan puesto: calorías y macros igual, anillo vacío, y un botón
    para apuntar el plan. Datos de Euridice (C-80: 1.894 kcal de objetivo)."""

    def test_sin_plan_se_ven_las_calorias_los_macros_y_el_boton(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        self.assertContains(respuesta, "1894 kcal")  # su objetivo (unidad 004, datos de fábrica)
        self.assertContains(respuesta, "Apuntar el plan")
        self.assertFalse(PlanDeDia.objects.filter(usuario=self.euridice).exists())

    def test_el_boton_lleva_a_la_pantalla_de_apuntar_su_propio_plan(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/")
        self.assertContains(respuesta, f'/planes/{self.euridice.id}/apuntar/')


class H2_EsperandoAceptacionNoOfreceEnlaceMuertoTests(PruebaConRegistroAbierto):
    """
    H2 de la revisión — mientras alguien espera que le acepten en un hogar (R14 de la unidad
    003: se registró CON el código de otro hogar y su cuenta queda "sola", `hogar = None`,
    hasta que alguien de dentro la acepte), su Inicio seguía enseñando el botón "Apuntar el
    plan", pero apuntaba a una URL que SIEMPRE daba 404 —`PlanDeDia.hogar` es obligatorio y
    no hay ningún hogar todavía al que colgar el plan—. Incumplía R5/G-153: "una pantalla
    vacía que no explica nada ni ofrece salida es una pantalla rota" — aquí la salida existía
    pero no llevaba a ningún sitio, que es casi peor. Es el MISMO estado ("esperando
    aceptación") que ya se había pasado por alto en el perfil propio de la unidad 004 (ver
    hallazgos.md de esta unidad, sección de descubrimientos).

    Clase aparte de `BaseConHogarDeDosPersonas` a propósito: esa base SIEMPRE acepta la
    solicitud en el `setUp`; aquí hace falta el estado intermedio, sin aceptar.
    """

    def setUp(self):
        super().setUp()
        parche_de_hoy = _con_hoy_fijo()
        parche_de_hoy.start()
        self.addCleanup(parche_de_hoy.stop)

        self.registrar_y_verificar("alejandro@example.com")
        self.alejandro = Usuario.objects.get(email="alejandro@example.com")
        self.client.logout()

        # Euridice pide entrar con el código de Alejandro, pero NADIE la acepta todavía: se
        # queda "esperando" (hogar = None), el estado que hay que comprobar aquí.
        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Usuario.objects.get(email="euridice@example.com")
        self.assertIsNone(self.euridice.hogar_id)  # control: sigue esperando, no aceptada

    def test_no_ofrece_el_enlace_muerto_de_apuntar_el_plan(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, f"/planes/{self.euridice.id}/apuntar/")
        self.assertContains(
            respuesta, "Cuando te acepten en el hogar podrás apuntar tu plan."
        )

    def test_sigue_ensenando_sus_calorias_y_macros_igual_r5(self):
        """R5/G-153 no se rompe por estar sin hogar: sin plan (y encima sin hogar todavía) el
        Inicio sigue sirviendo, con sus calorías y macros de siempre."""
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        self.assertContains(respuesta, "1894 kcal")  # datos de fábrica (unidad 004)

    def test_la_url_de_apuntar_tecleada_a_mano_sigue_dando_404(self):
        """Control negativo: quitar el enlace del botón no basta por sí solo — si alguien
        teclea la URL a mano (o la tenía guardada de antes de este arreglo), tiene que seguir
        respondiendo 404, no reventar con un `IntegrityError` al intentar crear un plan sin
        hogar."""
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get(f"/planes/{self.euridice.id}/apuntar/")

        self.assertEqual(respuesta.status_code, 404)


class R6_CualquieraDelHogarApuntaAOtroSinPedirPermisoTests(BaseConHogarDeDosPersonas):
    """
    R6/G-43, el corazón de la unidad — Alejandro puede apuntarle la cena a Euridice SIN pedir
    permiso a nadie. Es lo contrario del perfil (unidad 004): probado llamando al SERVIDOR,
    con Alejandro logueado y el `usuario_id` de Euridice en la URL, no mirando ninguna
    pantalla.
    """

    def test_alejandro_le_apunta_la_cena_a_euridice(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.apuntar(
            self.euridice, nombre="Cena que le puso Alejandro", momento_del_dia="cena"
        )

        self.assertEqual(respuesta.status_code, 200)
        plan_de_euridice = PlanDeDia.objects.get(usuario=self.euridice, fecha=timezone.localdate())
        comida = plan_de_euridice.comidas.get()
        self.assertEqual(comida.nombre, "Cena que le puso Alejandro")

    def test_euridice_ve_en_su_tarjeta_la_comida_que_le_puso_alejandro(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        self.apuntar(self.euridice, nombre="Cena que le puso Alejandro")
        self.client.logout()

        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/")

        self.assertContains(respuesta, "Cena que le puso Alejandro")

    def test_no_hace_falta_ninguna_aceptacion_ni_aviso_pendiente(self):
        """A diferencia de "entrar en el hogar" (unidad 003), esto no crea ninguna solicitud
        ni deja nada "pendiente": se guarda directamente."""
        conteo_antes = SolicitudEntrada.objects.count()
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        self.apuntar(self.euridice, nombre="Cena que le puso Alejandro")

        self.assertEqual(SolicitudEntrada.objects.count(), conteo_antes)


class R7_NadieDeOtroHogarVeNiTocaElPlanTests(BaseConHogarDeDosPersonas):
    """
    R7/Q-20/G-43 — Berta, de otro hogar, no puede ver ni tocar el plan de Alejandro ni de
    Euridice, tampoco llamando directamente al servidor con la dirección exacta. Mismo
    principio que `hogares/acceso.py`: 404, nunca 403 (indistinguible de "no existe").
    """

    def test_berta_no_puede_apuntarle_una_comida_a_alejandro(self):
        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)

        respuesta = self.apuntar(self.alejandro, nombre="Comida colada")

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(
            ComidaDelPlan.objects.filter(nombre="Comida colada").exists()
        )

    def test_berta_no_puede_ver_la_pantalla_de_apuntar_de_euridice(self):
        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get(f"/planes/{self.euridice.id}/apuntar/")

        self.assertEqual(respuesta.status_code, 404)

    def test_un_desconocido_sin_sesion_no_puede_tocar_nada(self):
        # Sin `follow`, a propósito: lo que hay que comprobar es el 302 crudo de
        # `@login_required` (la segunda cara del test que no protege — seguir la redirección
        # de más escondería justo lo que aquí se quiere ver).
        respuesta = self.client.post(
            f"/planes/{self.alejandro.id}/apuntar/", {"nombre": "Comida colada"}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuentas/login/", respuesta.url)
        self.assertFalse(ComidaDelPlan.objects.filter(nombre="Comida colada").exists())

    def test_el_plan_de_alejandro_no_sale_en_el_inicio_de_berta(self):
        """Berta vive sola en su propio hogar (R14 de la unidad 003): su Inicio no debe
        enseñar ni rastro del plan de Alejandro."""
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        self.apuntar(self.alejandro, nombre="Comida de Alejandro")
        self.client.logout()

        self.client.login(username="berta@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/")

        self.assertNotContains(respuesta, "Comida de Alejandro")
        self.assertNotContains(respuesta, "alejandro@example.com")


class R9_UnPlanPasadoNoRompeElAnilloTests(BaseConHogarDeDosPersonas):
    """R9 (caso límite) — un plan que suma más calorías que el objetivo del día no da
    porcentajes absurdos ni revienta la pantalla."""

    def test_un_plan_pasado_se_ve_de_verdad_pasado_sin_reventar(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        # 3.600 kcal frente a un objetivo de 3.006: 120% (calculado y probado ya en
        # servicios/tests.py; aquí se comprueba que llega intacto hasta la pantalla).
        self.apuntar(
            self.alejandro,
            nombre="Comida enorme",
            calorias="3600",
            proteina_g="0",
            grasa_g="0",
            carbos_g="0",
        )

        respuesta = self.client.get("/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "120%")


class R10_ValoresImposiblesSeRechazanTests(BaseConHogarDeDosPersonas):
    """R10 (caso límite) — calorías o macros negativos, o una comida sin nombre, se rechazan
    al apuntar, avisando de cuál está mal. Nada de eso llega a guardarse."""

    def test_calorias_negativas_se_rechazan(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.apuntar(self.alejandro, calorias="-100")

        self.assertEqual(respuesta.status_code, 200)  # re-muestra el formulario, no revienta
        self.assertFalse(ComidaDelPlan.objects.filter(plan__usuario=self.alejandro).exists())

    def test_macro_negativo_se_rechaza(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.apuntar(self.alejandro, proteina_g="-5")

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ComidaDelPlan.objects.filter(plan__usuario=self.alejandro).exists())

    def test_una_comida_sin_nombre_se_rechaza(self):
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.apuntar(self.alejandro, nombre="")

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(ComidaDelPlan.objects.filter(plan__usuario=self.alejandro).exists())

    def test_se_avisa_de_cual_esta_mal(self):
        """R10 — "se avisa de cuál está mal": el mensaje de error tiene que salir en la
        respuesta, no solo un 200 vacío (la primera cara del test que no protege:
        aserción floja)."""
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.apuntar(self.alejandro, calorias="-100")

        # El formulario vuelve con el error del campo de calorías señalado.
        self.assertFalse(respuesta.context["form"].is_valid())
        self.assertIn("calorias", respuesta.context["form"].errors)


class R11_SoloCuentaElPlanDeHoyTests(BaseConHogarDeDosPersonas):
    """R11 (caso límite) — un plan de ayer o de mañana no se suma ni aparece en el Inicio."""

    def test_un_plan_de_ayer_no_se_cuenta_en_el_inicio(self):
        ayer = PlanDeDia.objects.create(
            usuario=self.alejandro, hogar=self.alejandro.hogar, fecha=timezone.localdate() - timedelta(days=1)
        )
        ComidaDelPlan.objects.create(
            plan=ayer, nombre="Comida de ayer", momento_del_dia="comida", calorias=999
        )
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        # Unidad 012 (decir-si-cumpliste.md, R6) añadió a esta MISMA pantalla la pregunta de
        # si se cumplió el plan de ayer, que enseña —a propósito— el menú de ayer (§8 del
        # plano: "qué tenía puesto ayer"). Por eso el texto de "Comida de ayer" SÍ puede
        # aparecer en la página entera ahora; lo que R11 promete de verdad —que el ANILLO/
        # tarjeta de HOY no cuenta ni enseña un plan de otro día— sigue intacto y se comprueba
        # aislando esa comprobación a la TARJETA (id="tarjeta-<id>"), no a la página completa.
        contenido = respuesta.content.decode()
        inicio_tarjeta = contenido.index(f'id="tarjeta-{self.alejandro.id}"')
        fin_tarjeta = contenido.index("</section>", inicio_tarjeta)
        tarjeta = contenido[inicio_tarjeta:fin_tarjeta]
        self.assertNotIn("Comida de ayer", tarjeta)
        self.assertIn("Apuntar el plan", tarjeta)  # a ojos de hoy, sigue sin plan

    def test_un_plan_de_manana_no_se_cuenta_en_el_inicio(self):
        manana = PlanDeDia.objects.create(
            usuario=self.alejandro, hogar=self.alejandro.hogar, fecha=timezone.localdate() + timedelta(days=1)
        )
        ComidaDelPlan.objects.create(
            plan=manana, nombre="Comida de mañana", momento_del_dia="comida", calorias=999
        )
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.get("/")

        self.assertNotContains(respuesta, "Comida de mañana")

    def test_apuntar_una_comida_hoy_cuelga_del_plan_de_hoy_no_del_de_ayer_ni_manana(self):
        PlanDeDia.objects.create(
            usuario=self.alejandro, hogar=self.alejandro.hogar, fecha=timezone.localdate() - timedelta(days=1)
        )
        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)

        self.apuntar(self.alejandro, nombre="Comida de hoy")

        plan_de_hoy = PlanDeDia.objects.get(usuario=self.alejandro, fecha=timezone.localdate())
        self.assertEqual(plan_de_hoy.comidas.get().nombre, "Comida de hoy")
        # El de ayer sigue existiendo, intacto y sin la comida de hoy dentro.
        plan_de_ayer = PlanDeDia.objects.get(
            usuario=self.alejandro, fecha=timezone.localdate() - timedelta(days=1)
        )
        self.assertEqual(plan_de_ayer.comidas.count(), 0)


class UnPlanPorPersonaYDiaTests(TestCase):
    """"Cómo" de la especificación — restricción de base de datos: no se pueden colgar dos
    `PlanDeDia` del mismo día para la misma persona (sustitución, no acumulación, G-20)."""

    def test_la_base_de_datos_impide_dos_planes_del_mismo_dia_para_la_misma_persona(self):
        from django.db import IntegrityError, transaction

        usuario = Usuario.objects.create_user(email="x@example.com", password="x")
        from hogares.models import crear_hogar_propio

        crear_hogar_propio(usuario)
        PlanDeDia.objects.create(usuario=usuario, hogar=usuario.hogar, fecha=timezone.localdate())

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlanDeDia.objects.create(
                    usuario=usuario, hogar=usuario.hogar, fecha=timezone.localdate()
                )
