"""
Tests de la unidad 011 (R1-R12, apuntar-un-entreno.md): apuntar, corregir y borrar un entreno
a mano, y que sus calorías cuenten en el objetivo del día.

Igual que en `perfiles/tests.py`, `planes/tests.py` y `progreso/tests.py`: todo pasa por el
cliente de pruebas de Django contra las URLs reales (la lección de
docs/conocimiento/tests-que-no-fallan-cuando-deben.md del meta-repo — la petición tiene que
LLEGAR a lo que dice probar). Los números exactos de C-37 (362 kcal) y C-38 (1.302 kcal) NO se
deducen aquí otra vez: ya están verificados en `servicios/tests.py` contra la fórmula pura;
estos tests demuestran que el CABLEADO completo (formulario -> vista -> lógica -> servicio)
llega a producirlos de punta a punta.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from hogares.models import Persona, SolicitudEntrada
from perfiles.logica import calcular_objetivo_del_dia

from .models import Entreno

Usuario = get_user_model()


class BaseEntrenosTests(PruebaConRegistroAbierto):
    """
    Alejandro y Euridice, en el MISMO hogar; Carlos, en el SUYO propio (nunca se une a
    nadie) — el mismo montaje de tres personas que ya usa `progreso/tests.py`, necesario para
    R10 (octava cara de conocimiento/tests-que-no-fallan-cuando-deben.md: un permiso "propio /
    mismo hogar / de fuera" necesita un TERCERO que nunca se una a nadie, no solo dos personas
    del mismo hogar). La sesión queda en Alejandro (93 kg, hombre) al terminar `setUp`.
    """

    def setUp(self):
        super().setUp()
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre", peso_kg="93")
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

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el tercero de R10.
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
        self.client.logout()

        self.client.login(username="alejandro@example.com", password=CLAVE_VALIDA)


class R1_C37_EstimarSinCaloriasTests(BaseEntrenosTests):
    """
    R1/R36/C-37 (el episodio real de Euridice) — 62 kg, 35 min de correr a intensidad media,
    calorías en blanco: la app estima 362 kcal.
    """

    def test_apuntar_sin_calorias_las_estima_en_362(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        respuesta = self.client.post(
            f"/entrenos/{self.euridice.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "35", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)

        entreno = Entreno.objects.get(persona=self.euridice)
        self.assertEqual(entreno.calorias, 362)
        self.assertFalse(entreno.calorias_manuales)
        self.assertContains(respuesta, "362")


class R2_C37_GuardaLasEscritasSinDiscutirlasTests(BaseEntrenosTests):
    """R2/R36/C-37/G-70 — si la persona escribe sus propias calorías (355, las de su
    pulsómetro), la app se queda EXACTAMENTE con esas, no con las 362 que habría estimado."""

    def test_apuntar_con_355_kcal_guarda_355_no_las_estimadas(self):
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        self.client.post(
            f"/entrenos/{self.euridice.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "35", "calorias": "355"},
        )
        entreno = Entreno.objects.get(persona=self.euridice)
        self.assertEqual(entreno.calorias, 355)
        self.assertTrue(entreno.calorias_manuales)


class R3_C38_HyroxSumaAlObjetivoTests(BaseEntrenosTests):
    """
    R3/R37/C-38 (el episodio real de Alejandro) — 93 kg, 60 min de Hyrox a intensidad fuerte,
    sin calorías: la app estima 1.302 kcal y se las suma a SU objetivo del día.
    """

    def test_hyrox_sin_calorias_estima_1302_y_sube_el_objetivo(self):
        with_fijo = timezone.localdate()
        objetivo_antes = calcular_objetivo_del_dia(self.alejandro)

        self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": with_fijo.isoformat(), "deporte": "hyrox",
             "intensidad": "fuerte", "minutos": "60", "calorias": ""},
        )

        entreno = Entreno.objects.get(persona=self.alejandro)
        self.assertEqual(entreno.calorias, 1302)

        objetivo_despues = calcular_objetivo_del_dia(self.alejandro)
        self.assertEqual(objetivo_despues["calorias"], objetivo_antes["calorias"] + 1302)


class R4_LosSieteDeportesTests(BaseEntrenosTests):
    """R4/G-71 — la app ofrece los siete deportes, CrossFit y Hyrox incluidos (nuevos: hoy no
    existían), cada uno con sus tres intensidades."""

    def test_el_formulario_ofrece_los_siete_deportes(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        for deporte in ["correr", "bici", "nadar", "fuerza", "crossfit", "hyrox", "otro"]:
            self.assertIn(f'value="{deporte}"', contenido)

    def test_el_formulario_ofrece_las_tres_intensidades(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        contenido = respuesta.content.decode()
        for intensidad in ["suave", "media", "fuerte"]:
            self.assertIn(f'value="{intensidad}"', contenido)

    def test_crossfit_y_hyrox_estiman_con_su_propia_tabla(self):
        # CrossFit media (9 kcal/min) y Hyrox media (11 kcal/min) NO pueden dar el mismo
        # número: si el formulario los tratara como "otro" (6 kcal/min, el hueco de antes),
        # los tres coincidirían.
        self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "crossfit",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "hyrox",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        crossfit = Entreno.objects.get(persona=self.alejandro, deporte="crossfit")
        hyrox = Entreno.objects.get(persona=self.alejandro, deporte="hyrox")
        self.assertNotEqual(crossfit.calorias, hyrox.calorias)
        self.assertGreater(hyrox.calorias, crossfit.calorias)  # 11 > 9 kcal/min


class R5_CorregirRecalculaSolasTests(BaseEntrenosTests):
    """
    R5/R38/G-72 — corregir CUALQUIER dato (minutos, deporte, intensidad, día, calorías)
    actualiza sin borrar y recalcula las calorías igual que al crear. "Qué" de la
    especificación, textual: "cambia el minuto, el deporte o el día, y las calorías se rehacen
    solas" — sin que la persona tenga que volver a tocar el campo de calorías.
    """

    def _apuntar_estimado(self, usuario, **campos):
        base = {
            "fecha": timezone.localdate().isoformat(), "deporte": "correr",
            "intensidad": "media", "minutos": "35", "calorias": "",
        }
        base.update(campos)
        self.client.post(f"/entrenos/{usuario.id}/apuntar/", base)
        return Entreno.objects.get(persona=usuario)

    def test_corregir_los_minutos_rehace_las_calorias_solas(self):
        entreno = self._apuntar_estimado(self.alejandro, deporte="correr", intensidad="media",
                                          minutos="35", calorias="")
        self.assertEqual(entreno.calorias, entreno.calorias)  # sanity
        calorias_antes = entreno.calorias  # estimadas con 35 min

        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": entreno.fecha.isoformat(), "deporte": "correr", "intensidad": "media",
             "minutos": "50", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 302)
        entreno.refresh_from_db()
        self.assertNotEqual(entreno.calorias, calorias_antes)
        self.assertFalse(entreno.calorias_manuales)

    def test_corregir_el_deporte_rehace_las_calorias_solas(self):
        entreno = self._apuntar_estimado(self.alejandro, deporte="correr", intensidad="media",
                                          minutos="35", calorias="")
        calorias_antes = entreno.calorias

        self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": entreno.fecha.isoformat(), "deporte": "hyrox", "intensidad": "media",
             "minutos": "35", "calorias": ""},
        )
        entreno.refresh_from_db()
        self.assertNotEqual(entreno.calorias, calorias_antes)
        self.assertEqual(entreno.deporte, "hyrox")

    def test_corregir_no_borra_sigue_siendo_el_mismo_registro(self):
        entreno = self._apuntar_estimado(self.alejandro)
        id_antes = entreno.id
        self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": entreno.fecha.isoformat(), "deporte": "bici", "intensidad": "suave",
             "minutos": "20", "calorias": ""},
        )
        self.assertEqual(Entreno.objects.filter(persona=self.alejandro).count(), 1)
        self.assertEqual(Entreno.objects.get().id, id_antes)

    def test_corregir_escribiendo_calorias_a_mano_las_respeta(self):
        """Si en la corrección la persona SÍ escribe unas calorías, la app se queda con
        esas (G-70 se aplica igual al corregir que al crear)."""
        entreno = self._apuntar_estimado(self.alejandro)
        self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": entreno.fecha.isoformat(), "deporte": "correr", "intensidad": "media",
             "minutos": "35", "calorias": "999"},
        )
        entreno.refresh_from_db()
        self.assertEqual(entreno.calorias, 999)
        self.assertTrue(entreno.calorias_manuales)

    def test_corregir_la_intensidad_rehace_las_calorias_solas(self):
        entreno = self._apuntar_estimado(self.alejandro, deporte="correr", intensidad="suave",
                                          minutos="35", calorias="")
        calorias_antes = entreno.calorias  # estimadas a intensidad SUAVE

        self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": entreno.fecha.isoformat(), "deporte": "correr", "intensidad": "fuerte",
             "minutos": "35", "calorias": ""},
        )
        entreno.refresh_from_db()
        self.assertGreater(entreno.calorias, calorias_antes)  # fuerte quema más que suave
        self.assertEqual(entreno.intensidad, "fuerte")

    def test_el_dia_tambien_se_puede_corregir(self):
        entreno = self._apuntar_estimado(self.alejandro)
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": ayer, "deporte": "correr", "intensidad": "media", "minutos": "35",
             "calorias": ""},
        )
        entreno.refresh_from_db()
        self.assertEqual(entreno.fecha.isoformat(), ayer)


class R6_C39_CorregirElHistoricoEnSilencioTests(BaseEntrenosTests):
    """
    R6/R38/C-39 (el episodio real de Alejandro) — corregir un entreno de un día PASADO
    recalcula el histórico sin avisar de nada: ni mensaje, ni tarea pendiente.
    """

    def test_corregir_un_entreno_pasado_no_deja_ningun_mensaje(self):
        ayer = timezone.localdate() - timedelta(days=1)
        entreno = Entreno.objects.create(
            persona=self.alejandro, fecha=ayer, deporte="hyrox", intensidad="fuerte",
            minutos=45, calorias=977, calorias_manuales=False,
        )
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": ayer.isoformat(), "deporte": "hyrox", "intensidad": "fuerte",
             "minutos": "55", "calorias": ""},
            follow=True,
        )
        entreno.refresh_from_db()
        self.assertNotEqual(entreno.minutos, 45)
        self.assertEqual(list(respuesta.context.get("messages", [])), [])

    def test_el_objetivo_de_aquel_dia_pasado_refleja_la_correccion(self):
        ayer = timezone.localdate() - timedelta(days=1)
        entreno = Entreno.objects.create(
            persona=self.alejandro, fecha=ayer, deporte="hyrox", intensidad="fuerte",
            minutos=45, calorias=977, calorias_manuales=True,
        )
        self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": ayer.isoformat(), "deporte": "hyrox", "intensidad": "fuerte",
             "minutos": "55", "calorias": "1195"},
        )
        objetivo_de_ayer = calcular_objetivo_del_dia(self.alejandro, fecha=ayer)
        self.assertEqual(objetivo_de_ayer["entreno_kcal"], 1195)


class R9_EntradasInvalidasSeRechazanTests(BaseEntrenosTests):
    """R9 — minutos cero/negativos, deporte o intensidad fuera de lista, o calorías negativas:
    no se guardan, y la pantalla lo dice sin romperse (nunca un 500)."""

    def test_minutos_cero_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "0", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro).exists())

    def test_minutos_negativos_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "-5", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro).exists())

    def test_deporte_que_no_esta_en_la_lista_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "esgrima",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro).exists())

    def test_intensidad_que_no_esta_en_la_lista_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "extrema", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro).exists())

    def test_calorias_negativas_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": "-10"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro).exists())


class R10_SoloSobreUnoMismoTests(BaseEntrenosTests):
    """
    R10 — apuntar, corregir o borrar un entreno de OTRA persona (del hogar, o de fuera) da
    404, nunca 403. Euridice está en el MISMO hogar que Alejandro; Carlos, en el suyo propio
    (octava cara de conocimiento/tests-que-no-fallan-cuando-deben.md: hacen falta los DOS
    casos, no solo "no soy yo").
    """

    def setUp(self):
        super().setUp()
        self.entreno_de_alejandro = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="hyrox",
            intensidad="fuerte", minutos=60, calorias=1302, calorias_manuales=False,
        )
        self.client.logout()
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

    def test_no_puede_apuntar_un_entreno_para_otra_persona_del_hogar(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_corregir_un_entreno_de_otra_persona_del_mismo_hogar(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/corregir/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "5", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.entreno_de_alejandro.refresh_from_db()
        self.assertEqual(self.entreno_de_alejandro.minutos, 60)  # intacto

    def test_no_puede_borrar_un_entreno_de_otra_persona_del_mismo_hogar(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/borrar/"
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Entreno.objects.filter(id=self.entreno_de_alejandro.id).exists())

    def test_de_otro_hogar_tambien_da_404_no_solo_del_mismo(self):
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/corregir/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "5", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_apuntar_para_otra_persona_de_otro_hogar_tambien_da_404(self):
        """Ronda 2 — la mitad "apuntar x otro hogar" de las seis combinaciones ajenas de R10
        que faltaba: Carlos (su propio hogar) intentando apuntar un entreno "para" Alejandro."""
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_borrar_de_otra_persona_de_otro_hogar_tambien_da_404(self):
        """Ronda 2 — la mitad "borrar x otro hogar" de las seis combinaciones ajenas de R10 que
        faltaba: Carlos (su propio hogar) intentando borrar un entreno de Alejandro."""
        self.client.logout()
        self.client.login(username="carlos@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{self.entreno_de_alejandro.id}/borrar/"
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Entreno.objects.filter(id=self.entreno_de_alejandro.id).exists())

    def test_nunca_403_siempre_404(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertNotEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.status_code, 404)


class BorrarTests(BaseEntrenosTests):
    """Superficie de uso (§8 del plano): "Qué puede hacer... Borrarlo". No lo pide ningún R*
    por número, pero R10 lo nombra explícitamente entre las tres acciones protegidas."""

    def test_borrar_el_propio_lo_quita_de_la_lista(self):
        entreno = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=30, calorias=300, calorias_manuales=True,
        )
        respuesta = self.client.post(f"/entrenos/{self.alejandro.id}/{entreno.id}/borrar/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Entreno.objects.filter(id=entreno.id).exists())

    def test_borrar_con_hx_request_responde_solo_el_trozo(self):
        """Ronda 2 (H1) — `ver.html` manda el borrado con `hx-post` + `hx-target` +
        `hx-swap="outerHTML"` (igual que `apuntar`, ver Q51ActualizaSinRecargarTests): con la
        cabecera HX-Request que el navegador siempre manda en ese POST, la respuesta tiene que
        ser el TROZO, no la página entera con <html>/<head> incrustados dentro del div."""
        entreno = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="correr",
            intensidad="media", minutos=30, calorias=300, calorias_manuales=True,
        )
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/borrar/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(id=entreno.id).exists())
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn('id="entrenos-de-hoy"', contenido)


class R12_PantallaVaciaTests(BaseEntrenosTests):
    """R12 — sin ningún entreno todavía, la pantalla lo dice con naturalidad: no parece rota
    ni da error."""

    def test_sin_ningun_entreno_no_da_error_y_lo_dice(self):
        respuesta = self.client.get(f"/entrenos/{self.alejandro.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "0 kcal")


class Q51ActualizaSinRecargarTests(BaseEntrenosTests):
    """Q-51 — al guardar un entreno de HOY, las calorías del día se actualizan sin recargar
    (HTMX): la petición con la cabecera HX-Request recibe solo el TROZO de plantilla, no la
    página completa (nunca <html> ni <head>)."""

    def test_con_hx_request_responde_solo_el_trozo(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": "300"},
            HTTP_HX_REQUEST="true",
        )
        contenido = respuesta.content.decode()
        self.assertNotIn("<html", contenido)
        self.assertIn("300", contenido)


class SinPesoNoRevientaTests(BaseEntrenosTests):
    """Defensivo (no lo nombra ningún R* por número, pero es la misma cautela de R9: "sin
    romper la pantalla"): si por lo que sea no hay NINGUNA medición de peso, la app no puede
    dividir por un peso inexistente — se avisa con un mensaje de formulario, no un 500."""

    def test_sin_ninguna_medicion_de_peso_pide_las_calorias_en_vez_de_reventar(self):
        from perfiles.models import MedicionPeso

        MedicionPeso.objects.filter(persona=self.alejandro).delete()
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(persona=self.alejandro).exists())


class Bug030_LaPuertaCompartidaSinRedEnAisladoTests(PruebaConRegistroAbierto):
    """
    Bug 030 — `entrenos/acceso.py:persona_propia_o_404` no compara nada por su cuenta: delega
    ENTERA en `hogares.acceso.puede_cambiar_lo_de` (línea 98: `if
    str(persona_que_pregunta.id) == str(persona_id)`), la puerta ÚNICA que comparten
    `perfiles/`, `progreso/`, `entrenos/` y `cierres/`. Ninguno de los tests de arriba
    (`BaseEntrenosTests` registra a Alejandro EL PRIMERO de la tanda) protege esa comparación
    en AISLADO: con las secuencias de `Persona` y `Usuario` recién migradas, el `persona.id` y
    el `usuario.id` de quien registra primero coinciden por pura casualidad (los dos valen 1)
    — la 16ª cara (`tests-que-no-fallan-cuando-deben.md`, unidad 023: los contadores van a la
    par), que 027 y 029 ya cerraron para `progreso/` y `perfiles/` respectivamente, pero que
    nunca se había cerrado aquí.

    Antes de esta clase, mutando la línea 98 para comparar `persona_que_pregunta.usuario_id`
    en vez de `.id` (la MISMA forma que protegen 027/029, no una mutación cómoda),
    `python manage.py test entrenos` SOLO daba `OK` (42 tests) — la coincidencia numérica de
    más arriba tapaba el defecto entonces; remedido restaurando la versión anterior de este
    fichero (docs/bugs/030-la-puerta-compartida-sin-red-en-entrenos-y-cierres.md, sección 3).
    Con esta clase presente, la misma mutación SÍ cae (esa misma ficha, sección 2).

    La cura, la misma que 027/029: dar de alta a una `Persona` SIN `Usuario` (Marta) ANTES de
    que Alejandro registre su cuenta, adelantando la secuencia de `Persona` un paso por
    delante de la de `Usuario` para siempre, así su `persona.id` ya NUNCA coincide con su
    `usuario.id` por casualidad. La 19ª cara (revisión de la 029), aquí obligatoria: el
    montaje que crea el desfase se AFIRMA con un assert sobre lo que debía crearse, no se
    supone — si el alta de Marta fallara en silencio, la secuencia de `Persona` no avanzaría
    y esta red se apagaría sin un solo rojo.
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
        self.registrar_y_verificar("alejandro@example.com", sexo="hombre", peso_kg="93")
        self.alejandro = Persona.objects.get(usuario__email="alejandro@example.com")
        self.assertNotEqual(self.alejandro.id, self.alejandro.usuario_id)  # control del desfase

    def test_alejandro_apunta_su_propio_entreno_con_los_ids_desincronizados(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": "300"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Entreno.objects.filter(persona=self.alejandro, calorias=300).exists())

    def test_alejandro_corrige_su_propio_entreno_con_los_ids_desincronizados(self):
        entreno = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="hyrox",
            intensidad="fuerte", minutos=60, calorias=1302, calorias_manuales=False,
        )
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/{entreno.id}/corregir/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "5", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 302)  # sin HX-Request: redirect (R6)
        entreno.refresh_from_db()
        self.assertEqual(entreno.minutos, 5)

    def test_alejandro_borra_su_propio_entreno_con_los_ids_desincronizados(self):
        entreno = Entreno.objects.create(
            persona=self.alejandro, fecha=timezone.localdate(), deporte="hyrox",
            intensidad="fuerte", minutos=60, calorias=1302, calorias_manuales=False,
        )
        respuesta = self.client.post(f"/entrenos/{self.alejandro.id}/{entreno.id}/borrar/")
        self.assertEqual(respuesta.status_code, 302)  # sin HX-Request: redirect (BorrarTests)
        self.assertFalse(Entreno.objects.filter(id=entreno.id).exists())
