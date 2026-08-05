"""
Las pantallas de "cerrar el día" (unidad 012, decir-si-cumpliste.md): responder o saltar la
pregunta que sale al abrir la app (R6-R9, Q-140), y el cierre a mano desde Progreso (R10).
Solo lectura/escritura de UNO MISMO (R12): la puerta es `cierres/acceso.py:
usuario_propio_o_404`, la misma "mitad estricta" que usa `entrenos/views.py`.

R8 (arquitectura del proyecto, "las vistas no calculan; llaman"): estas vistas reciben la
petición HTTP, llaman a `cierres.logica` y renderizan lo que devuelve — el cálculo (qué día
está pendiente, la foto del menú) vive en `cierres/logica.py` y `servicios/cierres.py`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from planes.logica import obtener_plan_de

from .acceso import usuario_propio_o_404
from .forms import FormularioCierre, FormularioRespuestaRapida
from .logica import cerrar_dia, dia_pendiente_de_preguntar, saltar_dia_pendiente
from .models import CierreDeDia

# Igual que `entrenos/views.py`: la sintaxis "plantilla.html#nombre" es de
# django-template-partials, para que HTMX sustituya SOLO el trozo (novena cara de
# conocimiento/tests-que-no-fallan-cuando-deben.md — la vista responde el trozo, no un
# redirect, cuando la petición trae `HX-Request`).
NOMBRE_DEL_PARTIAL_PREGUNTA = "cierres/_pregunta_pendiente.html#pregunta_pendiente"
NOMBRE_DEL_PARTIAL_CERRAR = "cierres/cerrar.html#historico_de_cierres"


def _contexto_pregunta(usuario):
    """
    R6/§8 del plano ("Qué ve nada más entrar: qué tenía puesto ayer y las tres respuestas") —
    el día pendiente (o `None`, R9/R13) y el plan de ESE día, si lo había (R5, caso límite: sin
    plan puesto, no hay nada que enseñar aquí y la pantalla no se rompe por ello).
    """
    dia = dia_pendiente_de_preguntar(usuario)
    plan = obtener_plan_de(usuario, dia) if dia is not None else None
    return {"dia_pendiente": dia, "plan_pendiente": plan}


@login_required
@require_POST
def responder(request, usuario_id):
    """
    R1/R2/Q-140 — contesta EN UN TOQUE la pregunta del día pendiente. La fecha que se cierra es
    SIEMPRE la que calcula el servidor en este mismo instante (`dia_pendiente_de_preguntar`),
    nunca un valor que traiga el formulario: así nadie puede, con una petición manual, cerrar
    "por la puerta de la pregunta rápida" un día que no es el pendiente.

    Si para cuando llega esta petición ya no hay ningún día pendiente (doble clic, u otra
    pestaña que ya lo cerró/saltó antes), no hace nada: no hay nada que responder, y la
    pantalla no se rompe por ello.
    """
    usuario = usuario_propio_o_404(request, usuario_id)
    dia = dia_pendiente_de_preguntar(usuario)
    if dia is not None:
        form = FormularioRespuestaRapida(request.POST)
        if form.is_valid():
            cerrar_dia(usuario, {"fecha": dia, "respuesta": form.cleaned_data["respuesta"]})

    contexto = _contexto_pregunta(usuario)
    if request.headers.get("HX-Request"):
        return render(request, NOMBRE_DEL_PARTIAL_PREGUNTA, contexto)
    return redirect("paginas:inicio")


@login_required
@require_POST
def saltar(request, usuario_id):
    """R8/Q-141 — se salta la pregunta del día pendiente: no se vuelve a preguntar por ese día
    jamás (`saltar_dia_pendiente`), y el día se queda sin apuntar."""
    usuario = usuario_propio_o_404(request, usuario_id)
    saltar_dia_pendiente(usuario)

    contexto = _contexto_pregunta(usuario)
    if request.headers.get("HX-Request"):
        return render(request, NOMBRE_DEL_PARTIAL_PREGUNTA, contexto)
    return redirect("paginas:inicio")


@login_required
def cerrar(request, usuario_id):
    """
    R10/§8 del plano ("El cierre a mano desde Progreso"): cierra cualquier día, también
    pasados, y cambia uno ya cerrado. Con `?fecha=`, precarga el formulario con el cierre que
    ya hubiera ese día (si lo hay) para que "cambiarlo" sea editar, no adivinar qué había.

    R13 (caso límite) — sin ningún cierre todavía, la plantilla lo dice con naturalidad (ver
    `cierres/cerrar.html`): esta vista no distingue el caso, simplemente pasa una lista vacía.
    """
    usuario = usuario_propio_o_404(request, usuario_id)

    if request.method == "POST":
        form = FormularioCierre(request.POST)
        if form.is_valid():
            cerrar_dia(usuario, form.cleaned_data)
            form = FormularioCierre()  # formulario limpio, listo para el siguiente día
    else:
        instancia = None
        fecha_param = request.GET.get("fecha")
        if fecha_param:
            instancia = CierreDeDia.objects.filter(usuario=usuario, fecha=fecha_param).first()
        form = FormularioCierre(instance=instancia) if instancia else FormularioCierre()

    contexto = {
        "usuario_objetivo": usuario,
        "form": form,
        "cierres": CierreDeDia.objects.filter(usuario=usuario),
    }
    plantilla = (
        NOMBRE_DEL_PARTIAL_CERRAR if request.headers.get("HX-Request") else "cierres/cerrar.html"
    )
    return render(request, plantilla, contexto)
