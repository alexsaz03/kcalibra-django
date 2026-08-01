from django.shortcuts import render
from django.utils import timezone


def inicio(request):
    """
    Portada del esqueleto (R1). Demuestra que la app arranca y responde; no hace nada útil
    todavía, a propósito: eso llega en las siguientes unidades.
    """
    return render(request, "paginas/inicio.html")


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
