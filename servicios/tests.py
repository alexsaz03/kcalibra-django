"""
Tests del cálculo (R1, R2, R4, R8, R10): llaman a `servicios.metabolismo` DIRECTAMENTE, sin
pasar por ninguna vista ni por el cliente de pruebas HTTP — es justo lo que R8 exige poder
demostrar ("los tests del cálculo lo prueban llamándolo directamente, sin pasar por ninguna
pantalla"). No hace falta ni base de datos: por eso este fichero no usa `TestCase` de Django,
sino `unittest.TestCase` a secas (nada aquí toca la base).

Los números de R1 y R2 son los de los episodios reales de los planos (crear-cuenta.md,
cambiar-tus-datos.md), verificados a mano contra la fórmula antes de escribir esto (ver el
"Cómo" de la especificación de la unidad). `hoy` se fija explícitamente en vez de usar la
fecha real de la máquina: así el test no depende de en qué día se ejecute la suite.
"""

import unittest
from datetime import date, timedelta

from servicios import cierres
from servicios import entrenos
from servicios import metabolismo
from servicios import planes
from servicios import progreso

HOY_DE_REFERENCIA = date(2026, 8, 2)


class CalcularEdadTests(unittest.TestCase):
    """R10 — el caso límite del cumpleaños: sin cumplir años este año, un año menos."""

    def test_ya_cumplio_anios_este_anio(self):
        # Euridice, nacida el 29/06/1997: el 2 de agosto de 2026 ya ha cumplido 29.
        edad = metabolismo.calcular_edad(date(1997, 6, 29), hoy=HOY_DE_REFERENCIA)
        self.assertEqual(edad, 29)

    def test_aun_no_ha_cumplido_anios_este_anio(self):
        # Alejandro, nacido el 03/11/1998: en agosto de 2026 TODAVÍA no ha cumplido 28.
        edad = metabolismo.calcular_edad(date(1998, 11, 3), hoy=HOY_DE_REFERENCIA)
        self.assertEqual(edad, 27)

    def test_el_mismo_dia_del_cumpleanios_ya_cuenta_el_anio_nuevo(self):
        # Justo el día del cumpleaños: ya ha cumplido (no hace falta esperar al día siguiente).
        edad = metabolismo.calcular_edad(date(1998, 11, 3), hoy=date(2026, 11, 3))
        self.assertEqual(edad, 28)

    def test_la_vispera_del_cumpleanios_todavia_no_cuenta(self):
        edad = metabolismo.calcular_edad(date(1998, 11, 3), hoy=date(2026, 11, 2))
        self.assertEqual(edad, 27)


class CalcularEdadDe29DeFebreroTests(unittest.TestCase):
    """
    H1 de la revisión: quien nació un 29 de febrero (fecha de nacimiento válida, R11 no la
    rechaza) NO puede reventar `calcular_edad` en un año no bisiesto — antes lo hacía, con
    `ValueError: day is out of range for month`, al intentar construir `date(2026, 2, 29)`.

    Regla de negocio fijada (ver el docstring de `calcular_edad`): en un año no bisiesto,
    cumple años el 28 de febrero, no el 1 de marzo.
    """

    NACIDO_EL_29_DE_FEBRERO = date(2000, 2, 29)  # 2000 sí fue bisiesto

    def test_en_un_anio_no_bisiesto_no_revienta_y_da_la_edad_correcta(self):
        # 2026 NO es bisiesto. Antes del 28/2 (su cumpleaños "movido"), aún no ha cumplido.
        edad_antes = metabolismo.calcular_edad(
            self.NACIDO_EL_29_DE_FEBRERO, hoy=date(2026, 2, 27)
        )
        self.assertEqual(edad_antes, 25)

        # El propio 28/2 ya cuenta como cumplido (igual que cualquier otro cumpleaños, R10).
        edad_el_dia = metabolismo.calcular_edad(
            self.NACIDO_EL_29_DE_FEBRERO, hoy=date(2026, 2, 28)
        )
        self.assertEqual(edad_el_dia, 26)

        # Y sigue en 26 el resto del año (agosto, el "hoy" que usan R1/R2 de esta unidad).
        edad_en_agosto = metabolismo.calcular_edad(
            self.NACIDO_EL_29_DE_FEBRERO, hoy=date(2026, 8, 2)
        )
        self.assertEqual(edad_en_agosto, 26)

    def test_en_un_anio_bisiesto_cumple_el_29_de_verdad(self):
        # 2028 SÍ es bisiesto: existe un 29/2/2028 de verdad, y es ESE día el que cuenta.
        edad_la_vispera = metabolismo.calcular_edad(
            self.NACIDO_EL_29_DE_FEBRERO, hoy=date(2028, 2, 28)
        )
        self.assertEqual(edad_la_vispera, 27)

        edad_el_29 = metabolismo.calcular_edad(
            self.NACIDO_EL_29_DE_FEBRERO, hoy=date(2028, 2, 29)
        )
        self.assertEqual(edad_el_29, 28)


