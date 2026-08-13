"""
Las pantallas del perfil (R3, R7, R8, R9): ver los datos y las calorías del día de cualquier
persona del hogar, y cambiarlos solo si son los propios. Desde la unidad 006, también el
histórico de peso: apuntar una medición y borrar una equivocada (R1-R10 de
apuntar-el-peso.md).

Unidad 010 (R7/R8 de su especificación) — el histórico de peso deja de tratar lectura y
escritura igual: `ver_peso` ahora es del hogar entero (`perfil_visible_o_404`, mismo criterio
que `ver_perfil`), pero `apuntar_peso` y `borrar_peso` SIGUEN siendo solo de la propia persona
(`perfil_propio_o_404`, sin cambios) — R-23 (darle-cuenta-propia-a-los-de-casa.md) nombra
literalmente "el peso" entre lo que el hogar debe poder VER pero no cambiar, y G-171
(ver-tu-progreso.md) exige que "se vea el de todos, pero uno cada vez".

R8, la regla que más importa aquí: el CÁLCULO no se hace en ningún momento en este fichero.
Estas vistas solo reciben la petición HTTP, llaman a `perfiles.logica` (que a su vez llama a
`servicios.metabolismo`) y renderizan lo que les devuelve — igual que `hogares/views.py` con
`hogares.logica`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from hogares.acceso import persona_actual

from .acceso import (
    perfil_editable_o_404,
    perfil_propio_o_404,
    perfil_visible_o_404,
    puede_editar_perfil,
)
from .forms import FormularioMedicion, FormularioPerfil
from .logica import (
    apuntar_medicion,
    borrar_medicion,
    calcular_objetivo_del_dia,
    cambiar_objetivo,
    ultima_medicion,
)
from .models import MedicionPeso

NOMBRE_DEL_PARTIAL_DE_LA_TARJETA = "perfiles/ver.html#tarjeta_perfil"
NOMBRE_DEL_PARTIAL_DEL_HISTORICO = "perfiles/peso.html#historico_de_peso"


@login_required
def ver_perfil(request, persona_id=None):
    """
    R7 (superficie de uso) — "Qué ve nada más entrar: sus datos actuales y, debajo, sus
    calorías del día y sus macros ya calculados". Sin `persona_id`, enseña el propio (el
    enlace de la barra de navegación apunta aquí). Con `persona_id`, el de cualquier persona
    del MISMO hogar (R9: se ve, pero el formulario de cambiarlo no aparece si no es el suyo).
    """
    persona_id = persona_id if persona_id is not None else persona_actual(request).id
    perfil = perfil_visible_o_404(request, persona_id)
    yo = persona_actual(request)
    es_propio = perfil.persona_id == yo.id
    # Unidad 024, R4/G-43 — quien puede CAMBIAR este perfil no es solo su dueña: también su
    # responsable, si es una persona a cargo (R-99). `es_propio` sigue decidiendo el TEXTO
    # ("Tus datos" / "Datos de X"); `puede_editar` decide si aparece el formulario. Se calcula
    # con la MISMA función que usa la puerta de escritura (`perfil_editable_o_404`), para que
    # la pantalla nunca ofrezca un formulario que el servidor luego rechace.
    puede_editar = puede_editar_perfil(request, persona_id)

    contexto = {
        "perfil": perfil,
        "es_propio": es_propio,
        "puede_editar": puede_editar,
        "resultado": calcular_objetivo_del_dia(perfil.persona),
        "form": FormularioPerfil(instance=perfil) if puede_editar else None,
    }
    return render(request, "perfiles/ver.html", contexto)


@login_required
@require_POST
def actualizar_perfil(request, persona_id):
    """
    R3/R5/R6 — guarda los cambios y recalcula al momento. `perfil_editable_o_404` es la puerta
    de R9/R4: si `persona_id` no es el de quien hace la petición NI de alguien a su cargo,
    esto responde 404 ANTES de mirar siquiera el formulario — no hay forma de cambiar el
    perfil de otra persona con cuenta propia ni llamando aquí directamente con su id exacto
    (Q-20/Q-175).

    Con HTMX (R3: "sin recargar la pantalla"), la petición trae la cabecera `HX-Request` y
    aquí se responde SOLO el trozo de la tarjeta (plantillas parciales, como ya hace
    `paginas/views.py:hora_servidor` desde la unidad 002) — nunca la página entera.
    """
    perfil = perfil_editable_o_404(request, persona_id)
    es_propio = perfil.persona_id == persona_actual(request).id
    objetivo_antes_de_este_cambio = perfil.objetivo

    form = FormularioPerfil(request.POST, instance=perfil)
    if form.is_valid():
        perfil = form.save(commit=False)
        objetivo_nuevo = form.cleaned_data["objetivo"]
        if objetivo_nuevo != objetivo_antes_de_este_cambio:
            # R5/G-60: el ajuste vuelve SIEMPRE al de fábrica del objetivo nuevo, sin
            # excepción — aunque en esta MISMA petición viniera también un ajuste distinto
            # tecleado a mano, se ignora (G-60: "aunque hubiera uno puesto a mano... se
            # acepta a propósito"). Cambiar el ajuste a mano es un gesto APARTE (R6), en un
            # envío posterior, una vez visto cuál es el de fábrica del objetivo nuevo.
            cambiar_objetivo(perfil, objetivo_nuevo)
        perfil.save()
        # El formulario que se vuelve a mostrar refleja lo que de verdad quedó guardado (el
        # ajuste ya resuelto por R5, no lo que se hubiera tecleado y se descartó).
        form = FormularioPerfil(instance=perfil)

    resultado = calcular_objetivo_del_dia(perfil.persona)
    contexto = {
        "perfil": perfil,
        "es_propio": es_propio,
        "puede_editar": True,
        "resultado": resultado,
        "form": form,
    }

    plantilla = (
        NOMBRE_DEL_PARTIAL_DE_LA_TARJETA
        if request.headers.get("HX-Request")
        else "perfiles/ver.html"
    )
    return render(request, plantilla, contexto)


def _contexto_peso(persona, es_propio, form=None):
    """
    Reúne lo que necesita la pantalla del histórico de peso: el formulario (uno nuevo si no
    se pasa uno ya validado/con errores), el histórico completo, la última medición y el
    objetivo del día — R6/Q-112: `ultima` (lo que marcó la báscula) y `resultado["peso_kg"]`
    (el peso con el que se calcula) son DOS valores distintos, cada uno con su origen, para
    que la plantilla los rotule aparte sin confundirlos.

    Unidad 010, R7/R8 — `es_propio` es lo que la plantilla usa para decidir si enseña el
    formulario de apuntar y los botones de borrar (solo si es la propia persona): la LECTURA
    ya puede llegar aquí siendo ajena (`ver_peso` abajo), pero la ESCRITURA sigue exigiendo
    serlo (`apuntar_peso`/`borrar_peso`, sin cambios).
    """
    return {
        "persona_objetivo": persona,
        "es_propio": es_propio,
        "form": form if form is not None else FormularioMedicion(),
        "mediciones": persona.mediciones_peso.all(),
        "ultima": ultima_medicion(persona),
        "resultado": calcular_objetivo_del_dia(persona),
    }


@login_required
def ver_peso(request, persona_id=None):
    """
    R1/R3/R6/R9 (superficie de uso, apuntar-el-peso.md) — el histórico de peso de
    `persona_id`, y el formulario para apuntar una pesada nueva. Sin `persona_id`, el propio
    (enlace de la barra de navegación).

    Unidad 010, R7/R8 — la LECTURA de esta pantalla ahora es del hogar entero (mismo
    principio que `ver_perfil`, y la puerta que R7/R-23/G-171 exigían para "ver el progreso
    de otra persona de tu casa"): `perfil_visible_o_404` deja pasar el propio siempre y el
    ajeno solo si comparte hogar. La ESCRITURA (`apuntar_peso`, `borrar_peso`, aquí abajo)
    sigue exigiendo `perfil_propio_o_404` — nadie apunta ni borra el peso de otra persona con
    cuenta propia (R8), eso NO cambia. La plantilla usa `es_propio` para no enseñar el
    formulario ni los botones de borrar cuando se mira el de otra persona.
    """
    persona_id = persona_id if persona_id is not None else persona_actual(request).id
    perfil = perfil_visible_o_404(request, persona_id)
    es_propio = perfil.persona_id == persona_actual(request).id
    return render(request, "perfiles/peso.html", _contexto_peso(perfil.persona, es_propio))


@login_required
@require_POST
def apuntar_peso(request, persona_id):
    """
    R1/R2/R3/R10 — apunta una medición (o sustituye la de hoy si ya existía, R2/G-130: lo hace
    `apuntar_medicion` con su `update_or_create`). `perfil_propio_o_404` es la puerta de R7:
    nadie apunta el peso de otra persona, tampoco llamando aquí con su id exacto — 404, nunca
    403. Con HTMX, responde solo el trozo del histórico (mismo patrón que
    `actualizar_perfil`); sin HTMX, la página completa.
    """
    perfil = perfil_propio_o_404(request, persona_id)
    form = FormularioMedicion(request.POST)
    if form.is_valid():
        apuntar_medicion(perfil.persona, form.cleaned_data)
        form = FormularioMedicion()  # formulario limpio, listo para la siguiente pesada

    contexto = _contexto_peso(perfil.persona, es_propio=True, form=form)
    plantilla = (
        NOMBRE_DEL_PARTIAL_DEL_HISTORICO
        if request.headers.get("HX-Request")
        else "perfiles/peso.html"
    )
    return render(request, plantilla, contexto)


@login_required
@require_POST
def borrar_peso(request, persona_id, medicion_id):
    """
    R8/R9 — borra una medición equivocada; el objetivo del día se recalcula solo, con las que
    queden (o "sin ninguna", R9, sin reventar). Doble cinturón de R7: `perfil_propio_o_404`
    comprueba que `persona_id` es quien pregunta, y el `get_object_or_404` de abajo exige
    ADEMÁS que `medicion_id` sea SUYA — sin esto último, alguien podría apuntarse a sí mismo
    (pasando su propio `persona_id`) y colar el id de una medición ajena para borrarla.
    """
    perfil = perfil_propio_o_404(request, persona_id)
    medicion = get_object_or_404(MedicionPeso, id=medicion_id, persona=perfil.persona)
    borrar_medicion(medicion)

    contexto = _contexto_peso(perfil.persona, es_propio=True)
    plantilla = (
        NOMBRE_DEL_PARTIAL_DEL_HISTORICO
        if request.headers.get("HX-Request")
        else "perfiles/peso.html"
    )
    return render(request, plantilla, contexto)
