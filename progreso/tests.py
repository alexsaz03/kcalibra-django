"""
Tests de la unidad 010 (R1-R11, ver-tu-progreso.md): la pantalla de Progreso.

Igual que en `perfiles/tests.py` y `planes/tests.py`: todo pasa por el cliente de pruebas de
Django contra las URLs reales, nunca llamando a las vistas directamente (la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo — la petición tiene que
LLEGAR a lo que dice probar).

Las mediciones se fijan con `_fijar_mediciones` (más abajo): borra el histórico completo de
la persona y lo sustituye por exactamente lo que cada test necesita, en días relativos a
"hoy" (nunca fechas absolutas, para que la suite no dependa de en qué día se ejecute) —
incluida la medición automática que deja el alta (unidad 004), que si no se estorbaría con el
escenario que cada test quiere montar.
"""

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import SolicitudEntrada
from perfiles.models import MedicionPeso

Usuario = get_user_model()


def _fijar_mediciones(usuario, mediciones):
    """
    Sustituye TODO el histórico de `usuario` por `mediciones`: una lista de dicts con
    "dias_atras" (entero, 0 = hoy) y "peso_kg", más opcionalmente "grasa_pct"/"cintura_cm".
    Se usa para controlar EXACTAMENTE qué hay en el periodo de cada test, sin que la medición
    que deja el alta (siempre "hoy", unidad 004) se cuele sin que el test la pidiera.
    """
    MedicionPeso.objects.filter(usuario=usuario).delete()
    hoy = timezone.localdate()
    for datos in mediciones:
        MedicionPeso.objects.create(
            usuario=usuario,
            fecha=hoy - timedelta(days=datos["dias_atras"]),
            peso_kg=datos["peso_kg"],
            grasa_pct=datos.get("grasa_pct"),
            cintura_cm=datos.get("cintura_cm"),
        )