class CatalogoDeObjetivosTests(unittest.TestCase):
    """R4/G-60 — los cinco objetivos, con su ajuste y su proteína por kilo de fábrica."""

    def test_existen_los_cinco_objetivos(self):
        self.assertEqual(
            set(metabolismo.OBJETIVOS),
            {
                "mantener",
                "perder_grasa",
                "ganar_musculo",
                "rendimiento",
                "recomposicion_corporal",
            },
        )

    def test_los_ajustes_y_la_proteina_de_fabrica_de_cada_objetivo(self):
        self.assertEqual(
            metabolismo.OBJETIVOS["mantener"], {"ajuste_pct": 0, "proteina_por_kg": 1.8}
        )
        self.assertEqual(
            metabolismo.OBJETIVOS["perder_grasa"],
            {"ajuste_pct": -10, "proteina_por_kg": 2.2},
        )
        self.assertEqual(
            metabolismo.OBJETIVOS["ganar_musculo"],
            {"ajuste_pct": 10, "proteina_por_kg": 2.0},
        )
        self.assertEqual(
            metabolismo.OBJETIVOS["rendimiento"], {"ajuste_pct": 5, "proteina_por_kg": 1.8}
        )
        self.assertEqual(
            metabolismo.OBJETIVOS["recomposicion_corporal"],
            {"ajuste_pct": 10, "proteina_por_kg": 2.2},
        )


class R1_EuridiceTests(unittest.TestCase):
    """
    R1 — Euridice: 62 kg, 167 cm, nacida el 29/06/1997, mujer, actividad moderada, perder
    grasa. Tiene que salir CLAVADO: 1.894 kcal, 136 g de proteína, 59 g de grasa, 205 g de
    carbohidratos (C-13 de crear-cuenta.md).
    """

    def setUp(self):
        self.resultado = metabolismo.calcular_perfil_nutricional(
            sexo="mujer",
            fecha_nacimiento=date(1997, 6, 29),
            altura_cm=167,
            peso_kg=62,
            actividad="moderado",
            objetivo="perder_grasa",
            ajuste_pct=metabolismo.OBJETIVOS["perder_grasa"]["ajuste_pct"],
            hoy=HOY_DE_REFERENCIA,
        )

    def test_las_calorias_salen_clavadas(self):
        self.assertEqual(self.resultado["calorias"], 1894)

    def test_los_macros_salen_clavados(self):
        self.assertEqual(self.resultado["proteina_g"], 136)
        self.assertEqual(self.resultado["grasa_g"], 59)
        self.assertEqual(self.resultado["carbos_g"], 205)

    def test_la_edad_usada_es_29(self):
        self.assertEqual(self.resultado["edad"], 29)


class R2_AlejandroRecomposicionTests(unittest.TestCase):
    """
    R2 — Alejandro: 93 kg, 190 cm, nacido el 03/11/1998, hombre, actividad ligera,
    recomposición corporal. Tiene que salir CLAVADO: 3.006 kcal, 205 g de proteína, 94 g de
    grasa, 336 g de carbohidratos (episodio de cambiar-tus-datos.md, G-60).
    """

    def setUp(self):
        self.resultado = metabolismo.calcular_perfil_nutricional(
            sexo="hombre",
            fecha_nacimiento=date(1998, 11, 3),
            altura_cm=190,
            peso_kg=93,
            actividad="ligero",
            objetivo="recomposicion_corporal",
            ajuste_pct=metabolismo.OBJETIVOS["recomposicion_corporal"]["ajuste_pct"],
            hoy=HOY_DE_REFERENCIA,
        )

    def test_las_calorias_salen_clavadas(self):
        self.assertEqual(self.resultado["calorias"], 3006)

    def test_los_macros_salen_clavados(self):
        self.assertEqual(self.resultado["proteina_g"], 205)
        self.assertEqual(self.resultado["grasa_g"], 94)
        self.assertEqual(self.resultado["carbos_g"], 336)

    def test_la_edad_usada_es_27(self):
        # R10: en agosto de 2026 Alejandro (nacido el 03/11) todavía no ha cumplido 28.
        self.assertEqual(self.resultado["edad"], 27)


class C33_AlejandroPerderGrasaTests(unittest.TestCase):
    """
    La "errata de los planos" documentada en la especificación: C-33 dice que Alejandro en
    perder grasa está en 2.459 kcal, pero la fórmula da 2.459,53 → 2.460 (el plano redondeó
    hacia abajo por error de transcripción). Es el CONTEXTO del criterio, no lo que verifica
    (el "Entonces" es R2, que sí sale clavado): este test fija que la fórmula manda, tal como
    dice la especificación, y no el número del plano.
    """

    def test_perder_grasa_da_2460_no_2459(self):
        resultado = metabolismo.calcular_perfil_nutricional(
            sexo="hombre",
            fecha_nacimiento=date(1998, 11, 3),
            altura_cm=190,
            peso_kg=93,
            actividad="ligero",
            objetivo="perder_grasa",
            ajuste_pct=metabolismo.OBJETIVOS["perder_grasa"]["ajuste_pct"],
            hoy=HOY_DE_REFERENCIA,
        )
        self.assertEqual(resultado["calorias"], 2460)


class RedondeoAlFinalTests(unittest.TestCase):
    """R8/"Cómo" — se redondea al entero más próximo, y SOLO al final: un cambio de un solo
    gramo en el peso tiene que notarse en el resultado (si se redondeara a mitad de camino,
    cambios pequeños podrían desaparecer)."""

    def test_un_kilo_de_diferencia_cambia_las_calorias(self):
        base = metabolismo.calcular_perfil_nutricional(
            sexo="mujer",
            fecha_nacimiento=date(1997, 6, 29),
            altura_cm=167,
            peso_kg=62,
            actividad="moderado",
            objetivo="mantener",
            ajuste_pct=0,
            hoy=HOY_DE_REFERENCIA,
        )
        con_un_kilo_mas = metabolismo.calcular_perfil_nutricional(
            sexo="mujer",
            fecha_nacimiento=date(1997, 6, 29),
            altura_cm=167,
            peso_kg=63,
            actividad="moderado",
            objetivo="mantener",
            ajuste_pct=0,
            hoy=HOY_DE_REFERENCIA,
        )
        self.assertNotEqual(base["calorias"], con_un_kilo_mas["calorias"])


