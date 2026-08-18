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

from cierres.models import CierreDeDia
from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from entrenos.models import Entreno
from hogares.models import Persona, SolicitudEntrada
from perfiles.models import MedicionPeso

Usuario = get_user_model()


def _fijar_mediciones(usuario, mediciones):
    """
    Sustituye TODO el histórico de `usuario` por `mediciones`: una lista de dicts con
    "dias_atras" (entero, 0 = hoy) y "peso_kg", más opcionalmente "grasa_pct"/"cintura_cm".
    Se usa para controlar EXACTAMENTE qué hay en el periodo de cada test, sin que la medición
    que deja el alta (siempre "hoy", unidad 004) se cuele sin que el test la pidiera.
    """
    MedicionPeso.objects.filter(persona=usuario).delete()
    hoy = timezone.localdate()
    for datos in mediciones:
        MedicionPeso.objects.create(
            persona=usuario,
            fecha=hoy - timedelta(days=datos["dias_atras"]),
            peso_kg=datos["peso_kg"],
            grasa_pct=datos.get("grasa_pct"),
            cintura_cm=datos.get("cintura_cm"),
        )


def _fijar_entrenos(usuario, entrenos):
    """
    Unidad 013 — sustituye TODOS los entrenos de `usuario` por `entrenos`: lista de dicts con
    "dias_atras" (entero, 0 = hoy), "minutos" y "calorias". Deporte e intensidad son datos de
    relleno (no afectan a R1: esta unidad AGRUPA entrenos ya existentes, no vuelve a calcular
    sus calorías — eso ya lo prueban `servicios/tests.py` y `entrenos/tests.py`).
    """
    Entreno.objects.filter(persona=usuario).delete()
    hoy = timezone.localdate()
    for datos in entrenos:
        Entreno.objects.create(
            persona=usuario,
            fecha=hoy - timedelta(days=datos["dias_atras"]),
            deporte=datos.get("deporte", "correr"),
            intensidad=datos.get("intensidad", "media"),
            minutos=datos["minutos"],
            calorias=datos["calorias"],
            calorias_manuales=True,
        )


def _fijar_cierres(usuario, cierres):
    """
    Unidad 013 — sustituye TODOS los cierres de `usuario` por `cierres`: lista de dicts con
    "dias_atras" y "respuesta" (`CierreDeDia.LO_SEGUI` / `A_MEDIAS` / `NO_LO_SEGUI`).
    """
    CierreDeDia.objects.filter(persona=usuario).delete()
    hoy = timezone.localdate()
    for datos in cierres:
        CierreDeDia.objects.create(
            persona=usuario,
            fecha=hoy - timedelta(days=datos["dias_atras"]),
            respuesta=datos["respuesta"],
        )


# Bugs 016/018/019 — el mismo regex de acotado se necesitaba ya TRES veces (016, 018, y las
# dos escenas de este bug), así que con estas serían SEIS copias: se extrae aquí, la tercera
# vez que aparece la misma forma (docs/bugs/019-...md, "Dos cosas que el 018 dejó dichas").
# Los tests del 016 y del 018 pasan a llamarlo, sin cambiar UNA COMA de lo que comprueban —
# solo dejan de repetir el regex.
#
# Por qué existe: un assert de texto sobre `respuesta.content` ENTERA prueba "existe en algún
# sitio de la página", no "está donde el criterio promete" (doceava cara de
# tests-que-no-fallan-cuando-deben.md). La página lleva el
# `<input type="hidden" name="csrfmiddlewaretoken">` de `templates/base.html`, con un token
# ALEATORIO en cada carga que a veces contiene por pura coincidencia el literal corto que un
# test anda buscando (medido en el 016: 9 de 300 peticiones idénticas). El arreglo NO afloja
# el assert: lo ACOTA a la(s) GRÁFICA(S) — `progreso/templates/progreso/_grafica.html`: el
# `<section>` que envuelve el título, el resumen con el peso legible ("93,0 kg") y el `<svg>`
# con los `<circle>` — que es exactamente lo que R1/R10/R11 prometen. Se ancla al CONTENIDO
# (el bloque que tiene un `<svg>` dentro), no a una POSICIÓN como "lo que hay tras el último
# `</form>`": una posición se desplaza sola el día que alguien añade un formulario nuevo, y lo
# hace en silencio.
_REGEX_ZONA_DE_DATOS = re.compile(
    r"<section\b(?:(?!<section\b|</section>).)*?<svg\b.*?</svg>.*?</section>",
    re.DOTALL,
)


def _zona_de_datos(contenido):
    """
    Devuelve `(graficas, zona)`: `graficas` es la lista de `<section>` (con su `<svg>` dentro)
    que el regex de arriba encontró en `contenido` (una por gráfica visible: peso, y grasa/
    cintura si las hay) — se comprueba con `assertTrue(graficas, ...)` para que un rojo por
    "el regex dejó de casar" no se confunda con "el dato ya no está" (bug 015: un rojo mudo
    apunta al síntoma equivocado). `zona` es la concatenación de todas ellas, el único sitio
    donde un test de esta familia debe buscar un literal corto.
    """
    graficas = _REGEX_ZONA_DE_DATOS.findall(contenido)
    return graficas, "".join(graficas)


