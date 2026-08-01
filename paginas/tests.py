"""
Tests del esqueleto (unidad 002).

Estos tests se escribieron ANTES de que existiera la implementación (regla del plan de
trabajo: "tests primero y en rojo"). Cada uno demuestra un criterio de aceptación concreto
de la especificación:

- R1: la aplicación responde en el navegador con una página que dice que está viva.
- R2: la aplicación habla de verdad con PostgreSQL (no con el sqlite de defecto de Django).
- R7: si falta la configuración obligatoria, la app se niega a arrancar explicando qué falta
  (no arranca con valores por defecto inseguros, ni revienta con un traceback incomprensible).
"""

import os
import subprocess
import sys
from pathlib import Path

from django.db import connection
from django.test import TestCase


class InicioRespondeTests(TestCase):
    """R1 — la portada tiene que responder y decir que la app está viva."""

    def test_inicio_responde_con_pagina_viva(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        # OJO: "KCalibra" a secas NO sirve como aserción — también aparece en el <title> de
        # base.html ("Inicio · KCalibra"), así que un 200 con el <body> vacío de contenido
        # también la pasaría. "está viva" solo está en el <h1> del cuerpo de la página: si
        # alguien cambia ese titular por otra cosa, este test tiene que enterarse.
        self.assertContains(respuesta, "está viva")


class ConexionPostgresTests(TestCase):
    """R2 — la app tiene que hablar con PostgreSQL de verdad, no con sqlite de defecto."""

    def test_settings_apunta_a_postgresql(self):
        motor = connection.settings_dict["ENGINE"]
        self.assertIn(
            "postgresql",
            motor,
            "el motor configurado debe ser PostgreSQL, no el sqlite de defecto de Django",
        )

    def test_la_conexion_ejecuta_una_consulta_real(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            resultado = cursor.fetchone()
        self.assertEqual(resultado, (1,))


class ArranqueSinConfiguracionTests(TestCase):
    """
    R7 (caso límite) — sin la configuración obligatoria (clave secreta, datos de conexión a
    la base), la aplicación debe negarse a arrancar y decir qué falta. Se prueba lanzando
    "manage.py check" en un proceso aparte, con esas variables de entorno borradas, porque
    una vez que Python ya ha importado el módulo de configuración en ESTE proceso de test no
    hay forma de "desconfigurarlo" limpiamente.
    """

    VARIABLES_OBLIGATORIAS = [
        "DJANGO_SECRET_KEY",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
    ]

    def test_se_niega_a_arrancar_por_cada_variable_obligatoria(self):
        """
        Antes esta prueba solo comprobaba `DJANGO_SECRET_KEY` (con todas las variables vacías
        a la vez, pero afirmando solo sobre una). Eso dejaba colarse un fallo real: si alguien
        cambiaba las cinco variables `DB_*` para que usaran un valor por defecto en vez de
        exigirse (justo lo que R7 prohíbe: "los datos de conexión a la base"), el test seguía
        en verde porque nunca miraba esas cinco.

        Ahora se prueba UNA variable a la vez: se deja SOLO esa vacía (las demás quedan con su
        valor real, ya cargado en el entorno de este proceso desde el .env — ver el `env=`
        de abajo) y se exige que el mensaje de error la nombre explícitamente. Así cada una de
        las seis está protegida por su propia comprobación, no solo por estar en la misma lista.
        """
        raiz_proyecto = Path(__file__).resolve().parent.parent

        for variable in self.VARIABLES_OBLIGATORIAS:
            with self.subTest(variable=variable):
                entorno = os.environ.copy()
                # Vacía, no borrada (pop): el cargador de .env en settings.py usa
                # os.environ.setdefault(), así que una variable BORRADA del entorno del
                # subproceso se volvería a rellenar leyendo el .env real del disco (necesario
                # para que el resto de tests funcione) y el test nunca vería una app sin
                # configurar. Dejarla vacía sí la deja "ausente" a ojos de
                # variable_obligatoria(), que trata cualquier valor falsy como si no estuviera.
                entorno[variable] = ""

                resultado = subprocess.run(
                    [sys.executable, "manage.py", "check"],
                    cwd=str(raiz_proyecto),
                    env=entorno,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                salida_completa = resultado.stdout + resultado.stderr

                self.assertNotEqual(
                    resultado.returncode,
                    0,
                    f"la app NO debe arrancar si falta '{variable}'",
                )
                # El mensaje debe nombrar EXPLÍCITAMENTE la variable que falta, no ser un
                # traceback críptico ni un error genérico que valga para cualquier variable.
                self.assertIn(
                    variable,
                    salida_completa,
                    f"el mensaje de error debe decir '{variable}', no solo que algo falta",
                )