class MacrosNuncaNegativosTests(unittest.TestCase):
    """Caso límite defensivo: si algún día un ajuste extremo dejara las calorías por debajo
    de lo que ya "gastan" la proteína y la grasa, los carbohidratos no deben salir negativos
    (la fórmula de la referencia Node ya se protege con `Math.max(0, ...)`)."""

    def test_los_carbohidratos_nunca_bajan_de_cero(self):
        macros = metabolismo.calcular_macros(objetivo="mantener", calorias=1, peso_kg=200)
        self.assertGreaterEqual(macros["carbos_g"], 0)


class SumarComidasTests(unittest.TestCase):
    """
    Unidad 005, R1/R8 — `servicios.planes.sumar_comidas` suma las 4 magnitudes de una lista de
    comidas. Se prueba llamándola DIRECTAMENTE, sin base de datos ni vista (R8: "se prueban
    llamándolos directamente").
    """

    def test_suma_las_cuatro_magnitudes_de_varias_comidas(self):
        comidas = [
            {"calorias": 500, "proteina_g": 30, "grasa_g": 15, "carbos_g": 50},
            {"calorias": 700, "proteina_g": 40, "grasa_g": 20, "carbos_g": 80},
        ]
        totales = planes.sumar_comidas(comidas)
        self.assertEqual(
            totales,
            {"calorias": 1200, "proteina_g": 70, "grasa_g": 35, "carbos_g": 130},
        )

    def test_una_lista_vacia_suma_cero_en_todo(self):
        """R5 — "el anillo vacío": sin ninguna comida, el total es cero, no un error."""
        totales = planes.sumar_comidas([])
        self.assertEqual(
            totales, {"calorias": 0, "proteina_g": 0, "grasa_g": 0, "carbos_g": 0}
        )


class CalcularPorcentajeCoberturaTests(unittest.TestCase):
    """
    R2/R3/C-79 — el % que el plan cubre del objetivo del día. El episodio de los planos:
    Alejandro, 3.006 kcal de objetivo, plan de 2.800 kcal → en torno al 93%.
    """

    def test_el_episodio_de_alejandro_da_en_torno_al_93_por_ciento(self):
        porcentaje = planes.calcular_porcentaje_cobertura(2800, 3006)
        self.assertEqual(porcentaje, 93)

    def test_sin_objetivo_no_revienta_por_cero_y_da_cero(self):
        self.assertEqual(planes.calcular_porcentaje_cobertura(500, 0), 0)
        self.assertEqual(planes.calcular_porcentaje_cobertura(500, None), 0)

    def test_plan_vacio_frente_a_un_objetivo_real_da_cero(self):
        self.assertEqual(planes.calcular_porcentaje_cobertura(0, 3006), 0)

    def test_r9_un_plan_pasado_supera_el_100_por_ciento_sin_reventar(self):
        """
        R9 (caso límite) — un plan que suma MÁS que el objetivo no debe dar un porcentaje
        absurdo (negativo, `inf`, una excepción): da un número por encima de 100, tal cual,
        para que quien pinte el anillo decida cómo mostrarlo "pasado".
        """
        porcentaje = planes.calcular_porcentaje_cobertura(3600, 3006)
        self.assertGreater(porcentaje, 100)
        self.assertEqual(porcentaje, 120)


class CalcularResumenDelDiaTests(unittest.TestCase):
    """
    R2/R3/R5/R8/R9 — la función que junta todo lo que necesita una tarjeta del Inicio: los
    totales, el % de cobertura, si el plan está "pasado" (R9) y el % ya capado a 100 para
    pintar el anillo sin desbordarlo (R9: "sin... anillos desbordados").
    """

    def test_con_plan_normal_no_esta_pasado_y_el_porcentaje_visual_es_el_mismo(self):
        comidas = [{"calorias": 2800, "proteina_g": 0, "grasa_g": 0, "carbos_g": 0}]
        resumen = planes.calcular_resumen_del_dia(comidas, 3006)
        self.assertEqual(resumen["calorias"], 2800)
        self.assertEqual(resumen["porcentaje"], 93)
        self.assertEqual(resumen["porcentaje_visual"], 93)
        self.assertFalse(resumen["pasado"])
        self.assertTrue(resumen["tiene_comidas"])

    def test_r9_un_plan_pasado_marca_pasado_y_capa_el_porcentaje_visual_a_100(self):
        comidas = [{"calorias": 3600, "proteina_g": 0, "grasa_g": 0, "carbos_g": 0}]
        resumen = planes.calcular_resumen_del_dia(comidas, 3006)
        self.assertEqual(resumen["porcentaje"], 120)  # el dato real no se pierde (R9)
        self.assertEqual(resumen["porcentaje_visual"], 100)  # pero el anillo no se desborda
        self.assertTrue(resumen["pasado"])

    def test_r5_sin_comidas_el_resumen_es_el_anillo_vacio(self):
        resumen = planes.calcular_resumen_del_dia([], 3006)
        self.assertEqual(resumen["calorias"], 0)
        self.assertEqual(resumen["porcentaje"], 0)
        self.assertFalse(resumen["pasado"])
        self.assertFalse(resumen["tiene_comidas"])

    def test_r3_el_resultado_depende_solo_de_las_comidas_y_el_objetivo_pasados(self):
        """
        R3 — "el anillo mide el plan, no lo comido": esta función pura no recibe (ni podría
        leer) nada más que `comidas` y `calorias_objetivo`. Llamarla dos veces con los MISMOS
        argumentos da SIEMPRE el mismo resultado — no hay ningún estado oculto (reloj, base de
        datos, "lo comido") que pueda moverla.
        """
        comidas = [{"calorias": 1000, "proteina_g": 10, "grasa_g": 10, "carbos_g": 10}]
        primera_llamada = planes.calcular_resumen_del_dia(comidas, 2000)
        segunda_llamada = planes.calcular_resumen_del_dia(comidas, 2000)
        self.assertEqual(primera_llamada, segunda_llamada)


