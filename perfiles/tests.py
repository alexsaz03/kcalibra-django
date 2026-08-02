"""
Tests de la unidad 004: R1-R11.

Como en `cuentas/tests.py` y `hogares/tests.py`, todo pasa por el cliente de pruebas de
Django contra las URLs reales (nunca `Perfil.objects.create(...)` a mano cuando lo que se
prueba es un flujo completo) — la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo: la petición tiene que
LLEGAR a lo que dice probar, así que las respuestas de HTMX se comprueban por su CONTENIDO
(los números cambiaron de verdad), no solo por el código de estado.

R1 y R2 (los números clavados) YA están probados llamando al servicio directamente, sin
pasar por ninguna pantalla, en `servicios/tests.py` (R8: "verificable... llamándolo
directamente"). Aquí se prueban otra vez, pero de punta a punta por HTTP —alta, verificación,
pantalla de "tus datos"— para demostrar que el CABLEADO (formulario → perfil → vista) también
funciona, no solo la fórmula suelta. Como una fecha de nacimiento hace que la edad (y por
tanto las calorías) cambie el día del cumpleaños, estos dos tests fijan "hoy" con
`unittest.mock.patch` en vez de confiar en la fecha real de la máquina que ejecute la suite.
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from cuentas.ayuda_pruebas import PruebaConRegistroAbierto
from perfiles.forms import FormularioPerfil
from perfiles.logica import calcular_objetivo_del_dia, peso_medio_7_dias
from perfiles.models import MedicionPeso, Perfil

Usuario = get_user_model()

HOY_DE_REFERENCIA = date(2026, 8, 2)


class _FechaFija(date):
    """
    Subclase de `date` que fija `.today()` a `HOY_DE_REFERENCIA`, para congelar "hoy" en los
    tests que necesitan un resultado EXACTO (R1/R2 por HTTP) sin depender de en qué día real
    se ejecute la suite. Sigue siendo un `date` de verdad (no un mock a ciegas): construir
    fechas con ella (`_FechaFija(1997, 6, 29)`) se comporta exactamente igual que con `date`.
    """

    @classmethod
    def today(cls):
        return HOY_DE_REFERENCIA


def _con_hoy_fijo():
    """`servicios.metabolismo` es el ÚNICO sitio que llama a `date.today()` (R8: es la única
    pieza que decide "hoy" para el cálculo); parchear su `date` basta para congelar la edad
    en toda la cadena perfiles → servicios, sin tocar nada de Django."""
    return mock.patch("servicios.metabolismo.date", _FechaFija)


class AltaConDatosFisicosTests(PruebaConRegistroAbierto):
    """R7/"El alta crece" — registrarse crea el Perfil Y la primera medición de peso."""

    def test_el_alta_crea_perfil_y_primera_medicion_de_peso(self):
        self.registrar_y_verificar("alejandro@example.com")
        usuario = Usuario.objects.get(email="alejandro@example.com")

        self.assertTrue(Perfil.objects.filter(usuario=usuario).exists())
        perfil = usuario.perfil
        # Los valores de fábrica de `DATOS_FISICOS_POR_DEFECTO` (los de Euridice, C-13).
        self.assertEqual(perfil.sexo, "mujer")
        self.assertEqual(perfil.altura_cm, 167)
        self.assertEqual(perfil.objetivo, "perder_grasa")

        mediciones = MedicionPeso.objects.filter(usuario=usuario)
        self.assertEqual(mediciones.count(), 1)
        self.assertEqual(mediciones.first().peso_kg, 62)
        self.assertEqual(mediciones.first().fecha, date.today())

    def test_sin_ajuste_manual_el_perfil_usa_el_de_fabrica_del_objetivo(self):
        # DATOS_FISICOS_POR_DEFECTO trae objetivo=perder_grasa y ajuste_pct="" (en blanco).
        self.registrar_y_verificar("alejandro@example.com")
        perfil = Usuario.objects.get(email="alejandro@example.com").perfil
        self.assertEqual(perfil.ajuste_pct, -10)  # de fábrica de "perder_grasa" (G-60)

    def test_con_ajuste_manual_en_el_alta_se_respeta_el_suyo(self):
        # "Cómo" de crear-cuenta.md: "si quiso ajustó a mano su porcentaje".
        self.registrar_y_verificar("alejandro@example.com", ajuste_pct="-15")
        perfil = Usuario.objects.get(email="alejandro@example.com").perfil
        self.assertEqual(perfil.ajuste_pct, -15)

    def test_las_manias_se_guardan_aunque_nada_las_lea_todavia(self):
        self.registrar_y_verificar(
            "alejandro@example.com",
            dieta="vegetariana",
            alergias="frutos secos",
            intolerancias="lactosa",
            no_le_gusta="brócoli",
        )
        perfil = Usuario.objects.get(email="alejandro@example.com").perfil
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
            alejandro = Usuario.objects.get(email="alejandro@example.com")
            self.client.logout()

            self.registrar_y_verificar(
                "euridice@example.com", codigo_hogar=alejandro.hogar.codigo
            )
            euridice = Usuario.objects.get(email="euridice@example.com")
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
        self.usuario = Usuario.objects.get(email="alejandro@example.com")
        # El alta ya dejó una medición de 62 kg hoy; la sustituimos por un histórico a medida
        # para controlar exactamente qué entra en la media.
        MedicionPeso.objects.filter(usuario=self.usuario).delete()

    def test_la_media_solo_cuenta_los_ultimos_7_dias(self):
        hoy = date.today()
        MedicionPeso.objects.create(usuario=self.usuario, fecha=hoy, peso_kg=60)
        MedicionPeso.objects.create(
            usuario=self.usuario, fecha=hoy - timedelta(days=3), peso_kg=62
        )
        # Esta, de hace 10 días, NO debe entrar en la media (fuera de la ventana de 7 días).
        MedicionPeso.objects.create(
            usuario=self.usuario, fecha=hoy - timedelta(days=10), peso_kg=100
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
        hoy = date.today()
        MedicionPeso.objects.create(
            usuario=self.usuario, fecha=hoy - timedelta(days=6), peso_kg=70
        )
        MedicionPeso.objects.create(
            usuario=self.usuario, fecha=hoy - timedelta(days=7), peso_kg=200
        )

        media = peso_medio_7_dias(self.usuario)

        self.assertEqual(media, 70)  # SOLO la de hace 6 días; la de hace 7 queda fuera

    def test_una_sola_medicion_reciente_es_su_propia_media(self):
        MedicionPeso.objects.create(usuario=self.usuario, fecha=date.today(), peso_kg=75)
        self.assertEqual(peso_medio_7_dias(self.usuario), 75)

    def test_apuntar_un_peso_nuevo_cambia_las_calorias_sin_tocar_el_perfil(self):
        """C-35 (cambiar-tus-datos.md): apuntar un peso nuevo mueve las calorías SOLAS, sin
        pasar por la pantalla de perfil. Aquí no hay pantalla de "apuntar peso" (fuera de
        alcance de esta unidad): se demuestra creando la medición directamente y comprobando
        que el CÁLCULO ya la usa, sin que nadie haya tocado el Perfil."""
        with _con_hoy_fijo():
            MedicionPeso.objects.create(
                usuario=self.usuario, fecha=date.today(), peso_kg=61
            )
            objetivo_original = self.usuario.perfil.objetivo
            resultado_antes = calcular_objetivo_del_dia(self.usuario)

            MedicionPeso.objects.create(
                usuario=self.usuario, fecha=date.today(), peso_kg=59
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
        self.usuario = Usuario.objects.get(email="euridice@example.com")

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
        self.usuario = Usuario.objects.get(email="alejandro@example.com")
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
        self.alejandro = Usuario.objects.get(email="alejandro@example.com")
        self.client.logout()

        self.registrar_y_verificar(
            "euridice@example.com", codigo_hogar=self.alejandro.hogar.codigo
        )
        self.euridice = Usuario.objects.get(email="euridice@example.com")
        self.client.logout()

        # Alejandro la acepta: quedan en el MISMO hogar (necesario para que R9 tenga sentido:
        # "todo el hogar la ve" presupone que están en el mismo hogar).
        self.client.login(username="alejandro@example.com", password="una-clave-de-verdad-2026")
        from hogares.models import SolicitudEntrada

        solicitud = SolicitudEntrada.objects.get(usuario=self.euridice)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.euridice.refresh_from_db()
        self.assertEqual(self.euridice.hogar_id, self.alejandro.hogar_id)  # control

    def test_alejandro_ve_los_datos_y_las_calorias_de_euridice(self):
        respuesta = self.client.get(f"/perfiles/{self.euridice.id}/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "euridice@example.com")
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
        fecha_futura = (date.today() + timedelta(days=365)).isoformat()
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
        self.usuario = Usuario.objects.get(email="alejandro@example.com")

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
