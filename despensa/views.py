"""
La pantalla de la despensa (unidad 014, llevar-la-despensa.md): lo que hay en casa, agrupado
por categorías (R8), con el formulario para añadir (R1-R3) y, en cada línea, para corregir
(R5/R7) o quitar (R6). Es DEL HOGAR entero, no de una persona (G-43): no hay "la despensa DE
alguien" — a diferencia de `entrenos/views.py` o `perfiles/views.py`, ninguna vista de aquí
recibe un `persona_id` en la URL; todas trabajan sobre EL HOGAR de quien pregunta
(`despensa/acceso.py`). R9/R10 — cualquiera del hogar ve y cambia sin pedir permiso a nadie;
nadie de fuera, ni siquiera adivinando el id de un producto (404, nunca 403).

R8 (arquitectura del proyecto, "las vistas no calculan; llaman"): el cálculo (agrupar por
categoría, sumar, fundir) no se hace aquí. Estas vistas reciben la petición HTTP, llaman a
`despensa.logica` y renderizan lo que devuelve.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .acceso import hogar_o_404, obtener_de_mi_hogar_o_404
from .forms import FormularioCorregirProducto, FormularioProducto
from .logica import anadir_producto, corregir_producto, productos_por_categoria, quitar_producto
from .models import CATEGORIAS, UNIDADES, ProductoDespensa

# La sintaxis "plantilla.html#nombre" es de django-template-partials (ya en uso desde la
# unidad 002): pide SOLO ese trozo, para que HTMX lo sustituya sin recargar nada más.
NOMBRE_DEL_PARTIAL = "despensa/ver.html#despensa_del_hogar"


def _contexto(hogar, form=None, error_correccion=None):
    return {
        "categorias_productos": productos_por_categoria(hogar),
        "form": form if form is not None else FormularioProducto(),
        "unidades": UNIDADES,
        "categorias": CATEGORIAS,
        "error_correccion": error_correccion,
    }


def _errores_como_texto(form):
    """Junta los errores de un formulario inválido en una frase, para el aviso genérico de
    R11 en las correcciones de una línea (que no tienen su propio hueco de errores por
    campo, a diferencia del formulario de añadir)."""
    partes = []
    for campo, errores in form.errors.items():
        etiqueta = form.fields[campo].label if campo in form.fields else campo
        partes.append(f"{etiqueta}: {' '.join(errores)}")
    return " · ".join(partes) if partes else "No se pudo guardar la corrección."


@login_required
def ver_despensa(request):
    """R8/R9 — todo lo que hay en el hogar de quien pregunta, agrupado por categorías, con el
    formulario para añadir un producto. R12 — sin ningún producto todavía, `_contexto`
    simplemente devuelve una lista vacía y la plantilla lo dice con naturalidad."""
    hogar = hogar_o_404(request)
    return render(request, "despensa/ver.html", _contexto(hogar))


@login_required
@require_POST
def anadir(request):
    """R1/R2/R3 — añade un producto (o lo suma a una línea ya existente, R-55/G-110/C-57).
    `hogar_o_404` es la puerta de R9: cualquiera del hogar puede llegar aquí, sin pedir
    permiso a nadie."""
    hogar = hogar_o_404(request)
    form = FormularioProducto(request.POST)
    if form.is_valid():
        anadir_producto(hogar, form.cleaned_data)
        form = FormularioProducto()  # formulario limpio, listo para el siguiente producto

    contexto = _contexto(hogar, form=form)
    plantilla = NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "despensa/ver.html"
    return render(request, plantilla, contexto)


@login_required
@require_POST
def corregir(request, producto_id):
    """
    R5/R7 — corrige la cantidad, la unidad y la categoría de un producto. `producto_id` pasa
    por `obtener_de_mi_hogar_o_404` (R10): si es de otro hogar, o no existe, 404 — nunca 403,
    y nunca llega a mirarse el formulario.
    """
    producto = obtener_de_mi_hogar_o_404(request, ProductoDespensa, id=producto_id)
    hogar = producto.hogar
    # Capturada ANTES de construir el formulario: ver el docstring de
    # `despensa.logica.corregir_producto` — `ModelForm(instance=producto).is_valid()` muta
    # `producto.unidad` en sitio, así que después de esa llamada ya sería tarde para saber
    # cuál era la unidad ANTES de corregir.
    unidad_antes = producto.unidad

    form = FormularioCorregirProducto(request.POST, instance=producto)
    error_correccion = None
    if form.is_valid():
        corregir_producto(producto, form.cleaned_data, unidad_antes)
    else:
        # R11 — no se guarda y se dice, sin romper la pantalla: un aviso genérico (la línea
        # en sí ya vuelve a mostrar los valores que tenía antes de la corrección fallida,
        # porque `_contexto` relee la despensa entera desde la base de datos).
        error_correccion = _errores_como_texto(form)

    contexto = _contexto(hogar, error_correccion=error_correccion)
    plantilla = NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "despensa/ver.html"
    return render(request, plantilla, contexto)


@login_required
@require_POST
def quitar(request, producto_id):
    """R6/C-62 — quita un producto sin pedir ninguna explicación. Mismo doble cinturón de R10
    que el resto de la app: `obtener_de_mi_hogar_o_404` exige que `producto_id` sea del hogar
    de quien pregunta."""
    producto = obtener_de_mi_hogar_o_404(request, ProductoDespensa, id=producto_id)
    hogar = producto.hogar
    quitar_producto(producto)

    contexto = _contexto(hogar)
    plantilla = NOMBRE_DEL_PARTIAL if request.headers.get("HX-Request") else "despensa/ver.html"
    return render(request, plantilla, contexto)
