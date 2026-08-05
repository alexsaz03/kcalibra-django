"""
La puerta de Cerrar el día (R12, decir-si-cumpliste.md; §8 "Qué NO debe poder jamás: cerrar el
día de otra persona con cuenta propia").

Copiado de `entrenos/acceso.py` (unidad 011): igual que los entrenos, esto NO abre ninguna
lectura del hogar sobre cierres ajenos ("personas a cargo" —R-26/R-27— sigue sin construir) ni
"de quién es". Cerrar y cambiar un cierre son SIEMPRE sobre uno mismo — la "mitad estricta" de
`hogares/acceso.py`, sin necesitar `hogar_actual` ni `usuario_del_hogar_o_404`.
"""

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404

Usuario = get_user_model()


def usuario_propio_o_404(request, usuario_id):
    """
    El `Usuario` `usuario_id`, SOLO si es quien pregunta (R12). 404 en cualquier otro caso
    —incluido "existe, pero es de otra persona", del mismo hogar o de otro—, nunca 403: mismo
    principio que `entrenos/acceso.py` y `hogares/acceso.py`.
    """
    if str(request.user.id) != str(usuario_id):
        raise Http404("No existe.")
    return get_object_or_404(Usuario, pk=usuario_id)
