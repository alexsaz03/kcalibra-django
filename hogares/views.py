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
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from perfiles.logica import crear_perfil_desde_alta

from .acceso import obtener_de_mi_hogar_o_404, persona_actual
from .forms import FormularioAltaPersonaACargo
from .logica import crear_hogar_propio, resolver_solicitudes_caducadas
from .models import Persona, SolicitudEntrada, persona_de


def _contexto_mi_hogar(hogar, form):
    """Reúne lo que pinta "mi hogar" (R3/R100): la lista de miembros —con su nombre, quién
    entra con su cuenta y, si no entra, quién es su responsable— y las peticiones pendientes.
    Compartido entre el GET normal y el POST inválido del alta de abajo, para no repetir la
    misma consulta dos veces en el fichero."""
    # Unidad 024 — `select_related("responsable")` trae de la misma consulta el nombre del
    # responsable de una persona a cargo (R100: "para las que no [entran], quién es su
    # responsable"), sin una consulta extra por fila.
    miembros = hogar.miembros.select_related("usuario", "responsable").order_by(
        "usuario__date_joined"
    )
    pendientes = (
        SolicitudEntrada.del_hogar(hogar)
        .filter(estado=SolicitudEntrada.PENDIENTE)
        .select_related("usuario", "usuario__persona")
        .order_by("creada_en")
    )
    return {"hogar": hogar, "miembros": miembros, "pendientes": pendientes, "form": form}


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

    contexto = _contexto_mi_hogar(hogar, form=FormularioAltaPersonaACargo())
    return render(request, "hogares/mi_hogar.html", contexto)


@login_required
@require_POST
def dar_de_alta_persona_a_cargo(request):
    """
    R2/R-99 — Alejandro da de alta a Euridice, que no tiene ni tendrá cuenta: su ficha nace
    con su nombre, sus datos físicos y su objetivo, y con Alejandro (quien la da de alta) como
    su `responsable` — el único que podrá cambiarle sus datos después (R4).

    `crear_perfil_desde_alta` es la MISMA función que usa el alta de una cuenta con cuenta
    propia (`cuentas/forms.py:FormularioAlta.signup`): con ella, el objetivo diario de Euridice
    se calcula exactamente igual que el de cualquiera (R2, "Cómo" punto 4 — no se duplica el
    cálculo, se reutiliza).
    """
    persona = persona_actual(request)
    hogar = persona.hogar if persona is not None else None
    if hogar is None:
        # Sin hogar propio todavía (R14 de la unidad 003) no hay una casa a la que dar de
        # alta a nadie — mismo criterio que el resto de puertas de esta app (404, nunca 403).
        raise Http404("No existe.")

    form = FormularioAltaPersonaACargo(request.POST)
    if form.is_valid():
        nueva_persona = Persona.objects.create(
            hogar=hogar,
            nombre=form.cleaned_data["nombre"],
            responsable=persona,
        )
        crear_perfil_desde_alta(nueva_persona, form.cleaned_data)
        messages.success(
            request, f"Diste de alta a {nueva_persona.nombre}, a tu cargo."
        )
        return redirect("hogares:mi_hogar")

    # Formulario inválido: se vuelve a pintar "mi hogar" con los errores señalados, sin perder
    # el resto de la pantalla (mismo patrón que perfiles/views.py:actualizar_perfil cuando no
    # hay HTMX de por medio: la pantalla entera, con el formulario que ya tenía).
    resolver_solicitudes_caducadas(hogar=hogar)
    contexto = _contexto_mi_hogar(hogar, form=form)
    return render(request, "hogares/mi_hogar.html", contexto)


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

    # R1/G-196: el aviso se lee en la pantalla de la casa — se llama a quien entra por su
    # nombre, nunca por su correo.
    messages.success(request, f"{persona_solicitante.nombre} ya está dentro del hogar.")
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