# ------------------------------------------------------------------------------------------
# Unidad 010 (ver-tu-progreso.md): `servicios.progreso` — cuántas semanas mirar (R5/R6), qué
# mediciones caen en ese periodo (R5), y cómo convertir una serie en los puntos de un SVG
# (R1/R2/R4). Funciones puras, probadas DIRECTAMENTE (R8), sin base de datos ni vista.
# ------------------------------------------------------------------------------------------


class SemanasDesdeParametroTests(unittest.TestCase):
    """
    R5/R6 — el número de semanas llega como parámetro de URL: cualquiera puede teclear lo que
    sea. Dentro de [4, 52] se respeta tal cual (R5); fuera de rango, no numérico o ausente cae
    al valor por defecto (12) SIN reventar (R6) — al contrario que la unidad 009 (una
    variable de entorno que no se entiende SÍ tumba el arranque, porque es despliegue, no
    entrada de una persona).
    """

    def test_un_valor_dentro_del_rango_se_respeta(self):
        # R5/sexta cara de tests-que-no-fallan-cuando-deben.md: no basta con probar "cae al
        # defecto", hace falta probar también que un valor VÁLIDO se usa de verdad, no que la
        # función esté simplemente ciega y devuelva siempre 12.
        self.assertEqual(progreso.semanas_desde_parametro("8"), 8)
        self.assertEqual(progreso.semanas_desde_parametro("4"), 4)  # el mínimo, inclusive
        self.assertEqual(progreso.semanas_desde_parametro("52"), 52)  # el máximo, inclusive

    def test_ausente_cae_al_defecto(self):
        self.assertEqual(progreso.semanas_desde_parametro(None), 12)

    def test_no_numerico_cae_al_defecto_sin_reventar(self):
        self.assertEqual(progreso.semanas_desde_parametro("abc"), 12)
        self.assertEqual(progreso.semanas_desde_parametro(""), 12)
        self.assertEqual(progreso.semanas_desde_parametro("12.5"), 12)
        self.assertEqual(progreso.semanas_desde_parametro("doce"), 12)

    def test_fuera_de_rango_cae_al_defecto(self):
        self.assertEqual(progreso.semanas_desde_parametro("3"), 12)  # justo por debajo del mínimo
        self.assertEqual(progreso.semanas_desde_parametro("53"), 12)  # justo por encima del máximo
        self.assertEqual(progreso.semanas_desde_parametro("-5"), 12)
        self.assertEqual(progreso.semanas_desde_parametro("9999"), 12)
        self.assertEqual(progreso.semanas_desde_parametro("0"), 12)


class RecortarPorPeriodoTests(unittest.TestCase):
    """R5 — solo las mediciones de las últimas `semanas` semanas, ambos extremos incluidos,
    ordenadas de más antigua a más reciente."""

    def test_deja_fuera_lo_anterior_al_periodo_y_ordena_ascendente(self):
        hoy = date(2026, 8, 4)
        mediciones = [
            {"fecha": date(2026, 8, 1), "peso_kg": 93},
            {"fecha": date(2026, 5, 1), "peso_kg": 96},  # más de 12 semanas antes de "hoy"
            {"fecha": date(2026, 7, 1), "peso_kg": 94},
        ]
        recortadas = progreso.recortar_por_periodo(mediciones, semanas=12, hoy=hoy)
        self.assertEqual([m["fecha"] for m in recortadas], [date(2026, 7, 1), date(2026, 8, 1)])

    def test_los_dos_extremos_del_periodo_estan_incluidos(self):
        hoy = date(2026, 8, 4)
        limite = hoy - timedelta(weeks=4)
        mediciones = [{"fecha": hoy, "peso_kg": 93}, {"fecha": limite, "peso_kg": 95}]
        recortadas = progreso.recortar_por_periodo(mediciones, semanas=4, hoy=hoy)
        self.assertEqual(len(recortadas), 2)

    def test_sin_mediciones_da_una_lista_vacia_sin_reventar(self):
        self.assertEqual(progreso.recortar_por_periodo([], semanas=12, hoy=date(2026, 8, 4)), [])


