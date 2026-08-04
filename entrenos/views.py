"""
Las pantallas de Entrenos (unidad 011, apuntar-un-entreno.md): ver los tuyos y cuánto llevas
quemado hoy (§8 del plano), apuntar uno en pocos toques (Q-50), corregirlo sin borrarlo (R38) y
borrarlo. Solo lectura/escritura de UNO MISMO (R10): no hay "de quién es" (personas a cargo,
fuera de alcance) ni lectura del hogar sobre entrenos ajenos (R-79 en Progreso, otra unidad) —
la puerta es la mitad estricta de `entrenos/acceso.py`.

R8 (arquitectura del proyecto, "las vistas no calculan; llaman"): el CÁLCULO no se hace aquí.
Estas vistas reciben la petición HTTP, llaman a `entrenos.logica` (que a su vez llama a
`servicios.entrenos` para estimar y a `perfiles.logica` para el peso) y renderizan lo que
devuelve.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from perfiles.logica import calcular_objetivo_del_dia

from .acceso import usuario_propio_o_404
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


def _contexto(usuario, form=None):
    return {
        "usuario_objetivo": usuario,
        "form": form if form is not None else FormularioEntreno(),
        "entrenos": todos_los_entrenos(usuario),
        "calorias_hoy": calorias_de_hoy(usuario),
        "objetivo": calcular_objetivo_del_dia(usuario),
    }


@login_required
def ver_entrenos(request, usuario_id=None):
    """
    §8 del plano — "Qué ve nada más entrar: sus entrenos y cuántas calorías lleva quemadas
    hoy". Sin `usuario_id`, el propio (mismo patrón que `perfiles:ver_mio`,
    `progreso:ver_mio`...). R12 — sin ningún entreno todavía, la plantilla lo dice con
    naturalidad (ver entrenos/ver.html): esta vista no distingue el caso, simplemente pasa una
    lista vacía.
    """
    usuario_id = usuario_id if usuario_id is not None else request.user.id
    usuario = usuario_propio_o_404(request, usuario_id)
    return render(request, "entrenos/ver.html", _contexto(usuario))


@login_required
@require_POST
def apuntar(request, usuario_id):
    """
    R-36/R-37 — apunta un entreno nuevo. `usuario_propio_o_404` es la puerta de R10: nadie
    apunta un entreno "para" otra persona, tampoco llamando aquí con su id exacto.

    Q-51 — con HTMX (cabecera `HX-Request`), responde SOLO el trozo con las calorías de hoy y
    el formulario, para que la pantalla se actualice sin recargar; sin HTMX, la página entera.
    """
    usuario = usuario_propio_o_404(request, usuario_id)
    form = FormularioEntreno(request.POST)
    if form.is_valid():
        try:
            apuntar_entreno(usuario, form.cleaned_data)
            form = FormularioEntreno()
        except SinPesoParaEstimar as error:
            form.add_error("calorias", str(error))

    contexto = _contexto(usuario, form=form)
    plantilla = NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "entrenos/ver.html"
    return render(request, plantilla, contexto)


@login_required
def corregir(request, usuario_id, entreno_id):
    """
    R-38/G-72 — corrige cualquiera de sus datos sin borrarlo (R5) y recalcula sus calorías
    igual que al crearlo. R6/C-39 — sea el día que sea el entreno (de hoy o de uno pasado), NO
    se añade ningún mensaje ni aviso: esta vista, a propósito, no llama a `django.contrib.
    messages` en ningún camino — el silencio es el comportamiento correcto para TODOS los
    casos que trata esta unidad (un entreno futuro con aviso, R-79, no existe todavía: los
    entrenos previstos están fuera de alcance).

    Doble cinturón de R10 (mismo patrón que `perfiles/views.py:borrar_peso`):
    `usuario_propio_o_404` comprueba que `usuario_id` es quien pregunta, y el
    `get_object_or_404` de abajo exige ADEMÁS que `entreno_id` sea SUYO.
    """
    usuario = usuario_propio_o_404(request, usuario_id)
    entreno = get_object_or_404(Entreno, id=entreno_id, usuario=usuario)

    if request.method == "POST":
        form = FormularioEntreno(request.POST, instance=entreno)
        if form.is_valid():
            try:
                corregir_entreno(entreno, form.cleaned_data)
                return redirect("entrenos:ver", usuario_id=usuario.id)
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

    return render(
        request,
        "entrenos/corregir.html",
        {"usuario_objetivo": usuario, "entreno": entreno, "form": form},
    )


@login_required
@require_POST
def borrar(request, usuario_id, entreno_id):
    """§8 del plano ("Qué puede hacer... Borrarlo"). Mismo doble cinturón de R10 que
    `corregir`, arriba."""
    usuario = usuario_propio_o_404(request, usuario_id)
    entreno = get_object_or_404(Entreno, id=entreno_id, usuario=usuario)
    borrar_entreno(entreno)
    return redirect("entrenos:ver", usuario_id=usuario.id)
