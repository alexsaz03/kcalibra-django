"""
Las pantallas del plan de comidas (R1, R5, R6): apuntar una comida al plan de HOY de
cualquier persona del hogar, y ver cómo queda el día. R6/R7: pasa por
`usuario_del_hogar_o_404` (la puerta de `planes/acceso.py`, que reutiliza
`hogares/acceso.py`), nunca por un `if` propio comparando hogares.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .acceso import usuario_del_hogar_o_404
from .forms import FormularioComida
from .logica import apuntar_comida, resumen_del_dia

NOMBRE_DEL_PARTIAL = "planes/apuntar.html#plan_de_hoy"


@login_required
def apuntar_plan(request, usuario_id):
    """
    R1/R6 — la pantalla de "apuntar el plan" (nota de alcance de la especificación: el botón
    que los planos llaman "generar un plan" es, en esta unidad, "apuntar el plan") de
    `usuario_id`, que puede ser CUALQUIERA del hogar, propio o ajeno (G-43: es lo contrario
    del perfil, unidad 004). Con GET, enseña las comidas ya puestas hoy y el formulario vacío.
    Con POST, añade la comida y —si viene de HTMX— responde SOLO el trozo de plantilla
    (mismo patrón que `perfiles/views.py:actualizar_perfil`), para no recargar la página.
    """
    usuario_objetivo = usuario_del_hogar_o_404(request, usuario_id)

    if request.method == "POST":
        form = FormularioComida(request.POST)
        if form.is_valid():
            apuntar_comida(usuario_objetivo, form.cleaned_data)
            form = FormularioComida()  # formulario limpio, listo para la siguiente comida
    else:
        form = FormularioComida()

    contexto = {
        "usuario_objetivo": usuario_objetivo,
        "es_propio": usuario_objetivo.id == request.user.id,
        "form": form,
        **resumen_del_dia(usuario_objetivo),
    }

    plantilla = (
        NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "planes/apuntar.html"
    )
    return render(request, plantilla, contexto)