class BaseProgresoTests(PruebaConRegistroAbierto):
    """
    Alejandro y Euridice, en el MISMO hogar (mismo montaje que
    `perfiles.tests.AislamientoDePesoTests`); Carlos, en el SUYO propio, para R9. La sesión
    queda en Alejandro al terminar `setUp` — el escenario más común de los tests de abajo.
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

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el escenario de R9.
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
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
        # Bug 019: "95" y "93" son literales de DOS caracteres — el mismo defecto que el
        # 016/018 (ver `_zona_de_datos`, arriba), buscados antes sobre la página ENTERA. Aquí
        # el escenario tiene TRES mediciones (no una), así que la mina que el 018 dejó
        # dormida —que las coordenadas del SVG (x∈[12,588], y∈[12,148]) contengan el literal
        # DENTRO de la zona acotada— está viva en teoría. Medido para este escenario exacto
        # (docs/bugs/019-...md, sección 2): las coordenadas reales son 12.0/300.0/588.0 (x) y
        # 12.0/80.0/148.0 (y) — ninguna contiene "95" ni "93"; las dos únicas apariciones en
        # la zona acotada son el resumen legible ("95,0 kg" y "93,0 kg"). No se ha vuelto a
        # medir con otros pesos: si algún día este test cambia sus valores, hay que volcar la
        # zona de nuevo antes de confiar en que sigue sin colisión.
        graficas, zona_de_datos = _zona_de_datos(contenido)
        self.assertTrue(graficas, "no casó ninguna gráfica: ¿cambió _grafica.html?")
        # Un <circle> por pesada real (progreso/templates/progreso/_grafica.html).
        self.assertEqual(zona_de_datos.count("<circle"), 3)
        self.assertIn("95", zona_de_datos)  # la primera pesada real del periodo
        self.assertIn("93", zona_de_datos)  # la última


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
        contenido = respuesta.content.decode()
        # Bug 018 (el gemelo del 016, con el signo peligroso): la página ENTERA no es el
        # sitio a mirar. `templates/base.html` mete en la barra de arriba un <form> de
        # "Salir" con {% csrf_token %} — un token ALEATORIO, distinto en cada carga, que a
        # veces contiene "61" por pura coincidencia (medido en el 016: 9 de 300 peticiones
        # idénticas, sin ningún cambio de código — ver
        # docs/bugs/016-test-de-progreso-intermitente.md del meta-repo). Un
        # assertContains(respuesta, "61") sobre la página entera pasaba en VERDE por esa
        # casualidad aunque la pantalla hubiera DEJADO de pintar el peso de Eurídice —
        # verificado con mutación en docs/bugs/018-test-que-pasa-aunque-el-dato-no-este.md:
        # con la pantalla mutada para pintar el peso de quien pregunta en vez del de la
        # persona pedida, y el token forzado a contener "61", el test ORIGINAL seguía en
        # verde (la única aparición de "61" en toda la respuesta era el token).
        #
        # El arreglo NO afloja el assert: lo acota a la(s) GRÁFICA(S) —
        # `progreso/templates/progreso/_grafica.html`: el <section> que envuelve el título,
        # el resumen con el peso legible ("61,0 kg") y el <svg> con los <circle> — que es
        # exactamente lo que R7 promete (que SE VE el dato). Se ancla al CONTENIDO (el
        # bloque que tiene un <svg> dentro), no a una POSICIÓN, por la misma razón que el
        # 016: una posición se desplaza sola el día que alguien añade un formulario o un
        # enlace nuevo con una PK en la URL, y lo hace en silencio.
        #
        # Bug 019: este regex, ya duplicado con el del 016, se extrajo a `_zona_de_datos`
        # (arriba del fichero) al aparecer una tercera vez — sin cambiar lo que este test
        # comprueba, solo deja de repetir el patrón.
        graficas, zona_de_datos = _zona_de_datos(contenido)
        # Si esto falla, NO es que desapareciera el peso de Eurídice: es que el regex de
        # arriba dejó de casar (p. ej. `_grafica.html` cambió de <section> a otra etiqueta).
        # Mismo aviso que el 016, para no repetir el error del 015 (un rojo mudo que apunta
        # al síntoma equivocado).
        self.assertTrue(graficas, "no casó ninguna gráfica: ¿cambió _grafica.html?")
        self.assertIn("61", zona_de_datos)


class EscrituraAjenaSigueBloqueadaTests(BaseProgresoTests):
    """
    R8 — la otra mitad de la pareja R7/R8: SOLO mirar. Apuntar y borrar el peso de Euridice
    siguen dando 404, exactamente igual que antes de esta unidad (los mismos endpoints que
    `perfiles.tests.AislamientoDePesoTests` ya prueba; se repiten aquí, desde la puerta de
    entrada natural de esta unidad, para que la pareja R7/R8 quede clavada junta).
    """

    def test_r8_apuntar_el_peso_de_euridice_sigue_dando_404(self):
        mediciones_antes = MedicionPeso.objects.filter(persona=self.euridice).count()
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
            MedicionPeso.objects.filter(persona=self.euridice).count(), mediciones_antes
        )

    def test_r8_borrar_una_medicion_de_euridice_sigue_dando_404(self):
        medicion = MedicionPeso.objects.filter(persona=self.euridice).first()  # la del alta
        self.assertIsNotNone(medicion)  # control
        respuesta = self.client.post(f"/perfiles/{self.euridice.id}/peso/{medicion.id}/borrar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(MedicionPeso.objects.filter(id=medicion.id).exists())


class EsperandoAceptacionEnElHogarTests(PruebaConRegistroAbierto):
    """
    Bug 027 (8ª cara de tests-que-no-fallan-cuando-deben.md, medida en la revisión de la 023
    y nunca cerrada hasta ahora): ningún test de este fichero monta el estado "esperando que
    le acepten en el hogar, todavía sin hogar propio" (R14 de la unidad 003) para /progreso/.
    `BaseProgresoTests.setUp` (arriba) SIEMPRE acepta a Euridice en el hogar de Alejandro
    ANTES de que ningún test corra, así que la rama de
    `progreso/acceso.py:persona_visible_o_404` que deja ver la PROPIA persona sin necesitar
    ningún hogar (`hogar_actual` puede ser `None` — R7 de la especificación de esta unidad,
    "la PROPIA siempre es visible, aunque todavía no tenga hogar asignado") nunca se
    ejercita. Consecuencia medida: mutar esa comparación para que compare el id de la CUENTA
    en vez de la PERSONA (`persona.usuario_id` en vez de `persona.id`) deja pasar la suite
    ENTERA — 601 tests, `python manage.py test` sigue en `OK` con la mutación puesta (ver
    docs/bugs/027-asserts-de-la-024-y-una-rama-de-progreso-sin-red.md, sección 2, para el
    output completo).

    Su hermana `perfiles.tests.R1_EuridicePorHTTPTests
    .test_ve_sus_calorias_incluso_registrandose_con_codigo_de_otro_hogar_sin_que_nadie_la_acepte`
    SÍ cubre este estado para `/perfiles/`, con el mismo montaje (registrarse CON el código de
    otro hogar y no ser aceptada). Este test hace lo mismo para `/progreso/`, que se había
    quedado sin su versión.
    """

    def test_ve_su_propio_progreso_aunque_todavia_no_le_hayan_aceptado_en_el_hogar(self):
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        alejandro = Persona.objects.get(usuario__email="alejandro@example.com")

        # Desincroniza a propósito el id de `Persona` del id de `Usuario` ANTES de que
        # Euridice exista. Medido: sin este paso, en una tanda aislada (solo este test) el id
        # de la `Persona` de Euridice coincide por PURA CASUALIDAD con el id de su propia
        # `Usuario` — las dos secuencias arrancan en 1 y avanzan 1 a 1 cuando cada cuenta
        # estrena su persona — así que la mutación de Forma B (comparar `persona.usuario_id`
        # en vez de `persona.id`) pasaba en verde IGUAL, no porque el código protegiera nada,
        # sino por la coincidencia. Dar de alta a Marta (una `Persona` SIN `Usuario`, R2 de la
        # unidad 024) adelanta la secuencia de `Persona` un paso por delante de la de
        # `Usuario`, para que el id de Euridice YA NO pueda coincidir con el de su cuenta.
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

        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=alejandro.hogar.codigo
        )
        euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.assertIsNone(euridice.hogar_id)  # control: sigue "esperando que le acepten"
        # Euridice registra DESPUÉS de Marta: su persona.id queda por delante de su
        # usuario.id, así que la coincidencia numérica del montaje sin red deja de darse.
        self.assertNotEqual(euridice.id, euridice.usuario_id)  # control del desfase

        _fijar_mediciones(euridice, [{"dias_atras": 0, "peso_kg": 61}])

        # Sin `persona_id` en la URL (el enlace "Tu progreso" de la barra de arriba): cae al
        # `persona_id = yo.id` de la propia vista (progreso/views.py).
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        graficas, zona_de_datos = _zona_de_datos(contenido)
        self.assertTrue(graficas, "no casó ninguna gráfica: ¿cambió _grafica.html?")
        self.assertIn("61", zona_de_datos)

        # Y también con su propio id explícito en la URL, saltándose el enlace de la barra.
        respuesta_con_id = self.client.get(f"/progreso/{euridice.id}/")
        self.assertEqual(respuesta_con_id.status_code, 200)

        # R81 — sin hogar todavía, el selector no ofrece a nadie más que a ella misma (no hay
        # nadie más de "su hogar" que ofrecer: `progreso/views.py` cae al caso
        # `miembros_del_hogar = [yo]` cuando `yo.hogar` es `None`). Un
        # `assertNotContains(respuesta, "alejandro@example.com")` no puede fallar NUNCA aquí
        # (sin hogar el `{% if miembros_del_hogar|length > 1 %}` ni siquiera renderiza el
        # selector, y desde la unidad 024 la app no imprime ningún correo en ninguna
        # pantalla) — medido: con la vista mutada para filtrar TODA la base de `Persona` al
        # selector (la regresión exacta que R81 vigila), ese assert seguía en verde. Alejandro
        # y Marta SÍ existen en la base en este momento (se dieron de alta arriba, para la
        # desincronización de ids) — son el contrafactual real: si la vista mezclara personas
        # de fuera del hogar de Euridice, sus nombres aparecerían aquí.
        self.assertNotIn(
            'flex flex-wrap gap-2">', contenido,
            "el selector se renderizó aunque Euridice no tiene hogar todavía",
        )
        self.assertNotIn("Alejandro", contenido)
        self.assertNotIn("Marta", contenido)


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
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        # Bug 016: la página ENTERA no es el sitio a mirar. `templates/base.html` mete en la
        # barra de arriba un <form> de "Salir" con {% csrf_token %} — un token ALEATORIO,
        # distinto en cada carga, que a veces contiene "61" por pura coincidencia (medido: 9
        # de 300 peticiones idénticas, sin ningún cambio de código — ver
        # docs/bugs/016-test-de-progreso-intermitente.md del meta-repo). Buscar en la página
        # entera hace que el test se ponga rojo sin que nada esté mal (décima cara de
        # tests-que-no-fallan-cuando-deben.md, con una vuelta de tuerca: aquí no caduca por
        # otra unidad, sino por contenido aleatorio de la propia página).
        #
        # El arreglo NO afloja el assert: lo acota a la(s) GRÁFICA(S) —
        # `progreso/templates/progreso/_grafica.html`: el <section> que envuelve el título, el
        # resumen con el peso legible ("93,0 kg") y el <svg> con los <circle> — que es
        # exactamente lo que R10 promete. Se ancla al CONTENIDO (el bloque que tiene un <svg>
        # dentro), no a una POSICIÓN como "el último </form>": esa primera versión dejaba fuera
        # el CSRF, pero colaba la cola de la plantilla con los enlaces "Ver tu histórico" y
        # "Cerrar un día", que llevan la PK del usuario en la URL (`ver.html:168,180`) — una
        # mina latente, porque el día que esa PK contuviera "61" (61, 161, 610-619, 961…)
        # volvería la misma intermitencia que este bug vino a matar. Anclar al <svg> de la
        # gráfica no depende de dónde caiga el último `</form>` y no puede colar una PK.
        # Contraprobado con mutación (misma ficha del bug): quitar el filtro por persona en
        # progreso/views.py sigue poniendo este test en ROJO.
        #
        # Bug 019: este regex, ya duplicado con el del 018, se extrajo a `_zona_de_datos`
        # (arriba del fichero) al aparecer una tercera vez — sin cambiar lo que este test
        # comprueba, solo deja de repetir el patrón.
        graficas, zona_de_datos = _zona_de_datos(contenido)
        # Si esto falla, NO es que desapareciera el punto de Alejandro: es que el regex de
        # arriba dejó de casar (p. ej. `_grafica.html` cambió de <section> a otra etiqueta).
        # Sin este aviso, el rojo de las tres aserciones de abajo sería correcto pero mudo
        # sobre la causa real — el mismo riesgo que ya nos costó caro en el bug 015.
        self.assertTrue(graficas, "no casó ninguna gráfica: ¿cambió _grafica.html?")
        # Un único punto: el de Alejandro. Si el hogar se mezclara, habría dos.
        self.assertEqual(zona_de_datos.count("<circle"), 1)
        self.assertIn("93", zona_de_datos)
        self.assertNotIn("61", zona_de_datos)


class SinDatosTests(BaseProgresoTests):
    """R11 — sin pesadas (o con una sola), la pantalla lo dice con naturalidad, sin error."""

    def test_r11_sin_ninguna_pesada_no_da_error_y_lo_dice_con_naturalidad(self):
        MedicionPeso.objects.filter(persona=self.alejandro).delete()
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no tienes ninguna pesada apuntada")

    def test_r11_con_una_unica_pesada_tampoco_parece_rota(self):
        _fijar_mediciones(self.alejandro, [{"dias_atras": 0, "peso_kg": 93}])
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        # Bug 019 (el tercer hermano): mismo defecto que arriba, con una única medición. Aquí
        # SÍ hay una sola pesada (el escenario del 018), pero se mide igual en vez de suponer
        # que "una medición" implica "sin mina": medido, la zona acotada contiene "93,0 kg" dos
        # veces (primero y último son el mismo punto) y la coordenada "300.0,80.0" no colisiona.
        graficas, zona_de_datos = _zona_de_datos(contenido)
        self.assertTrue(graficas, "no casó ninguna gráfica: ¿cambió _grafica.html?")
        self.assertIn("93", zona_de_datos)
        self.assertEqual(zona_de_datos.count("<circle"), 1)

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


# ==========================================================================================
# Unidad 013 (completar-progreso.md): entrenos por semanas (R-79) y cumplimiento (R-80).
# Las clases de arriba son de la 010 y NO se tocan (regla del constructor); todo lo de abajo
# es nuevo, sobre la MISMA pantalla.
# ==========================================================================================


class EntrenosPorSemanaTests(BaseProgresoTests):
    """R1/R-79 — los entrenos realizados agrupados por semanas, con sus tres números: cuántos,
    minutos y calorías, sumados dentro de la misma semana."""

    def test_r1_una_semana_con_dos_entrenos_suma_los_tres_numeros(self):
        _fijar_entrenos(
            self.alejandro,
            [
                {"dias_atras": 1, "minutos": 30, "calorias": 300},
                {"dias_atras": 3, "minutos": 45, "calorias": 400},
            ],
        )
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        semanas = respuesta.context["semanas_de_entreno"]
        self.assertEqual(len(semanas), 1)
        self.assertEqual(semanas[0]["entrenos"], 2)
        self.assertEqual(semanas[0]["minutos"], 75)
        self.assertEqual(semanas[0]["calorias"], 700)
        # Y los tres números también SE VEN (segunda cara: la respuesta se renderiza de verdad).
        self.assertContains(respuesta, "75 min")
        self.assertContains(respuesta, "700 kcal")


class EntrenosDeVariasSemanasTests(BaseProgresoTests):
    """R1 — semanas DISTINTAS no se mezclan entre sí (mutación de Verificación #4)."""

    def test_r1_dos_semanas_distintas_quedan_separadas_sin_mezclarse(self):
        _fijar_entrenos(
            self.alejandro,
            [
                {"dias_atras": 1, "minutos": 30, "calorias": 300},  # semana actual
                {"dias_atras": 10, "minutos": 20, "calorias": 200},  # semana anterior
            ],
        )
        respuesta = self.client.get("/progreso/?semanas=12")
        semanas = respuesta.context["semanas_de_entreno"]
        self.assertEqual(len(semanas), 2)
        for semana in semanas:
            self.assertEqual(semana["entrenos"], 1)  # ninguna semana se queda con las dos
        minutos_por_semana = sorted(s["minutos"] for s in semanas)
        self.assertEqual(minutos_por_semana, [20, 30])


class NuncaSeMezclanEntrenosTests(BaseProgresoTests):
    """R2/R10/C-89 (el episodio real) — Alejandro entrenó 5 veces esta semana, Euridice 2;
    mirando el progreso de Euridice se ven 2, nunca los de Alejandro sumados ni mezclados."""

    def test_r2_c89_ve_los_entrenos_de_euridice_no_los_de_alejandro(self):
        _fijar_entrenos(
            self.alejandro,
            [{"dias_atras": d, "minutos": 30, "calorias": 300} for d in range(5)],
        )
        _fijar_entrenos(
            self.euridice,
            [
                {"dias_atras": 0, "minutos": 20, "calorias": 150},
                {"dias_atras": 1, "minutos": 25, "calorias": 180},
            ],
        )
        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        semanas = respuesta.context["semanas_de_entreno"]
        self.assertEqual(len(semanas), 1)
        self.assertEqual(semanas[0]["entrenos"], 2)


class CumplimientoTests(BaseProgresoTests):
    """
    R3/R-80/C-87 (el episodio real, y el aviso del padre) — cerró 20, cumplió 14, y el
    porcentaje va sobre los 20 que CERRÓ (70%), nunca sobre el periodo entero.
    """

    def test_r3_c87_el_porcentaje_es_sobre_los_dias_cerrados_no_sobre_el_periodo(self):
        cierres = (
            [{"dias_atras": d, "respuesta": CierreDeDia.LO_SEGUI} for d in range(14)]
            + [{"dias_atras": d, "respuesta": CierreDeDia.A_MEDIAS} for d in range(14, 18)]
            + [{"dias_atras": d, "respuesta": CierreDeDia.NO_LO_SEGUI} for d in range(18, 20)]
        )
        _fijar_cierres(self.alejandro, cierres)
        respuesta = self.client.get("/progreso/")  # semanas=12 por defecto -> periodo de 84 días
        self.assertEqual(respuesta.status_code, 200)
        cumplimiento = respuesta.context["cumplimiento"]
        self.assertEqual(cumplimiento["cerrados"], 20)
        self.assertEqual(cumplimiento["lo_segui"], 14)
        self.assertEqual(cumplimiento["porcentaje"], 70)
        # Si alguien calculara sobre el periodo (84 días) saldría 17%, NO 70%.
        self.assertNotEqual(cumplimiento["porcentaje"], round(14 / 84 * 100))
        self.assertContains(respuesta, "70%")


class CumplimientoCuatroNumerosTests(BaseProgresoTests):
    """R4/R-80 — los cuatro números que nombra R-80: cerrados, lo_segui, a_medias y
    no_lo_segui, y los tres últimos suman EXACTAMENTE los cerrados."""

    def test_r4_los_tres_ultimos_suman_exactamente_los_dias_cerrados(self):
        cierres = (
            [{"dias_atras": d, "respuesta": CierreDeDia.LO_SEGUI} for d in range(3)]
            + [{"dias_atras": d, "respuesta": CierreDeDia.A_MEDIAS} for d in range(3, 5)]
            + [{"dias_atras": 5, "respuesta": CierreDeDia.NO_LO_SEGUI}]
        )
        _fijar_cierres(self.alejandro, cierres)
        respuesta = self.client.get("/progreso/")
        cumplimiento = respuesta.context["cumplimiento"]
        self.assertEqual(cumplimiento["cerrados"], 6)
        self.assertEqual(cumplimiento["lo_segui"], 3)
        self.assertEqual(cumplimiento["a_medias"], 2)
        self.assertEqual(cumplimiento["no_lo_segui"], 1)
        self.assertEqual(
            cumplimiento["lo_segui"] + cumplimiento["a_medias"] + cumplimiento["no_lo_segui"],
            cumplimiento["cerrados"],
        )


class CumplimientoSinCierresTests(BaseProgresoTests):
    """R5, caso límite — sin ningún día cerrado en el periodo, ni porcentaje inventado ni
    división por cero: la pantalla sigue entera y lo dice con naturalidad."""

    def test_r5_sin_cierres_no_hay_porcentaje_inventado_ni_error(self):
        CierreDeDia.objects.filter(persona=self.alejandro).delete()
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        cumplimiento = respuesta.context["cumplimiento"]
        self.assertEqual(cumplimiento["cerrados"], 0)
        self.assertIsNone(cumplimiento["porcentaje"])
        self.assertContains(respuesta, 'id="progreso-cumplimiento"')  # la sección sigue entera


class SinEntrenosEnPeriodoTests(BaseProgresoTests):
    """R6/G-172 — sin entrenos en el periodo, la sección de entrenos NO aparece con huecos
    vacíos ni reclama nada, mismo trato que ya reciben grasa y cintura en la 010."""

    def test_r6_sin_entrenos_la_seccion_no_aparece(self):
        Entreno.objects.filter(persona=self.alejandro).delete()
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'id="progreso-entrenos"')
        self.assertEqual(respuesta.context["semanas_de_entreno"], [])


