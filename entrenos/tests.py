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
from hogares.models import SolicitudEntrada
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

        # Carlos, en SU PROPIO hogar (nunca se une a nadie): el tercero de R10.
        self.registrar_y_verificar("carlos@example.com", sexo="hombre")
        self.carlos = Usuario.objects.get(email="carlos@example.com")
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

        entreno = Entreno.objects.get(usuario=self.euridice)
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
        entreno = Entreno.objects.get(usuario=self.euridice)
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

        entreno = Entreno.objects.get(usuario=self.alejandro)
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
        crossfit = Entreno.objects.get(usuario=self.alejandro, deporte="crossfit")
        hyrox = Entreno.objects.get(usuario=self.alejandro, deporte="hyrox")
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
        return Entreno.objects.get(usuario=usuario)

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
        self.assertEqual(Entreno.objects.filter(usuario=self.alejandro).count(), 1)
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
            usuario=self.alejandro, fecha=ayer, deporte="hyrox", intensidad="fuerte",
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
            usuario=self.alejandro, fecha=ayer, deporte="hyrox", intensidad="fuerte",
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
        self.assertFalse(Entreno.objects.filter(usuario=self.alejandro).exists())

    def test_minutos_negativos_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "-5", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(usuario=self.alejandro).exists())

    def test_deporte_que_no_esta_en_la_lista_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "esgrima",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(usuario=self.alejandro).exists())

    def test_intensidad_que_no_esta_en_la_lista_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "extrema", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(usuario=self.alejandro).exists())

    def test_calorias_negativas_no_se_guarda(self):
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": "-10"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(usuario=self.alejandro).exists())


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
            usuario=self.alejandro, fecha=timezone.localdate(), deporte="hyrox",
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
            usuario=self.alejandro, fecha=timezone.localdate(), deporte="correr",
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
            usuario=self.alejandro, fecha=timezone.localdate(), deporte="correr",
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

        MedicionPeso.objects.filter(usuario=self.alejandro).delete()
        respuesta = self.client.post(
            f"/entrenos/{self.alejandro.id}/apuntar/",
            {"fecha": timezone.localdate().isoformat(), "deporte": "correr",
             "intensidad": "media", "minutos": "30", "calorias": ""},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entreno.objects.filter(usuario=self.alejandro).exists())
