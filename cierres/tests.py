"""
Tests de la unidad 012 (R1-R13, decir-si-cumpliste.md): cerrar el día diciendo si se siguió el
plan, con la pregunta al abrir la app para el último día pendiente (R6-R9) y el cierre a mano
desde Progreso (R10).

Igual que en `entrenos/tests.py`, `progreso/tests.py` y `planes/tests.py`: todo pasa por el
cliente de pruebas de Django contra las URLs reales (la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo — la petición tiene que
LLEGAR a lo que dice probar). `calcular_dia_pendiente` (la función pura) ya está probada sin
base de datos ni vista en `servicios/tests.py`; aquí se prueba el CABLEADO completo: modelo →
lógica → vista → puerta de acceso → plantilla.

El montaje de `BaseCierresTests` sigue el mismo patrón de tres personas que ya usa
`entrenos/tests.py` y `progreso/tests.py` (octava cara de
conocimiento/tests-que-no-fallan-cuando-deben.md: un permiso "propio / mismo hogar / de fuera"
necesita un TERCERO que nunca se una a nadie, no solo dos personas del mismo hogar) — R12 lo
exige literalmente ("del hogar o de fuera").
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Persona, SolicitudEntrada
from planes.models import ComidaDelPlan, PlanDeDia

from .logica import cerrar_dia, dia_pendiente_de_preguntar, saltar_dia_pendiente
from .models import CierreDeDia, ComidaSeguida, DiaSaltado, MenuSeguido

Usuario = get_user_model()


def _crear_plan(usuario, fecha, comidas):
    """Crea un `PlanDeDia` de `usuario` en `fecha` con las `comidas` dadas (lista de dicts con
    nombre/momento_del_dia/calorias/macros). Ayuda a montar el escenario de R4/R5 sin pasar
    por la pantalla de "apuntar el plan" (eso ya lo prueba `planes/tests.py`)."""
    plan = PlanDeDia.objects.create(persona=usuario, fecha=fecha, hogar=usuario.hogar)
    for datos in comidas:
        ComidaDelPlan.objects.create(plan=plan, **datos)
    return plan


class BaseCierresTests(PruebaConRegistroAbierto):
    """
    Alejandro y Euridice, en el MISMO hogar; Carlos, en el SUYO propio (nunca se une a
    nadie) — el mismo montaje de tres personas que ya usa `entrenos/tests.py` y
    `progreso/tests.py`, necesario para R12. La sesión queda en Alejandro al terminar `setUp`.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.client.logout()

        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice.usuario)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control
        self.client.logout()

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el tercero de R12.
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)


# ---------------------------------------------------------------------------------------- #
# R1/R2 — las tres respuestas, con calorías y nota opcionales de verdad.
# ---------------------------------------------------------------------------------------- #


class R1_CierreAMediasSinCaloriasNiNotaTests(BaseCierresTests):
    """R1 (el episodio real de Alejandro) — "a medias", sin calorías ni nota: el día queda
    cerrado igual y cuenta como parcial."""

    def test_cerrar_a_medias_sin_calorias_ni_nota_queda_cerrado(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "a_medias",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro)
        self.assertEqual(cierre.respuesta, CierreDeDia.A_MEDIAS)
        self.assertIsNone(cierre.calorias_comidas)
        self.assertEqual(cierre.nota, "")


class R2_TresRespuestasYCamposOpcionalesTests(BaseCierresTests):
    """
    R2 — la app ofrece EXACTAMENTE tres respuestas, ninguna más; calorías y nota son
    opcionales de verdad (heurística de conocimiento/tests-que-no-fallan-cuando-deben.md: el
    criterio nombra "tres respuestas Y dos campos opcionales", así que hacen falta las DOS
    comprobaciones, no solo una).
    """

    def test_el_formulario_ofrece_exactamente_tres_respuestas_ninguna_mas(self):
        from .forms import FormularioCierre

        valores = [clave for clave, _ in FormularioCierre().fields["respuesta"].choices]
        self.assertEqual(sorted(valores), sorted(["lo_segui", "a_medias", "no_lo_segui"]))
        self.assertEqual(len(valores), 3)

    def test_se_puede_cerrar_con_las_tres_respuestas_sin_reventar(self):
        for i, respuesta in enumerate(["lo_segui", "a_medias", "no_lo_segui"]):
            fecha = (timezone.localdate() - timedelta(days=i + 10)).isoformat()
            respuesta_http = self.client.post(
                f"/cierres/{self.alejandro.id}/",
                {"fecha": fecha, "respuesta": respuesta, "calorias_comidas": "", "nota": ""},
            )
            self.assertEqual(respuesta_http.status_code, 200)
        self.assertEqual(CierreDeDia.objects.filter(persona=self.alejandro).count(), 3)

    def test_calorias_y_nota_son_opcionales_se_puede_omitir_solo_una(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "1800", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro)
        self.assertEqual(cierre.calorias_comidas, 1800)
        self.assertEqual(cierre.nota, "")


