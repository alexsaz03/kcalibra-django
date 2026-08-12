"""
La puerta de la despensa (R9, R10, G-43): es DEL HOGAR, así que cualquiera de dentro la ve y
la cambia —añade, corrige y quita, sin pedir permiso a nadie—, y nadie de fuera, tampoco
llamando al servidor con el id exacto de un producto (404, nunca 403).

Mismo mecanismo que `planes/acceso.py` (el precedente exacto de "el hogar también ESCRIBE"),
pero sin la parte de "¿a qué PERSONA del hogar te refieres?": la despensa no cuelga de una
persona —no hay "la despensa DE alguien"—, cuelga directamente del hogar entero. Por eso aquí
no hace falta `persona_del_hogar_o_404`: basta con `hogares.acceso.hogar_actual` (para
listar/añadir, sin ningún id de por medio) y `hogares.acceso.obtener_de_mi_hogar_o_404` (para
tocar un producto concreto por su id, filtrando siempre por el hogar de quien pregunta).
"""

from django.http import Http404

from hogares.acceso import hogar_actual, obtener_de_mi_hogar_o_404

__all__ = ["hogar_actual", "obtener_de_mi_hogar_o_404", "hogar_o_404"]


def hogar_o_404(request):
    """
    El hogar de quien pregunta, o 404 si todavía no tiene ninguno (R14 de `hogares/acceso.py`:
    sin hogar propio no hay ninguna despensa que ver — por ejemplo, mientras se espera que
    otra persona del hogar acepte la solicitud de entrada).
    """
    hogar = hogar_actual(request)
    if hogar is None:
        raise Http404("No existe.")
    return hogar
