"""
La puerta de Progreso (R7, R8, R9 de la especificación de la unidad 010; G-1, R-23, G-171 del
mapa): cualquiera del hogar VE el progreso de cualquiera de dentro, uno cada vez — nadie de
fuera, tampoco llamando al servidor con el id exacto (R9, Q-20).

Es la misma "puerta doble" que ya usa `perfiles/acceso.py:perfil_visible_o_404` (el PROPIO
siempre es visible, esté o no esté todavía en un hogar — H2 de la unidad 004, el estado
"esperando que le acepten"; el de OTRA persona, solo si comparte hogar) pero devolviendo el
`Usuario` en sí, no un `Perfil`: `progreso/` necesita las `MedicionPeso` de esa persona
directamente (`usuario.mediciones_peso`), no sus datos físicos.

La rama "ajena" reutiliza `hogares.acceso.usuario_del_hogar_o_404` (unidad 010: consolidado
desde `planes/acceso.py`, su tercera aparición) en vez de repetir el `if hogar is None /
get_object_or_404(..., hogar=hogar)` una cuarta vez.

Esta puerta es SOLO de lectura: Progreso no tiene ninguna vista de escritura propia (apuntar y
borrar el peso siguen siendo cosa de `perfiles/`, con su propia puerta sin cambios — R8).
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from hogares.acceso import usuario_del_hogar_o_404

Usuario = get_user_model()


def usuario_visible_o_404(request, usuario_id):
    """
    El `Usuario` `usuario_id`: el PROPIO siempre es visible (R7, aunque todavía no tenga
    hogar asignado); el de OTRA persona, solo si está en el MISMO hogar que quien pregunta
    (R7/R-23/G-171: "se ve el de todos, pero uno cada vez"). 404 si es de otro hogar (R9), o
    si no existe — nunca 403 (Q-20).
    """
    if str(request.user.id) == str(usuario_id):
        return get_object_or_404(Usuario, pk=usuario_id)
    return usuario_del_hogar_o_404(request, usuario_id)
