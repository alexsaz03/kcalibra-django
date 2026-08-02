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


class ResolverSolicitudesDelUsuarioMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and usuario.hogar_id is None:
            # Solo puede tener una solicitud pendiente a la vez (o ninguna, si aún no ha
            # metido ningún código): una sola consulta, barata, y solo para quien de verdad
            # está en ese estado transitorio.
            resolver_solicitudes_caducadas(usuario=usuario)
        return self.get_response(request)