class SemanasCambianEntrenosYCumplimientoTests(BaseProgresoTests):
    """R7 — al cambiar cuántas semanas mira, los entrenos y el cumplimiento cambian con ella
    (mutación de Verificación #3: ignorar `semanas` y usar siempre el defecto)."""

    def test_r7_cambiar_semanas_cambia_los_entrenos_mostrados(self):
        _fijar_entrenos(
            self.alejandro,
            [
                {"dias_atras": 1, "minutos": 30, "calorias": 300},
                {"dias_atras": 40, "minutos": 20, "calorias": 200},  # fuera de 4 sem., dentro de 12
            ],
        )
        respuesta_4 = self.client.get("/progreso/?semanas=4")
        self.assertEqual(len(respuesta_4.context["semanas_de_entreno"]), 1)

        respuesta_12 = self.client.get("/progreso/?semanas=12")
        self.assertEqual(len(respuesta_12.context["semanas_de_entreno"]), 2)

    def test_r7_cambiar_semanas_cambia_el_cumplimiento_mostrado(self):
        _fijar_cierres(
            self.alejandro,
            [
                {"dias_atras": 1, "respuesta": CierreDeDia.LO_SEGUI},
                {"dias_atras": 40, "respuesta": CierreDeDia.LO_SEGUI},
            ],
        )
        respuesta_4 = self.client.get("/progreso/?semanas=4")
        self.assertEqual(respuesta_4.context["cumplimiento"]["cerrados"], 1)

        respuesta_12 = self.client.get("/progreso/?semanas=12")
        self.assertEqual(respuesta_12.context["cumplimiento"]["cerrados"], 2)


