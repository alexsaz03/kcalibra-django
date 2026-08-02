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
from datetime import date

from servicios import metabolismo

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


if __name__ == "__main__":
    unittest.main()
