"""
Las pantallas de recetas (unidad 021, guardar-tus-recetas.md): la lista (R7), el formulario de
alta (R1/R2/R3/R5), el detalle de una receta abierta (R1/R4), editarla (R4) y borrarla (R6). Es
DEL HOGAR entero, no de una persona (G-43, R-70): ninguna vista de aquí recibe un `persona_id`
en la URL, todas trabajan sobre EL HOGAR de quien pregunta (`recetas/acceso.py`).

R8 (arquitectura del proyecto, "las vistas no calculan; llaman"): el cálculo y la escritura en
base de datos no se hacen aquí. Estas vistas reciben la petición HTTP, llaman a `recetas.logica`
y renderizan lo que hace falta.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .acceso import hogar_o_404, obtener_de_mi_hogar_o_404
from .forms import FormularioReceta
from .logica import (
    actualizar_receta,
    con_comidas_legibles,
    crear_receta,
    filas_de_ingredientes,
    recetas_del_hogar,
    validar_ingredientes,
)
from .models import UNIDADES, Receta


def _filas_iniciales(receta):
    """Los ingredientes ya guardados de `receta`, en la misma forma (dict con `cantidad_texto`
    en formato de MÁQUINA, con punto) que usa el formulario para rellenar sus filas al editar —
    `str(Decimal(...))` nunca usa coma, a diferencia de la localización de plantilla."""
    return [
        {"nombre": i.nombre, "cantidad_texto": str(i.cantidad), "unidad": i.unidad}
        for i in receta.ingredientes.all()
    ]


_FILA_VACIA = {"nombre": "", "cantidad_texto": "", "unidad": ""}


def _contexto_formulario(form, filas, errores_ingredientes, modo, receta=None):
    # Siempre al menos una fila visible (R1: "tan fácil como escribirla en una nota" — nunca
    # una pantalla sin ningún hueco para el primer ingrediente).
    return {
        "form": form,
        "filas_mostradas": filas or [_FILA_VACIA],
        "fila_vacia": _FILA_VACIA,
        "errores_ingredientes": errores_ingredientes,
        "unidades": UNIDADES,
        "modo": modo,
        "receta": receta,
    }


@login_required
def lista(request):
    """R7/§8 — todas las recetas del hogar de quien pregunta. Sin ninguna, la pantalla lo dice
    con naturalidad y ofrece apuntar la primera (la propia plantilla)."""
    hogar = hogar_o_404(request)
    return render(request, "recetas/lista.html", {"recetas": recetas_del_hogar(hogar)})


@login_required
def detalle(request, receta_id):
    """R1/R4 — abre una receta con sus ingredientes intactos. `obtener_de_mi_hogar_o_404` es la
    puerta de R4: de otro hogar, 404, nunca 403."""
    receta = obtener_de_mi_hogar_o_404(request, Receta, id=receta_id)
    con_comidas_legibles(receta)
    return render(request, "recetas/detalle.html", {"receta": receta})


@login_required
def nueva(request):
    """R1/R2/R3/R5 — apunta una receta nueva con sus ingredientes. Nombre, raciones y al menos
    un ingrediente son obligatorios; comidas y preparación, opcionales (R2)."""
    hogar = hogar_o_404(request)
    if request.method == "POST":
        form = FormularioReceta(request.POST)
        filas = filas_de_ingredientes(request.POST)
        ingredientes, errores_ingredientes = validar_ingredientes(filas)
        if form.is_valid() and not errores_ingredientes:
            receta = crear_receta(hogar, form.cleaned_data, ingredientes)
            return redirect("recetas:detalle", receta_id=receta.id)
    else:
        form = FormularioReceta()
        filas = []
        errores_ingredientes = []
    return render(
        request,
        "recetas/formulario.html",
        _contexto_formulario(form, filas, errores_ingredientes, modo="nueva"),
    )


@login_required
def editar(request, receta_id):
    """R4 — corrige una receta que quizás escribió otra persona del hogar; nadie pide permiso a
    nadie. Reemplaza la lista de ingredientes entera (ver `recetas.logica.actualizar_receta`)."""
    receta = obtener_de_mi_hogar_o_404(request, Receta, id=receta_id)
    if request.method == "POST":
        form = FormularioReceta(request.POST, instance=receta)
        filas = filas_de_ingredientes(request.POST)
        ingredientes, errores_ingredientes = validar_ingredientes(filas)
        if form.is_valid() and not errores_ingredientes:
            actualizar_receta(receta, form.cleaned_data, ingredientes)
            return redirect("recetas:detalle", receta_id=receta.id)
    else:
        form = FormularioReceta(instance=receta)
        filas = _filas_iniciales(receta)
        errores_ingredientes = []
    return render(
        request,
        "recetas/formulario.html",
        _contexto_formulario(form, filas, errores_ingredientes, modo="editar", receta=receta),
    )


@login_required
@require_POST
def borrar(request, receta_id):
    """R6 — borra una receta sin pedir ninguna explicación; la confirmación la pide el
    navegador ANTES de mandar este POST (la plantilla lleva `hx-confirm`/`confirm(...)`). No
    toca la despensa ni ningún otro dato del hogar: solo borra la receta y sus ingredientes
    (`on_delete=CASCADE` de `IngredienteDeReceta.receta`)."""
    receta = obtener_de_mi_hogar_o_404(request, Receta, id=receta_id)
    receta.delete()
    return redirect("recetas:lista")
