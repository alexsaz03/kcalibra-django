"""
Utilidades COMPARTIDAS entre `cuentas/tests.py` y `hogares/tests.py`: registrar una cuenta de
principio a fin (rellenar el formulario, sacar el enlace del correo de la consola, pulsarlo)
usando el cliente de pruebas de Django contra las URLs reales — nunca llamando a los modelos
directamente — porque lo que hay que demostrar es que la APP, de punta a punta, se comporta
así (ver la lección de docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo).

Este fichero NO empieza por "test": la suite de Django no lo recorre como si tuviera tests
propios, solo lo importan los ficheros que sí lo son.

Unidad 004: el formulario de alta creció (ahora pide también los datos físicos, la actividad,
el objetivo y las manías, ver `cuentas/forms.py`). `registrar()` manda unos valores válidos
de fábrica para esos campos nuevos —los de Euridice, el episodio de C-13— así que TODAS las
llamadas ya existentes en `cuentas/tests.py` y `hogares/tests.py` (que solo pasan `email`,
`codigo_hogar` y `password`) siguen funcionando sin tocar ni una línea de esos ficheros. Los
tests de la unidad 004 que necesiten datos físicos concretos (Alejandro, R11...) los
sobrescriben pasándolos como argumentos con nombre.
"""

import re

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

CLAVE_VALIDA = "una-clave-de-verdad-2026"

_RE_ENLACE = re.compile(r"(http\S+/cuentas/confirm-email/\S+/)")

# Unidad 004 — datos físicos válidos de fábrica para `registrar()`: los de Euridice (C-13 de
# crear-cuenta.md), que además sirven de segunda comprobación gratuita de R1 en cualquier
# test que registre una cuenta sin pedir otra cosa.
DATOS_FISICOS_POR_DEFECTO = {
    "sexo": "mujer",
    "fecha_nacimiento": "1997-06-29",
    "altura_cm": "167",
    "peso_kg": "62",
    "actividad": "moderado",
    "objetivo": "perder_grasa",
    "ajuste_pct": "",
    "dieta": "",
    "alergias": "",
    "intolerancias": "",
    "no_le_gusta": "",
}


@override_settings(REGISTRO_ABIERTO=True)
class PruebaConRegistroAbierto(TestCase):
    """
    Base común: el registro abierto (si no, ninguna de estas pruebas podría ni empezar — R12
    se prueba aparte, con el registro CERRADO a propósito).
    """

    def setUp(self):
        super().setUp()
        # Los límites de intentos de allauth (R4) viven en la caché de Django, que NO se
        # limpia sola entre tests (a diferencia de la base de datos, que sí se hace rollback).
        # Sin este `clear()`, un test que registra o falla contraseñas contra un correo deja
        # "gastado" ese límite para el siguiente test que use el mismo correo, y ese siguiente
        # test falla por una razón que no tiene nada que ver con lo que dice probar.
        cache.clear()

    def registrar(self, email, codigo_hogar="", password=CLAVE_VALIDA, nombre=None, **datos_fisicos):
        """
        Rellena el formulario de alta de verdad, vía HTTP. Devuelve la respuesta.

        Los datos físicos (unidad 004) toman los de `DATOS_FISICOS_POR_DEFECTO` salvo que se
        sobrescriban por nombre, p. ej. `self.registrar(email, sexo="hombre", peso_kg="93")`.

        Unidad 024 (R-98) — `nombre` es ahora un campo obligatorio del alta. Sin pasarlo, se
        deriva del correo con el MISMO criterio que usa la migración de datos de esta unidad
        (`hogares/migrations/0005_rellena_y_exige_el_nombre.py`: la parte antes de la "@",
        capitalizada — "alejandro@example.com" -> "Alejandro"), para que los cientos de
        llamadas ya existentes en toda la suite (que solo pasaban `email`) sigan funcionando
        sin tocarlas una a una, y para que las aserciones sobre "qué nombre enseña la
        pantalla" sean predecibles sin tener que leerlas todas.
        """
        if nombre is None:
            nombre = email.split("@", 1)[0].capitalize()
        datos = {**DATOS_FISICOS_POR_DEFECTO, **datos_fisicos}
        return self.client.post(
            "/cuentas/signup/",
            {
                "email": email,
                "password1": password,
                "password2": password,
                "codigo_hogar": codigo_hogar,
                "nombre": nombre,
                **datos,
            },
            follow=True,
        )

    def ultimo_enlace_de_verificacion(self, para_correo=None):
        """
        Saca el enlace de verificación del último correo mandado (capturado por Django en
        `mail.outbox` durante los tests, sea cual sea el EMAIL_BACKEND real de settings.py).
        Si se pasa `para_correo`, busca el correo dirigido a esa dirección en vez de coger
        siempre el último (hace falta cuando en un mismo test hay más de una persona
        registrándose).
        """
        mensajes = mail.outbox
        if para_correo:
            mensajes = [m for m in mensajes if para_correo in m.to]
        self.assertTrue(mensajes, f"no se mandó ningún correo a {para_correo!r}")
        cuerpo = mensajes[-1].body
        coincidencia = _RE_ENLACE.search(cuerpo)
        self.assertIsNotNone(
            coincidencia, f"el correo no contiene un enlace de verificación: {cuerpo!r}"
        )
        return coincidencia.group(1)

    def registrar_y_verificar(self, email, codigo_hogar="", password=CLAVE_VALIDA, **datos_fisicos):
        """Alta completa: rellena el formulario Y pulsa el enlace del correo, con el MISMO
        cliente (para que allauth la deje entrar directa, R13)."""
        self.registrar(email, codigo_hogar=codigo_hogar, password=password, **datos_fisicos)
        enlace = self.ultimo_enlace_de_verificacion(para_correo=email)
        return self.client.get(enlace, follow=True)