# ---------------------------------------------------------------------------------------- #
# R3 — un registro por persona y día, el nuevo sustituye al anterior.
# ---------------------------------------------------------------------------------------- #


class R3_SustituirNoDuplicarTests(BaseCierresTests):
    def test_cerrar_el_mismo_dia_dos_veces_sustituye_no_duplica(self):
        fecha = timezone.localdate().isoformat()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha, "respuesta": "no_lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha, "respuesta": "lo_segui", "calorias_comidas": "2000", "nota": "ok"},
        )
        self.assertEqual(CierreDeDia.objects.filter(persona=self.alejandro).count(), 1)
        cierre = CierreDeDia.objects.get(persona=self.alejandro)
        self.assertEqual(cierre.respuesta, CierreDeDia.LO_SEGUI)
        self.assertEqual(cierre.calorias_comidas, 2000)
        self.assertEqual(cierre.nota, "ok")

    def test_la_restriccion_vive_en_la_base_de_datos(self):
        """Igual que `MedicionPeso.una_medicion_por_persona_y_dia` (unidad 006): un `create()`
        suelto que se salte la capa de lógica revienta contra la base, no solo contra la vista."""
        hoy = timezone.localdate()
        CierreDeDia.objects.create(persona=self.alejandro, fecha=hoy, respuesta="lo_segui")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CierreDeDia.objects.create(persona=self.alejandro, fecha=hoy, respuesta="no_lo_segui")


# ---------------------------------------------------------------------------------------- #
# R4/R5 — la foto del menú: SÍ si "lo seguí" entero, NO si "a medias" o "no", y el registro
# del día queda en los dos casos. Sin plan puesto, no hay nada que fotografiar.
# ---------------------------------------------------------------------------------------- #


class R4_C84_FotoDelMenuTests(BaseCierresTests):
    """
    R4/C-84 (el caso de Alejandro: martes lo siguió entero, miércoles no) — el menú del
    martes queda guardado como plan seguido; el del miércoles no, aunque de los dos queda el
    registro del día (heurística de conocimiento/tests-que-no-fallan-cuando-deben.md: "el
    menú SÍ y el menú NO, MÁS que el registro queda en los dos casos" son tres comprobaciones).
    """

    def setUp(self):
        super().setUp()
        self.martes = timezone.localdate() - timedelta(days=2)
        self.miercoles = timezone.localdate() - timedelta(days=1)
        self.plan_martes = _crear_plan(
            self.alejandro, self.martes,
            [{"nombre": "Pollo con arroz", "momento_del_dia": "comida", "calorias": 700,
              "proteina_g": 50, "grasa_g": 15, "carbos_g": 80}],
        )
        self.plan_miercoles = _crear_plan(
            self.alejandro, self.miercoles,
            [{"nombre": "Ensalada", "momento_del_dia": "comida", "calorias": 400,
              "proteina_g": 20, "grasa_g": 10, "carbos_g": 40}],
        )

    def test_el_martes_lo_siguio_entero_y_el_menu_queda_guardado(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": self.martes.isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro, fecha=self.martes)
        self.assertTrue(MenuSeguido.objects.filter(cierre=cierre).exists())
        comida = ComidaSeguida.objects.get(menu__cierre=cierre)
        self.assertEqual(comida.nombre, "Pollo con arroz")
        self.assertEqual(comida.calorias, 700)

    def test_el_miercoles_no_lo_siguio_y_el_menu_NO_se_guarda(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": self.miercoles.isoformat(), "respuesta": "no_lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro, fecha=self.miercoles)
        self.assertFalse(MenuSeguido.objects.filter(cierre=cierre).exists())

    def test_los_dos_dias_dejan_su_registro_aunque_solo_uno_guarde_el_menu(self):
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": self.martes.isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": self.miercoles.isoformat(), "respuesta": "no_lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(CierreDeDia.objects.filter(persona=self.alejandro).count(), 2)
        self.assertEqual(MenuSeguido.objects.filter(cierre__persona=self.alejandro).count(), 1)

    def test_a_medias_tampoco_guarda_el_menu(self):
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": self.martes.isoformat(), "respuesta": "a_medias",
             "calorias_comidas": "", "nota": ""},
        )
        cierre = CierreDeDia.objects.get(persona=self.alejandro, fecha=self.martes)
        self.assertFalse(MenuSeguido.objects.filter(cierre=cierre).exists())

    def test_cambiar_de_lo_segui_a_no_lo_segui_borra_la_foto_anterior(self):
        cerrar_dia(self.alejandro, {"fecha": self.martes, "respuesta": CierreDeDia.LO_SEGUI})
        cierre = CierreDeDia.objects.get(persona=self.alejandro, fecha=self.martes)
        self.assertTrue(MenuSeguido.objects.filter(cierre=cierre).exists())

        cerrar_dia(self.alejandro, {"fecha": self.martes, "respuesta": CierreDeDia.NO_LO_SEGUI})
        self.assertFalse(MenuSeguido.objects.filter(cierre=cierre).exists())


