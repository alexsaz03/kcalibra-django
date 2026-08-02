"""
La puerta única del aislamiento por hogar (R9, R14, Q-11, Q-20).

Toda vista que necesite un objeto de un `ModeloDeHogar` (la despensa, las recetas, el
calendario de las unidades futuras; aquí, `SolicitudEntrada`) pasa por AQUÍ, no por su propio
`get_object_or_404`. Así el comportamiento es uno solo en toda la app, en vez de un `if hogar
== request.user.hogar` copiado y quizás olvidado en alguna vista nueva:

- Resuelve "el hogar de quien está usando la app" en un único sitio (`hogar_actual`).
- Si el objeto no es de ESE hogar (o no existe), responde 404 ("no existe"), nunca 403
  ("no tienes permiso"): así no se filtra ni la existencia de datos ajenos.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404


def hogar_actual(request):
    """
    El hogar de quien está haciendo la petición, o `None` si no está en ninguno todavía
    (por ejemplo, mientras espera que le acepten en el hogar de otro — R5). Requiere que
    `request.user` esté autenticado; se asume que la vista ya lo comprobó con
    `@login_required` (una cuenta sin verificar nunca llega aquí autenticada, R14).
    """
    return request.user.hogar


def obtener_de_mi_hogar_o_404(request, modelo, **filtros):
    """
    Trae UN objeto de `modelo` (un `ModeloDeHogar`) que además cumpla `filtros`, pero SOLO si
    pertenece al hogar de quien pregunta. Si pertenece a otro hogar, o no existe, el resultado
    es indistinguible desde fuera: un 404 en los dos casos (Q-11, Q-20, R9).
    """
    hogar = hogar_actual(request)
    if hogar is None:
        # Sin hogar propio no hay nada que ver de ningún hogar (R14): ni siquiera se llega a
        # mirar si el objeto existe.
        raise Http404("No existe.")
    return get_object_or_404(modelo, hogar=hogar, **filtros)