class ConstruirGraficaTests(unittest.TestCase):
    """
    R1/R2/R4 — construye los puntos de un SVG a partir de una lista de mediciones YA
    recortadas por periodo. R2/Q-152: sin ningún dato de ese campo, `None` — nunca una
    gráfica vacía ni un aviso.
    """

    def test_sin_ningun_dato_de_ese_campo_devuelve_none(self):
        """R2, la mitad de "aparece si tiene grasa Y cintura": sin grasa apuntada, la
        gráfica de grasa ni se construye."""
        mediciones = [{"fecha": date(2026, 8, 1), "peso_kg": 93, "grasa_pct": None, "cintura_cm": None}]
        self.assertIsNone(progreso.construir_grafica(mediciones, "grasa_pct"))
        self.assertIsNone(progreso.construir_grafica(mediciones, "cintura_cm"))  # la otra mitad

    def test_r4_ignora_los_dias_sueltos_sin_ese_campo_sin_inventarlos(self):
        """R4 — "grasa solo algunos días sueltos": la gráfica se dibuja con los días que
        tenga, no con un punto interpolado en los que faltan."""
        mediciones = [
            {"fecha": date(2026, 8, 1), "peso_kg": 93, "grasa_pct": 22, "cintura_cm": None},
            {"fecha": date(2026, 8, 2), "peso_kg": 92.8, "grasa_pct": None, "cintura_cm": None},
            {"fecha": date(2026, 8, 3), "peso_kg": 92.9, "grasa_pct": 21.5, "cintura_cm": None},
        ]
        grafica_grasa = progreso.construir_grafica(mediciones, "grasa_pct")
        self.assertIsNotNone(grafica_grasa)
        # Dos puntos, no tres: el día de en medio (sin grasa) no se cuela como un 0 ni como
        # un valor inventado.
        self.assertEqual(len(grafica_grasa["coordenadas"]), 2)
        self.assertEqual(grafica_grasa["primero"], 22)
        self.assertEqual(grafica_grasa["ultimo"], 21.5)

        # La gráfica de PESO, en cambio, sí tiene los tres días (todos tienen peso).
        grafica_peso = progreso.construir_grafica(mediciones, "peso_kg")
        self.assertEqual(len(grafica_peso["coordenadas"]), 3)

    def test_un_valor_que_no_varia_no_revienta_por_dividir_entre_cero(self):
        """C-88, el episodio que da sentido a la pantalla: el peso se queda exactamente
        igual semana tras semana. Sin este caso especial, escalar el valor a un rango de
        anchura cero dividiría entre cero."""
        mediciones = [
            {"fecha": date(2026, 6, 1), "peso_kg": 93, "grasa_pct": 22, "cintura_cm": None},
            {"fecha": date(2026, 7, 1), "peso_kg": 93, "grasa_pct": 20.5, "cintura_cm": None},
            {"fecha": date(2026, 8, 1), "peso_kg": 93, "grasa_pct": 19, "cintura_cm": None},
        ]
        grafica_peso = progreso.construir_grafica(mediciones, "peso_kg")
        self.assertIsNotNone(grafica_peso)
        self.assertEqual(grafica_peso["primero"], 93)
        self.assertEqual(grafica_peso["ultimo"], 93)
        # Las tres coordenadas Y caen en la misma altura (línea recta y horizontal).
        alturas = {y for _, y in grafica_peso["coordenadas"]}
        self.assertEqual(len(alturas), 1)

        # Pero la grasa, que SÍ varía, se sigue viendo bajar (C-88: "la línea del peso
        # plana y la de la grasa bajando").
        grafica_grasa = progreso.construir_grafica(mediciones, "grasa_pct")
        self.assertLess(grafica_grasa["ultimo"], grafica_grasa["primero"])
        primera_altura = grafica_grasa["coordenadas"][0][1]
        ultima_altura = grafica_grasa["coordenadas"][-1][1]
        # La grasa BAJA de valor (22 → 19); en un SVG "abajo" es "y grande" (invertir=True:
        # el valor más ALTO, el primero, va con la "y" más PEQUEÑA — más arriba en el
        # dibujo), así que la línea desciende de izquierda a derecha: la "y" final es MAYOR
        # que la inicial.
        self.assertGreater(ultima_altura, primera_altura)

    def test_un_unico_punto_no_revienta_y_se_centra(self):
        """R11 — con una sola medición no hay ningún rango que repartir (ni de fechas ni de
        valores): se centra en el lienzo en vez de dividir entre cero."""
        mediciones = [{"fecha": date(2026, 8, 1), "peso_kg": 93, "grasa_pct": None, "cintura_cm": None}]
        grafica = progreso.construir_grafica(mediciones, "peso_kg")
        self.assertEqual(len(grafica["coordenadas"]), 1)
        x, y = grafica["coordenadas"][0]
        self.assertAlmostEqual(x, grafica["ancho"] / 2, delta=1)
        self.assertAlmostEqual(y, grafica["alto"] / 2, delta=1)

    def test_ninguna_medicion_en_absoluto_da_none(self):
        self.assertIsNone(progreso.construir_grafica([], "peso_kg"))


class ConstruirEvolucionTests(unittest.TestCase):
    """R1/R2 — las tres gráficas juntas, cada una calculada de forma independiente: que una
    tenga datos no obliga a las otras a tenerlos también."""

    def test_solo_peso_apuntado_da_grasa_y_cintura_en_none(self):
        mediciones = [{"fecha": date(2026, 8, 1), "peso_kg": 93, "grasa_pct": None, "cintura_cm": None}]
        evolucion = progreso.construir_evolucion(mediciones)
        self.assertIsNotNone(evolucion["peso_kg"])
        self.assertIsNone(evolucion["grasa_pct"])
        self.assertIsNone(evolucion["cintura_cm"])

    def test_las_tres_apuntadas_dan_las_tres_graficas(self):
        mediciones = [
            {"fecha": date(2026, 8, 1), "peso_kg": 93, "grasa_pct": 22, "cintura_cm": 95},
        ]
        evolucion = progreso.construir_evolucion(mediciones)
        self.assertIsNotNone(evolucion["peso_kg"])
        self.assertIsNotNone(evolucion["grasa_pct"])
        self.assertIsNotNone(evolucion["cintura_cm"])