class R5_SinPlanPuestoTests(BaseCierresTests):
    """R5, caso límite de R-77 — sin ningún plan puesto ese día, decir que se siguió no guarda
    ningún menú y la pantalla no se rompe: no hay nada que guardar."""

    def test_lo_segui_sin_plan_puesto_no_rompe_y_no_guarda_menu(self):
        fecha = timezone.localdate() - timedelta(days=3)
        self.assertFalse(PlanDeDia.objects.filter(persona=self.alejandro, fecha=fecha).exists())

        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha.isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro, fecha=fecha)
        self.assertEqual(cierre.respuesta, CierreDeDia.LO_SEGUI)
        self.assertFalse(MenuSeguido.objects.filter(cierre=cierre).exists())


# ---------------------------------------------------------------------------------------- #
# R6-R9 — la pregunta al abrir la app, solo por el último día pendiente.
# ---------------------------------------------------------------------------------------- #


class R6_PreguntaAlAbrirTests(BaseCierresTests):
    """R6/C-82 — si ayer quedó sin cerrar, lo primero que se ve al abrir la app es la
    pregunta, contestable en un toque."""

    def test_con_ayer_sin_cerrar_la_pregunta_aparece_en_el_inicio(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "pregunta-cierre")
        self.assertContains(respuesta, "¿Cumpliste el plan de ayer")
        # Los tres botones, contestables en un toque (Q-140).
        self.assertContains(respuesta, 'value="lo_segui"')
        self.assertContains(respuesta, 'value="a_medias"')
        self.assertContains(respuesta, 'value="no_lo_segui"')

    def test_la_pregunta_ensena_lo_que_tenia_puesto_ayer(self):
        ayer = timezone.localdate() - timedelta(days=1)
        _crear_plan(
            self.alejandro, ayer,
            [{"nombre": "Tortilla de patatas", "momento_del_dia": "cena", "calorias": 500,
              "proteina_g": 20, "grasa_g": 25, "carbos_g": 40}],
        )
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "Tortilla de patatas")


class R7_C83_SoloElUltimoDiaTests(BaseCierresTests):
    """R7/C-83 (el episodio real de Euridice) — cinco días sin cerrar: solo se pregunta por
    AYER, no por los cinco."""

    def setUp(self):
        super().setUp()
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

    def test_con_cinco_dias_sin_cerrar_solo_se_pregunta_por_ayer(self):
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        hace_cinco = hoy - timedelta(days=5)

        respuesta = self.client.get("/")
        contenido = respuesta.content.decode()
        self.assertIn(f'data-fecha="{ayer.isoformat()}"', contenido)
        self.assertNotIn(f'data-fecha="{hace_cinco.isoformat()}"', contenido)
        # Un único bloque de pregunta, no cinco.
        self.assertEqual(contenido.count("¿Cumpliste el plan de ayer"), 1)


