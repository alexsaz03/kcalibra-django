"""
La puerta del perfil de una persona (R9, G-43): todo el hogar VE el perfil de cualquier
miembro, pero solo su propia dueña puede CAMBIARLO — nadie más, tampoco llamando al servidor
con el id exacto (R9, Q-20).

Mismo principio que `hogares/acceso.py` (la puerta única del aislamiento por hogar de la
unidad 003): la ruta de ESCRITURA responde 404 si no es el perfil de quien pregunta, nunca
403 — un 403 confirmaría "existe, pero no es tuyo"; un 404 es indistinguible de "no existe".
Aquí la VISIBILIDAD es más amplia que en `hogares/acceso.py` (cualquiera del hogar ve
cualquier perfil del hogar, no solo el suyo): son dos puertas distintas a propósito.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Perfil


def perfil_visible_o_404(request, usuario_id):
    """
    El `Perfil` de `usuario_id`, si esa persona está en el MISMO hogar que quien pregunta
    (R9: "todo el hogar lo ve"). 404 si es de otro hogar, o si no existe.
    """
    hogar = request.user.hogar
    if hogar is None:
        # Sin hogar propio todavía (R14 de la unidad 003) no hay nada que ver de nadie.
        raise Http404("No existe.")
    return get_object_or_404(Perfil, usuario_id=usuario_id, usuario__hogar=hogar)


def perfil_propio_o_404(request, usuario_id):
    """
    El `Perfil` de `usuario_id`, SOLO si es el de quien pregunta (R9: nadie más puede
    cambiarlo). 404 en cualquier otro caso — incluido "existe, pero es de otra persona": no
    se distingue de "no existe" (mismo principio que `hogares/acceso.py`).
    """
    if str(request.user.id) != str(usuario_id):
        raise Http404("No existe.")
    return get_object_or_404(Perfil, usuario_id=usuario_id)
