"""
Las pantallas del perfil (R3, R7, R8, R9): ver los datos y las calorías del día de cualquier
persona del hogar, y cambiarlos solo si son los propios.

R8, la regla que más importa aquí: el CÁLCULO no se hace en ningún momento en este fichero.
Estas vistas solo reciben la petición HTTP, llaman a `perfiles.logica` (que a su vez llama a
`servicios.metabolismo`) y renderizan lo que les devuelve — igual que `hogares/views.py` con
`hogares.logica`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .acceso import perfil_propio_o_404, perfil_visible_o_404
from .forms import FormularioPerfil
from .logica import calcular_objetivo_del_dia, cambiar_objetivo

NOMBRE_DEL_PARTIAL_DE_LA_TARJETA = "perfiles/ver.html#tarjeta_perfil"


@login_required
def ver_perfil(request, usuario_id=None):
    """
    R7 (superficie de uso) — "Qué ve nada más entrar: sus datos actuales y, debajo, sus
    calorías del día y sus macros ya calculados". Sin `usuario_id`, enseña el propio (el
    enlace de la barra de navegación apunta aquí). Con `usuario_id`, el de cualquier persona
    del MISMO hogar (R9: se ve, pero el formulario de cambiarlo no aparece si no es el suyo).
    """
    usuario_id = usuario_id if usuario_id is not None else request.user.id
    perfil = perfil_visible_o_404(request, usuario_id)
    es_propio = perfil.usuario_id == request.user.id

    contexto = {
        "perfil": perfil,
        "es_propio": es_propio,
        "resultado": calcular_objetivo_del_dia(perfil.usuario),
        "form": FormularioPerfil(instance=perfil) if es_propio else None,
    }
    return render(request, "perfiles/ver.html", contexto)


@login_required
@require_POST
def actualizar_perfil(request, usuario_id):
    """
    R3/R5/R6 — guarda los cambios y recalcula al momento. `perfil_propio_o_404` es la puerta
    de R9: si `usuario_id` no es el de quien hace la petición, esto responde 404 ANTES de
    mirar siquiera el formulario — no hay forma de cambiar el perfil de otra persona ni
    llamando aquí directamente con su id exacto.

    Con HTMX (R3: "sin recargar la pantalla"), la petición trae la cabecera `HX-Request` y
    aquí se responde SOLO el trozo de la tarjeta (plantillas parciales, como ya hace
    `paginas/views.py:hora_servidor` desde la unidad 002) — nunca la página entera.
    """
    perfil = perfil_propio_o_404(request, usuario_id)
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

    resultado = calcular_objetivo_del_dia(perfil.usuario)
    contexto = {"perfil": perfil, "es_propio": True, "resultado": resultado, "form": form}

    plantilla = (
        NOMBRE_DEL_PARTIAL_DE_LA_TARJETA
        if request.headers.get("HX-Request")
        else "perfiles/ver.html"
    )
    return render(request, plantilla, contexto)
