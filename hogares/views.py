"""
Las pantallas del hogar: el código para invitar, quién está dentro, y las peticiones
pendientes con sus botones de aceptar/rechazar (R1, R5, R7, R8, R9).

Las vistas de aceptar/rechazar pasan SIEMPRE por `obtener_de_mi_hogar_o_404` (la puerta
única de `hogares.acceso`): es lo que garantiza R9 — alguien de fuera del hogar que llame
directamente a la URL, con el id exacto de una solicitud ajena, recibe un 404 idéntico al de
"esa solicitud no existe", nunca un 403 que confirme que sí existe pero en otra casa.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .acceso import obtener_de_mi_hogar_o_404, persona_actual
from .logica import crear_hogar_propio, resolver_solicitudes_caducadas
from .models import SolicitudEntrada, persona_de


@login_required
def mi_hogar(request):
    usuario = request.user
    persona = persona_actual(request)

    if persona is None or persona.hogar_id is None:
        # Está "sola": o bien pidió entrar en un hogar con código y sigue esperando, o su
        # petición se acaba de resolver y todavía no se le ha asignado nada (transitorio,
        # el middleware lo cierra en la siguiente petición). R5, R14.
        solicitud = (
            SolicitudEntrada.objects.filter(
                usuario=usuario, estado=SolicitudEntrada.PENDIENTE
            )
            .select_related("hogar")
            .first()
        )
        return render(request, "hogares/esperando_aceptacion.html", {"solicitud": solicitud})

    hogar = persona.hogar
    # Antes de enseñar la lista de pendientes, se cierran las que ya cumplieron su hora
    # (Q-10, G-34): así quien mira esta pantalla nunca ve (ni puede aceptar) una petición que
    # ya debería estar caducada.
    resolver_solicitudes_caducadas(hogar=hogar)

    # Unidad 023 — `hogar.miembros` son ahora `Persona`, no cuentas. El orden sigue siendo
    # el mismo dato de siempre (cuándo se dio de alta esa cuenta), leído a través de ella;
    # `select_related` lo trae en la misma consulta, sin una por miembro para pintar su correo.
    miembros = hogar.miembros.select_related("usuario").order_by("usuario__date_joined")
    pendientes = (
        SolicitudEntrada.del_hogar(hogar)
        .filter(estado=SolicitudEntrada.PENDIENTE)
        .select_related("usuario")
        .order_by("creada_en")
    )
    return render(
        request,
        "hogares/mi_hogar.html",
        {"hogar": hogar, "miembros": miembros, "pendientes": pendientes},
    )


@login_required
@require_POST
def aceptar_solicitud(request, pk):
    solicitud = obtener_de_mi_hogar_o_404(request, SolicitudEntrada, pk=pk)

    # Comprobación en caliente (no se fía solo del campo `estado`, que puede llevar un rato
    # sin refrescar): una petición caducada nunca se acepta, aunque nadie la hubiera cerrado
    # todavía (Q-10: "una aceptación posterior a esa hora no revive la petición").
    if solicitud.estado != SolicitudEntrada.PENDIENTE or solicitud.ha_caducado():
        _cerrar_como_caducada_si_hace_falta(solicitud)
        messages.error(request, "Esa petición ya no está pendiente: caducó o se resolvió.")
        return redirect("hogares:mi_hogar")

    solicitud.estado = SolicitudEntrada.ACEPTADA
    solicitud.resuelta_en = timezone.now()
    solicitud.resuelta_por = request.user
    solicitud.save(update_fields=["estado", "resuelta_en", "resuelta_por"])

    solicitante = solicitud.usuario
    persona_solicitante = persona_de(solicitante)
    persona_solicitante.hogar = solicitud.hogar
    persona_solicitante.save(update_fields=["hogar"])

    messages.success(request, f"{solicitante.email} ya está dentro del hogar.")
    return redirect("hogares:mi_hogar")


@login_required
@require_POST
def rechazar_solicitud(request, pk):
    solicitud = obtener_de_mi_hogar_o_404(request, SolicitudEntrada, pk=pk)

    if solicitud.estado != SolicitudEntrada.PENDIENTE:
        messages.error(request, "Esa petición ya no está pendiente.")
        return redirect("hogares:mi_hogar")

    if solicitud.ha_caducado():
        _cerrar_como_caducada_si_hace_falta(solicitud)
    else:
        solicitud.estado = SolicitudEntrada.RECHAZADA
        solicitud.resuelta_en = timezone.now()
        solicitud.resuelta_por = request.user
        solicitud.save(update_fields=["estado", "resuelta_en", "resuelta_por"])
        crear_hogar_propio(persona_de(solicitud.usuario))

    messages.success(request, "Petición rechazada.")
    return redirect("hogares:mi_hogar")


def _cerrar_como_caducada_si_hace_falta(solicitud):
    """Si sigue en PENDIENTE en la base de datos pero ya cumplió su hora, la cierra ahora
    mismo (mismo efecto que `resolver_solicitudes_caducadas`, para UNA sola solicitud
    concreta que ya tenemos en mano)."""
    if solicitud.estado == SolicitudEntrada.PENDIENTE:
        solicitud.estado = SolicitudEntrada.CADUCADA
        solicitud.resuelta_en = timezone.now()
        solicitud.save(update_fields=["estado", "resuelta_en"])
        crear_hogar_propio(persona_de(solicitud.usuario))
