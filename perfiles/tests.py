"""
Tests de las unidades 004 (R1-R11) y 006 (R1-R10, "apuntar el peso").

Como en `cuentas/tests.py` y `hogares/tests.py`, todo pasa por el cliente de pruebas de
Django contra las URLs reales (nunca `Perfil.objects.create(...)` a mano cuando lo que se
prueba es un flujo completo) — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo: la petición tiene que
LLEGAR a lo que dice probar, así que las respuestas de HTMX se comprueban por su CONTENIDO
(los números cambiaron de verdad), no solo por el código de estado. Excepción declarada, la
misma que ya usa `perfiles/logica.py`: R2 de la unidad 006 exige demostrar que la restricción
de unicidad vive en la BASE DE DATOS, así que ESE test concreto sí llama a
`MedicionPeso.objects.create(...)` directamente, a propósito, saltándose el formulario.

R1 y R2 de la unidad 004 (los números clavados) YA están probados llamando al servicio
directamente, sin pasar por ninguna pantalla, en `servicios/tests.py` (R8: "verificable...
llamándolo directamente"). Aquí se prueban otra vez, pero de punta a punta por HTTP —alta,
verificación, pantalla de "tus datos"— para demostrar que el CABLEADO (formulario → perfil →
vista) también funciona, no solo la fórmula suelta. Como una fecha de nacimiento hace que la
edad (y por tanto las calorías) cambie el día del cumpleaños, estos dos tests fijan "hoy" con
`unittest.mock.patch` en vez de confiar en la fecha real de la máquina que ejecute la suite.

Unidad 006, punto 6 del "Cómo" de su especificación (unificar relojes): `perfiles/logica.py`
ahora pasa SIEMPRE `hoy=timezone.localdate()` a `servicios.metabolismo`, así que fijar "hoy"
en estos tests ya no consiste en parchear `servicios.metabolismo.date` (eso dejó de tener
efecto: el `hoy` que le llega nunca es `None`) sino `django.utils.timezone.localdate`
directamente — un único reloj mockeable para toda la cadena (edad, ventana de 7 días, fecha de
la medición del alta). Por lo mismo, los tests que antes escribían `date.today()` para
construir fechas "de hoy" de verdad ahora escriben `timezone.localdate()`, coherente con lo
que usa el código que están probando (`MedicionPeso.fecha`, `peso_medio_7_dias`).
"""

import re
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import PruebaConRegistroAbierto
from hogares.models import Persona
from entrenos.models import Entreno
from perfiles.forms import FormularioPerfil, FormularioMedicion
from perfiles.logica import (
    apuntar_medicion,
    borrar_medicion,
    calcular_objetivo_del_dia,
    peso_medio_7_dias,
    ultima_medicion,
)
from perfiles.models import MedicionPeso, Perfil
from perfiles import constantes

Usuario = get_user_model()

HOY_DE_REFERENCIA = date(2026, 8, 2)


def _con_hoy_fijo():
    """
    Congela "hoy" a `HOY_DE_REFERENCIA` para los tests que necesitan un resultado EXACTO
    (R1/R2 de la 004 por HTTP) sin depender de en qué día real se ejecute la suite.

    Unidad 006: `perfiles/logica.py` ahora pasa `hoy=timezone.localdate()` explícito a
    `servicios.metabolismo` (el reloj unificado del punto 6 del "Cómo"), así que parchear
    `servicios.metabolismo.date` ya no tiene ningún efecto — el `hoy` que le llega nunca es
    `None`. El único reloj que hace falta congelar es `django.utils.timezone.localdate`: lo
    usan a la vez `crear_perfil_desde_alta` (la fecha de la primera medición),
    `calcular_objetivo_del_dia` (el `hoy` que le pasa a la fórmula de la edad) y
    `peso_medio_7_dias` (la ventana de 7 días), así que un único mock deja los tres en el
    mismo día, sin que se puedan desincronizar entre sí.
    """
    return mock.patch("django.utils.timezone.localdate", return_value=HOY_DE_REFERENCIA)


class AltaConDatosFisicosTests(PruebaConRegistroAbierto):
    """R7/"El alta crece" — registrarse crea el Perfil Y la primera medición de peso."""

    def test_el_alta_crea_perfil_y_primera_medicion_de_peso(self):
        self.registrar_y_verificar("alejandro@example.com")
        usuario = Persona.objects.get(usuario__email="alejandro@example.com")

        self.assertTrue(Perfil.objects.filter(persona=usuario).exists())
        perfil = usuario.perfil
        # Los valores de fábrica de `DATOS_FISICOS_POR_DEFECTO` (los de Euridice, C-13).
        self.assertEqual(perfil.sexo, "mujer")
        self.assertEqual(perfil.altura_cm, 167)
        self.assertEqual(perfil.objetivo, "perder_grasa")

        mediciones = MedicionPeso.objects.filter(persona=usuario)
        self.assertEqual(mediciones.count(), 1)
        self.assertEqual(mediciones.first().peso_kg, 62)
        self.assertEqual(mediciones.first().fecha, timezone.localdate())

    def test_sin_ajuste_manual_el_perfil_usa_el_de_fabrica_del_objetivo(self):
        # DATOS_FISICOS_POR_DEFECTO trae objetivo=perder_grasa y ajuste_pct="" (en blanco).
        self.registrar_y_verificar("alejandro@example.com")
        perfil = Persona.objects.get(usuario__email="alejandro@example.com").perfil
        self.assertEqual(perfil.ajuste_pct, -10)  # de fábrica de "perder_grasa" (G-60)

    def test_con_ajuste_manual_en_el_alta_se_respeta_el_suyo(self):
        # "Cómo" de crear-cuenta.md: "si quiso ajustó a mano su porcentaje".
        self.registrar_y_verificar("alejandro@example.com", ajuste_pct="-15")
        perfil = Persona.objects.get(usuario__email="alejandro@example.com").perfil
        self.assertEqual(perfil.ajuste_pct, -15)

    def test_las_manias_se_guardan_aunque_nada_las_lea_todavia(self):
        self.registrar_y_verificar(
            "alejandro@example.com",
            dieta="vegetariana",
            alergias="frutos secos",
            intolerancias="lactosa",
            no_le_gusta="brócoli",
        )
        perfil = Persona.objects.get(usuario__email="alejandro@example.com").perfil
        self.assertEqual(perfil.dieta, "vegetariana")
        self.assertEqual(perfil.alergias, "frutos secos")
        self.assertEqual(perfil.intolerancias, "lactosa")
        self.assertEqual(perfil.no_le_gusta, "brócoli")