class R8_NoVuelveAPreguntarSiSeSaltoTests(BaseCierresTests):
    """R8/Q-141 — al saltarse la pregunta, no se vuelve a preguntar por ese día jamás, y el
    día se queda sin apuntar."""

    def test_saltar_hace_que_la_pregunta_desaparezca(self):
        respuesta = self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        self.assertEqual(respuesta.status_code, 302)  # sin HX-Request: redirect a Inicio

        respuesta_inicio = self.client.get("/")
        self.assertNotContains(respuesta_inicio, "¿Cumpliste el plan de ayer")

    def test_saltar_no_crea_ningun_cierre_el_dia_se_queda_sin_apuntar(self):
        self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        self.assertEqual(CierreDeDia.objects.filter(persona=self.alejandro).count(), 0)

    def test_reabrir_la_app_el_mismo_dia_tras_saltar_no_vuelve_a_preguntar(self):
        """El escenario que de verdad protege R8: sin persistir el salto, una segunda visita
        el MISMO día (mientras "ayer" sigue siendo el mismo) volvería a preguntar."""
        self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        for _ in range(3):
            respuesta = self.client.get("/")
            self.assertNotContains(respuesta, "¿Cumpliste el plan de ayer")

    def test_saltar_registra_la_fecha_saltada(self):
        ayer = timezone.localdate() - timedelta(days=1)
        self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        salto = DiaSaltado.objects.get(persona=self.alejandro)
        self.assertEqual(salto.fecha, ayer)


class R9_CerrarHoyNoPreguntaPorHoyTests(BaseCierresTests):
    """R9 — cerrar el día de HOY no dispara ninguna pregunta por hoy al abrir la app; la
    pregunta sigue siendo, si acaso, por el último día PENDIENTE (ayer)."""

    def test_cerrar_hoy_no_hace_que_se_pregunte_por_hoy(self):
        hoy = timezone.localdate()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": hoy.isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        respuesta = self.client.get("/")
        # La única fecha que la pregunta puede mostrar es "ayer" (nunca "hoy"), y aquí ayer
        # sigue sin cerrar: la pregunta sigue apareciendo, por AYER.
        ayer = hoy - timedelta(days=1)
        self.assertContains(respuesta, f'data-fecha="{ayer.isoformat()}"')

    def test_cerrar_hoy_no_tapa_la_pregunta_pendiente_de_ayer(self):
        """El caso que de verdad distingue R9 de un bug: cerrar HOY no debe hacer que la app
        deje de preguntar por AYER, que sigue sin cerrar."""
        hoy = timezone.localdate()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": hoy.isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        dia = dia_pendiente_de_preguntar(self.alejandro)
        self.assertEqual(dia, hoy - timedelta(days=1))

    def test_cerrando_tambien_ayer_ya_no_queda_nada_pendiente(self):
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        for fecha in (hoy, ayer):
            self.client.post(
                f"/cierres/{self.alejandro.id}/",
                {"fecha": fecha.isoformat(), "respuesta": "lo_segui",
                 "calorias_comidas": "", "nota": ""},
            )
        respuesta = self.client.get("/")
        self.assertNotContains(respuesta, "¿Cumpliste el plan de ayer")


# ---------------------------------------------------------------------------------------- #
# HTMX (novena cara de conocimiento/tests-que-no-fallan-cuando-deben.md): la vista responde
# el TROZO, no un redirect, cuando la petición trae la cabecera que el navegador manda.
# ---------------------------------------------------------------------------------------- #


