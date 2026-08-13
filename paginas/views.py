from django.shortcuts import render
from django.utils import timezone

from cierres.logica import dia_pendiente_de_preguntar
from hogares.acceso import persona_actual
from planes.logica import obtener_plan_de, resumen_del_dia


def inicio(request):
    """
    R1-R11 (unidad 005) — el Inicio de verdad. Portada pública para quien no tiene sesión
    (unidad 002/003, intacta: "está viva" sigue siendo lo primero que se ve). Para quien SÍ
    tiene sesión, esto ya no es una demo: es la pantalla de negocio de la unidad, una tarjeta
    por persona del hogar —la propia SIEMPRE la primera, R4/G-152— con sus calorías, sus
    macros, el anillo de cuánto cubre su plan de HOY (R2/R3/R11) y sus comidas, o el botón de
    apuntarlas si no tiene ninguna (R5).

    R6-R9 (unidad 012, decir-si-cumpliste.md) — "la pregunta al abrir vive en
    paginas/views.py:inicio... no la metas en base.html", porque el plano dice "al abrir la
    app" (esta pantalla), no "en todas partes". Es SIEMPRE sobre la propia persona (G-162:
    "cada persona del hogar con cuenta" contesta la suya, nunca la de otra): por eso se calcula
    para la persona de quien mira, no para cada tarjeta del hogar.
    """
    if not request.user.is_authenticated:
        return render(request, "paginas/inicio.html")

    yo = persona_actual(request)
    hogar = yo.hogar
    # H2 de la revisión: mientras espera que le acepten en otro hogar (R14 de la unidad 003,
    # el mismo estado que ya se había pasado por alto en el perfil propio de la unidad 004),
    # la persona no tiene hogar todavía. No hay "hogar" del que sacar las tarjetas de
    # nadie más (se enseña solo la suya) NI del que colgar un plan (`PlanDeDia.hogar` es
    # obligatorio): `hogar_pendiente` se lleva a la plantilla para que NO ofrezca el botón de
    # "Apuntar el plan" en ese estado — sería un enlace muerto (404 al pulsarlo) — y explique
    # por qué en su lugar, en vez de una salida que no lleva a ningún sitio.
    hogar_pendiente = hogar is None
    if hogar_pendiente:
        miembros = [yo]
    else:
        # G-152: la propia SIEMPRE la primera; el resto, detrás, sin más criterio de orden.
        todos = list(hogar.miembros.select_related("usuario").order_by("usuario__date_joined"))
        miembros = [yo] + [m for m in todos if m.id != yo.id]

    tarjetas = [
        {
            "persona": miembro,
            "es_propio": miembro.id == yo.id,
            "hogar_pendiente": hogar_pendiente,
            **resumen_del_dia(miembro),
        }
        for miembro in miembros
    ]

    dia_pendiente = dia_pendiente_de_preguntar(yo)
    plan_pendiente = obtener_plan_de(yo, dia_pendiente) if dia_pendiente else None

    return render(
        request,
        "paginas/inicio.html",
        {
            "tarjetas": tarjetas,
            "dia_pendiente": dia_pendiente,
            "plan_pendiente": plan_pendiente,
        },
    )


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