class R1_EuridicePorHTTPTests(PruebaConRegistroAbierto):
    """R1 — de punta a punta: alta con los datos de Euridice, verificar, y ver 1.894 kcal
    (136/59/205) en la pantalla de "tus datos"."""

    def test_al_verificar_ve_sus_calorias_y_macros_clavados(self):
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")  # datos de fábrica = Euridice
            respuesta = self.client.get("/perfiles/")

        self.assertContains(respuesta, "1894 kcal")
        # H-menor de la revisión: `assertContains(respuesta, "59")` o `"205"` sueltos casan
        # con casi cualquier cosa de la página (un id, una clase, un año...) — la red de R1 ya
        # está en servicios/tests.py; aquí lo que hace falta es comprobar que CADA número
        # aparece pegado a SU macro, tal como lo pinta la plantilla (perfiles/ver.html).
        self.assertContains(respuesta, "Proteína: <strong>136 g</strong>")
        self.assertContains(respuesta, "Grasa: <strong>59 g</strong>")
        self.assertContains(respuesta, "Carbohidratos: <strong>205 g</strong>")

    def test_ve_sus_calorias_incluso_registrandose_con_codigo_de_otro_hogar_sin_que_nadie_la_acepte(
        self,
    ):
        """
        H2 de la revisión: el episodio REAL de R1/C-13 y crear-cuenta.md no es "se registra
        sin más" — es "se registra con el código de Alejandro" (C-16/C-104: su cuenta queda
        SOLA, con `hogar = None`, hasta que alguien la acepte). El test anterior nunca
        recorría ese camino porque registraba a Euridice SIN código — una aserción fuerte
        sobre un escenario más cómodo, no el que el criterio describe (la lección de
        `tests-que-no-fallan-cuando-deben.md`, otra vez, con otra cara).

        El perfil PROPIO no es "una cosa del hogar" (G-43): tiene que verse aunque todavía no
        haya ningún hogar de por medio.
        """
        with _con_hoy_fijo():
            self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
            alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
            self.client.logout()

            self.registrar_y_verificar(
                "euridice@example.com", codigo_hogar=alejandro.hogar.codigo
            )
            euridice = Persona.objects.get(usuario__email="euridice@example.com")
            self.assertIsNone(euridice.hogar_id)  # control: sigue "esperando que le acepten"

            respuesta = self.client.get("/perfiles/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "1894 kcal")
        self.assertContains(respuesta, "Proteína: <strong>136 g</strong>")
        self.assertContains(respuesta, "Grasa: <strong>59 g</strong>")
        self.assertContains(respuesta, "Carbohidratos: <strong>205 g</strong>")


class R2_AlejandroPorHTTPTests(PruebaConRegistroAbierto):
    """R2 — de punta a punta: alta con los datos de Alejandro en recomposición corporal, y
    ver 3.006 kcal (205/94/336)."""

    def test_al_verificar_ve_sus_calorias_y_macros_clavados(self):
        with _con_hoy_fijo():
            self.registrar_y_verificar(
                "alejandro@example.com",
                sexo="hombre",
                fecha_nacimiento="1998-11-03",
                altura_cm="190",
                peso_kg="93",
                actividad="ligero",
                objetivo="recomposicion_corporal",
            )
            respuesta = self.client.get("/perfiles/")

        self.assertContains(respuesta, "3006 kcal")
        self.assertContains(respuesta, "Proteína: <strong>205 g</strong>")
        self.assertContains(respuesta, "Grasa: <strong>94 g</strong>")
        self.assertContains(respuesta, "Carbohidratos: <strong>336 g</strong>")


class PesoMedio7DiasTests(PruebaConRegistroAbierto):
    """R7/G-61 — el cálculo usa SIEMPRE la media de los últimos 7 días, nunca la última
    medición suelta ni un dato tecleado a mano."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com")
        self.usuario = Persona.objects.get(usuario__email="alejandro@example.com")
        # El alta ya dejó una medición de 62 kg hoy; la sustituimos por un histórico a medida
        # para controlar exactamente qué entra en la media.
        MedicionPeso.objects.filter(persona=self.usuario).delete()

    def test_la_media_solo_cuenta_los_ultimos_7_dias(self):
        hoy = timezone.localdate()
        MedicionPeso.objects.create(persona=self.usuario, fecha=hoy, peso_kg=60)
        MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=3), peso_kg=62
        )
        # Esta, de hace 10 días, NO debe entrar en la media (fuera de la ventana de 7 días).
        MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=10), peso_kg=100
        )

        media = peso_medio_7_dias(self.usuario)

        self.assertEqual(media, 61)  # (60 + 62) / 2, SIN la de 100 kg

    def test_la_ventana_es_hoy_y_los_6_anteriores_no_7_dias_atras(self):
        """
        Aclaración de contrato de la revisión: "los últimos 7 días" son HOY + 6 anteriores
        (7 fechas de calendario en total), no `hoy - 7 días` en adelante (eso serían 8
        fechas). Este test falla si la ventana se corre un día en cualquier dirección: la
        medición de hace exactamente 6 días DEBE entrar, la de hace exactamente 7 días NO.
        """
        hoy = timezone.localdate()
        MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=6), peso_kg=70
        )
        MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=7), peso_kg=200
        )

        media = peso_medio_7_dias(self.usuario)

        self.assertEqual(media, 70)  # SOLO la de hace 6 días; la de hace 7 queda fuera

    def test_una_sola_medicion_reciente_es_su_propia_media(self):
        MedicionPeso.objects.create(persona=self.usuario, fecha=timezone.localdate(), peso_kg=75)
        self.assertEqual(peso_medio_7_dias(self.usuario), 75)

    def test_apuntar_un_peso_nuevo_cambia_las_calorias_sin_tocar_el_perfil(self):
        """
        C-35 (cambiar-tus-datos.md): apuntar un peso nuevo mueve las calorías SOLAS, sin
        pasar por la pantalla de perfil. Se demuestra creando la medición directamente y
        comprobando que el CÁLCULO ya la usa, sin que nadie haya tocado el Perfil (la unidad
        006 añadió su propia pantalla de "apuntar peso" — con red de HTTP en
        `ApuntarPesoTests`, más abajo — pero esto de aquí sigue probando la pieza de más
        abajo del todo: la base de datos).

        Dos MEDICIONES en DÍAS DISTINTOS (no la misma, sustituida): desde la unidad 006,
        `MedicionPeso` tiene como mucho una fila por (usuario, fecha) — G-130/Q-110 — así que
        "apuntar un peso nuevo" para este test es un DÍA nuevo, no una segunda fila del mismo
        día (eso lo prueba `SustituirMedicionDelMismoDiaTests`).
        """
        with _con_hoy_fijo():
            hoy = timezone.localdate()
            MedicionPeso.objects.create(persona=self.usuario, fecha=hoy, peso_kg=61)
            objetivo_original = self.usuario.perfil.objetivo
            resultado_antes = calcular_objetivo_del_dia(self.usuario)

            MedicionPeso.objects.create(
                persona=self.usuario, fecha=hoy - timedelta(days=1), peso_kg=59
            )
            resultado_despues = calcular_objetivo_del_dia(self.usuario)

        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.objetivo, objetivo_original)  # el perfil no cambió
        self.assertNotEqual(resultado_antes["calorias"], resultado_despues["calorias"])


class FormularioPerfilNoPideElPesoTests(TestCase):
    """R7 — "el peso no se puede editar desde el perfil": ni siquiera está en el formulario
    (no es que se esconda con CSS: no hay campo que enviar)."""

    def test_peso_kg_no_es_un_campo_del_formulario(self):
        self.assertNotIn("peso_kg", FormularioPerfil().fields)


class RecalculoAlMomentoTests(PruebaConRegistroAbierto):
    """R3/Q-40 — cambiar altura, actividad, objetivo o ajuste recalcula al momento, y la
    respuesta de HTMX es SOLO el trozo de la tarjeta (nunca la página entera: si lo fuera,
    HTMX no podría "no recargar nada más")."""

    def setUp(self):
        super().setUp()
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")
        self.usuario = Persona.objects.get(usuario__email="euridice@example.com")

    def _payload_base(self):
        perfil = self.usuario.perfil
        return {
            "altura_cm": perfil.altura_cm,
            "actividad": perfil.actividad,
            "objetivo": perfil.objetivo,
            "ajuste_pct": perfil.ajuste_pct,
            "dieta": perfil.dieta,
            "alergias": perfil.alergias,
            "intolerancias": perfil.intolerancias,
            "no_le_gusta": perfil.no_le_gusta,
        }

    def test_cambiar_la_altura_cambia_las_calorias_sin_recargar(self):
        with _con_hoy_fijo():
            antes = self.client.get("/perfiles/")
            self.assertContains(antes, "1894 kcal")

            payload = self._payload_base()
            payload["altura_cm"] = 180  # más alto → gasta más → más calorías objetivo

            respuesta = self.client.post(
                f"/perfiles/{self.usuario.id}/actualizar/",
                payload,
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(respuesta.status_code, 200)
        # Es un TROZO, no la página entera: nada de <html> ni de la barra de navegación.
        contenido = respuesta.content.decode()
        self.assertNotIn("<!DOCTYPE html>", contenido)
        self.assertNotIn("Crear cuenta", contenido)  # texto que solo sale en la barra de arriba
        # Y el número SÍ cambió de verdad (no es el mismo 1.894 de antes de tocar nada).
        self.assertNotIn("1894 kcal", contenido)

        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.altura_cm, 180)

    def test_sin_cabecera_hx_devuelve_la_pagina_completa(self):
        """Control negativo: si alguien manda el formulario SIN HTMX (JS desactivado, por
        ejemplo), la respuesta sigue siendo una página completa y válida, no un trozo suelto
        sin barra de navegación ni `<html>`."""
        payload = self._payload_base()
        payload["altura_cm"] = 170

        respuesta = self.client.post(f"/perfiles/{self.usuario.id}/actualizar/", payload)

        self.assertContains(respuesta, "<!DOCTYPE html>", status_code=200)


class CambiarObjetivoTests(PruebaConRegistroAbierto):
    """R5/R6/G-60 — el ajuste vuelve SIEMPRE al de fábrica al cambiar de objetivo, y se puede
    sobrescribir a mano en un envío APARTE; la proteína por kilo nunca se toca a mano (no es
    ni siquiera un campo: la fija el objetivo)."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", ajuste_pct="-15")  # a mano
        self.usuario = Persona.objects.get(usuario__email="alejandro@example.com")
        self.assertEqual(self.usuario.perfil.ajuste_pct, -15)  # control: quedó su ajuste manual

    def _payload_base(self):
        perfil = self.usuario.perfil
        return {
            "altura_cm": perfil.altura_cm,
            "actividad": perfil.actividad,
            "objetivo": perfil.objetivo,
            "ajuste_pct": perfil.ajuste_pct,
            "dieta": "",
            "alergias": "",
            "intolerancias": "",
            "no_le_gusta": "",
        }

    def test_cambiar_de_objetivo_resetea_el_ajuste_al_de_fabrica_perdiendo_el_manual(self):
        """R5/C-34: tenía −15 % a mano en 'perder_grasa'; cambia a 'recomposicion_corporal' y
        el ajuste pasa a +10 % (el de fábrica), perdiendo el −15 % sin avisar (a propósito)."""
        payload = self._payload_base()
        payload["objetivo"] = "recomposicion_corporal"
        # Aunque en la MISMA petición se mande también un ajuste distinto, el cambio de
        # objetivo manda y lo ignora (G-60: "vuelve SIEMPRE al de fábrica").
        payload["ajuste_pct"] = "99"

        self.client.post(f"/perfiles/{self.usuario.id}/actualizar/", payload)

        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.objetivo, "recomposicion_corporal")
        self.assertEqual(self.usuario.perfil.ajuste_pct, 10)  # de fábrica, NO 99 ni −15

    def test_sobrescribir_el_ajuste_a_mano_sin_cambiar_de_objetivo_manda_el_suyo(self):
        """R6: en un envío que NO cambia el objetivo, el ajuste tecleado a mano sí se
        respeta y sobrescribe al que hubiera."""
        payload = self._payload_base()
        payload["ajuste_pct"] = "-20"  # objetivo se queda igual (perder_grasa)

        self.client.post(f"/perfiles/{self.usuario.id}/actualizar/", payload)

        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.objetivo, "perder_grasa")
        self.assertEqual(self.usuario.perfil.ajuste_pct, -20)

    def test_la_proteina_por_kg_nunca_es_un_campo_que_se_pueda_tocar(self):
        """R6: "la proteína por kilo no se toca nunca" — ni siquiera existe como campo del
        formulario ni del modelo: la calcula servicios.metabolismo a partir del objetivo."""
        self.assertNotIn("proteina_por_kg", FormularioPerfil().fields)
        self.assertFalse(hasattr(Perfil, "proteina_por_kg"))