class HTMXTests(BaseCierresTests):
    def test_responder_con_hx_request_responde_solo_el_trozo(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/responder/",
            {"respuesta": "lo_segui"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn('id="pregunta-cierre"', contenido)
        # Y la pregunta ya no aparece: se acaba de contestar.
        self.assertNotIn("¿Cumpliste el plan de ayer", contenido)
        # Se guardó de verdad, no solo se pintó distinto.
        ayer = timezone.localdate() - timedelta(days=1)
        self.assertTrue(CierreDeDia.objects.filter(persona=self.alejandro, fecha=ayer).exists())

    def test_saltar_con_hx_request_responde_solo_el_trozo(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/saltar/", HTTP_HX_REQUEST="true"
        )
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertNotIn("¿Cumpliste el plan de ayer", contenido)

    def test_cerrar_desde_progreso_con_hx_request_responde_solo_el_trozo(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn('id="historico-de-cierres"', contenido)

    def test_responder_sin_hx_request_redirige_al_inicio(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, "/")


# ---------------------------------------------------------------------------------------- #
# R10 — el cierre a mano desde Progreso: cualquier día, también cambiar uno ya cerrado.
# ---------------------------------------------------------------------------------------- #


class R10_CierreAManoDesdeProgresoTests(BaseCierresTests):
    def test_se_puede_cerrar_un_dia_bien_pasado(self):
        hace_20_dias = (timezone.localdate() - timedelta(days=20)).isoformat()
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": hace_20_dias, "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            CierreDeDia.objects.filter(persona=self.alejandro, fecha=hace_20_dias).exists()
        )

    def test_se_puede_cambiar_un_dia_ya_cerrado(self):
        fecha = (timezone.localdate() - timedelta(days=5)).isoformat()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha, "respuesta": "no_lo_segui", "calorias_comidas": "", "nota": ""},
        )
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha, "respuesta": "lo_segui", "calorias_comidas": "1900", "nota": "cambiado"},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro, fecha=fecha)
        self.assertEqual(cierre.respuesta, CierreDeDia.LO_SEGUI)
        self.assertEqual(cierre.calorias_comidas, 1900)
        self.assertEqual(cierre.nota, "cambiado")
        self.assertEqual(CierreDeDia.objects.filter(persona=self.alejandro).count(), 1)

    def test_el_enlace_cambiar_precarga_el_formulario_con_lo_que_ya_habia(self):
        fecha = (timezone.localdate() - timedelta(days=5)).isoformat()
        self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha, "respuesta": "no_lo_segui", "calorias_comidas": "1500", "nota": "meh"},
        )
        respuesta = self.client.get(f"/cierres/{self.alejandro.id}/?fecha={fecha}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "1500")
        self.assertContains(respuesta, "meh")

    def test_desde_progreso_hay_un_enlace_al_cierre_a_mano(self):
        respuesta = self.client.get("/progreso/")
        self.assertContains(respuesta, f"/cierres/{self.alejandro.id}/")

    def test_un_fecha_param_con_basura_no_rompe_la_pantalla(self):
        # Ronda 2, hueco 1: `?fecha=pepe` no tiene forma de fecha en absoluto. Mismo
        # criterio que `servicios/progreso.py:semanas_desde_parametro` — se trata como si
        # `?fecha=` no hubiera llegado, formulario limpio, pantalla funcionando.
        respuesta = self.client.get(f"/cierres/{self.alejandro.id}/?fecha=pepe")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["form"].instance.pk)

    def test_un_fecha_param_con_formato_valido_pero_fecha_imposible_no_rompe_la_pantalla(self):
        # Caso distinto del anterior: el formato SÍ es de fecha (AAAA-MM-DD) pero la fecha no
        # existe (mes 13) — esto revienta por otro sitio del parseo, así que necesita su
        # propio caso.
        respuesta = self.client.get(f"/cierres/{self.alejandro.id}/?fecha=2026-13-45")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["form"].instance.pk)


# ---------------------------------------------------------------------------------------- #
# R11 — entradas inválidas: no se guardan, y la app lo dice sin romperse.
# ---------------------------------------------------------------------------------------- #


