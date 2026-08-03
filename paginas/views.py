from django.shortcuts import render
from django.utils import timezone

from planes.logica import resumen_del_dia


def inicio(request):
    """
    R1-R11 (unidad 005) — el Inicio de verdad. Portada pública para quien no tiene sesión
    (unidad 002/003, intacta: "está viva" sigue siendo lo primero que se ve). Para quien SÍ
    tiene sesión, esto ya no es una demo: es la pantalla de negocio de la unidad, una tarjeta
    por persona del hogar —la propia SIEMPRE la primera, R4/G-152— con sus calorías, sus
    macros, el anillo de cuánto cubre su plan de HOY (R2/R3/R11) y sus comidas, o el botón de
    apuntarlas si no tiene ninguna (R5).
    """
    if not request.user.is_authenticated:
        return render(request, "paginas/inicio.html")

    hogar = request.user.hogar
    # H2 de la revisión: mientras espera que le acepten en otro hogar (R14 de la unidad 003,
    # el mismo estado que ya se había pasado por alto en el perfil propio de la unidad 004),
    # `request.user.hogar` es `None`. Todavía no hay "hogar" del que sacar las tarjetas de
    # nadie más (se enseña solo la suya) NI del que colgar un plan (`PlanDeDia.hogar` es
    # obligatorio): `hogar_pendiente` se lleva a la plantilla para que NO ofrezca el botón de
    # "Apuntar el plan" en ese estado — sería un enlace muerto (404 al pulsarlo) — y explique
    # por qué en su lugar, en vez de una salida que no lleva a ningún sitio.
    hogar_pendiente = hogar is None
    if hogar_pendiente:
        miembros = [request.user]
    else:
        # G-152: la propia SIEMPRE la primera; el resto, detrás, sin más criterio de orden.
        todos = list(hogar.miembros.order_by("date_joined"))
        miembros = [request.user] + [m for m in todos if m.id != request.user.id]

    tarjetas = [
        {
            "usuario": miembro,
            "es_propio": miembro.id == request.user.id,
            "hogar_pendiente": hogar_pendiente,
            **resumen_del_dia(miembro),
        }
        for miembro in miembros
    ]

    return render(request, "paginas/inicio.html", {"tarjetas": tarjetas})


def hora_servidor(request):
    """
    Endpoint al que llama el botón de HTMX (R5). Solo devuelve el TROZO de plantilla llamado
    "hora_servidor" (no la página entera): por eso HTMX puede sustituir únicamente ese trozo
    sin recargar nada más.

    La sintaxis "plantilla.html#nombre_del_partial" es de django-template-partials: pide el
    mismo partial que ya está empotrado dentro de inicio.html (R4), reutilizado aquí suelto.
    """
    return render(
        request,
        "paginas/inicio.html#hora_servidor",
        {"hora": timezone.localtime().strftime("%H:%M:%S")},
    )