class AislamientoDePerfilesTests(PruebaConRegistroAbierto):
    """
    R9/Q-20, "ahora con datos de una persona" (el punto que más importa de la unidad, según
    la especificación): todo el hogar VE el perfil de cualquiera, pero solo su dueña lo
    cambia — ni siquiera llamando al servidor con su id exacto, saltándose la pantalla.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.client.logout()

        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.client.logout()

        # Alejandro la acepta: quedan en el MISMO hogar (necesario para que R9 tenga sentido:
        # "todo el hogar la ve" presupone que están en el mismo hogar).
        self.client.login(username="alejandro@example.com", password="una-clave-de-verdad-2026")
        from hogares.models import SolicitudEntrada

        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice.usuario)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control

    def test_alejandro_ve_los_datos_y_las_calorias_de_euridice(self):
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/")

        self.assertEqual(respuesta.status_code, 200)
        # Unidad 024, R1/G-196: por su nombre, nunca por su correo.
        self.assertContains(respuesta, "Euridice")
        self.assertContains(respuesta, "kcal")  # sus calorías, no un hueco vacío

    def test_alejandro_no_ve_ningun_formulario_en_el_perfil_de_euridice(self):
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/")
        # Que no aparezca "Guardar" (el botón del formulario de edición): no hay manera de
        # cambiarlo, ni siquiera visualmente.
        self.assertNotContains(respuesta, "Guardar")

    def test_alejandro_no_puede_cambiar_el_perfil_de_euridice_llamando_al_servidor(self):
        altura_original = self.euridice.perfil.altura_cm

        respuesta = self.client.post(
            f"/perfiles/{self.euridice.id}/actualizar/",
            {
                "altura_cm": 200,
                "actividad": "activo",
                "objetivo": "ganar_musculo",
                "ajuste_pct": 50,
                "dieta": "",
                "alergias": "",
                "intolerancias": "",
                "no_le_gusta": "",
            },
        )

        self.assertEqual(respuesta.status_code, 404)
        self.euridice.perfil.refresh_from_db()
        self.assertEqual(self.euridice.perfil.altura_cm, altura_original)

    def test_pedir_un_perfil_que_no_existe_da_el_mismo_404_que_uno_ajeno(self):
        """Q-20/Q-11: no se distingue "existe pero no es tuyo" de "no existe en absoluto"."""
        respuesta_inexistente = self.client.post("/perfiles/999999/actualizar/")
        respuesta_ajeno = self.client.post(f"/perfiles/{self.euridice.id}/actualizar/")
        self.assertEqual(respuesta_inexistente.status_code, respuesta_ajeno.status_code)

    def test_un_desconocido_sin_sesion_no_ve_ni_cambia_nada(self):
        self.client.logout()
        respuesta_ver = self.client.get(f"/perfiles/{self.euridice.id}/")
        respuesta_cambiar = self.client.post(f"/perfiles/{self.euridice.id}/actualizar/")
        # @login_required manda a iniciar sesión (302), nunca deja pasar la petición.
        self.assertEqual(respuesta_ver.status_code, 302)
        self.assertEqual(respuesta_cambiar.status_code, 302)


class DatosImposiblesEnElAltaTests(PruebaConRegistroAbierto):
    """R11 — los datos imposibles se rechazan AL ENTRAR (el alta no crea nada), no revientan
    después. Cada test comprueba que NO se creó ninguna cuenta: si los datos físicos no
    bastaran para tumbar el formulario ENTERO, se colaría una cuenta con un perfil roto."""

    def test_altura_cero_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", altura_cm="0")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_altura_negativa_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", altura_cm="-10")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_peso_cero_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", peso_kg="0")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_peso_negativo_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", peso_kg="-5")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_fecha_de_nacimiento_futura_no_crea_ninguna_cuenta(self):
        fecha_futura = (timezone.localdate() + timedelta(days=365)).isoformat()
        self.registrar("alguien@example.com", fecha_nacimiento=fecha_futura)
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_sexo_fuera_de_la_lista_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", sexo="marciano")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_actividad_fuera_de_la_lista_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", actividad="hiperactivo")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_objetivo_fuera_de_la_lista_no_crea_ninguna_cuenta(self):
        self.registrar("alguien@example.com", objetivo="ser_superheroe")
        self.assertFalse(Usuario.objects.filter(email="alguien@example.com").exists())

    def test_el_error_senala_el_campo_concreto_que_esta_mal(self):
        """"Se avisa de cuál está mal": el mensaje de error aparece asociado al campo, no
        como un aviso genérico de "algo falló"."""
        respuesta = self.registrar("alguien@example.com", altura_cm="-10")
        formulario = respuesta.context["form"]
        self.assertIn("altura_cm", formulario.errors)


class DatosImposiblesAlCambiarElPerfilTests(PruebaConRegistroAbierto):
    """R11, la otra mitad: también se rechazan al CAMBIAR el perfil desde "tus datos", no
    solo al crear la cuenta."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com")
        self.usuario = Persona.objects.get(usuario__email="alejandro@example.com")

    def test_poner_la_altura_a_cero_no_cambia_nada(self):
        altura_original = self.usuario.perfil.altura_cm

        self.client.post(
            f"/perfiles/{self.usuario.id}/actualizar/",
            {
                "altura_cm": 0,
                "actividad": "moderado",
                "objetivo": "mantener",
                "ajuste_pct": 0,
                "dieta": "",
                "alergias": "",
                "intolerancias": "",
                "no_le_gusta": "",
            },
        )

        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.altura_cm, altura_original)


# ==============================================================================================
# Unidad 006 — "Apuntar el peso" (R1-R10). Los R* de aquí abajo son los de
# docs/05-trabajo/006-apuntar-el-peso/especificacion.md, que a su vez remiten a
# docs/02-flujos/apuntar-el-peso.md (R-63 a R-66, C-68 a C-72, G-130 a G-132, Q-110 a Q-112).
# ==============================================================================================


