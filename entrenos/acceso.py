"""
La puerta de Entrenos (R10, apuntar-un-entreno.md; "Qué NO debe poder jamás: apuntar ni
corregir entrenos de otra persona con cuenta propia", §8 del plano).

A diferencia de `perfiles/acceso.py` o `progreso/acceso.py`, aquí NO hay una mitad "se ve,
pero no se toca": esta unidad no abre ninguna lectura del hogar sobre entrenos ajenos (R-23 los
nombra, pero llega con R-79 en Progreso, otra unidad) ni "de quién es" (personas a cargo,
R-26/R-27, sin construir). Ver, apuntar, corregir y borrar son SIEMPRE sobre uno mismo — es la
"mitad estricta" de `hogares/acceso.py` que menciona el punto 7 del "Cómo" de la especificación,
sin necesitar `hogar_actual` ni `usuario_del_hogar_o_404`: no hay ningún caso "del mismo hogar,
pero no tú" que deba pasar.
"""

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404

Usuario = get_user_model()


def usuario_propio_o_404(request, usuario_id):
    """
    El `Usuario` `usuario_id`, SOLO si es quien pregunta (R10). 404 en cualquier otro caso
    —incluido "existe, pero es de otra persona", del mismo hogar o de otro—, nunca 403: mismo
    principio que `hogares/acceso.py` y `perfiles/acceso.py:perfil_propio_o_404`.
    """
    if str(request.user.id) != str(usuario_id):
        raise Http404("No existe.")
    return get_object_or_404(Usuario, pk=usuario_id)