class OtraPersonaDelHogarEntrenosYCumplimientoTests(BaseProgresoTests):
    """R8/R-23/G-171 — el hogar ve los entrenos y el cumplimiento de otra persona de casa."""

    def test_r8_ve_los_entrenos_y_cumplimiento_de_euridice(self):
        _fijar_entrenos(self.euridice, [{"dias_atras": 0, "minutos": 20, "calorias": 150}])
        _fijar_cierres(self.euridice, [{"dias_atras": 0, "respuesta": CierreDeDia.LO_SEGUI}])
        respuesta = self.client.get(f"/progreso/{self.euridice.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["semanas_de_entreno"]), 1)
        self.assertEqual(respuesta.context["cumplimiento"]["cerrados"], 1)


class AislamientoEntreHogaresEntrenosYCumplimientoTests(BaseProgresoTests):
    """
    R9 — de otro hogar, 404, también para las secciones nuevas (mutación de Verificación #5).
    Carlos nunca se une a nadie (octava cara de tests-que-no-fallan-cuando-deben.md).
    """

    def test_r9_el_progreso_de_alguien_de_otro_hogar_da_404_con_entrenos_y_cierres(self):
        _fijar_entrenos(self.carlos, [{"dias_atras": 0, "minutos": 20, "calorias": 150}])
        _fijar_cierres(self.carlos, [{"dias_atras": 0, "respuesta": CierreDeDia.LO_SEGUI}])
        respuesta = self.client.get(f"/progreso/{self.carlos.id}/")
        self.assertEqual(respuesta.status_code, 404)


class NuncaSeMezclanCumplimientoTests(BaseProgresoTests):
    """R10/G-171 — el cumplimiento de dos personas del hogar nunca se mezcla ni se suma
    (mutación de Verificación #2, la mitad de cierres — la de entrenos la prueba C-89 arriba)."""

    def test_r10_el_cumplimiento_de_dos_personas_no_se_mezcla(self):
        _fijar_cierres(self.alejandro, [{"dias_atras": 0, "respuesta": CierreDeDia.LO_SEGUI}])
        _fijar_cierres(
            self.euridice,
            [
                {"dias_atras": 0, "respuesta": CierreDeDia.LO_SEGUI},
                {"dias_atras": 1, "respuesta": CierreDeDia.A_MEDIAS},
            ],
        )
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.context["cumplimiento"]["cerrados"], 1)