class ApuntarPesoTests(PruebaConRegistroAbierto):
    """R1/R3/R-63/R-66/G-131 — apuntar una medición, completa o solo con el peso obligatorio."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("euridice@example.com")
        self.usuario = Persona.objects.get(usuario__email="euridice@example.com")
        # El alta ya dejó una medición (62 kg, hoy); se limpia para partir de un histórico
        # controlado en cada escenario, sin que la del alta interfiera con las fechas exactas
        # que arma cada test.
        MedicionPeso.objects.filter(persona=self.usuario).delete()

    def _apuntar(self, **campos):
        payload = {
            "fecha": timezone.localdate().isoformat(),
            "peso_kg": "60",
            "grasa_pct": "",
            "cintura_cm": "",
            **campos,
        }
        return self.client.post(f"/perfiles/{self.usuario.id}/peso/apuntar/", payload)

    def test_apuntar_solo_el_peso_deja_la_grasa_y_la_cintura_en_blanco_y_no_degrada_nada(self):
        """R1/C-68 — Euridice apunta 61,4 kg sin grasa ni cintura (su báscula no las mide): la
        medición se guarda igual y su objetivo del día se sigue calculando con normalidad."""
        respuesta = self._apuntar(peso_kg="61.4")

        self.assertEqual(respuesta.status_code, 200)
        medicion = MedicionPeso.objects.get(persona=self.usuario)
        self.assertEqual(medicion.peso_kg, Decimal("61.4"))
        self.assertIsNone(medicion.grasa_pct)
        self.assertIsNone(medicion.cintura_cm)
        # "nada queda degradado por que falten esos dos datos" (R1, R-66): el cálculo sigue
        # funcionando, no se queda en blanco ni revienta.
        self.assertIsNotNone(calcular_objetivo_del_dia(self.usuario))

    def test_apuntar_peso_grasa_y_cintura_los_tres_se_guardan_y_se_ven_en_el_historico(self):
        """R3 — apuntando los tres juntos, los tres se guardan y se pueden volver a ver."""
        respuesta = self._apuntar(peso_kg="70.5", grasa_pct="18.2", cintura_cm="82.3")
        self.assertEqual(respuesta.status_code, 200)

        medicion = MedicionPeso.objects.get(persona=self.usuario)
        self.assertEqual(medicion.peso_kg, Decimal("70.5"))
        self.assertEqual(medicion.grasa_pct, Decimal("18.2"))
        self.assertEqual(medicion.cintura_cm, Decimal("82.3"))

        respuesta_historico = self.client.get(f"/perfiles/{self.usuario.id}/peso/")
        # LANGUAGE_CODE="es": la plantilla pinta los decimales con coma, no con punto (mismo
        # formato que ya usa el resto de la app para cualquier número localizado).
        self.assertContains(respuesta_historico, "70,5")
        self.assertContains(respuesta_historico, "18,2")
        self.assertContains(respuesta_historico, "82,3")

    def test_grasa_0_apuntada_se_ve_en_el_historico_no_se_esconde(self):
        """
        H4 de la revisión (2ª ronda) — 0% de grasa es un valor válido (R10: 0-100 inclusive,
        `test_grasa_0_es_valida` en `FormularioMedicionTests` ya lo prueba a nivel de
        formulario). `{% if medicion.grasa_pct %}` en la plantilla trataría `Decimal("0.0")`
        como "falso" y se comería el dato en el histórico, aunque SÍ se guardó — un 0 no es
        lo mismo que "no se apuntó grasa". Este test comprueba la PANTALLA, no el modelo.
        """
        respuesta = self._apuntar(peso_kg="70.0", grasa_pct="0", cintura_cm="")

        respuesta_historico = self.client.get(f"/perfiles/{self.usuario.id}/peso/")
        self.assertContains(respuesta_historico, "0,0% grasa")  # "0,0": Decimal(0.0) en es


class SustituirMedicionDelMismoDiaTests(PruebaConRegistroAbierto):
    """
    R2/C-69/G-130/Q-110 — la nueva pesada del mismo día SUSTITUYE a la anterior, no se
    acumula. R2 exige, además, que sea la BASE DE DATOS quien lo garantice, no solo el
    formulario: el segundo test de esta clase lo demuestra con un `create` directo, sin pasar
    por `apuntar_medicion` ni por ningún formulario.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        self.usuario = Persona.objects.get(usuario__email="alejandro@example.com")
        MedicionPeso.objects.filter(persona=self.usuario).delete()

    def test_apuntar_dos_veces_el_mismo_dia_deja_una_sola_medicion_la_de_la_tarde(self):
        hoy = timezone.localdate().isoformat()
        self.client.post(
            f"/perfiles/{self.usuario.id}/peso/apuntar/",
            {"fecha": hoy, "peso_kg": "93.2", "grasa_pct": "", "cintura_cm": ""},
        )
        self.client.post(
            f"/perfiles/{self.usuario.id}/peso/apuntar/",
            {"fecha": hoy, "peso_kg": "94.1", "grasa_pct": "", "cintura_cm": ""},
        )

        mediciones = MedicionPeso.objects.filter(persona=self.usuario)
        self.assertEqual(mediciones.count(), 1)
        self.assertEqual(mediciones.first().peso_kg, Decimal("94.1"))

    def test_la_restriccion_de_unicidad_vive_en_la_base_de_datos_no_solo_en_el_formulario(self):
        """R2 — un `create` directo (saltándose `apuntar_medicion` y el formulario por
        completo) también tiene que reventar: la garantía es de la base de datos, con su
        `UniqueConstraint`, no una comprobación que solo vive en Python."""
        hoy = timezone.localdate()
        MedicionPeso.objects.create(persona=self.usuario, fecha=hoy, peso_kg=Decimal("93.2"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MedicionPeso.objects.create(
                    persona=self.usuario, fecha=hoy, peso_kg=Decimal("94.1")
                )

        # Y sigue habiendo solo una, la primera (el `create` que revienta no deja nada a medias).
        self.assertEqual(MedicionPeso.objects.filter(persona=self.usuario).count(), 1)


class UnMalDiaDeBasculaNoDescolocaElPlanTests(PruebaConRegistroAbierto):
    """R4/C-70/Q-111 — una medición aislada muy distinta de las demás no mueve las calorías
    del día más de un 3%, porque se calculan con la media de los últimos 7 días, no con la
    pesada suelta de hoy."""

    def test_una_pesada_alta_tras_una_semana_estable_mueve_las_calorias_menos_de_un_3_por_ciento(
        self,
    ):
        with _con_hoy_fijo():
            self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
            usuario = Persona.objects.get(usuario__email="alejandro@example.com")
            MedicionPeso.objects.filter(persona=usuario).delete()

            hoy = timezone.localdate()
            for delta in range(1, 7):  # los 6 días anteriores, toda la semana sobre 93 kg
                MedicionPeso.objects.create(
                    persona=usuario, fecha=hoy - timedelta(days=delta), peso_kg=Decimal("93.0")
                )
            resultado_antes = calcular_objetivo_del_dia(usuario)  # media de 93 kg (6 días)

            # Hoy, tras una comida salada, marca 95 kg.
            self.client.post(
                f"/perfiles/{usuario.id}/peso/apuntar/",
                {"fecha": hoy.isoformat(), "peso_kg": "95", "grasa_pct": "", "cintura_cm": ""},
            )
            resultado_despues = calcular_objetivo_del_dia(usuario)

        cambio_pct = (
            abs(resultado_despues["calorias"] - resultado_antes["calorias"])
            / resultado_antes["calorias"]
            * 100
        )
        self.assertLessEqual(cambio_pct, 3)
        # Y de verdad se movió (para que la aserción de arriba no pase "por casualidad" con
        # dos números iguales): la media SÍ se desplazó un poco con el dato de hoy.
        self.assertNotEqual(resultado_antes["calorias"], resultado_despues["calorias"])

        # H3 de la revisión (2ª ronda): el techo del 3% de Q-111 por sí solo NO distingue
        # "se calculó con la MEDIA de 7 días" (R4/C-70, lo que el criterio exige) de "se
        # calculó con la ÚLTIMA medición suelta" (justo lo que C-70/G-132 PROHÍBEN) — con
        # estos números concretos, la media da un cambio del 0,17% y la última suelta del
        # 1,06%: ambos caben bajo el 3%, así que un `assertLessEqual` a secas pasaría igual
        # con la implementación prohibida. Clavar el PESO con el que se recalculó (93,3 kg,
        # la media de (93×6 + 95)/7, NO los 95 kg sueltos de hoy) es lo que mata ese mutante.
        self.assertEqual(resultado_despues["peso_kg"], 93.3)


class UnaSolaMedicionEsLaQueSeUsaTests(PruebaConRegistroAbierto):
    """R5/C-71 — recién creada la cuenta con 62 kg, si solo se ha apuntado una pesada de
    verdad (61,4 kg), el cálculo usa esos 61,4 kg, no los 62 del alta."""

    def test_con_una_sola_medicion_de_verdad_el_calculo_usa_esa(self):
        self.registrar_y_verificar("euridice@example.com")  # 62 kg de fábrica, hoy
        usuario = Persona.objects.get(usuario__email="euridice@example.com")

        # Su primera pesada de verdad, el mismo día que el alta: sustituye a la de 62 kg
        # ("solo se ha pesado una vez", el criterio).
        self.client.post(
            f"/perfiles/{usuario.id}/peso/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "peso_kg": "61.4",
                "grasa_pct": "",
                "cintura_cm": "",
            },
        )

        self.assertEqual(MedicionPeso.objects.filter(persona=usuario).count(), 1)
        resultado = calcular_objetivo_del_dia(usuario)
        self.assertEqual(resultado["peso_kg"], 61.4)


class DosNumerosDistintosTests(PruebaConRegistroAbierto):
    """
    R6/C-72/Q-112 — lo que marcó la báscula y el peso con el que se calcula son dos números
    DISTINTOS, en sitios distintos y rotulados aparte. No vale que el mismo número sirva para
    los dos sitios: este test monta un escenario donde de verdad difieren (92,8 kg de ayer
    frente a 93,4 kg de media, los mismos números del criterio) y comprueba que cada uno
    aparece SOLO en su marcador, no en los dos.
    """

    def test_la_pantalla_distingue_la_ultima_pesada_de_la_media_con_la_que_se_calcula(self):
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre")
        usuario = Persona.objects.get(usuario__email="alejandro@example.com")
        MedicionPeso.objects.filter(persona=usuario).delete()

        hoy = timezone.localdate()
        # Ayer 92,8 kg, hace dos días 94,0 kg → media de la semana: 93,4 kg (los números del
        # criterio C-72, tal cual).
        MedicionPeso.objects.create(
            persona=usuario, fecha=hoy - timedelta(days=1), peso_kg=Decimal("92.8")
        )
        MedicionPeso.objects.create(
            persona=usuario, fecha=hoy - timedelta(days=2), peso_kg=Decimal("94.0")
        )

        respuesta = self.client.get(f"/perfiles/{usuario.id}/peso/")
        contenido = respuesta.content.decode()

        bloque_bascula = re.search(r'id="peso-bascula".*?</p>', contenido, re.S)
        bloque_calculo = re.search(r'id="peso-calculo".*?</p>', contenido, re.S)
        self.assertIsNotNone(bloque_bascula, "falta el marcador #peso-bascula en la pantalla")
        self.assertIsNotNone(bloque_calculo, "falta el marcador #peso-calculo en la pantalla")

        # LANGUAGE_CODE="es": la plantilla pinta los decimales con coma, no con punto.
        self.assertIn("92,8", bloque_bascula.group())
        self.assertNotIn("93,4", bloque_bascula.group())
        self.assertIn("93,4", bloque_calculo.group())
        self.assertNotIn("92,8", bloque_calculo.group())


class AislamientoDePesoTests(PruebaConRegistroAbierto):
    """
    R7/§8 "Qué NO debe poder jamás" — nadie apunta ni borra el peso de otra persona con
    cuenta propia, tampoco llamando al servidor con el id exacto. Siempre 404, nunca 403
    (mismo principio que `perfiles/acceso.py` ya prueba para el perfil, unidad 004).

    Unidad 010 (R7/R8 de ver-tu-progreso.md, y R-23 de darle-cuenta-propia-a-los-de-casa.md):
    la LECTURA de esta pantalla dejó de estar aislada — el resto del hogar SÍ puede verla
    ahora (`test_alejandro_puede_ver_la_pantalla_de_peso_de_euridice`, más abajo, reemplaza al
    test que antes probaba lo contrario). Apuntar y borrar siguen dando 404 exactamente igual
    que antes: esta clase es la prueba de que la 010 abrió la lectura sin tocar la escritura.
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

        # Alejandro la acepta: quedan en el MISMO hogar (R7 presupone que comparten hogar; si
        # ni siquiera eso, con más razón sigue sin poder tocar su peso).
        self.client.login(username="alejandro@example.com", password="una-clave-de-verdad-2026")
        from hogares.models import SolicitudEntrada

        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice.usuario)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control
        self.client.logout()

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): la tercera puerta que faltaba,
        # H1 de la 2ª ronda de revisión — `perfil_visible_o_404` pasó a `perfil_propio_o_404`
        # más "mismo hogar", y esta clase solo montaba DOS personas, las dos del MISMO hogar
        # (mismo patrón que `progreso.tests.BaseProgresoTests`, `progreso/tests.py:74-77`).
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password="una-clave-de-verdad-2026")

    def test_alejandro_puede_ver_la_pantalla_de_peso_de_euridice(self):
        """
        Unidad 010, R7 — antes de esta unidad esto daba 404 (el test se llamaba
        "...no_puede_ver..."); R-23 nombra literalmente "el peso" entre lo que el hogar debe
        poder VER de otra persona, así que ahora se renderiza de verdad (no solo un 200:
        `render()` con una plantilla que ya no existiera también daría 200 si algo fuera
        HttpResponse a pelo — se comprueba que el peso de EURIDICE sale en el HTML).
        """
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/peso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "62,0 kg")  # el peso de alta de Euridice (unidad 004)

        # R8, la otra mitad de la pareja: ver no es apuntar. Sin formulario ni botón de
        # borrar en el HTML de la pantalla ajena (no basta con que la RUTA siga dando 404 —
        # comprobado en los tests de abajo — si esta MISMA pantalla ofreciera el atajo).
        self.assertNotContains(respuesta, "Apuntar pesada")
        self.assertNotContains(respuesta, ">Borrar<")

    def test_alejandro_ve_el_titulo_propio_y_ajeno_distintos(self):
        """R7, matiz de UI: la pantalla deja claro DE QUIÉN es el peso que se mira, para que
        no parezca la suya propia por error (dato delicado, G-1). El título de la barra de
        navegación dice SIEMPRE "Tu peso" (enlace al propio, `templates/base.html`) — por eso
        aquí se aísla el `<h1>` de la pantalla en sí, no un `assertContains` a pelo que
        colaría igual con o sin el arreglo."""
        respuesta_propia = self.client.get(f"/perfiles/{self.alejandro.id}/peso/")
        respuesta_ajena = self.client.get(f"/perfiles/{self.euridice.id}/peso/")

        h1_propio = re.search(r"<h1[^>]*>(.*?)</h1>", respuesta_propia.content.decode(), re.S)
        h1_ajeno = re.search(r"<h1[^>]*>(.*?)</h1>", respuesta_ajena.content.decode(), re.S)
        self.assertIsNotNone(h1_propio)
        self.assertIsNotNone(h1_ajeno)
        self.assertIn("Tu peso", h1_propio.group(1))
        # Unidad 024, R1/G-196: por su nombre, nunca por su correo.
        self.assertIn("Peso de Euridice", h1_ajeno.group(1))

    def test_alejandro_no_puede_apuntar_peso_a_euridice_llamando_al_servidor(self):
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

    def test_alejandro_no_puede_borrar_una_medicion_de_euridice_llamando_al_servidor(self):
        medicion = MedicionPeso.objects.filter(persona=self.euridice).first()  # la del alta
        self.assertIsNotNone(medicion)  # control

        respuesta = self.client.post(f"/perfiles/{self.euridice.id}/peso/{medicion.id}/borrar/")

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(MedicionPeso.objects.filter(id=medicion.id).exists())

    def test_el_404_es_igual_para_una_medicion_que_no_existe_que_para_una_ajena(self):
        respuesta_inexistente = self.client.post(
            f"/perfiles/{self.euridice.id}/peso/999999/borrar/"
        )
        medicion_ajena = MedicionPeso.objects.filter(persona=self.euridice).first()
        respuesta_ajena = self.client.post(
            f"/perfiles/{self.euridice.id}/peso/{medicion_ajena.id}/borrar/"
        )
        self.assertEqual(respuesta_inexistente.status_code, respuesta_ajena.status_code)
        self.assertEqual(respuesta_inexistente.status_code, 404)

    def test_un_desconocido_sin_sesion_no_ve_ni_apunta_ni_borra_nada(self):
        self.client.logout()
        respuesta_ver = self.client.get(f"/perfiles/{self.euridice.id}/peso/")
        respuesta_apuntar = self.client.post(f"/perfiles/{self.euridice.id}/peso/apuntar/")
        respuesta_borrar = self.client.post(f"/perfiles/{self.euridice.id}/peso/1/borrar/")
        # @login_required manda a iniciar sesión (302), nunca deja pasar la petición.
        self.assertEqual(respuesta_ver.status_code, 302)
        self.assertEqual(respuesta_apuntar.status_code, 302)
        self.assertEqual(respuesta_borrar.status_code, 302)

    def test_alejandro_no_puede_borrar_la_medicion_de_euridice_pasando_su_propio_usuario_id(self):
        """
        H2 de la revisión (2ª ronda) — el ataque que R7 nombra LITERALMENTE ("tampoco
        llamando al servidor con el id exacto") no es probarlo con el `usuario_id` de
        Euridice (eso muere en la PRIMERA puerta, `perfil_propio_o_404`, y ni siquiera llega
        a mirar `medicion_id`): es Alejandro llamando con SU PROPIO `usuario_id` —de verdad
        el suyo, pasa la primera puerta sin problema— pero colando el `medicion_id` de
        Euridice en la URL. Sin el segundo cinturón de `borrar_peso`
        (`get_object_or_404(MedicionPeso, id=medicion_id, persona=perfil.usuario)`, que exige
        que la medición sea TAMBIÉN suya) esto borraría una medición ajena. Se comprobó a
        mano que si ese filtro se cambia por `get_object_or_404(MedicionPeso, id=medicion_id)`
        a secas, este test se pone en rojo (y la suite entera seguía en verde sin él antes de
        este arreglo — el hueco que delató la revisión).
        """
        medicion_de_euridice = MedicionPeso.objects.filter(persona=self.euridice).first()
        self.assertIsNotNone(medicion_de_euridice)  # control

        respuesta = self.client.post(
            f"/perfiles/{self.alejandro.id}/peso/{medicion_de_euridice.id}/borrar/"
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(MedicionPeso.objects.filter(id=medicion_de_euridice.id).exists())

    def test_carlos_no_ve_la_pantalla_de_peso_de_euridice_es_de_otro_hogar(self):
        """
        H1 de la 2ª ronda de revisión — la rama que nació al abrir la LECTURA de esta
        pantalla al hogar (unidad 010) y que ningún test tocaba todavía: "de OTRO hogar" ya
        no es lo mismo que "no soy yo". `perfil_visible_o_404` (`perfiles/acceso.py:47`) debe
        seguir dando 404, nunca 403 — el mismo dato delicado (G-1, el peso) abierto de par en
        par si este filtro por hogar fallara. Se comprobó a mano (ver hallazgos.md, Ronda 2)
        que si se le quita el filtro por hogar, este test es el que se pone en rojo.
        """
        self.client.logout()
        self.client.login(username="carlos@example.com", password="una-clave-de-verdad-2026")

        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/peso/")

        self.assertEqual(respuesta.status_code, 404)
        self.assertNotEqual(respuesta.status_code, 403)


class BorrarMedicionTests(PruebaConRegistroAbierto):
    """R8/§6 Estados — borrar una medición equivocada la quita del histórico y el objetivo
    del día se recalcula al momento con las que queden."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("euridice@example.com")
        self.usuario = Persona.objects.get(usuario__email="euridice@example.com")
        MedicionPeso.objects.filter(persona=self.usuario).delete()
        hoy = timezone.localdate()
        self.buena = MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy, peso_kg=Decimal("62.0")
        )
        self.equivocada = MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=1), peso_kg=Decimal("99.9")
        )

    def test_borrar_una_medicion_la_quita_del_historico(self):
        respuesta = self.client.post(
            f"/perfiles/{self.usuario.id}/peso/{self.equivocada.id}/borrar/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MedicionPeso.objects.filter(id=self.equivocada.id).exists())
        self.assertTrue(MedicionPeso.objects.filter(id=self.buena.id).exists())

    def test_borrar_una_medicion_recalcula_el_objetivo_al_momento(self):
        resultado_antes = calcular_objetivo_del_dia(self.usuario)  # media con la de 99,9 kg

        self.client.post(f"/perfiles/{self.usuario.id}/peso/{self.equivocada.id}/borrar/")

        resultado_despues = calcular_objetivo_del_dia(self.usuario)
        self.assertNotEqual(resultado_antes["calorias"], resultado_despues["calorias"])


class SinNingunaMedicionTests(PruebaConRegistroAbierto):
    """
    R9, caso límite (§6 Estados) — borrar la ÚLTIMA medición que quedaba no revienta ni
    inventa un número: la app se queda "sin ninguna medición" y la pantalla lo dice con
    claridad, invitando a apuntar una. Prohibido resolverlo devolviendo el peso a `Perfil`
    (nota de alcance de la especificación): este test comprueba que sigue sin existir ese
    campo (ver también `FormularioPerfilNoPideElPesoTests` de la unidad 004, más arriba).
    """

    def test_borrar_la_ultima_medicion_deja_sin_ninguna_y_no_revienta(self):
        self.registrar_y_verificar("euridice@example.com")
        usuario = Persona.objects.get(usuario__email="euridice@example.com")
        medicion = MedicionPeso.objects.get(persona=usuario)  # la única, la del alta

        respuesta = self.client.post(f"/perfiles/{usuario.id}/peso/{medicion.id}/borrar/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MedicionPeso.objects.filter(persona=usuario).exists())
        self.assertIsNone(calcular_objetivo_del_dia(usuario))  # no revienta, no inventa nada
        self.assertIsNone(ultima_medicion(usuario))
        self.assertContains(respuesta, "ninguna medici")  # el mensaje del estado, en pantalla

    def test_la_pantalla_de_peso_sin_mediciones_no_revienta_al_entrar(self):
        self.registrar_y_verificar("euridice@example.com")
        usuario = Persona.objects.get(usuario__email="euridice@example.com")
        MedicionPeso.objects.get(persona=usuario).delete()

        respuesta = self.client.get(f"/perfiles/{usuario.id}/peso/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ninguna medici")

    def test_el_peso_no_vuelve_a_ser_un_campo_de_perfil_para_resolver_este_estado(self):
        """Nota de alcance de la especificación: prohibido por escrito. `Perfil` sigue sin
        ningún campo de peso, esté como esté el histórico de mediciones."""
        self.assertNotIn("peso_kg", FormularioPerfil().fields)
        self.assertFalse(hasattr(Perfil, "peso_kg"))


class DatosImposiblesAlApuntarPesoTests(PruebaConRegistroAbierto):
    """R10, caso límite (R-63 del plano) — un peso de cero o negativo, una grasa fuera de
    0-100 y una fecha futura se rechazan AL ENTRAR, con su mensaje, sin llegar a la base de
    datos."""

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("euridice@example.com")
        self.usuario = Persona.objects.get(usuario__email="euridice@example.com")
        MedicionPeso.objects.filter(persona=self.usuario).delete()

    def _apuntar(self, **campos):
        payload = {
            "fecha": timezone.localdate().isoformat(),
            "peso_kg": "60",
            "grasa_pct": "",
            "cintura_cm": "",
            **campos,
        }
        return self.client.post(f"/perfiles/{self.usuario.id}/peso/apuntar/", payload)

    def test_peso_cero_se_rechaza_sin_llegar_a_la_base_de_datos(self):
        respuesta = self._apuntar(peso_kg="0")
        self.assertFalse(MedicionPeso.objects.filter(persona=self.usuario).exists())
        self.assertIn("peso_kg", respuesta.context["form"].errors)

    def test_peso_negativo_se_rechaza_sin_llegar_a_la_base_de_datos(self):
        respuesta = self._apuntar(peso_kg="-5")
        self.assertFalse(MedicionPeso.objects.filter(persona=self.usuario).exists())
        self.assertIn("peso_kg", respuesta.context["form"].errors)

    def test_grasa_por_encima_de_cien_se_rechaza(self):
        respuesta = self._apuntar(grasa_pct="101")
        self.assertFalse(MedicionPeso.objects.filter(persona=self.usuario).exists())
        self.assertIn("grasa_pct", respuesta.context["form"].errors)

    def test_grasa_negativa_se_rechaza(self):
        respuesta = self._apuntar(grasa_pct="-1")
        self.assertFalse(MedicionPeso.objects.filter(persona=self.usuario).exists())
        self.assertIn("grasa_pct", respuesta.context["form"].errors)

    def test_fecha_futura_se_rechaza(self):
        fecha_futura = (timezone.localdate() + timedelta(days=1)).isoformat()
        respuesta = self._apuntar(fecha=fecha_futura)
        self.assertFalse(MedicionPeso.objects.filter(persona=self.usuario).exists())
        self.assertIn("fecha", respuesta.context["form"].errors)

    def test_el_error_senala_el_campo_concreto_que_esta_mal(self):
        """"Se avisa de cuál está mal": consistente con R11 de la unidad 004
        (`test_el_error_senala_el_campo_concreto_que_esta_mal` de más arriba)."""
        respuesta = self._apuntar(peso_kg="-5")
        self.assertIn("peso_kg", respuesta.context["form"].errors)
        self.assertNotIn("grasa_pct", respuesta.context["form"].errors)


class LogicaDeMedicionesTests(TestCase):
    """
    Unit tests directos de `perfiles/logica.py` (sin pasar por HTTP), para las piezas nuevas
    de la unidad 006 que no tienen ya una red de HTTP arriba: `apuntar_medicion` hace upsert
    de verdad (no dos `create`), y `ultima_medicion` es un número DISTINTO del que calcula
    `peso_medio_7_dias` (la base misma de R6).
    """

    def setUp(self):
        cuenta = Usuario.objects.create_user(
            email="directo@example.com", password="una-clave-de-verdad-2026"
        )
        self.usuario = Persona.objects.get(usuario=cuenta)

    def test_apuntar_medicion_dos_veces_el_mismo_dia_actualiza_en_vez_de_duplicar(self):
        hoy = timezone.localdate()
        apuntar_medicion(self.usuario, {"fecha": hoy, "peso_kg": Decimal("80.0")})
        apuntar_medicion(self.usuario, {"fecha": hoy, "peso_kg": Decimal("81.5")})

        mediciones = MedicionPeso.objects.filter(persona=self.usuario)
        self.assertEqual(mediciones.count(), 1)
        self.assertEqual(mediciones.first().peso_kg, Decimal("81.5"))

    def test_apuntar_medicion_con_grasa_y_cintura_las_guarda(self):
        medicion = apuntar_medicion(
            self.usuario,
            {
                "fecha": timezone.localdate(),
                "peso_kg": Decimal("80.0"),
                "grasa_pct": Decimal("20.5"),
                "cintura_cm": Decimal("90.0"),
            },
        )
        self.assertEqual(medicion.grasa_pct, Decimal("20.5"))
        self.assertEqual(medicion.cintura_cm, Decimal("90.0"))

    def test_ultima_medicion_es_la_mas_reciente_por_fecha_no_la_de_mayor_peso(self):
        hoy = timezone.localdate()
        MedicionPeso.objects.create(persona=self.usuario, fecha=hoy - timedelta(days=5), peso_kg=Decimal("99.0"))
        reciente = MedicionPeso.objects.create(persona=self.usuario, fecha=hoy, peso_kg=Decimal("80.0"))

        self.assertEqual(ultima_medicion(self.usuario), reciente)

    def test_ultima_medicion_sin_ninguna_es_none(self):
        self.assertIsNone(ultima_medicion(self.usuario))

    def test_borrar_medicion_la_elimina_de_verdad(self):
        medicion = MedicionPeso.objects.create(
            persona=self.usuario, fecha=timezone.localdate(), peso_kg=Decimal("80.0")
        )
        borrar_medicion(medicion)
        self.assertFalse(MedicionPeso.objects.filter(id=medicion.id).exists())

    def test_ultima_medicion_y_peso_medio_7_dias_son_numeros_distintos_cuando_difieren(self):
        """La base de R6: si la última pesada y la media de la semana difieren, las dos
        funciones tienen que devolver valores DISTINTOS entre sí (nunca el mismo número por
        casualidad de la implementación)."""
        hoy = timezone.localdate()
        MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=1), peso_kg=Decimal("92.8")
        )
        MedicionPeso.objects.create(
            persona=self.usuario, fecha=hoy - timedelta(days=2), peso_kg=Decimal("94.0")
        )

        self.assertEqual(ultima_medicion(self.usuario).peso_kg, Decimal("92.8"))
        self.assertEqual(peso_medio_7_dias(self.usuario), 93.4)
        self.assertNotEqual(ultima_medicion(self.usuario).peso_kg, peso_medio_7_dias(self.usuario))