class BaseProgresoTests(PruebaConRegistroAbierto):
    """
    Alejandro y Euridice, en el MISMO hogar (mismo montaje que
    `perfiles.tests.AislamientoDePesoTests`); Carlos, en el SUYO propio, para R9. La sesión
    queda en Alejandro al terminar `setUp` — el escenario más común de los tests de abajo.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
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

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el escenario de R9.
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Usuario.objects.get(email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)


class EvolucionDePesoTests(BaseProgresoTests):
    """R1 — la evolución del peso, con las pesadas reales de la persona."""

    def test_r1_ve_la_evolucion_de_su_peso_con_sus_pesadas_reales(self):
        _fijar_mediciones(
            self.alejandro,
            [
                {"dias_atras": 20, "peso_kg": 95},
                {"dias_atras": 10, "peso_kg": 94},
                {"dias_atras": 0, "peso_kg": 93},
            ],
        )
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        # Un <circle> por pesada real (progreso/templates/progreso/_grafica.html).
        self.assertEqual(contenido.count("<circle"), 3)
        self.assertContains(respuesta, "95")  # la primera pesada real del periodo
        self.assertContains(respuesta, "93")  # la última


class GraficasOpcionalesTests(BaseProgresoTests):
    """
    R2/Q-152 — grasa y cintura solo aparecen si esa persona las tiene apuntadas, cada una por
    SEPARADO (R2 nombra las dos: "cuando esa persona tiene grasa apuntada... Lo mismo, por
    separado, con la cintura" — cada mitad necesita su propio test, heurística de
    tests-que-no-fallan-cuando-deben.md).
    """

    def test_r2_sin_grasa_apuntada_esa_grafica_no_aparece_en_absoluto(self):
        _fijar_mediciones(self.alejandro, [{"dias_atras": 0, "peso_kg": 93}])
        respuesta = self.client.get("/progreso/")
        self.assertNotContains(respuesta, "Grasa corporal")
        self.assertNotContains(respuesta, "progreso-sin-datos")  # no es "sin datos": sí tiene peso

    def test_r2_sin_cintura_apuntada_esa_grafica_no_aparece_en_absoluto(self):
        _fijar_mediciones(
            self.alejandro, [{"dias_atras": 0, "peso_kg": 93, "grasa_pct": 20}]
        )
        respuesta = self.client.get("/progreso/")
        self.assertContains(respuesta, "Grasa corporal")
        self.assertNotContains(respuesta, "Cintura")

    def test_r2_con_grasa_y_cintura_apuntadas_aparecen_las_dos_evoluciones(self):
        _fijar_mediciones(
            self.alejandro,
            [{"dias_atras": 0, "peso_kg": 93, "grasa_pct": 20, "cintura_cm": 90}],
        )
        respuesta = self.client.get("/progreso/")
        self.assertContains(respuesta, "Grasa corporal")
        self.assertContains(respuesta, "Cintura")


class RecomposicionCorporalTests(BaseProgresoTests):
    """C-88 — el episodio que da sentido a la pantalla entera: peso plano, grasa bajando."""

    def test_r3_peso_plano_y_grasa_bajando_se_ven_las_dos_evoluciones(self):
        _fijar_mediciones(
            self.alejandro,
            [
                {"dias_atras": 60, "peso_kg": 93, "grasa_pct": 22},
                {"dias_atras": 30, "peso_kg": 93, "grasa_pct": 20},
                {"dias_atras": 0, "peso_kg": 93, "grasa_pct": 19},
            ],
        )
        respuesta = self.client.get("/progreso/?semanas=12")
        self.assertContains(respuesta, "Peso")
        self.assertContains(respuesta, "Grasa corporal")
        # 3 puntos de peso + 3 de grasa: las DOS series completas, no una a medias.
        self.assertEqual(respuesta.content.decode().count("<circle"), 6)


class GrasaConDiasSueltosTests(BaseProgresoTests):
    """R4 — grasa apuntada solo algunos días: se dibuja con los que tenga, sin inventar."""

    def test_r4_grasa_solo_algunos_dias_sueltos_se_dibuja_con_los_que_tenga(self):
        _fijar_mediciones(
            self.alejandro,
            [
                {"dias_atras": 20, "peso_kg": 95, "grasa_pct": 24},
                {"dias_atras": 10, "peso_kg": 94},  # sin grasa ese día
                {"dias_atras": 0, "peso_kg": 93, "grasa_pct": 22},
            ],
        )
        respuesta = self.client.get("/progreso/")
        # Peso: 3 puntos (todos los días la tienen). Grasa: 2 (el día suelto sin grasa no
        # se inventa ni se interpola) → 5 en total.
        self.assertEqual(respuesta.content.decode().count("<circle"), 5)


class SemanasTests(BaseProgresoTests):
    """R5 — cambiar cuántas semanas se miran cambia lo que se ve, de verdad."""

    def test_r5_cambia_el_periodo_y_solo_ve_las_pesadas_de_ese_rango(self):
        _fijar_mediciones(
            self.alejandro,
            [
                {"dias_atras": 200, "peso_kg": 100},  # fuera de cualquiera de los dos rangos
                {"dias_atras": 40, "peso_kg": 96},  # dentro de 12 semanas, fuera de 4
                {"dias_atras": 0, "peso_kg": 93},  # dentro de los dos
            ],
        )
        respuesta_4_semanas = self.client.get("/progreso/?semanas=4")
        self.assertEqual(respuesta_4_semanas.content.decode().count("<circle"), 1)

        respuesta_12_semanas = self.client.get("/progreso/?semanas=12")
        self.assertEqual(respuesta_12_semanas.content.decode().count("<circle"), 2)

    def test_r5_el_rango_por_defecto_es_12_y_se_ve_en_el_campo(self):
        respuesta = self.client.get("/progreso/")
        self.assertContains(respuesta, 'value="12"')


class SemanasEntradaRaraTests(BaseProgresoTests):
    """
    R6, caso límite de entrada — un `?semanas=` que no se entiende NUNCA rompe la pantalla,
    al contrario que la unidad 009 (allí SÍ tumbaba el arranque, porque era configuración de
    despliegue; esto es una persona tecleando algo en la URL).
    """

    def test_r6_valores_raros_caen_al_defecto_y_la_pantalla_sigue_funcionando(self):
        _fijar_mediciones(self.alejandro, [{"dias_atras": 0, "peso_kg": 93}])
        for crudo in ["abc", "9999", "-3", "0", "3.5", ""]:
            respuesta = self.client.get(f"/progreso/?semanas={crudo}")
            self.assertEqual(respuesta.status_code, 200, f"reventó con semanas={crudo!r}")
            self.assertContains(respuesta, 'value="12"', msg_prefix=f"semanas={crudo!r}")

    def test_r6_sin_el_parametro_tambien_cae_al_defecto(self):
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'value="12"')


class LecturaAjenaTests(BaseProgresoTests):
    """
    R7/G-1/R-23/G-171 — la deuda que la unidad 006 dejó escrita: el hogar SÍ puede ver el
    progreso de otra persona de casa. Antes de esta unidad, esto daba 404 (no había ni
    siquiera esta URL) — la mutación de Verificación #3 es justo devolver esto a 404.
    """

    def test_r7_alejandro_ve_el_progreso_de_euridice(self):
        _fijar_mediciones(self.euridice, [{"dias_atras": 0, "peso_kg": 61}])
        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "61")


class EscrituraAjenaSigueBloqueadaTests(BaseProgresoTests):
    """
    R8 — la otra mitad de la pareja R7/R8: SOLO mirar. Apuntar y borrar el peso de Euridice
    siguen dando 404, exactamente igual que antes de esta unidad (los mismos endpoints que
    `perfiles.tests.AislamientoDePesoTests` ya prueba; se repiten aquí, desde la puerta de
    entrada natural de esta unidad, para que la pareja R7/R8 quede clavada junta).
    """

    def test_r8_apuntar_el_peso_de_euridice_sigue_dando_404(self):
        mediciones_antes = MedicionPeso.objects.filter(usuario=self.euridice).count()
        respuesta = self.client.post(
            f"/perfiles/{self.euridice.id}/peso/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "peso_kg": "50",
                "grasa_pct": "",
                "cintura_cm": "",
            },
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(
            MedicionPeso.objects.filter(usuario=self.euridice).count(), mediciones_antes
        )

    def test_r8_borrar_una_medicion_de_euridice_sigue_dando_404(self):
        medicion = MedicionPeso.objects.filter(usuario=self.euridice).first()  # la del alta
        self.assertIsNotNone(medicion)  # control
        respuesta = self.client.post(f"/perfiles/{self.euridice.id}/peso/{medicion.id}/borrar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(MedicionPeso.objects.filter(id=medicion.id).exists())


class AislamientoEntreHogaresTests(BaseProgresoTests):
    """R9 — de OTRO hogar, 404, nunca 403 (misma puerta que el resto de la app, unidad 003)."""

    def test_r9_el_progreso_de_alguien_de_otro_hogar_da_404(self):
        respuesta = self.client.get(f"/progreso/{self.carlos.id}/")
        self.assertEqual(respuesta.status_code, 404)


class NuncaSeMezclanPersonasTests(BaseProgresoTests):
    """
    R10/G-171 — nunca se suman ni promedian los datos de dos personas del hogar. La mutación
    de Verificación #2 es justo quitar el filtro por persona (mezclar el hogar): este test es
    el que se pone ROJO cuando eso pasa.
    """

    def test_r10_las_pesadas_de_dos_personas_del_hogar_no_se_mezclan(self):
        _fijar_mediciones(self.alejandro, [{"dias_atras": 0, "peso_kg": 93}])
        _fijar_mediciones(self.euridice, [{"dias_atras": 0, "peso_kg": 61}])

        respuesta = self.client.get("/progreso/")
        contenido = respuesta.content.decode()
        # Un único punto: el de Alejandro. Si el hogar se mezclara, habría dos.
        self.assertEqual(contenido.count("<circle"), 1)
        self.assertContains(respuesta, "93")
        self.assertNotContains(respuesta, "61")


class SinDatosTests(BaseProgresoTests):
    """R11 — sin pesadas (o con una sola), la pantalla lo dice con naturalidad, sin error."""

    def test_r11_sin_ninguna_pesada_no_da_error_y_lo_dice_con_naturalidad(self):
        MedicionPeso.objects.filter(usuario=self.alejandro).delete()
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no tienes ninguna pesada apuntada")

    def test_r11_con_una_unica_pesada_tampoco_parece_rota(self):
        _fijar_mediciones(self.alejandro, [{"dias_atras": 0, "peso_kg": 93}])
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "93")
        self.assertEqual(respuesta.content.decode().count("<circle"), 1)

    def test_r11_con_pesadas_pero_ninguna_en_el_periodo_elegido_lo_dice_distinto(self):
        """No es lo mismo "nunca ha apuntado nada" que "tiene datos, pero no en estas
        semanas": dos mensajes distintos para no confundir a quien mira."""
        _fijar_mediciones(self.alejandro, [{"dias_atras": 200, "peso_kg": 93}])
        respuesta = self.client.get("/progreso/?semanas=4")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "progreso-sin-datos-en-periodo")
        self.assertNotContains(respuesta, "progreso-sin-datos\"")