class AgruparEntrenosPorSemanaTests(unittest.TestCase):
    """
    Unidad 013 (completar-progreso.md), R-79/R1 — agrupa entrenos YA recortados por periodo en
    bloques de 7 días contando hacia atrás desde "hoy", sumando cuántos, minutos y calorías.
    """

    def test_dos_entrenos_de_la_misma_semana_se_suman_juntos(self):
        hoy = date(2026, 8, 5)
        entrenos = [
            {"fecha": date(2026, 8, 4), "minutos": 30, "calorias": 300},
            {"fecha": date(2026, 8, 2), "minutos": 45, "calorias": 400},
        ]
        semanas = progreso.agrupar_entrenos_por_semana(entrenos, hoy, semanas=12)
        self.assertEqual(len(semanas), 1)
        self.assertEqual(semanas[0]["entrenos"], 2)
        self.assertEqual(semanas[0]["minutos"], 75)
        self.assertEqual(semanas[0]["calorias"], 700)

    def test_dos_semanas_distintas_no_se_mezclan(self):
        """R1 — la mutación más literal: agrupar mal metería el entreno de hace 10 días en
        la semana actual."""
        hoy = date(2026, 8, 5)
        entrenos = [
            {"fecha": date(2026, 8, 4), "minutos": 30, "calorias": 300},  # semana actual (idx 0)
            {"fecha": date(2026, 7, 26), "minutos": 20, "calorias": 200},  # 10 días atrás (idx 1)
        ]
        semanas = progreso.agrupar_entrenos_por_semana(entrenos, hoy, semanas=12)
        self.assertEqual(len(semanas), 2)
        for semana in semanas:
            self.assertEqual(semana["entrenos"], 1)

    def test_sale_ordenado_de_la_semana_mas_antigua_a_la_mas_reciente(self):
        hoy = date(2026, 8, 5)
        entrenos = [
            {"fecha": date(2026, 8, 4), "minutos": 30, "calorias": 300},  # más reciente
            {"fecha": date(2026, 7, 20), "minutos": 20, "calorias": 200},  # más antiguo
        ]
        semanas = progreso.agrupar_entrenos_por_semana(entrenos, hoy, semanas=12)
        self.assertLess(semanas[0]["inicio"], semanas[1]["inicio"])

    def test_sin_entrenos_da_una_lista_vacia_sin_reventar(self):
        self.assertEqual(
            progreso.agrupar_entrenos_por_semana([], date(2026, 8, 5), semanas=12), []
        )

    def test_la_semana_con_mas_entrenos_llega_al_100_por_cien_de_altura(self):
        hoy = date(2026, 8, 5)
        entrenos = [
            {"fecha": date(2026, 8, 4), "minutos": 30, "calorias": 300},
            {"fecha": date(2026, 8, 3), "minutos": 30, "calorias": 300},
            {"fecha": date(2026, 7, 20), "minutos": 30, "calorias": 300},  # semana con 1 solo
        ]
        semanas = progreso.agrupar_entrenos_por_semana(entrenos, hoy, semanas=12)
        alturas = {semana["entrenos"]: semana["altura_pct"] for semana in semanas}
        self.assertEqual(alturas[2], 100)
        self.assertLess(alturas[1], 100)


class AgruparEntrenosPorSemanaPeriodoLlenoTests(unittest.TestCase):
    """
    Ronda 2 (hueco de la revisión, `hallazgos.md`) — el caso que ninguno de los tests de arriba
    cazaba: con un entreno CADA día del periodo (nadie falla ni un día), la barra más antigua NO
    puede ser un cubo de 1 día disfrazado de semana entera.

    `recortar_por_periodo` usa un límite INCLUSIVO (`hoy - semanas semanas` hasta `hoy`, ambos
    dentro): el periodo tiene `semanas*7 + 1` días, uno más de los que caben en `semanas`
    bloques de 7. Por eso el montaje es exactamente ese: un entreno por cada uno de esos
    `semanas*7 + 1` días, sin huecos — así el día sobrante SIEMPRE está presente y cualquier
    desbordamiento se nota.

    Se comprueba, para dos periodos distintos (el de 12 semanas por defecto y uno pequeño de 4):
    que salen EXACTAMENTE `semanas` barras (nunca `semanas + 1`, el síntoma del hueco), que cada
    barra no miente — su cuenta de entrenos coincide con el número real de días de su propio
    rango (`fin - inicio + 1`), y que la suma de entrenos de todas las barras es el total del
    periodo (ni se pierde ni se duplica ninguno).
    """

    @staticmethod
    def _entrenos_por_cada_dia_del_periodo(hoy, semanas):
        dias_del_periodo = semanas * 7 + 1  # el límite de recortar_por_periodo es inclusivo
        return [
            {"fecha": hoy - timedelta(days=i), "minutos": 30, "calorias": 300}
            for i in range(dias_del_periodo)
        ]

    def _verificar_periodo_lleno(self, hoy, semanas):
        entrenos = self._entrenos_por_cada_dia_del_periodo(hoy, semanas)
        semanas_agrupadas = progreso.agrupar_entrenos_por_semana(entrenos, hoy, semanas)

        self.assertEqual(len(semanas_agrupadas), semanas)
        for semana in semanas_agrupadas:
            dias_del_rango = (semana["fin"] - semana["inicio"]).days + 1
            self.assertEqual(semana["entrenos"], dias_del_rango)
        self.assertEqual(sum(s["entrenos"] for s in semanas_agrupadas), len(entrenos))

    def test_periodo_lleno_con_las_12_semanas_por_defecto(self):
        self._verificar_periodo_lleno(hoy=date(2026, 8, 5), semanas=12)

    def test_periodo_lleno_con_4_semanas(self):
        self._verificar_periodo_lleno(hoy=date(2026, 8, 5), semanas=4)