class RespuestaHTMXDelHistoricoTests(PruebaConRegistroAbierto):
    """
    Caso límite del "Cómo" de la especificación (punto 5: "HTMX para apuntar sin recargar,
    como ya hace la 005"): con la cabecera `HX-Request`, la respuesta es SOLO el trozo del
    histórico (nunca la página entera, para que HTMX pueda "no recargar nada más"); sin ella,
    sigue siendo una página completa y válida — mismo control negativo que ya tiene
    `RecalculoAlMomentoTests.test_sin_cabecera_hx_devuelve_la_pagina_completa` para el perfil.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("euridice@example.com")
        self.usuario = Persona.objects.get(usuario__email="euridice@example.com")

    def _payload(self):
        return {
            "fecha": timezone.localdate().isoformat(),
            "peso_kg": "61.4",
            "grasa_pct": "",
            "cintura_cm": "",
        }

    def test_con_htmx_la_respuesta_es_solo_el_trozo_del_historico(self):
        respuesta = self.client.post(
            f"/perfiles/{self.usuario.id}/peso/apuntar/",
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertNotIn("<!DOCTYPE html>", contenido)
        self.assertNotIn("Crear cuenta", contenido)  # texto que solo sale en la barra de arriba
        self.assertIn('id="historico-de-peso"', contenido)

    def test_sin_htmx_la_respuesta_es_la_pagina_completa(self):
        respuesta = self.client.post(f"/perfiles/{self.usuario.id}/peso/apuntar/", self._payload())
        self.assertContains(respuesta, "<!DOCTYPE html>", status_code=200)

    def test_borrar_con_htmx_tambien_devuelve_solo_el_trozo_del_historico(self):
        medicion = MedicionPeso.objects.get(persona=self.usuario)

        respuesta = self.client.post(
            f"/perfiles/{self.usuario.id}/peso/{medicion.id}/borrar/",
            HTTP_HX_REQUEST="true",
        )

        contenido = respuesta.content.decode()
        self.assertNotIn("<!DOCTYPE html>", contenido)
        self.assertIn('id="historico-de-peso"', contenido)

    def test_el_enlace_de_conveniencia_peso_mio_resuelve_al_propio_sin_pasar_el_id(self):
        """`perfiles:peso_mio` (usado desde la barra de navegación, `templates/base.html`) —
        mismo patrón que `perfiles:ver_mio` de la unidad 004."""
        respuesta = self.client.get("/perfiles/peso/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Tu peso")


class FormularioMedicionTests(TestCase):
    """R10/R11 — validación de `FormularioMedicion` a nivel de formulario, para que el
    mensaje salga ANTES de tocar la base de datos y señalando el campo exacto (mismo patrón
    que `clean_altura_cm` de `FormularioPerfil`, unidad 004)."""

    def _datos_base(self, **campos):
        return {
            "fecha": timezone.localdate().isoformat(),
            "peso_kg": "70",
            "grasa_pct": "",
            "cintura_cm": "",
            **campos,
        }

    def test_formulario_valido_con_solo_el_peso(self):
        form = FormularioMedicion(self._datos_base())
        self.assertTrue(form.is_valid(), form.errors)

    def test_peso_cero_no_es_valido(self):
        form = FormularioMedicion(self._datos_base(peso_kg="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("peso_kg", form.errors)

    def test_grasa_100_es_valida_grasa_101_no(self):
        self.assertTrue(FormularioMedicion(self._datos_base(grasa_pct="100")).is_valid())
        self.assertFalse(FormularioMedicion(self._datos_base(grasa_pct="101")).is_valid())

    def test_grasa_0_es_valida(self):
        self.assertTrue(FormularioMedicion(self._datos_base(grasa_pct="0")).is_valid())

    def test_fecha_de_hoy_es_valida_fecha_futura_no(self):
        self.assertTrue(FormularioMedicion(self._datos_base()).is_valid())
        fecha_futura = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertFalse(FormularioMedicion(self._datos_base(fecha=fecha_futura)).is_valid())

    def test_el_campo_fecha_sale_relleno_con_hoy_en_formato_que_el_input_date_entiende(self):
        """
        H1 de la revisión (2ª ronda): un formulario recién abierto (sin datos, `is_bound`
        `False`) tiene que traer "hoy" YA puesto en el campo `fecha` — el gesto tiene que ser
        corto (§8, "descalzo y con prisa"), sin que la persona tenga que teclear la fecha cada
        vez. Con `LANGUAGE_CODE="es"` Django localiza los `DateField` por defecto y pinta
        `03/08/2026`; un `<input type="date">` SOLO entiende `yyyy-mm-dd` en su `value` y
        descarta cualquier otra cosa, dejando el campo VACÍO en el navegador aunque Python
        tenga el valor correcto por dentro.

        Trampa real encontrada escribiendo ESTE mismo test: `MedicionPeso.fecha` tiene un
        `default` CALLABLE (`timezone.localdate`), así que Django ya renderiza por su cuenta
        un segundo `<input type="hidden" name="initial-fecha" value="2026-08-03">` (su propio
        mecanismo de "initial oculto" para defaults callable, nada que ver con nuestro
        `__init__`) que SIEMPRE lleva el valor en ISO — un primer intento de este test con
        `assertIn('value="...."', html)` a secas daba positivo por ESE campo oculto incluso
        con el bug del `<input type="date">` visible sin arreglar. Por eso aquí se aísla con
        una regexp el input `id="id_fecha"` en concreto (el visible, el que de verdad rellena
        el navegador), no cualquier `value="yyyy-mm-dd"` suelto en el HTML.
        """
        html = str(FormularioMedicion()["fecha"])
        input_visible = re.search(r'<input type="date"[^>]*id="id_fecha"[^>]*>', html)
        self.assertIsNotNone(input_visible, f"no se encontró el input visible en: {html!r}")

        hoy_iso = timezone.localdate().isoformat()  # yyyy-mm-dd, lo único que entiende el input
        self.assertIn(f'value="{hoy_iso}"', input_visible.group())


class LaPantallaDePesoProponeHoyDeFabricaTests(PruebaConRegistroAbierto):
    """H1 de la revisión (2ª ronda), la misma comprobación pero de punta a punta por HTTP:
    la pantalla real que ve la persona (no solo el formulario en aislamiento) trae el campo
    "Día" ya relleno con hoy, en el formato que el navegador necesita."""

    def test_la_pagina_de_peso_trae_el_campo_dia_ya_relleno_con_hoy(self):
        self.registrar_y_verificar("euridice@example.com")
        usuario = Persona.objects.get(usuario__email="euridice@example.com")

        respuesta = self.client.get(f"/perfiles/{usuario.id}/peso/")
        contenido = respuesta.content.decode()

        # Mismo cuidado que en FormularioMedicionTests: aislar el input VISIBLE (`id_fecha`),
        # no el `initial-fecha` oculto que Django añade solo porque el modelo tiene un
        # `default` callable, y que siempre lleva la fecha en ISO pase lo que pase con el
        # widget visible.
        input_visible = re.search(r'<input type="date"[^>]*id="id_fecha"[^>]*>', contenido)
        self.assertIsNotNone(input_visible, "no se encontró el input de fecha visible")

        hoy_iso = timezone.localdate().isoformat()
        self.assertIn(f'value="{hoy_iso}"', input_visible.group())


class R7_ElObjetivoSubeConLosEntrenosDeHoyTests(PruebaConRegistroAbierto):
    """
    R7 (unidad 011, apuntar-un-entreno.md) — con entrenos apuntados HOY, el objetivo del día
    sube esas calorías y los macros escalan en la misma proporción (R-2 de
    generar-el-plan.md). Episodio real que fija el número exacto: C-2 de generar-el-plan.md
    (Euridice, base 1.894 kcal / 136-59-205 g, entrena 355 kcal más -> objetivo 2.249 kcal /
    162-70-243 g) — el MISMO perfil que ya prueba R1 de la unidad 004 (`DATOS_FISICOS_POR_DEFECTO`
    son los suyos), para no tener que recalcular la base a mano.
    """

    def test_con_355_kcal_de_entreno_el_objetivo_sube_a_2249_y_los_macros_escalan(self):
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")  # 62 kg, perder_grasa: base 1894
            usuario = Persona.objects.get(usuario__email="euridice@example.com")

            Entreno.objects.create(
                persona=usuario,
                fecha=timezone.localdate(),
                deporte="correr",
                intensidad="media",
                minutos=35,
                calorias=355,
                calorias_manuales=True,
            )
            resultado = calcular_objetivo_del_dia(usuario)

        self.assertEqual(resultado["calorias"], 2249)
        self.assertEqual(resultado["proteina_g"], 162)
        self.assertEqual(resultado["grasa_g"], 70)
        self.assertEqual(resultado["carbos_g"], 243)
        self.assertEqual(resultado["entreno_kcal"], 355)

    def test_dos_entrenos_del_mismo_dia_se_suman_los_dos(self):
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")
            usuario = Persona.objects.get(usuario__email="euridice@example.com")
            Entreno.objects.create(
                persona=usuario,
                fecha=timezone.localdate(),
                deporte="correr",
                intensidad="media",
                minutos=35,
                calorias=200,
                calorias_manuales=True,
            )
            Entreno.objects.create(
                persona=usuario,
                fecha=timezone.localdate(),
                deporte="fuerza",
                intensidad="suave",
                minutos=20,
                calorias=100,
                calorias_manuales=True,
            )
            resultado = calcular_objetivo_del_dia(usuario)
        self.assertEqual(resultado["entreno_kcal"], 300)
        self.assertEqual(resultado["calorias"], 1894 + 300)


class R8_SinEntrenosNiUnaKcalSeMueveTests(PruebaConRegistroAbierto):
    """
    R8 (unidad 011) — la red de seguridad de las siete unidades anteriores: con CERO entrenos
    ese día, el objetivo es EXACTAMENTE el de antes de esta unidad, sin cambiar ni una kcal.
    Mismos datos y mismo número que R1_EuridicePorHTTPTests (unidad 004): si este test
    cambiara de número, alguna promesa anterior se ha roto — "PARA y escala" (aviso del padre).
    """

    def test_sin_ningun_entreno_el_objetivo_es_el_de_siempre(self):
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")
            usuario = Persona.objects.get(usuario__email="euridice@example.com")
            self.assertFalse(Entreno.objects.filter(persona=usuario).exists())
            resultado = calcular_objetivo_del_dia(usuario)

        self.assertEqual(resultado["calorias"], 1894)
        self.assertEqual(resultado["proteina_g"], 136)
        self.assertEqual(resultado["grasa_g"], 59)
        self.assertEqual(resultado["carbos_g"], 205)
        self.assertEqual(resultado["entreno_kcal"], 0)

    def test_un_entreno_de_OTRO_dia_no_cuenta_para_hoy(self):
        """Mutación obligatoria nº4 ("sumar también los entrenos de OTROS días", ver
        hallazgos.md): tiene que dejar esto en rojo — un entreno de ayer no puede subir el
        objetivo de HOY."""
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")
            usuario = Persona.objects.get(usuario__email="euridice@example.com")
            Entreno.objects.create(
                persona=usuario,
                fecha=timezone.localdate() - timedelta(days=1),
                deporte="correr",
                intensidad="media",
                minutos=35,
                calorias=355,
                calorias_manuales=True,
            )
            resultado = calcular_objetivo_del_dia(usuario)

        self.assertEqual(resultado["calorias"], 1894)
        self.assertEqual(resultado["entreno_kcal"], 0)


class CalcularObjetivoDelDiaAceptaFechaTests(PruebaConRegistroAbierto):
    """
    R6/C-39 (unidad 011) — "para corregir el histórico, el cálculo tiene que aceptar una
    fecha" (punto 4 del "Cómo" de la especificación): `calcular_objetivo_del_dia` gana un
    parámetro `fecha` opcional, con `hoy` por defecto, SIN cambiar a ninguno de sus llamadores
    actuales (perfiles/views.py, planes/logica.py — ninguno de los dos pasa `fecha`).
    """

    def test_con_fecha_explicita_suma_los_entrenos_de_ESE_dia_no_los_de_hoy(self):
        with _con_hoy_fijo():
            self.registrar_y_verificar("alejandro@example.com", sexo="hombre", peso_kg="93")
            usuario = Persona.objects.get(usuario__email="alejandro@example.com")
            ayer = timezone.localdate() - timedelta(days=1)
            Entreno.objects.create(
                persona=usuario,
                fecha=ayer,
                deporte="hyrox",
                intensidad="fuerte",
                minutos=60,
                calorias=1302,
                calorias_manuales=True,
            )

            resultado_de_hoy = calcular_objetivo_del_dia(usuario)
            resultado_de_ayer = calcular_objetivo_del_dia(usuario, fecha=ayer)

        self.assertEqual(resultado_de_hoy["entreno_kcal"], 0)
        self.assertEqual(resultado_de_ayer["entreno_kcal"], 1302)
        self.assertGreater(resultado_de_ayer["calorias"], resultado_de_hoy["calorias"])

    def test_sin_pasar_fecha_sigue_siendo_hoy_por_defecto(self):
        """Los llamadores existentes siguen sin pasar `fecha`: el comportamiento por defecto
        no puede cambiar bajo sus pies."""
        with _con_hoy_fijo():
            self.registrar_y_verificar("euridice@example.com")
            usuario = Persona.objects.get(usuario__email="euridice@example.com")
            Entreno.objects.create(
                persona=usuario,
                fecha=timezone.localdate(),
                deporte="correr",
                intensidad="media",
                minutos=35,
                calorias=355,
                calorias_manuales=True,
            )
            con_fecha_explicita = calcular_objetivo_del_dia(usuario, fecha=timezone.localdate())
            sin_pasar_fecha = calcular_objetivo_del_dia(usuario)

        self.assertEqual(con_fecha_explicita["calorias"], sin_pasar_fecha["calorias"])


class R11_EtiquetasDeActividadDelDiaADiaTests(PruebaConRegistroAbierto):
    """
    R11 (unidad 011) — las CINCO etiquetas del nivel de actividad hablan del día a día SIN
    contar los entrenos, y NINGUNA menciona días de ejercicio por semana. Coherencia con el
    plano de `crear-cuenta` ("eligió su nivel de actividad DEL DÍA A DÍA") y con R-2 de
    `generar-el-plan` (los entrenos se suman aparte, unidad 011 — no deben contarse dos
    veces, una en la etiqueta y otra en el entreno apuntado).
    """

    def test_las_cinco_claves_siguen_intactas(self):
        # R11 cambia el TEXTO, nunca las claves que se guardan en la base de datos.
        self.assertEqual(
            set(dict(constantes.ACTIVIDAD_CHOICES)),
            {"sedentario", "ligero", "moderado", "activo", "muy_activo"},
        )

    def test_ninguna_etiqueta_menciona_dias_de_ejercicio_por_semana(self):
        for clave, etiqueta in constantes.ACTIVIDAD_CHOICES:
            etiqueta_normalizada = etiqueta.lower()
            self.assertNotIn(
                "días/semana", etiqueta_normalizada, f"'{clave}' todavía habla de días/semana"
            )
            self.assertNotIn(
                "dias/semana", etiqueta_normalizada, f"'{clave}' todavía habla de dias/semana"
            )
            self.assertNotIn(
                "ejercicio", etiqueta_normalizada, f"'{clave}' todavía menciona 'ejercicio'"
            )
            self.assertNotIn(
                "entreno", etiqueta_normalizada, f"'{clave}' todavía menciona los entrenos"
            )

    def test_la_pantalla_de_alta_ya_enseña_las_etiquetas_nuevas(self):
        """La petición LLEGA a donde dice probar (lección de conocimiento/tests-que-no-fallan-
        cuando-deben.md): no basta con que `constantes.py` esté bien, el `<select>` del
        formulario de alta tiene que pintar el texto nuevo de verdad."""
        respuesta = self.client.get("/cuentas/signup/")
        contenido = respuesta.content.decode()
        self.assertNotIn("días/semana", contenido)
