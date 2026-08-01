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
        # No basta un 200 vacío: la página tiene que decir algo reconocible.
        self.assertContains(respuesta, "KCalibra")


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

    def test_se_niega_a_arrancar_sin_variables_obligatorias(self):
        raiz_proyecto = Path(__file__).resolve().parent.parent
        entorno = os.environ.copy()
        # OJO: se ponen a "" y no se borran (pop). El proyecto ya tiene un .env real en disco
        # (necesario para que el resto de tests funcione); si solo las borráramos del entorno
        # del subproceso, el propio settings.py las volvería a rellenar leyendo ese fichero
        # (así está pensado el cargador: la variable ya puesta en el entorno manda sobre el
        # .env). Poniéndolas vacías sí simulan "el usuario no las ha configurado".
        for variable in self.VARIABLES_OBLIGATORIAS:
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
            "la app NO debe arrancar si falta configuración obligatoria",
        )
        # El mensaje debe decir explícitamente qué falta, no ser un traceback críptico.
        self.assertIn("SECRET_KEY", salida_completa)
