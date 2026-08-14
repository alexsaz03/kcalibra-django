"""
Las pantallas de "cerrar el día" (unidad 012, decir-si-cumpliste.md): responder o saltar la
pregunta que sale al abrir la app (R6-R9, Q-140), y el cierre a mano desde Progreso (R10). La
puerta es `cierres/acceso.py:persona_propia_o_404`, la misma que usa `entrenos/views.py` —
desde la unidad 025 (R3/G-43) también deja pasar al RESPONSABLE de una persona a cargo, no
solo a ella misma.

R8 (arquitectura del proyecto, "las vistas no calculan; llaman"): estas vistas reciben la
petición HTTP, llaman a `cierres.logica` y renderizan lo que devuelve — el cálculo (qué día
está pendiente, la foto del menú) vive en `cierres/logica.py` y `servicios/cierres.py`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from hogares.acceso import persona_actual
from planes.logica import obtener_plan_de

from .acceso import persona_propia_o_404
from .forms import FormularioCierre, FormularioRespuestaRapida
from .logica import cerrar_dia, dia_pendiente_de_preguntar, saltar_dia_pendiente
from .models import CierreDeDia

# Igual que `entrenos/views.py`: la sintaxis "plantilla.html#nombre" es de
# django-template-partials, para que HTMX sustituya SOLO el trozo (novena cara de
# conocimiento/tests-que-no-fallan-cuando-deben.md — la vista responde el trozo, no un
# redirect, cuando la petición trae `HX-Request`).
NOMBRE_DEL_PARTIAL_PREGUNTA = "cierres/_pregunta_pendiente.html#pregunta_pendiente"
NOMBRE_DEL_PARTIAL_CERRAR = "cierres/cerrar.html#historico_de_cierres"


def _contexto_pregunta(persona):
    """
    R6/§8 del plano ("Qué ve nada más entrar: qué tenía puesto ayer y las tres respuestas") —
    el día pendiente (o `None`, R9/R13) y el plan de ESE día, si lo había (R5, caso límite: sin
    plan puesto, no hay nada que enseñar aquí y la pantalla no se rompe por ello).
    """
    dia = dia_pendiente_de_preguntar(persona)
    plan = obtener_plan_de(persona, dia) if dia is not None else None
    return {"dia_pendiente": dia, "plan_pendiente": plan}


@login_required
@require_POST
def responder(request, persona_id):
    """
    R1/R2/Q-140 — contesta EN UN TOQUE la pregunta del día pendiente. La fecha que se cierra es
    SIEMPRE la que calcula el servidor en este mismo instante (`dia_pendiente_de_preguntar`),
    nunca un valor que traiga el formulario: así nadie puede, con una petición manual, cerrar
    "por la puerta de la pregunta rápida" un día que no es el pendiente.

    Si para cuando llega esta petición ya no hay ningún día pendiente (doble clic, u otra
    pestaña que ya lo cerró/saltó antes), no hace nada: no hay nada que responder, y la
    pantalla no se rompe por ello.
    """
    persona = persona_propia_o_404(request, persona_id)
    dia = dia_pendiente_de_preguntar(persona)
    if dia is not None:
        form = FormularioRespuestaRapida(request.POST)
        if form.is_valid():
            cerrar_dia(persona, {"fecha": dia, "respuesta": form.cleaned_data["respuesta"]})

    contexto = _contexto_pregunta(persona)
    if request.headers.get("HX-Request"):
        return render(request, NOMBRE_DEL_PARTIAL_PREGUNTA, contexto)
    return redirect("paginas:inicio")


@login_required
@require_POST
def saltar(request, persona_id):
    """R8/Q-141 — se salta la pregunta del día pendiente: no se vuelve a preguntar por ese día
    jamás (`saltar_dia_pendiente`), y el día se queda sin apuntar."""
    persona = persona_propia_o_404(request, persona_id)
    saltar_dia_pendiente(persona)

    contexto = _contexto_pregunta(persona)
    if request.headers.get("HX-Request"):
        return render(request, NOMBRE_DEL_PARTIAL_PREGUNTA, contexto)
    return redirect("paginas:inicio")


@login_required
def cerrar(request, persona_id):
    """
    R10/§8 del plano ("El cierre a mano desde Progreso"): cierra cualquier día, también
    pasados, y cambia uno ya cerrado. Con `?fecha=`, precarga el formulario con el cierre que
    ya hubiera ese día (si lo hay) para que "cambiarlo" sea editar, no adivinar qué había.

    R13 (caso límite) — sin ningún cierre todavía, la plantilla lo dice con naturalidad (ver
    `cierres/cerrar.html`): esta vista no distingue el caso, simplemente pasa una lista vacía.

    Unidad 025, R3/G-43 — `persona_id` puede ser una persona a cargo de quien pregunta
    (`persona_propia_o_404` delega en `hogares.acceso.persona_editable_o_404`).
    """
    persona = persona_propia_o_404(request, persona_id)
    quien_pregunta = persona_actual(request)

    if request.method == "POST":
        form = FormularioCierre(request.POST)
        if form.is_valid():
            cerrar_dia(persona, form.cleaned_data)
            form = FormularioCierre()  # formulario limpio, listo para el siguiente día
    else:
        instancia = None
        fecha_param = request.GET.get("fecha")
        if fecha_param:
            # Ronda 2, hueco 1: mismo criterio que `servicios/progreso.py:
            # semanas_desde_parametro` — esto es una persona (o un enlace roto) tecleando
            # algo en la URL, jamás debe romper la pantalla. `parse_date` devuelve `None`
            # para lo que no tiene forma de fecha ("pepe") y `ValueError` para lo que SÍ
            # tiene forma pero no existe ("2026-13-45"); ambos casos se tratan igual que si
            # `?fecha=` no hubiera llegado.
            try:
                fecha = parse_date(fecha_param)
            except ValueError:
                fecha = None
            if fecha is not None:
                instancia = CierreDeDia.objects.filter(persona=persona, fecha=fecha).first()
        form = FormularioCierre(instance=instancia) if instancia else FormularioCierre()

    contexto = {
        "persona_objetivo": persona,
        # Unidad 025, R3/R5/G-43 — misma separación que perfiles/ y entrenos/: `es_propio`
        # decide el TEXTO, `puede_editar` decide si se enseña el formulario. `puede_editar`
        # es siempre `True` aquí (la puerta ya filtró antes de renderizar; no hay, en esta
        # unidad, un tercer estado "lo veo pero no lo cambio" para cierres).
        "es_propio": persona.id == quien_pregunta.id,
        "puede_editar": True,
        "form": form,
        "cierres": CierreDeDia.objects.filter(persona=persona),
    }
    plantilla = (
        NOMBRE_DEL_PARTIAL_CERRAR if request.headers.get("HX-Request") else "cierres/cerrar.html"
    )
    return render(request, plantilla, contexto)