class CoordenadasDelSvgTests(BaseProgresoTests):
    """
    Hallazgo propio de esta unidad, no un R* del contrato: con `LANGUAGE_CODE="es"`, Django
    pinta los números con COMA ("300,0" en vez de "300.0") — el mismo patrón que ya delató el
    campo de fecha en la unidad 006 (docs/conocimiento/tests-que-no-fallan-cuando-deben.md,
    quinta cara). Un `cx="300,0"` no es un número válido en un atributo de SVG: el navegador
    lo descarta en silencio y el punto se dibuja en el origen (0,0), no donde toca. Sin este
    test, nada en la suite lo habría cazado — se destapó mirando el HTML crudo al montar la
    prueba de mutación #1.
    """

    def test_las_coordenadas_del_circle_usan_punto_no_coma(self):
        _fijar_mediciones(
            self.alejandro,
            [{"dias_atras": 20, "peso_kg": 95}, {"dias_atras": 0, "peso_kg": 93}],
        )
        respuesta = self.client.get("/progreso/")
        contenido = respuesta.content.decode()
        circulos = re.findall(r'<circle cx="([^"]+)" cy="([^"]+)"', contenido)
        self.assertEqual(len(circulos), 2)
        for cx, cy in circulos:
            self.assertRegex(cx, r"^\d+(\.\d+)?$", f"cx={cx!r} no es un número de SVG válido")
            self.assertRegex(cy, r"^\d+(\.\d+)?$", f"cy={cy!r} no es un número de SVG válido")


class SelectorDePersonaTests(BaseProgresoTests):
    """R81/§8 — se puede ver el progreso de otra persona de casa, una cada vez."""

    def test_el_selector_ofrece_un_enlace_a_cada_miembro_del_hogar(self):
        respuesta = self.client.get("/progreso/")
        self.assertContains(respuesta, f'/progreso/{self.euridice.id}/?semanas=12')


class SinSesionTests(BaseProgresoTests):
    def test_sin_sesion_no_ve_nada_lo_manda_a_iniciar_sesion(self):
        self.client.logout()
        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 302)
