"""
La puerta de las recetas (R4/R-70): son DEL HOGAR, así que cualquiera de dentro las ve, las
edita y las borra sin pedir permiso a nadie, y nadie de fuera — tampoco llamando al servidor con
el id exacto de una receta (404, nunca 403).

Copia literal de `despensa/acceso.py` (mismo mecanismo, mismo motivo): no hace falta
`persona_del_hogar_o_404` porque una receta no cuelga de una persona, cuelga del hogar entero.
Basta con `hogares.acceso.hogar_actual` (para listar/crear, sin ningún id de por medio) y
`hogares.acceso.obtener_de_mi_hogar_o_404` (para tocar una receta concreta por su id, filtrando
siempre por el hogar de quien pregunta).
"""

from django.http import Http404

from hogares.acceso import hogar_actual, obtener_de_mi_hogar_o_404

__all__ = ["hogar_actual", "obtener_de_mi_hogar_o_404", "hogar_o_404"]


def hogar_o_404(request):
    """El hogar de quien pregunta, o 404 si todavía no tiene ninguno (mientras espera que le
    acepten en el hogar de otra persona)."""
    hogar = hogar_actual(request)
    if hogar is None:
        raise Http404("No existe.")
    return hogar
