"""
Las pantallas del plan de comidas (R1, R5, R6): apuntar una comida al plan de HOY de
cualquier persona del hogar, y ver cómo queda el día. R6/R7: pasa por
`persona_del_hogar_o_404` (la puerta de `planes/acceso.py`, que reutiliza
`hogares/acceso.py`), nunca por un `if` propio comparando hogares.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from hogares.acceso import persona_actual

from .acceso import persona_del_hogar_o_404
from .forms import FormularioComida
from .logica import apuntar_comida, resumen_del_dia

NOMBRE_DEL_PARTIAL = "planes/apuntar.html#plan_de_hoy"


@login_required
def apuntar_plan(request, persona_id):
    """
    R1/R6 — la pantalla de "apuntar el plan" (nota de alcance de la especificación: el botón
    que los planos llaman "generar un plan" es, en esta unidad, "apuntar el plan") de
    `persona_id`, que puede ser CUALQUIERA del hogar, propio o ajeno (G-43: es lo contrario
    del perfil, unidad 004). Con GET, enseña las comidas ya puestas hoy y el formulario vacío.
    Con POST, añade la comida y —si viene de HTMX— responde SOLO el trozo de plantilla
    (mismo patrón que `perfiles/views.py:actualizar_perfil`), para no recargar la página.
    """
    persona_objetivo = persona_del_hogar_o_404(request, persona_id)

    if request.method == "POST":
        form = FormularioComida(request.POST)
        if form.is_valid():
            apuntar_comida(persona_objetivo, form.cleaned_data)
            form = FormularioComida()  # formulario limpio, listo para la siguiente comida
    else:
        form = FormularioComida()

    contexto = {
        "persona_objetivo": persona_objetivo,
        "es_propio": persona_objetivo.id == persona_actual(request).id,
        "form": form,
        **resumen_del_dia(persona_objetivo),
    }

    plantilla = (
        NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "planes/apuntar.html"
    )
    return render(request, plantilla, contexto)