class CalcularCumplimientoTests(unittest.TestCase):
    """
    Unidad 013, R-80/R3/R4/R5/Q-153/C-87 — el aviso del padre, hecho test: el porcentaje va
    sobre los días que la persona CERRÓ, nunca sobre los días del periodo.
    """

    def test_c87_el_porcentaje_es_sobre_los_cerrados_no_sobre_el_periodo(self):
        # 20 cerrados: 14 lo_segui, 4 a_medias, 2 no_lo_segui. El periodo podría ser de 30
        # días, pero esta función ni siquiera los recibe (no puede calcular sobre ellos).
        cierres = (
            [{"respuesta": "lo_segui"} for _ in range(14)]
            + [{"respuesta": "a_medias"} for _ in range(4)]
            + [{"respuesta": "no_lo_segui"} for _ in range(2)]
        )
        cumplimiento = progreso.calcular_cumplimiento(cierres)
        self.assertEqual(cumplimiento["cerrados"], 20)
        self.assertEqual(cumplimiento["lo_segui"], 14)
        self.assertEqual(cumplimiento["porcentaje"], 70)  # 14/20, NO 14/30 (47%)

    def test_r4_los_tres_ultimos_suman_los_cerrados(self):
        cierres = (
            [{"respuesta": "lo_segui"} for _ in range(3)]
            + [{"respuesta": "a_medias"} for _ in range(2)]
            + [{"respuesta": "no_lo_segui"} for _ in range(1)]
        )
        cumplimiento = progreso.calcular_cumplimiento(cierres)
        suma = cumplimiento["lo_segui"] + cumplimiento["a_medias"] + cumplimiento["no_lo_segui"]
        self.assertEqual(suma, cumplimiento["cerrados"])

    def test_r5_sin_cierres_no_hay_porcentaje_ni_division_por_cero(self):
        cumplimiento = progreso.calcular_cumplimiento([])
        self.assertEqual(cumplimiento["cerrados"], 0)
        self.assertIsNone(cumplimiento["porcentaje"])


class C37_EuridiceCorrerTests(unittest.TestCase):
    """R1/C-37 (unidad 011) — el episodio real de Euridice: 62 kg, 35 min de correr a
    intensidad media, sin escribir calorías. La fórmula la despeja la especificación de la
    unidad; este test es el que la clava contra el número exacto del plano."""

    def test_estima_362_kcal(self):
        # 10 kcal/min * 35 min * (62/60) = 361,6666... -> 362 con el redondeo de Math.round
        # (la mitad SIEMPRE hacia arriba), no el bancario de round() de Python: es justo el
        # tipo de número donde se nota la diferencia (conocimiento/round-python-vs-...).
        kcal = entrenos.estimar_calorias(
            deporte="correr", intensidad="media", minutos=35, peso_kg=62
        )
        self.assertEqual(kcal, 362)


class C38_AlejandroHyroxTests(unittest.TestCase):
    """R3/C-38 (unidad 011) — el episodio real de Alejandro: 93 kg, 60 min de Hyrox a
    intensidad fuerte, sin escribir calorías."""

    def test_estima_1302_kcal(self):
        kcal = entrenos.estimar_calorias(
            deporte="hyrox", intensidad="fuerte", minutos=60, peso_kg=93
        )
        self.assertEqual(kcal, 1302)


class TablaG71Tests(unittest.TestCase):
    """R4 — los siete deportes, cada uno con sus tres intensidades, exactamente los números
    de la tabla G-71 (a peso de referencia 60 kg, sin ajustar)."""

    TABLA_ESPERADA = {
        "correr": {"suave": 8, "media": 10, "fuerte": 13.5},
        "bici": {"suave": 6, "media": 8, "fuerte": 10},
        "nadar": {"suave": 6, "media": 8, "fuerte": 9.5},
        "fuerza": {"suave": 3.5, "media": 5, "fuerte": 6},
        "crossfit": {"suave": 6, "media": 9, "fuerte": 12},
        "hyrox": {"suave": 8, "media": 11, "fuerte": 14},
        "otro": {"suave": 4, "media": 6, "fuerte": 8},
    }

    def test_los_siete_deportes_estan_con_sus_tres_intensidades(self):
        self.assertEqual(set(entrenos.TABLA_KCAL_POR_MINUTO), set(self.TABLA_ESPERADA))
        for deporte, intensidades in self.TABLA_ESPERADA.items():
            self.assertEqual(entrenos.TABLA_KCAL_POR_MINUTO[deporte], intensidades)

    def test_a_peso_de_referencia_el_ajuste_no_cambia_nada(self):
        # A 60 kg exactos, peso_kg/60 = 1: la estimación es EXACTAMENTE el número de la tabla
        # multiplicado por los minutos, sin ningún ajuste. Con 10 minutos, los siete deportes
        # y sus tres intensidades dan siempre un entero EXACTO (ninguno cae en ",5"), así que
        # el test compara contra `int(...)` sin tener que tocar el redondeo privado del módulo.
        for deporte, intensidades in self.TABLA_ESPERADA.items():
            for intensidad, kcal_min in intensidades.items():
                estimado = entrenos.estimar_calorias(
                    deporte=deporte, intensidad=intensidad, minutos=10, peso_kg=60
                )
                self.assertEqual(estimado, int(kcal_min * 10))


