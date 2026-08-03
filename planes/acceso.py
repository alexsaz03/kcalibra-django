"""
La puerta del plan de comidas (R6, R7, G-43): es DEL HOGAR, así que cualquiera de dentro lo ve
y lo cambia —incluido el de otra persona de su misma casa—, pero NADIE de fuera, tampoco
llamando al servidor con la dirección exacta (Q-20).

Reutiliza `hogares.acceso.hogar_actual` TAL CUAL (unidad 003): no se escribe ningún `if hogar
== ...` propio, se llama a la misma función que ya resuelve "el hogar de quien pregunta" para
el resto de la app. La única pieza que aporta este fichero es resolver "¿a qué persona del
hogar de quien pregunta se refiere este `usuario_id`?": hace falta porque `Usuario` no es un
`ModeloDeHogar` (lo es `PlanDeDia`), y "apuntar el plan" puede ser la PRIMERA comida del día,
sin ningún `PlanDeDia` todavía que la puerta de `hogares.acceso.obtener_de_mi_hogar_o_404`
pudiera filtrar.

Mismo principio que en toda la app: 404, nunca 403 — un objeto de otro hogar es indistinguible
desde fuera de uno que no existe.
"""

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404

from hogares.acceso import hogar_actual

Usuario = get_user_model()


def usuario_del_hogar_o_404(request, usuario_id):
    """
    El `Usuario` `usuario_id`, SOLO si está en el MISMO hogar que quien pregunta (R6: puede
    ser cualquiera del hogar, incluida ella misma — a propósito, es lo contrario de
    `perfiles.acceso`, que solo deja cambiar lo propio). 404 si `usuario_id` es de otro hogar,
    si quien pregunta no tiene hogar todavía (R14 de la unidad 003), o si no existe.
    """
    hogar = hogar_actual(request)
    if hogar is None:
        raise Http404("No existe.")
    return get_object_or_404(Usuario, pk=usuario_id, hogar=hogar)
