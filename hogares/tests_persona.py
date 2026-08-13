"""
Tests de la unidad 023 (la persona deja de ser la cuenta) — R3 a R7 de su especificación.

Los demás criterios de esta unidad no tienen tests propios A PROPÓSITO: R1 ("la suite entera
sigue en verde con los tests intactos") y R2 ("los dos checks del equipo pasan sin editarlos")
se cumplen con LA SUITE QUE YA EXISTE, que es justamente lo que los hace fuertes. Un test
nuevo que dijera "el refactor está bien" no probaría nada que no prueben ya los 510 de antes.

Lo que sí hace falta escribir aquí es lo que ningún test cubría todavía:

- **R3** — que ningún dato personal cambie de dueño. Su prueba principal son los recuentos
  reales de ANTES y DESPUÉS de la migración, pegados en `hallazgos.md` (una migración de un
  solo sentido no se puede reejecutar dentro de la suite: las columnas de las que lee ya no
  existen). Lo que SÍ se puede vigilar para siempre —y es lo que hace este fichero— es la
  propiedad cuya violación causaría ese cambio de dueño: **un id de cuenta y un id de persona
  no son intercambiables**. Mientras los dos contadores vayan sincronizados por casualidad, un
  descuido de este tipo pasa desapercibido; aquí se desincronizan a propósito.
- **R4** — que la migración se declare irreversible A MANO, con su motivo y su rollback real.
- **R5** — que `createsuperuser` y el admin sigan funcionando sin `Usuario.hogar`.
- **R6** — que una cuenta SIN perfil siga siendo un estado tolerado.
- **R7** — que el aislamiento por hogar siga respondiendo 404 y jamás 403.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from cuentas.ayuda_pruebas import CLAVE_VALIDA, PruebaConRegistroAbierto
from entrenos.models import Entreno
from perfiles.logica import calcular_objetivo_del_dia
from perfiles.models import MedicionPeso, Perfil

from .models import Persona, SolicitudEntrada

Usuario = get_user_model()


def _desincronizar_los_contadores(cuantas=5):
    """
    Deja la secuencia de `hogares_persona` por delante de la de `cuentas_usuario`, creando y
    borrando unas cuantas personas de usar y tirar.

    Sin esto, en una base recién creada los dos contadores van a la par y `persona.id ==
    usuario.id` para todo el mundo: cualquier sitio que siguiera confundiendo los dos ids
    funcionaría igual y ningún test se enteraría. Es exactamente el fallo silencioso que la
    investigación de esta unidad midió como "probable, no teórico".
    """
    for _ in range(cuantas):
        provisional = Persona.objects.create()
        provisional.delete()


class R3_ConLosIdsDesincronizadosCadaPersonaSigueViendoLoSuyoTests(PruebaConRegistroAbierto):
    """
    R3 — ningún dato personal cambia de dueño.

    El montaje desincroniza los contadores ANTES de crear a nadie, así que el id de la persona
    y el de su cuenta NO coinciden para nadie. A partir de ahí se recorre la app entera por
    HTTP: cada pantalla tiene que seguir enseñando los datos de QUIEN toca. Cualquier resto de
    "el id de la URL es el de la cuenta" se cae aquí con un 404 o —peor y más importante— con
    los números de otra persona.
    """

    def setUp(self):
        super().setUp()
        _desincronizar_los_contadores()

        # Euridice (mujer, 167 cm, 62 kg, moderado, perder grasa) y Alejandro (hombre, 190 cm,
        # 93 kg, ligero, recomposición): los dos episodios reales de los planos, con calorías
        # conocidas — 1.894 y 3.006 kcal.
        self.registrar_y_verificar("euridice@example.com")
        self.cuenta_euridice = Usuario.objects.get(email="euridice@example.com")
        self.euridice = Persona.objects.get(usuario=self.cuenta_euridice)
        self.client.logout()

        self.registrar_y_verificar(
            "alejandro@example.com",
            codigo_hogar=self.euridice.hogar.codigo,
            sexo="hombre",
            fecha_nacimiento="1998-11-03",
            altura_cm="190",
            peso_kg="93",
            actividad="ligero",
            objetivo="recomposicion_corporal",
        )
        self.cuenta_alejandro = Usuario.objects.get(email="alejandro@example.com")
        self.alejandro = Persona.objects.get(usuario=self.cuenta_alejandro)
        self.client.logout()

        # Euridice la acepta: quedan en el MISMO hogar.
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        solicitud = SolicitudEntrada.objects.get(usuario=self.cuenta_alejandro)
        self.client.post(f"/hogares/mi-hogar/solicitudes/{solicitud.pk}/aceptar/")
        self.alejandro.refresh_from_db()
        self.assertEqual(self.alejandro.hogar_id, self.euridice.hogar_id)  # control

    def test_los_ids_de_cuenta_y_de_persona_de_verdad_no_coinciden(self):
        """Control del propio montaje: si esto dejara de ser cierto, los tests de abajo
        estarían pasando por casualidad y no probarían nada."""
        self.assertNotEqual(self.euridice.id, self.cuenta_euridice.id)
        self.assertNotEqual(self.alejandro.id, self.cuenta_alejandro.id)

    def test_cada_pantalla_ensena_los_datos_de_la_persona_de_la_url_no_los_de_su_cuenta(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        # Los suyos: 1.894 kcal (C-13 de crear-cuenta.md).
        propio = self.client.get(f"/perfiles/{self.euridice.id}/")
        self.assertEqual(propio.status_code, 200)
        # Unidad 024, R1/G-196: por su nombre, nunca por su correo (aquí, el de la barra de
        # arriba: la propia pantalla de "Tus datos" no enseña ningún nombre en su título).
        self.assertContains(propio, "Euridice")
        self.assertContains(propio, "1894 kcal")

        # Los de Alejandro, de la misma casa: 3.006 kcal (C-13 también). Que salgan ESTOS y no
        # los suyos es lo que demuestra que la traducción de dueños no mezcló a nadie.
        ajeno = self.client.get(f"/perfiles/{self.alejandro.id}/")
        self.assertEqual(ajeno.status_code, 200)
        self.assertContains(ajeno, "Alejandro")
        self.assertContains(ajeno, "3006 kcal")
        self.assertNotContains(ajeno, "1894 kcal")

    def test_el_peso_el_progreso_los_entrenos_y_el_plan_siguen_colgando_de_la_persona(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

        # La pesada del alta es de SU persona, no de un id de cuenta.
        self.assertTrue(MedicionPeso.objects.filter(persona=self.euridice).exists())
        self.assertEqual(MedicionPeso.objects.filter(persona=self.alejandro).count(), 1)

        # Apunta un entreno y una comida por las URLs reales, con el id de la persona.
        self.client.post(
            f"/entrenos/{self.euridice.id}/apuntar/",
            {
                "fecha": timezone.localdate().isoformat(),
                "deporte": "correr",
                "intensidad": "media",
                "minutos": "30",
                "calorias": "300",
            },
        )
        self.client.post(
            f"/planes/{self.euridice.id}/apuntar/",
            {
                "nombre": "Tortilla",
                "momento_del_dia": "cena",
                "calorias": "500",
                "proteina_g": "30",
                "grasa_g": "20",
                "carbos_g": "40",
            },
        )

        # Lo apuntado es SUYO, y de nadie más.
        self.assertEqual(Entreno.objects.filter(persona=self.euridice).count(), 1)
        self.assertEqual(Entreno.objects.filter(persona=self.alejandro).count(), 0)
        self.assertEqual(
            self.euridice.planes_de_dia.get().comidas.get().nombre, "Tortilla"
        )
        self.assertEqual(self.alejandro.planes_de_dia.count(), 0)

        # Y las pantallas de lectura siguen sirviendo lo de cada cual.
        for ruta in (
            f"/perfiles/{self.euridice.id}/peso/",
            f"/progreso/{self.euridice.id}/",
            f"/entrenos/{self.euridice.id}/",
            f"/cierres/{self.euridice.id}/",
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)

    def test_el_inicio_ensena_una_tarjeta_por_persona_con_el_numero_de_cada_una(self):
        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        # Las tarjetas se identifican por el id de la PERSONA (paginas/inicio.html).
        self.assertContains(respuesta, f'id="tarjeta-{self.euridice.id}"')
        self.assertContains(respuesta, f'id="tarjeta-{self.alejandro.id}"')
        self.assertContains(respuesta, "1894 kcal")
        self.assertContains(respuesta, "3006 kcal")


class R4_LaMigracionEsIrreversibleAPropositoTests(TransactionTestCase):
    """
    R4 — la migración de datos se declara irreversible A MANO. Intentar la vuelta tiene que
    chocar con un error que diga el motivo Y cuál es el rollback real, en vez de fingir en
    silencio que sabe deshacer lo que no sabe. Precedente y patrón: unidad 017
    (`despensa.tests.R6_RollbackDeLaMigracionEsIrreversibleAPropositoTests`).

    `TransactionTestCase`, no `TestCase`: aquí se llama a `MigrationExecutor.migrate()` de
    verdad (mueve el puntero de qué migraciones están aplicadas), y eso no puede ir envuelto
    en la transacción atómica que usa `TestCase`.
    """

    def tearDown(self):
        # El intento de retroceder debe abortar entero y dejar todo tal cual estaba, pero se
        # repara aquí por si acaso, para no contaminar el resto de la suite.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_intentar_deshacer_la_migracion_falla_diciendo_el_motivo_y_el_rollback_real(self):
        from django.db.migrations.exceptions import IrreversibleError

        executor = MigrationExecutor(connection)
        with self.assertRaises(IrreversibleError) as contexto:
            executor.migrate([("hogares", "0002_persona")])

        print("\n--- R4: intento de rollback de la 023 (esperado: falla) ---")
        print(repr(contexto.exception))

        mensaje = str(contexto.exception)
        self.assertIn("no se puede deshacer", mensaje)
        self.assertIn("pg_dump", mensaje)  # el rollback REAL, nombrado

        # Control: tras el intento fallido, la migración sigue aplicada — no se quedó a medias.
        self.assertIn(
            ("hogares", "0003_una_persona_por_cada_cuenta"),
            executor.loader.applied_migrations,
        )

    def test_las_seis_migraciones_de_la_unidad_declaran_su_motivo_a_mano(self):
        """Las seis migraciones de esta unidad tienen su `reverse_code` escrito a mano (no un
        `None` con el mensaje genérico de Django): se comprueba LLAMÁNDOLO, no leyéndolo."""
        import importlib

        from django.db.migrations.exceptions import IrreversibleError

        modulos = [
            "hogares.migrations.0003_una_persona_por_cada_cuenta",
            "perfiles.migrations.0004_el_perfil_y_las_pesadas_son_de_la_persona",
            "entrenos.migrations.0002_los_entrenos_son_de_la_persona",
            "planes.migrations.0002_el_plan_es_de_la_persona",
            "cierres.migrations.0002_los_cierres_son_de_la_persona",
            "cuentas.migrations.0004_la_cuenta_deja_de_saber_de_hogares",
        ]
        for nombre in modulos:
            with self.subTest(migracion=nombre):
                modulo = importlib.import_module(nombre)
                with self.assertRaises(IrreversibleError) as contexto:
                    modulo._irreversible(None, None)
                mensaje = str(contexto.exception)
                self.assertIn("no se puede deshacer", mensaje)
                self.assertIn("pg_dump", mensaje)


class R5_ElSuperusuarioYElAdminSiguenEnPieTests(TestCase):
    """
    R5 (caso límite) — `createsuperuser` sigue creando un superusuario que entra en el admin, y
    el admin sigue listando las cuentas. Es el caso que la investigación señaló como el que se
    rompe solo en cuanto `Usuario` pierde `hogar` (`cuentas/models.py:25-32` y
    `cuentas/admin.py:15`).
    """

    def test_createsuperuser_crea_la_cuenta_su_persona_y_deja_entrar_al_admin(self):
        call_command(
            "createsuperuser",
            interactive=False,
            email="jefa@example.com",
            verbosity=0,
        )
        jefa = Usuario.objects.get(email="jefa@example.com")
        self.assertTrue(jefa.is_staff)
        self.assertTrue(jefa.is_superuser)

        # Toda cuenta estrena su persona, también esta: sin hogar todavía, como antes de esta
        # unidad `Usuario.hogar` quedaba en `None` tras `createsuperuser`.
        self.assertTrue(Persona.objects.filter(usuario=jefa).exists())
        self.assertIsNone(jefa.persona.hogar)

        jefa.set_password(CLAVE_VALIDA)
        jefa.save()
        self.assertTrue(self.client.login(username="jefa@example.com", password=CLAVE_VALIDA))

        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_el_admin_sigue_listando_las_cuentas_con_su_hogar(self):
        call_command("createsuperuser", interactive=False, email="jefa@example.com", verbosity=0)
        jefa = Usuario.objects.get(email="jefa@example.com")
        jefa.set_password(CLAVE_VALIDA)
        jefa.save()
        self.client.login(username="jefa@example.com", password=CLAVE_VALIDA)

        lista = self.client.get("/admin/cuentas/usuario/")
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "jefa@example.com")

        # Y la ficha de una cuenta concreta se abre sin el campo `hogar` que ya no existe.
        ficha = self.client.get(f"/admin/cuentas/usuario/{jefa.id}/change/")
        self.assertEqual(ficha.status_code, 200)

    def test_el_admin_de_personas_es_donde_se_edita_ahora_el_hogar(self):
        call_command("createsuperuser", interactive=False, email="jefa@example.com", verbosity=0)
        jefa = Usuario.objects.get(email="jefa@example.com")
        jefa.set_password(CLAVE_VALIDA)
        jefa.save()
        self.client.login(username="jefa@example.com", password=CLAVE_VALIDA)

        lista = self.client.get("/admin/hogares/persona/")
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "jefa@example.com")


class R6_UnaCuentaSinPerfilSigueSiendoUnEstadoToleradoTests(TestCase):
    """
    R6 (caso límite) — hoy una cuenta puede no tener perfil (`create_user` de los tests,
    `createsuperuser`, la importación: ver `perfiles/logica.py`), y esta unidad NO puede
    convertir eso en un error. `Persona` es un modelo nuevo y DELGADO precisamente por esto:
    si fuera el `Perfil` renombrado, "de qué hogar eres" dependería de una fila que puede no
    existir.
    """

    def test_create_user_deja_una_cuenta_con_persona_y_sin_perfil_sin_reventar(self):
        cuenta = Usuario.objects.create_user(email="sin-perfil@example.com", password=CLAVE_VALIDA)
        persona = Persona.objects.get(usuario=cuenta)

        self.assertFalse(Perfil.objects.filter(persona=persona).exists())
        # El cálculo del día devuelve `None` sin excepción: "todavía no le corresponde ninguno".
        self.assertIsNone(calcular_objetivo_del_dia(persona))

    def test_una_cuenta_sin_perfil_entra_y_ve_el_inicio_sin_romperse(self):
        cuenta = Usuario.objects.create_user(email="sin-perfil@example.com", password=CLAVE_VALIDA)
        from hogares.models import crear_hogar_propio

        crear_hogar_propio(cuenta.persona)

        self.client.force_login(cuenta)
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Aún no hay datos suficientes para calcular")

    def test_una_persona_sin_perfil_no_impide_ver_el_hogar(self):
        cuenta = Usuario.objects.create_user(email="sin-perfil@example.com", password=CLAVE_VALIDA)
        from hogares.models import crear_hogar_propio

        # `create_user` no pasa por el formulario de alta (unidad 024): la señal
        # (`hogares.signals.crear_persona_de_la_cuenta`) le crea su `Persona` igual, pero sin
        # nombre — se pone aquí a mano, como haría cualquier alta de verdad.
        cuenta.persona.nombre = "Sin Perfil"
        cuenta.persona.save(update_fields=["nombre"])
        crear_hogar_propio(cuenta.persona)
        self.client.force_login(cuenta)

        respuesta = self.client.get("/hogares/mi-hogar/")
        self.assertEqual(respuesta.status_code, 200)
        # Unidad 024, R1/G-196: por su nombre, nunca por su correo.
        self.assertContains(respuesta, "Sin Perfil")


class R7_ElAislamientoPorHogarResponde404YNunca403Tests(PruebaConRegistroAbierto):
    """
    R7 (caso límite) — pedir los datos de alguien de OTRO hogar con su id EXACTO sigue
    respondiendo 404, nunca 403 (Q-20): un 403 confirmaría "existe, pero no es tuyo".

    Esto ya lo vigilan los tests de cada app; se repite aquí sobre el id de `Persona` —el que
    ahora viaja por la URL— porque es el id que esta unidad cambia, y con los contadores
    desincronizados a propósito para que ningún acierto casual lo tape.
    """

    def setUp(self):
        super().setUp()
        _desincronizar_los_contadores()
        self.registrar_y_verificar("euridice@example.com")
        self.euridice = Persona.objects.get(usuario__email="euridice@example.com")
        self.client.logout()

        self.registrar_y_verificar("carlos@example.com")  # su propio hogar, nunca se une
        self.carlos = Persona.objects.get(usuario__email="carlos@example.com")
        self.client.logout()

        self.client.login(username="euridice@example.com", password=CLAVE_VALIDA)

    def test_pedir_a_alguien_de_otro_hogar_con_su_id_exacto_da_404_y_nunca_403(self):
        rutas = [
            f"/perfiles/{self.carlos.id}/",
            f"/perfiles/{self.carlos.id}/peso/",
            f"/progreso/{self.carlos.id}/",
            f"/entrenos/{self.carlos.id}/",
            f"/cierres/{self.carlos.id}/",
            f"/planes/{self.carlos.id}/apuntar/",
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_un_id_que_no_existe_da_exactamente_lo_mismo_que_uno_ajeno(self):
        inexistente = self.carlos.id + 10_000
        self.assertFalse(Persona.objects.filter(pk=inexistente).exists())  # control
        self.assertEqual(
            self.client.get(f"/perfiles/{inexistente}/").status_code,
            self.client.get(f"/perfiles/{self.carlos.id}/").status_code,
        )
