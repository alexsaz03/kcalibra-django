"""
La lógica de negocio del hogar: qué pasa al verificar un correo con código pendiente, y cómo
se resuelven las peticiones caducadas. Vive separada de las vistas para que las vistas se
limiten a "recibir la petición HTTP y llamar aquí" (el AGENTS.md del repo pide justo eso: las
vistas llaman a la capa de lógica, nunca calculan ellas mismas).
"""

from django.db import transaction
from django.utils import timezone

from .models import Hogar, SolicitudEntrada, crear_hogar_propio


def procesar_codigo_al_verificar(usuario) -> None:
    """
    Se llama en el instante en que `usuario` verifica su correo (ver `hogares/signals.py`,
    enganchado a la señal `email_confirmed` de allauth). Es el punto exacto que exige R5/G-37:
    "la petición no sale hasta que verifica, y antes de eso el hogar no sabe que existe".

    Si `usuario` se registró sin código o con uno inválido, `codigo_hogar_pendiente` está
    vacío y aquí no hay nada que hacer (ya tiene su propio hogar desde el alta, ver
    `cuentas.forms.FormularioAlta`). Si se registró con un código válido, es AHORA cuando se
    crea la `SolicitudEntrada`: antes de este momento el hogar de destino no tenía ninguna fila
    que lo relacionara con esta persona.
    """
    codigo = usuario.codigo_hogar_pendiente
    if not codigo:
        return

    with transaction.atomic():
        hogar = Hogar.objects.filter(codigo=codigo).first()
        usuario.codigo_hogar_pendiente = ""
        usuario.save(update_fields=["codigo_hogar_pendiente"])

        if hogar is None:
            # El hogar existía al registrarse pero desapareció mientras tanto (no debería
            # pasar en esta unidad, donde los hogares no se borran nunca, pero no dejamos a
            # la persona sin hogar bajo ningún escenario).
            crear_hogar_propio(usuario)
            return

        SolicitudEntrada.objects.create(
            hogar=hogar,
            usuario=usuario,
            creada_en=timezone.now(),
        )


def resolver_solicitudes_caducadas(*, hogar=None, usuario=None) -> int:
    """
    Busca solicitudes PENDIENTES que ya pasaron su hora de plazo (Q-10, G-34) y las cierra:
    las marca CADUCADAS y le monta a quien pedía entrar su propio hogar (R7) — exactamente lo
    mismo que un rechazo explícito, salvo que nadie ha dicho que no, se ha acabado el tiempo.

    Se puede acotar por `hogar` (para cuando alguien mira "mi hogar": resuelve solo las suyas)
    o por `usuario` (para cuando la propia persona que pidió entrar hace cualquier petición:
    resuelve solo la suya, ver `hogares/middleware.py`). Sin acotar, resuelve todas — pensado
    para un futuro comando de mantenimiento, no se usa así en esta unidad.

    Devuelve cuántas solicitudes resolvió, para que quien llama pueda decidir si merece la
    pena refrescar lo que tenía leído.
    """
    qs = SolicitudEntrada.objects.filter(estado=SolicitudEntrada.PENDIENTE)
    if hogar is not None:
        qs = qs.filter(hogar=hogar)
    if usuario is not None:
        qs = qs.filter(usuario=usuario)

    resueltas = 0
    # No hay atajo de "UPDATE masivo" porque cada fila resuelta implica TAMBIÉN crear un hogar
    # propio para su usuario (una escritura en otra tabla), así que se recorren una a una.
    for solicitud in qs.select_related("usuario"):
        if not solicitud.ha_caducado():
            continue
        with transaction.atomic():
            solicitud.estado = SolicitudEntrada.CADUCADA
            solicitud.resuelta_en = timezone.now()
            solicitud.save(update_fields=["estado", "resuelta_en"])
            crear_hogar_propio(solicitud.usuario)
        resueltas += 1
    return resueltas
