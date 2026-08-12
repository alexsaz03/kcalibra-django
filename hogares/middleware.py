"""
Resuelve al vuelo la petición de entrada de quien está esperando (R7, Q-10), sin necesidad de
ningún proceso en segundo plano (no hay Celery ni cron en esta unidad — bias: mínimo código).

Si alguien pasa la hora de plazo sin que nadie de un hogar la acepte, tiene que quedar con su
propio hogar EN CUANTO se comprueba, no solo cuando alguien del hogar mira la lista de
pendientes (eso ya lo cubre `mi_hogar`, ver `hogares/views.py`). Este middleware cubre el otro
lado: la propia persona que pidió entrar, la primera vez que hace cualquier petición después de
cumplirse la hora, sin tener que visitar ninguna pantalla del hogar.
"""

from .logica import resolver_solicitudes_caducadas
from .models import persona_de


class ResolverSolicitudesDelUsuarioMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated:
            # Unidad 023 — el hogar cuelga de la persona, no de la cuenta. `persona_de` deja
            # el resultado cacheado en la instancia, así que esta consulta la aprovechan
            # después las puertas de la propia petición: no es una consulta "de más".
            persona = persona_de(usuario)
            if persona is not None and persona.hogar_id is None:
                # Solo puede tener una solicitud pendiente a la vez (o ninguna, si aún no ha
                # metido ningún código): una sola consulta, barata, y solo para quien de
                # verdad está en ese estado transitorio.
                resolver_solicitudes_caducadas(usuario=usuario)
        return self.get_response(request)