class R11_EntradasInvalidasTests(BaseCierresTests):
    def test_una_respuesta_que_no_es_una_de_las_tres_no_se_guarda(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "mas_o_menos",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(CierreDeDia.objects.filter(persona=self.alejandro).exists())
        # Ronda 2, hueco 2: R11 dice "no lo guarda Y LO DICE" — no basta con mirar
        # `form.errors`, el aviso tiene que llegar al HTML que ve la persona (mismo criterio
        # que `planes/tests.py:test_se_avisa_de_cual_esta_mal`, unidad 005).
        mensaje = respuesta.context["form"].errors["respuesta"][0]
        self.assertContains(respuesta, mensaje)

    def test_calorias_negativas_no_se_guardan(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "-100", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(CierreDeDia.objects.filter(persona=self.alejandro).exists())
        mensaje = respuesta.context["form"].errors["calorias_comidas"][0]
        self.assertContains(respuesta, mensaje)

    def test_una_fecha_futura_no_se_guarda(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": manana, "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(CierreDeDia.objects.filter(persona=self.alejandro).exists())
        mensaje = respuesta.context["form"].errors["fecha"][0]
        self.assertContains(respuesta, mensaje)

    def test_ninguna_entrada_invalida_rompe_la_pantalla(self):
        for datos in [
            {"fecha": timezone.localdate().isoformat(), "respuesta": "raro"},
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "-5"},
        ]:
            base = {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
                    "calorias_comidas": "", "nota": ""}
            base.update(datos)
            respuesta = self.client.post(f"/cierres/{self.alejandro.id}/", base)
            self.assertEqual(respuesta.status_code, 200)


# ---------------------------------------------------------------------------------------- #
# R12 — cerrar o cambiar el cierre de otra persona (del hogar, o de fuera) da 404, nunca 403.
# Cuatro celdas: cerrar/cambiar × del hogar/de fuera (más responder/saltar, los otros canales).
# ---------------------------------------------------------------------------------------- #


class R12_AislamientoTests(BaseCierresTests):
    def setUp(self):
        super().setUp()
        self.cierre_de_alejandro = CierreDeDia.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), respuesta=CierreDeDia.LO_SEGUI
        )
        self.client.logout()

    # --- cerrar (crear uno nuevo) ---------------------------------------------------------

    def test_no_puede_cerrar_el_dia_de_otra_persona_del_mismo_hogar(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": (timezone.localdate() - timedelta(days=1)).isoformat(),
             "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_cerrar_el_dia_de_alguien_de_otro_hogar(self):
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": (timezone.localdate() - timedelta(days=1)).isoformat(),
             "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)

    # --- cambiar (sustituir uno ya existente) ----------------------------------------------

    def test_no_puede_cambiar_un_cierre_ya_existente_de_otra_persona_del_mismo_hogar(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "no_lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.cierre_de_alejandro.refresh_from_db()
        self.assertEqual(self.cierre_de_alejandro.respuesta, CierreDeDia.LO_SEGUI)  # intacto

    def test_no_puede_cambiar_un_cierre_de_alguien_de_otro_hogar(self):
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "no_lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.cierre_de_alejandro.refresh_from_db()
        self.assertEqual(self.cierre_de_alejandro.respuesta, CierreDeDia.LO_SEGUI)  # intacto

    # --- responder (la pregunta rápida) -----------------------------------------------------

    def test_no_puede_responder_la_pregunta_de_otra_persona_del_mismo_hogar(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_responder_la_pregunta_de_alguien_de_otro_hogar(self):
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/responder/", {"respuesta": "lo_segui"}
        )
        self.assertEqual(respuesta.status_code, 404)

    # --- saltar -------------------------------------------------------------------------

    def test_no_puede_saltar_el_dia_de_otra_persona_del_mismo_hogar(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_saltar_el_dia_de_alguien_de_otro_hogar(self):
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        self.assertEqual(respuesta.status_code, 404)

    def test_nunca_403_siempre_404(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)


# ---------------------------------------------------------------------------------------- #
# R13 — sin ningún cierre todavía, la pantalla lo dice con naturalidad.
# ---------------------------------------------------------------------------------------- #


class R13_SinNingunCierreTests(BaseCierresTests):
    def test_sin_ningun_cierre_todavia_la_pantalla_lo_dice_sin_parecer_rota(self):
        respuesta = self.client.get(f"/cierres/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no has cerrado ningún día")

    def test_sin_ningun_cierre_todavia_el_inicio_tampoco_se_rompe(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)


class SinSesionTests(BaseCierresTests):
    def test_sin_sesion_no_puede_cerrar_nada_lo_manda_a_iniciar_sesion(self):
        self.client.logout()
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 302)


class Bug030_LaPuertaCompartidaSinRedEnAisladoTests(PruebaConRegistroAbierto):
    """
    Bug 030 — `cierres/acceso.py:persona_propia_o_404` no compara nada por su cuenta: delega
    ENTERA en `hogares.acceso.puede_cambiar_lo_de` (línea 98: `if
    str(persona_que_pregunta.id) == str(persona_id)`), la puerta ÚNICA que comparten
    `perfiles/`, `progreso/`, `entrenos/` y `cierres/`. Ninguno de los tests de arriba
    (`BaseCierresTests` registra a Alejandro EL PRIMERO de la tanda) protege esa comparación
    en AISLADO: con las secuencias de `Persona` y `Usuario` recién migradas, el `persona.id` y
    el `usuario.id` de quien registra primero coinciden por pura casualidad (los dos valen 1)
    — la 16ª cara (`tests-que-no-fallan-cuando-deben.md`, unidad 023: los contadores van a la
    par), que 027 y 029 ya cerraron para `progreso/` y `perfiles/` respectivamente, pero que
    nunca se había cerrado aquí.

    Antes de esta clase, mutando la línea 98 para comparar `persona_que_pregunta.usuario_id`
    en vez de `.id` (la MISMA forma que protegen 027/029, no una mutación cómoda),
    `python manage.py test cierres` SOLO daba `OK` (57 tests) — la coincidencia numérica de
    más arriba tapaba el defecto entonces; remedido restaurando la versión anterior de este
    fichero (docs/bugs/030-la-puerta-compartida-sin-red-en-entrenos-y-cierres.md, sección 3).
    Con esta clase presente, la misma mutación SÍ cae (esa misma ficha, sección 2).

    La cura, la misma que 027/029: dar de alta a una `Persona` SIN `Usuario` (Marta) ANTES de
    que Alejandro registre su cuenta, adelantando la secuencia de `Persona` un paso por
    delante de la de `Usuario` para siempre, así su `persona.id` ya NUNCA coincide con su
    `usuario.id` por casualidad. La 19ª cara (revisión de la 029), aquí obligatoria: el
    montaje que crea el desfase se AFIRMA con un assert sobre lo que debía crearse, no se
    supone — si el alta de Marta fallara en silencio, la secuencia de `Persona` no avanzaría y
    esta red se apagaría sin un solo rojo.
    """

    def setUp(self):
        super().setUp()
        # "Relleno" es quien da de alta a Marta: necesita su propio hogar antes de poder
        # llamar a /hogares/mi-hogar/dar-de-alta/.
        self.registrar_y_verificar("relleno@example.com", sexo="mujer")
        respuesta_alta = self.client.post(
            "/hogares/mi-hogar/dar-de-alta/",
            {
                "nombre": "Marta",
                "sexo": "mujer",
                "fecha_nacimiento": "2015-01-01",
                "altura_cm": "120",
                "peso_kg": "25",
                "actividad": "moderado",
                "objetivo": "mantener",
                "ajuste_pct": "",
                "dieta": "",
                "alergias": "",
                "intolerancias": "",
                "no_le_gusta": "",
            },
        )
        # El montaje se afirma, no se supone (19ª cara): un alta que falla en silencio (form
        # inválido, redirect distinto) dejaría el desfase sin crear.
        self.assertEqual(respuesta_alta.status_code, 302)
        self.assertTrue(
            Persona.objects.filter(nombre="Marta", usuario__isnull=True).exists()
        )
        self.client.logout()

        # Alejandro registra DESPUÉS de Marta: su persona.id queda por delante de su
        # usuario.id, así que la coincidencia numérica del montaje sin red deja de darse.
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        # Control estructural del desfase (no por el orden numérico: a escala de suite otros
        # tests ya pueden haber desalineado las secuencias por su cuenta, y entonces comparar
        # ids por casualidad deja de decir nada — 18ª cara operando sobre la red
        # anti-19ª-cara). Marta existe SIN Usuario y se creó ANTES que Alejandro: si el alta
        # falla o alguien la borra junto con sus asserts, este `.get()` revienta él solo, sin
        # depender de qué id le tocara a nadie.
        marta = Persona.objects.get(nombre="Marta", usuario__isnull=True)
        self.assertLess(marta.id, self.alejandro.id)  # control del desfase, estructural

    def test_alejandro_cierra_su_propio_dia_con_los_ids_desincronizados(self):
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": timezone.localdate().isoformat(), "respuesta": "lo_segui",
             "calorias_comidas": "1800", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            CierreDeDia.objects.filter(persona=self.alejandro, respuesta="lo_segui").exists()
        )

    def test_alejandro_cambia_su_propio_cierre_ya_existente_con_los_ids_desincronizados(self):
        fecha = timezone.localdate().isoformat()
        CierreDeDia.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(),
            respuesta=CierreDeDia.NO_LO_SEGUI,
        )
        respuesta = self.client.post(
            f"/cierres/{self.alejandro.id}/",
            {"fecha": fecha, "respuesta": "lo_segui", "calorias_comidas": "", "nota": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        cierre = CierreDeDia.objects.get(persona=self.alejandro)
        self.assertEqual(cierre.respuesta, CierreDeDia.LO_SEGUI)

    def test_alejandro_salta_su_propio_dia_con_los_ids_desincronizados(self):
        respuesta = self.client.post(f"/cierres/{self.alejandro.id}/saltar/")
        self.assertEqual(respuesta.status_code, 302)  # sin HX-Request: redirect a Inicio
        self.assertEqual(DiaSaltado.objects.filter(persona=self.alejandro).count(), 1)