class AjustePorPesoTests(unittest.TestCase):
    """G-70 — el ajuste es proporcional al peso de quien entrenó: a más peso, más kcal
    estimadas para el mismo entreno, y viceversa."""

    def test_mas_peso_da_mas_calorias_para_el_mismo_entreno(self):
        ligera = entrenos.estimar_calorias(deporte="bici", intensidad="suave", minutos=30, peso_kg=50)
        pesada = entrenos.estimar_calorias(deporte="bici", intensidad="suave", minutos=30, peso_kg=100)
        self.assertGreater(pesada, ligera)


class CalcularMacrosSinRedondearTests(unittest.TestCase):
    """
    `redondear=False` (unidad 011, para escalar los macros de un entreno sin arrastrar el
    error de haber redondeado antes de tiempo — bias.md): el comportamiento POR DEFECTO
    (`redondear=True`, sin pasarlo) tiene que seguir siendo EXACTAMENTE el de antes (R8 de la
    unidad 004): esta clase demuestra las dos cosas, no solo la nueva.
    """

    def test_por_defecto_sigue_dando_los_mismos_enteros_de_siempre(self):
        # Mismos datos y mismo resultado que R1_EuridiceTests de la unidad 004: 136/59/205.
        macros = metabolismo.calcular_macros(objetivo="perder_grasa", calorias=1894.06125, peso_kg=62)
        self.assertEqual(macros, {"proteina_g": 136, "grasa_g": 59, "carbos_g": 205})

    def test_sin_redondear_devuelve_floats_sin_tocar(self):
        macros = metabolismo.calcular_macros(
            objetivo="perder_grasa", calorias=1894.06125, peso_kg=62, redondear=False
        )
        self.assertAlmostEqual(macros["proteina_g"], 136.4, places=3)
        self.assertAlmostEqual(macros["grasa_g"], 58.92635, places=3)
        self.assertAlmostEqual(macros["carbos_g"], 204.531025, places=3)


class EscalarMacrosTests(unittest.TestCase):
    """
    R7 de generar-el-plan.md (unidad 011): "sumar las calorías de los entrenos... y escalar
    sus macros en la misma proporción". El episodio real que fija el número exacto (C-2 de
    generar-el-plan.md): Euridice, base 1.894 kcal / 136-59-205 g, entrena y su objetivo sube
    a 2.249 kcal (+355) → los macros escalan a 162-70-243 g. Si `escalar_macros` recibiera los
    macros YA REDONDEADOS en vez de los exactos, la proteína daría 161 en vez de 162 (probado
    a mano en hallazgos.md) — por eso esta unidad exige `calcular_macros(..., redondear=False)`
    como entrada, nunca el diccionario ya redondeado.
    """

    def test_escala_los_macros_exactos_del_episodio_de_euridice(self):
        macros_exactos = metabolismo.calcular_macros(
            objetivo="perder_grasa", calorias=1894.06125, peso_kg=62, redondear=False
        )
        factor = (1894 + 355) / 1894
        escalados = metabolismo.escalar_macros(macros_exactos, factor)
        self.assertEqual(escalados, {"proteina_g": 162, "grasa_g": 70, "carbos_g": 243})

    def test_escalar_por_1_no_cambia_nada(self):
        macros_exactos = {"proteina_g": 100.0, "grasa_g": 50.0, "carbos_g": 200.0}
        self.assertEqual(
            metabolismo.escalar_macros(macros_exactos, 1.0),
            {"proteina_g": 100, "grasa_g": 50, "carbos_g": 200},
        )


class CalcularDiaPendienteTests(unittest.TestCase):
    """
    Unidad 012 (decir-si-cumpliste.md), R6-R9 — la función pura que decide qué día preguntar
    al abrir la app. `hoy` se fija explícitamente (mismo criterio que el resto de este
    fichero): el test no depende de en qué día se ejecute la suite.
    """

    HOY = date(2026, 8, 5)
    AYER = date(2026, 8, 4)

    def test_r6_sin_cerrar_ni_saltar_el_dia_pendiente_es_ayer(self):
        dia = cierres.calcular_dia_pendiente(self.HOY, cerrado_ayer=False, saltado_ayer=False)
        self.assertEqual(dia, self.AYER)

    def test_r9_si_ayer_ya_esta_cerrado_no_hay_nada_pendiente(self):
        dia = cierres.calcular_dia_pendiente(self.HOY, cerrado_ayer=True, saltado_ayer=False)
        self.assertIsNone(dia)

    def test_r8_si_ayer_ya_se_salto_no_hay_nada_pendiente(self):
        dia = cierres.calcular_dia_pendiente(self.HOY, cerrado_ayer=False, saltado_ayer=True)
        self.assertIsNone(dia)

    def test_cerrado_y_saltado_a_la_vez_tampoco_hay_nada_pendiente(self):
        dia = cierres.calcular_dia_pendiente(self.HOY, cerrado_ayer=True, saltado_ayer=True)
        self.assertIsNone(dia)

    def test_r7_nunca_devuelve_un_dia_mas_antiguo_que_ayer(self):
        # Aunque hubiera cinco días sin cerrar, esta función solo conoce "ayer": no tiene
        # ningún parámetro por el que pudiera devolver un día más antiguo (R7, el episodio de
        # Euridice). Se comprueba con la firma: solo entran `cerrado_ayer`/`saltado_ayer`.
        dia = cierres.calcular_dia_pendiente(self.HOY, cerrado_ayer=False, saltado_ayer=False)
        self.assertEqual(dia, self.HOY - timedelta(days=1))
        self.assertNotEqual(dia, self.HOY - timedelta(days=5))


if __name__ == "__main__":
    unittest.main()
