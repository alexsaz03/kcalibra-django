"""
Las pantallas de Entrenos (unidad 011, apuntar-un-entreno.md): ver los tuyos y cuánto llevas
quemado hoy (§8 del plano), apuntar uno en pocos toques (Q-50), corregirlo sin borrarlo (R38) y
borrarlo. No hay lectura del hogar sobre entrenos ajenos (R-79 en Progreso, otra unidad) — la
puerta sigue siendo la mitad estricta de `entrenos/acceso.py`, con una única excepción desde la
unidad 025: quien pregunta puede ser también el RESPONSABLE de una persona a cargo (R2/G-43).

R8 (arquitectura del proyecto, "las vistas no calculan; llaman"): el CÁLCULO no se hace aquí.
Estas vistas reciben la petición HTTP, llaman a `entrenos.logica` (que a su vez llama a
`servicios.entrenos` para estimar y a `perfiles.logica` para el peso) y renderizan lo que
devuelve.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from hogares.acceso import persona_actual
from perfiles.logica import calcular_objetivo_del_dia

from .acceso import persona_propia_o_404
from .forms import FormularioEntreno
from .logica import (
    SinPesoParaEstimar,
    apuntar_entreno,
    borrar_entreno,
    calorias_de_hoy,
    corregir_entreno,
    todos_los_entrenos,
)
from .models import Entreno

# La sintaxis "plantilla.html#nombre" es de django-template-partials (ya en uso desde la
# unidad 002): pide SOLO ese trozo, para que HTMX lo sustituya sin recargar nada más (Q-51).
NOMBRE_DEL_PARTIAL = "entrenos/ver.html#entrenos_de_hoy"


def _contexto(persona, quien_pregunta, form=None):
    """
    Unidad 025, R2/R5/G-43 — `es_propio` decide el TEXTO ("tus entrenos" / "entrenos de
    Marta"); `puede_editar` decide si la plantilla enseña el formulario y los botones de
    borrar/corregir — misma separación que `perfiles/`. Aquí `puede_editar` es SIEMPRE `True`
    para quien llega a este contexto: la puerta (`persona_propia_o_404`, delegada en
    `hogares.acceso.persona_editable_o_404`) ya filtró antes de construirlo — no hay, en esta
    unidad, un tercer estado "lo veo pero no lo cambio" para entrenos (fuera de alcance: eso
    es abrir la mitad de VER de R-23 a todo el hogar). Se deja explícito, y no fijo a `True`
    en la plantilla, para que el día que se abra esa lectura baste con calcularlo aquí.
    """
    return {
        "persona_objetivo": persona,
        "es_propio": persona.id == quien_pregunta.id,
        "puede_editar": True,
        "form": form if form is not None else FormularioEntreno(),
        "entrenos": todos_los_entrenos(persona),
        "calorias_hoy": calorias_de_hoy(persona),
        "objetivo": calcular_objetivo_del_dia(persona),
    }


@login_required
def ver_entrenos(request, persona_id=None):
    """
    §8 del plano — "Qué ve nada más entrar: sus entrenos y cuántas calorías lleva quemadas
    hoy". Sin `persona_id`, el propio (mismo patrón que `perfiles:ver_mio`,
    `progreso:ver_mio`...). R12 — sin ningún entreno todavía, la plantilla lo dice con
    naturalidad (ver entrenos/ver.html): esta vista no distingue el caso, simplemente pasa una
    lista vacía.

    Unidad 025, R2 — `persona_id` puede ser una persona a cargo de quien pregunta: la
    pantalla se ve, y se puede apuntar, corregir y borrar (R2/G-43).
    """
    persona_id = persona_id if persona_id is not None else persona_actual(request).id
    persona = persona_propia_o_404(request, persona_id)
    return render(request, "entrenos/ver.html", _contexto(persona, persona_actual(request)))


@login_required
@require_POST
def apuntar(request, persona_id):
    """
    R-36/R-37 — apunta un entreno nuevo. `persona_propia_o_404` es la puerta de R10/R2 (unidad
    025): nadie apunta un entreno "para" otra persona salvo su responsable, tampoco llamando
    aquí con su id exacto.

    Q-51 — con HTMX (cabecera `HX-Request`), responde SOLO el trozo con las calorías de hoy y
    el formulario, para que la pantalla se actualice sin recargar; sin HTMX, la página entera.
    """
    persona = persona_propia_o_404(request, persona_id)
    form = FormularioEntreno(request.POST)
    if form.is_valid():
        try:
            apuntar_entreno(persona, form.cleaned_data)
            form = FormularioEntreno()
        except SinPesoParaEstimar as error:
            form.add_error("calorias", str(error))

    contexto = _contexto(persona, persona_actual(request), form=form)
    plantilla = NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "entrenos/ver.html"
    return render(request, plantilla, contexto)


@login_required
def corregir(request, persona_id, entreno_id):
    """
    R-38/G-72 — corrige cualquiera de sus datos sin borrarlo (R5) y recalcula sus calorías
    igual que al crearlo. R6/C-39 — sea el día que sea el entreno (de hoy o de uno pasado), NO
    se añade ningún mensaje ni aviso: esta vista, a propósito, no llama a `django.contrib.
    messages` en ningún camino — el silencio es el comportamiento correcto para TODOS los
    casos que trata esta unidad (un entreno futuro con aviso, R-79, no existe todavía: los
    entrenos previstos están fuera de alcance).

    Doble cinturón de R10/R2 (mismo patrón que `perfiles/views.py:borrar_peso`):
    `persona_propia_o_404` comprueba que `persona_id` es quien pregunta O su responsable, y el
    `get_object_or_404` de abajo exige ADEMÁS que `entreno_id` sea SUYO.
    """
    persona = persona_propia_o_404(request, persona_id)
    entreno = get_object_or_404(Entreno, id=entreno_id, persona=persona)

    if request.method == "POST":
        form = FormularioEntreno(request.POST, instance=entreno)
        if form.is_valid():
            try:
                corregir_entreno(entreno, form.cleaned_data)
                return redirect("entrenos:ver", persona_id=persona.id)
            except SinPesoParaEstimar as error:
                form.add_error("calorias", str(error))
    else:
        # El campo de calorías SOLO se pre-rellena si la persona las había escrito a mano
        # (`calorias_manuales`): así, si se dejaron en blanco (estimadas) y la persona corrige
        # otro campo sin tocar este, al enviar sigue llegando en blanco y G-70 las vuelve a
        # estimar con los datos nuevos — "las calorías se rehacen solas" (contrato de la
        # especificación), sin que la persona tenga que acordarse de borrar el número viejo.
        valor_inicial = entreno.calorias if entreno.calorias_manuales else None
        form = FormularioEntreno(instance=entreno, initial={"calorias": valor_inicial})

    quien_pregunta = persona_actual(request)
    return render(
        request,
        "entrenos/corregir.html",
        {
            "persona_objetivo": persona,
            "es_propio": persona.id == quien_pregunta.id,
            "entreno": entreno,
            "form": form,
        },
    )


@login_required
@require_POST
def borrar(request, persona_id, entreno_id):
    """§8 del plano ("Qué puede hacer... Borrarlo"). Mismo doble cinturón de R10/R2 que
    `corregir`, arriba.

    Q-51/R12 — igual que `apuntar`: con HTMX (cabecera `HX-Request`) responde SOLO el trozo
    (mismo patrón que `perfiles/views.py:borrar_peso`), para que `ver.html` pueda sustituir
    `#entrenos-de-hoy` sin incrustar la página entera dentro de sí misma; sin HTMX, el redirect
    de siempre.
    """
    persona = persona_propia_o_404(request, persona_id)
    entreno = get_object_or_404(Entreno, id=entreno_id, persona=persona)
    borrar_entreno(entreno)

    if request.headers.get("HX-Request"):
        return render(request, NOMBRE_DEL_PARTIAL, _contexto(persona, persona_actual(request)))
    return redirect("entrenos:ver", persona_id=persona.id)
