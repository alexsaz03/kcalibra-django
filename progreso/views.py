"""
La pantalla de Progreso (R1-R11 de la especificación de la unidad 010, "ver-tu-progreso.md"
del mapa): la evolución del peso —y, si las hay, de la grasa y la cintura— de la persona
elegida, en el periodo elegido (R-78, R-81; R-79 "entrenos" y R-80 "cumplimiento" quedan
fuera, sin modelo de datos que las respalde todavía — ver el "Alcance" de la especificación).

R8 (ROADMAP: "las vistas no calculan; llaman") — esta vista solo reúne los datos (las
`MedicionPeso` de la persona elegida) y llama a `servicios.progreso`, que hace TODO el
cálculo: recortar por periodo y sacar las coordenadas del SVG. Esta vista no suma, no
promedia, no decide qué semanas caen dentro de nada de eso — vive en `servicios/progreso.py`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from servicios.progreso import (
    SEMANAS_MAX,
    SEMANAS_MIN,
    construir_evolucion,
    recortar_por_periodo,
    semanas_desde_parametro,
)

from .acceso import usuario_visible_o_404


@login_required
def ver_progreso(request, usuario_id=None):
    """
    R1/R2/R3/R4 — la evolución de peso (y grasa/cintura si las hay) de `usuario_id` en las
    últimas `?semanas=` semanas. Sin `usuario_id`, la propia (enlace de la barra de
    navegación, igual que `perfiles:ver_mio`).

    R5/R6 — el número de semanas llega por la URL: `semanas_desde_parametro` (servicios/
    progreso.py) hace que cualquier entrada rara (ausente, no numérica, fuera de [4, 52])
    caiga al valor por defecto (12) SIN romper la pantalla — al contrario que la unidad 009,
    donde una configuración que no se entiende tumba el arranque a propósito: aquí es
    entrada de una persona por la URL, jamás puede reventar nada.

    R7/R9 — `usuario_visible_o_404` (progreso/acceso.py) deja ver el progreso de cualquiera
    del MISMO hogar; de otro hogar, 404 (R9), nunca 403. R10/G-171 — se calcula SIEMPRE para
    una única persona, `usuario_objetivo`: nunca se suman ni se promedian los datos de dos
    personas del hogar entre sí (no hay ninguna consulta que junte a más de una).
    """
    usuario_id = usuario_id if usuario_id is not None else request.user.id
    usuario_objetivo = usuario_visible_o_404(request, usuario_id)
    es_propio = usuario_objetivo.id == request.user.id

    semanas = semanas_desde_parametro(request.GET.get("semanas"))
    hoy = timezone.localdate()

    # Las mediciones DE ESA PERSONA, y solo de ella (R10/G-171): `usuario_objetivo.
    # mediciones_peso` ya viene filtrado por el `related_name` del modelo, sin ningún filtro
    # adicional que pudiera mezclar el hogar entero por error.
    mediciones = list(
        usuario_objetivo.mediciones_peso.values("fecha", "peso_kg", "grasa_pct", "cintura_cm")
    )
    mediciones_del_periodo = recortar_por_periodo(mediciones, semanas, hoy)
    evolucion = construir_evolucion(mediciones_del_periodo)

    # R81/§8 del plano — "ver el progreso de otra persona de tu casa, una cada vez": el
    # selector ofrece a todo el hogar (la propia primero, mismo criterio de orden que
    # paginas/views.py:inicio, unidad 005). Sin hogar todavía (R14 de la unidad 003,
    # "esperando que le acepten") no hay nadie más que ofrecer: solo la propia.
    hogar = request.user.hogar
    if hogar is None:
        miembros_del_hogar = [request.user]
    else:
        todos = list(hogar.miembros.order_by("date_joined"))
        miembros_del_hogar = [request.user] + [m for m in todos if m.id != request.user.id]

    contexto = {
        "usuario_objetivo": usuario_objetivo,
        "es_propio": es_propio,
        "miembros_del_hogar": miembros_del_hogar,
        "semanas": semanas,
        "semanas_min": SEMANAS_MIN,
        "semanas_max": SEMANAS_MAX,
        "grafica_peso": evolucion["peso_kg"],
        "grafica_grasa": evolucion["grasa_pct"],
        "grafica_cintura": evolucion["cintura_cm"],
        # R11 — distingue "nunca ha apuntado nada" de "tiene datos, pero no en ESTE
        # periodo": son dos mensajes distintos, ninguno de los dos un error.
        "tiene_alguna_medicion": bool(mediciones),
        "tiene_datos_en_periodo": bool(mediciones_del_periodo),
    }
    return render(request, "progreso/ver.html", contexto)