class TresSeccionesALaVezTests(BaseProgresoTests):
    """R11 — nada de la 010 cambia: peso, entrenos y cumplimiento conviven en la misma
    pantalla, las tres a la vez, sin que unas estorben a las otras."""

    def test_las_tres_secciones_aparecen_juntas_sin_estorbarse(self):
        _fijar_mediciones(self.alejandro, [{"dias_atras": 0, "peso_kg": 93}])
        _fijar_entrenos(self.alejandro, [{"dias_atras": 0, "minutos": 30, "calorias": 300}])
        _fijar_cierres(self.alejandro, [{"dias_atras": 0, "respuesta": CierreDeDia.LO_SEGUI}])
        respuesta = self.client.get("/progreso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Peso")  # la 010, intacta
        self.assertContains(respuesta, 'id="progreso-entrenos"')
        self.assertContains(respuesta, 'id="progreso-cumplimiento"')


class _ConAlejandroYMartaACargo(PruebaConRegistroAbierto):
    """Alejandro (cuenta propia) y Marta, a su cargo (sin cuenta, R-99/G-43) — mismo montaje
    que `cierres/tests_quien_tienes_a_cargo.py:R7_LaPuertaMiraResponsableNoPerfilTests`, sin
    `Perfil` porque no hace falta para lo que este bug prueba (la puerta de `progreso/` no
    depende de que exista uno). La sesión queda en Alejandro al terminar `setUp`."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.marta = Persona.objects.create(
            hogar=self.alejandro.hogar, nombre="Marta", responsable=self.alejandro
        )


class Bug028_ElResponsableVeElEnlaceDeCerrarTests(_ConAlejandroYMartaACargo):
    """
    Bug 028 — el patrón que la unidad 025 dejó escrito en el comentario de cada plantilla que
    lo aplica (`es_propio` decide el TEXTO, `puede_editar` decide si se ENSEÑA la acción) se
    quedó sin aplicar en `progreso/ver.html`: el enlace "Cerrar un día" usaba `es_propio`
    ("soy yo", a secas) en vez de `puede_editar`, así que el responsable de una persona a
    cargo —a quien `cierres/acceso.py` SÍ deja pasar, unidad 025— no veía el enlace en la
    pantalla donde está mirando el cumplimiento.
    """

    def test_alejandro_ve_el_enlace_de_cerrar_el_dia_de_marta(self):
        respuesta = self.client.get(f"/progreso/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        # `cierres/acceso.py` (unidad 025) ya deja pasar a Alejandro por esta URL; el enlace
        # tiene que existir en la PANTALLA, no solo la puerta de detrás.
        self.assertIn(f'href="/cierres/{self.marta.id}/"', contenido)


class Bug028_SegundoSintomaElTextoDelHistoricoTests(_ConAlejandroYMartaACargo):
    """
    Bug 028, segundo síntoma (sección 1 de la ficha) — `ver.html` decía "Ver su histórico →"
    a quien mira a su persona a cargo, cuando ahí también puede apuntarle una pesada
    (`perfiles/views.py:ver_peso` sí lo deja, R1/G-43 de la unidad 025). El texto prometía
    menos de lo que la app permite.

    Contraprueba (regla 2 del constructor): con la plantilla ANTES del arreglo —el `{% if
    es_propio %}/{% else %}` de dos ramas, sin la rama `puede_editar`— esta aserción da
    ROJO (el texto de abajo no existe en ninguna rama; solo sale "Ver su histórico →", sin
    "apuntarle una pesada"). Receta REAL y reejecutable (nunca `git stash`: la pila es única
    y compartida entre TODOS los worktrees, y aquí además ni siquiera sería reproducible —
    esta rama tiene un solo commit, así que un stash a secas se llevaría también estas clases
    de test y la corrida diría "no such test", no el `AssertionError` de abajo). Revierte SOLO
    la plantilla al commit anterior al arreglo (`34dd815`, el padre de este bug en la rama), y
    la restaura al terminar:

    $ git checkout 34dd815 -- progreso/templates/progreso/ver.html
    $ python manage.py test progreso.tests.Bug028_SegundoSintomaElTextoDelHistoricoTests -v 2
    FAIL: test_alejandro_ve_que_puede_apuntarle_una_pesada_a_marta ... AssertionError:
    'Ver su histórico y apuntarle una pesada →' not found in '...Ver su histórico →...'
    $ git checkout HEAD -- progreso/templates/progreso/ver.html
    (la plantilla vuelve a tener el arreglo; ver sección 5 de la ficha para el output literal
    completo de las dos corridas, ROJO y VERDE)
    """

    def test_alejandro_ve_que_puede_apuntarle_una_pesada_a_marta(self):
        respuesta = self.client.get(f"/progreso/{self.marta.id}/")
        contenido = respuesta.content.decode()
        self.assertIn("Ver su histórico y apuntarle una pesada →", contenido)


class Bug028_LaAmpliacionNoSeVaDeMadreTests(_ConAlejandroYMartaACargo):
    """
    Bug 028 — el arreglo cambia el CRITERIO de "¿se enseña el enlace?" de `es_propio` a
    `puede_editar`, pero `puede_editar` tiene que seguir siendo tan ESTRECHO como
    `hogares.acceso.puede_cambiar_lo_de` (G-43: la propia dueña, o SU responsable — nunca
    "cualquiera del hogar", que es lo que `es_propio` de tan estricto NO dejaba ver antes por
    accidente). Euridice está en el MISMO hogar que Marta (R7: la VE, R-23/G-171) pero no es
    su responsable — nunca debe ver el enlace de cerrar el día de Marta, ni el texto de
    "apuntarle una pesada".

    Contraprueba (regla 2): esta aserción da ROJO si `puede_editar_progreso` se implementa
    mal — por ejemplo, "cualquiera del MISMO hogar" en vez de "la dueña o su responsable"
    (`hogares.acceso.puede_cambiar_lo_de`). Receta REAL y reejecutable (probada tal cual:
    importa `Persona` DENTRO de la mutación —`progreso/acceso.py` no la tiene importada a
    nivel de módulo— porque sin ese `import` la llamada revienta con `NameError`, no con el
    `AssertionError` que se afirma abajo):

    $ python - <<'PY'
    p = "progreso/acceso.py"
    s = open(p).read()
    s2 = s.replace(
        "    return puede_cambiar_lo_de(request, persona_id)",
        "    from hogares.models import Persona  # MUTACION\n"
        "    persona = persona_actual(request)\n"
        "    return persona is not None and persona.hogar_id == "
        "Persona.objects.get(pk=persona_id).hogar_id  # MUTACION: todo el hogar, no solo la"
        " duena/responsable",
        1,
    )
    assert s2 != s, "el replace no encontró el texto a mutar"
    open(p, "w").write(s2)
    PY
    $ python manage.py test progreso.tests.Bug028_LaAmpliacionNoSeVaDeMadreTests -v 2
    FAIL: test_euridice_no_ve_el_enlace_de_cerrar_el_dia_de_marta ... AssertionError:
    'href="/cierres/2/"' unexpectedly found in ...
    $ git checkout HEAD -- progreso/acceso.py
    (mutación revertida; ver sección 5 de la ficha para el output literal completo de las dos
    corridas, ROJO y VERDE)
    """

    def setUp(self):
        super().setUp()
        self.client.logout()
        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo, sexo="mujer"
        )
        self.euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice.usuario)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control

        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

    def test_euridice_no_ve_el_enlace_de_cerrar_el_dia_de_marta(self):
        respuesta = self.client.get(f"/progreso/{self.marta.id}/")
        self.assertEqual(respuesta.status_code, 200)  # control: R7, sí la ve (solo lectura)
        contenido = respuesta.content.decode()
        self.assertNotIn(f'href="/cierres/{self.marta.id}/"', contenido)
        self.assertIn("Ver su histórico →", contenido)
        self.assertNotIn("apuntarle una pesada", contenido)
