"""
La lógica de negocio del perfil: crear el perfil y la primera medición al dar de alta a
alguien (R7), calcular el objetivo del día uniendo el perfil de una persona con su peso
reciente (R7/R34), y qué pasa al cambiar de objetivo (R5/R6). Vive separada de las vistas,
igual que `hogares/logica.py`: las vistas se limitan a "recibir la petición HTTP y llamar
aquí" — es la misma convención que ya sigue esta app (ver AGENTS.md del repo).

R8 (arquitectura): el CÁLCULO en sí —la fórmula— vive entera en `servicios.metabolismo`, que
no toca la base de datos. Este fichero es la pieza que SÍ toca la base de datos (consulta el
peso reciente, lee el perfil) y luego llama a `servicios.metabolismo` con los números ya
reunidos. Ninguna vista llama a `servicios.metabolismo` directamente: siempre pasan por aquí.
"""

from datetime import timedelta

from django.db import models as django_models
from django.utils import timezone

from servicios import metabolismo

from .models import MedicionPeso, Perfil


def crear_perfil_desde_alta(usuario, datos):
    """
    Crea el `Perfil` de `usuario` con lo que rellenó en el formulario de alta, y su PRIMERA
    medición de peso (R7: "el peso que se teclea al crear la cuenta es la primera medición,
    con su fecha"). `datos` es el `cleaned_data` del formulario de alta — ya validado por
    Django antes de llegar aquí (R11: los datos imposibles se rechazan al entrar, no aquí).
    """
    ajuste_pct = datos.get("ajuste_pct")
    if ajuste_pct in (None, ""):
        # Sin ajuste manual: el de fábrica del objetivo elegido (R4/G-60, "Cómo": "si quiso
        # ajustó a mano su porcentaje" — quien no quiso, se queda con el de fábrica).
        ajuste_pct = metabolismo.OBJETIVOS[datos["objetivo"]]["ajuste_pct"]

    perfil = Perfil.objects.create(
        usuario=usuario,
        sexo=datos["sexo"],
        fecha_nacimiento=datos["fecha_nacimiento"],
        altura_cm=datos["altura_cm"],
        actividad=datos["actividad"],
        objetivo=datos["objetivo"],
        ajuste_pct=ajuste_pct,
        dieta=datos.get("dieta", "") or "",
        alergias=datos.get("alergias", "") or "",
        intolerancias=datos.get("intolerancias", "") or "",
        no_le_gusta=datos.get("no_le_gusta", "") or "",
    )
    MedicionPeso.objects.create(
        usuario=usuario, fecha=timezone.localdate(), peso_kg=datos["peso_kg"]
    )
    return perfil


def peso_medio_7_dias(usuario):
    """
    R7/G-61 — la MEDIA de las mediciones de los últimos 7 días de esa persona, no la última
    suelta ("el peso de un día concreto oscila por cosas que no son grasa"). Si por lo que
    sea no hay ninguna medición en ese rango (no debería pasar tras el alta, que siempre crea
    la primera), cae a la última medición que exista, y `None` si de verdad no hay ninguna.
    """
    limite = timezone.localdate() - timedelta(days=7)
    mediciones_recientes = usuario.mediciones_peso.filter(fecha__gte=limite)
    promedio = mediciones_recientes.aggregate(media=django_models.Avg("peso_kg"))["media"]
    if promedio is not None:
        return float(promedio)

    ultima = usuario.mediciones_peso.order_by("-fecha").first()
    return float(ultima.peso_kg) if ultima else None


def calcular_objetivo_del_dia(usuario):
    """
    Une el perfil de `usuario` con su peso reciente y llama a `servicios.metabolismo` (R8: la
    fórmula solo vive ahí, esta función no la repite). Devuelve `None` si a esa persona
    todavía no le corresponde ningún cálculo (sin perfil, o sin ninguna medición de peso —
    ninguno de los dos debería pasar una vez completada el alta, pero se contempla).
    """
    try:
        perfil = usuario.perfil
    except Perfil.DoesNotExist:
        return None

    peso_kg = peso_medio_7_dias(usuario)
    if peso_kg is None:
        return None

    resultado = metabolismo.calcular_perfil_nutricional(
        sexo=perfil.sexo,
        fecha_nacimiento=perfil.fecha_nacimiento,
        altura_cm=perfil.altura_cm,
        peso_kg=peso_kg,
        actividad=perfil.actividad,
        objetivo=perfil.objetivo,
        ajuste_pct=perfil.ajuste_pct,
    )
    resultado["peso_kg"] = round(peso_kg, 1)
    return resultado


def cambiar_objetivo(perfil, objetivo_nuevo):
    """
    R5/G-60 — al cambiar de objetivo, el ajuste vuelve SIEMPRE al de fábrica del objetivo
    nuevo, aunque hubiera uno puesto a mano y aunque eso lo pierda sin avisar: "un ajuste
    hecho a medida de un objetivo no vale para otro" (G-60, textual). No modifica la
    proteína por kilo (no es un campo del perfil: la calcula `servicios.metabolismo` a
    partir del objetivo, R6 "la proteína por kilo no se toca nunca"). No guarda: quien llama
    decide cuándo persistir (ver `perfiles/views.py`).
    """
    perfil.objetivo = objetivo_nuevo
    perfil.ajuste_pct = metabolismo.OBJETIVOS[objetivo_nuevo]["ajuste_pct"]
    return perfil
