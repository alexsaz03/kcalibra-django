"""
La pantalla de Progreso (R1-R11 de la especificación de la unidad 010, "ver-tu-progreso.md"
del mapa): la evolución del peso —y, si las hay, de la grasa y la cintura— de la persona
elegida, en el periodo elegido (R-78, R-81).

Unidad 013 (completar-progreso.md) AÑADE aquí mismo los entrenos por semanas (R-79) y el
cumplimiento (R-80): la 010 dejó la pantalla parcial a propósito porque `Entreno` y
`CierreDeDia` no existían todavía (los crearon la 011 y la 012); ahora sí, y con esta unidad
`ver-tu-progreso` pasa a ENTREGADA.

R8 (ROADMAP: "las vistas no calculan; llaman") — esta vista solo reúne los datos (las
`MedicionPeso`, `Entreno` y `CierreDeDia` de la persona elegida) y llama a
`servicios.progreso`, que hace TODO el cálculo: recortar por periodo, agrupar por semana,
contar el cumplimiento y sacar las coordenadas del SVG. Esta vista no suma, no promedia, no
decide qué semanas caen dentro de nada de eso — vive en `servicios/progreso.py`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from servicios.progreso import (
    SEMANAS_MAX,
    SEMANAS_MIN,
    agrupar_entrenos_por_semana,
    calcular_cumplimiento,
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

    # R-79/R1/R2/C-89 — los entrenos REALIZADOS de esa persona, y solo de ella (mismo criterio
    # que las mediciones de arriba: `usuario_objetivo.entrenos` ya viene filtrado por el
    # `related_name` de `Entreno`, sin ningún filtro adicional que pudiera mezclar el hogar).
    # `recortar_por_periodo` es la MISMA función que ya usa el peso (Cómo, punto 3): solo mira
    # la clave "fecha", así que sirve tal cual sin escribir una segunda resta de fechas.
    entrenos = list(usuario_objetivo.entrenos.values("fecha", "minutos", "calorias"))
    entrenos_del_periodo = recortar_por_periodo(entrenos, semanas, hoy)
    semanas_de_entreno = agrupar_entrenos_por_semana(entrenos_del_periodo, hoy)

    # R-80/R3/R4/R5/R10/C-87 — el cumplimiento de esa persona, y solo de ella (mismo criterio:
    # `usuario_objetivo.cierres_de_dia`, sin mezclar el hogar). El porcentaje se calcula sobre
    # los cierres YA recortados por periodo, nunca sobre el número de días del periodo
    # (Q-153/C-87: es el error que un humano cometería leyendo R-80 deprisa).
    cierres = list(usuario_objetivo.cierres_de_dia.values("fecha", "respuesta"))
    cierres_del_periodo = recortar_por_periodo(cierres, semanas, hoy)
    cumplimiento = calcular_cumplimiento(cierres_del_periodo)

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
        # R-79/R1/R6 — la sección de entrenos entera desaparece si no hay ninguno en el
        # periodo (G-172: mismo trato que ya reciben grasa y cintura), en vez de enseñar un
        # hueco vacío o una fila a cero.
        "semanas_de_entreno": semanas_de_entreno,
        # R-80/R3/R4/R5 — el cumplimiento SIEMPRE se enseña (a diferencia de los entrenos): con
        # cero cierres, la plantilla lo dice con naturalidad en vez de esconder la sección
        # entera (R5 es explícito: "la pantalla sigue entera").
        "cumplimiento": cumplimiento,
    }
    return render(request, "progreso/ver.html", contexto)
