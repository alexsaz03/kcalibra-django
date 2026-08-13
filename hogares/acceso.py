"""
La puerta única del aislamiento por hogar (R9/R14 — criterios de aceptación de la unidad 003,
`docs/05-trabajo/archivo/003-cuentas-y-hogares/especificacion.md` — y Q-11/Q-20, del mapa de
flujos: `crear-cuenta.md` y `darle-cuenta-propia-a-los-de-casa.md`).

Toda vista que necesite un objeto de un `ModeloDeHogar` (la despensa, las recetas, el
calendario de las unidades futuras; aquí, `SolicitudEntrada`) pasa por AQUÍ, no por su propio
`get_object_or_404`. Así el comportamiento es uno solo en toda la app, en vez de un `if hogar
== request.user.persona.hogar` copiado y quizás olvidado en alguna vista nueva:

- Resuelve "quién está usando la app" y "de qué hogar es" en un único sitio (`persona_actual`,
  `hogar_actual`).
- Si el objeto no es de ESE hogar (o no existe), responde 404 ("no existe"), nunca 403
  ("no tienes permiso"): así no se filtra ni la existencia de datos ajenos.

Unidad 023 — la puerta pregunta por PERSONAS, no por cuentas: `usuario_del_hogar_o_404` pasó a
llamarse `persona_del_hogar_o_404` y devuelve una `hogares.Persona`. El comportamiento es el
mismo hasta la última coma (mismo 404, mismas ramas); lo que cambia es de quién cuelga el
hogar, que ya no es del correo con el que se entra.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Persona, persona_de


def persona_actual(request):
    """
    La `Persona` de quien está haciendo la petición. Requiere que `request.user` esté
    autenticado; se asume que la vista ya lo comprobó con `@login_required` (una cuenta sin
    verificar nunca llega aquí autenticada, R14).

    Devuelve `None` solo en el caso que no debería darse: una cuenta sin persona (toda cuenta
    estrena la suya, ver `hogares/signals.py`). Se contempla para que las puertas no revienten
    con una excepción sin sentido si alguna vez ocurriera.
    """
    return persona_de(request.user)


def hogar_actual(request):
    """
    El hogar de quien está haciendo la petición, o `None` si no está en ninguno todavía
    (por ejemplo, mientras espera que le acepten en el hogar de otro — R5).
    """
    persona = persona_actual(request)
    return persona.hogar if persona is not None else None


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


def persona_del_hogar_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si está en el MISMO hogar que quien pregunta (puede ser
    cualquiera del hogar, incluida ella misma). 404 si `persona_id` es de otro hogar, si quien
    pregunta no tiene hogar todavía (R14), o si no existe — nunca 403 (Q-11, Q-20): una
    persona de otro hogar es indistinguible desde fuera de una que no existe.

    Unidad 010 — consolidado aquí desde `planes/acceso.py` (unidad 005), que fue el primero
    en necesitarlo: la misma comprobación ("¿este id es de alguien del MISMO hogar que quien
    pregunta?") vivía duplicada en espíritu entre `planes/acceso.py` y la rama "ajena" de
    `perfiles/acceso.py:perfil_visible_o_404`. `progreso/acceso.py` es la TERCERA aparición —
    la señal de que tocaba subirlo a la puerta única del hogar en vez de escribirlo una cuarta
    vez. Los tres sitios llaman ahora a esta misma función.
    """
    hogar = hogar_actual(request)
    if hogar is None:
        raise Http404("No existe.")
    return get_object_or_404(Persona, pk=persona_id, hogar=hogar)
