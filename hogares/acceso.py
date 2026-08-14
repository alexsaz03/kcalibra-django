"""
La puerta única del aislamiento por hogar (R9/R14 — criterios de aceptación de la unidad 003,
`docs/05-trabajo/archivo/003-cuentas-y-hogares/especificacion.md` — y Q-11/Q-20, del mapa de
flujos: `crear-cuenta.md` y `darle-cuenta-propia-a-los-de-casa.md`).

Toda vista que necesite un objeto de un `ModeloDeHogar` (la despensa, las recetas, el
calendario de las unidades futuras; aquí, `SolicitudEntrada`) pasa por AQUÍ, no por su propio
`get_object_or_404`. Así el comportamiento es uno solo en toda la app, en vez de un `if hogar
== request.user.persona.hogar` copiado y quizás olvidado en alguna vista nueva:

- Resuelve "quién está usando la app" y "de qué hogar es" en un único sitio (`persona_actual`,
  `hogar_actual`).
- Si el objeto no es de ESE hogar (o no existe), responde 404 ("no existe"), nunca 403
  ("no tienes permiso"): así no se filtra ni la existencia de datos ajenos.

Unidad 023 — la puerta pregunta por PERSONAS, no por cuentas: `usuario_del_hogar_o_404` pasó a
llamarse `persona_del_hogar_o_404` y devuelve una `hogares.Persona`. El comportamiento es el
mismo hasta la última coma (mismo 404, mismas ramas); lo que cambia es de quién cuelga el
hogar, que ya no es del correo con el que se entra.

Unidad 025 — se suma la OTRA mitad de G-43 ("lo de una persona lo cambia solo ella, o su
responsable si es una persona a cargo"): `puede_cambiar_lo_de` y `persona_editable_o_404`, de
aquí abajo. Es la puerta única que usan `perfiles/`, `entrenos/` y `cierres/` para decidir
quién puede CAMBIAR los datos de una persona — antes vivía triplicada en espíritu (o, en
`entrenos/`/`cierres/`, ni existía: autoescritura estrictamente propia).
"""

from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Persona, persona_de


def persona_actual(request):
    """
    La `Persona` de quien está haciendo la petición. Requiere que `request.user` esté
    autenticado; se asume que la vista ya lo comprobó con `@login_required` (una cuenta sin
    verificar nunca llega aquí autenticada, R14).

    Devuelve `None` solo en el caso que no debería darse: una cuenta sin persona (toda cuenta
    estrena la suya, ver `hogares/signals.py`). Se contempla para que las puertas no revienten
    con una excepción sin sentido si alguna vez ocurriera.
    """
    return persona_de(request.user)


def hogar_actual(request):
    """
    El hogar de quien está haciendo la petición, o `None` si no está en ninguno todavía
    (por ejemplo, mientras espera que le acepten en el hogar de otro — R5).
    """
    persona = persona_actual(request)
    return persona.hogar if persona is not None else None


def obtener_de_mi_hogar_o_404(request, modelo, **filtros):
    """
    Trae UN objeto de `modelo` (un `ModeloDeHogar`) que además cumpla `filtros`, pero SOLO si
    pertenece al hogar de quien pregunta. Si pertenece a otro hogar, o no existe, el resultado
    es indistinguible desde fuera: un 404 en los dos casos (Q-11, Q-20, R9).
    """
    hogar = hogar_actual(request)
    if hogar is None:
        # Sin hogar propio no hay nada que ver de ningún hogar (R14): ni siquiera se llega a
        # mirar si el objeto existe.
        raise Http404("No existe.")
    return get_object_or_404(modelo, hogar=hogar, **filtros)


def puede_cambiar_lo_de(request, persona_id) -> bool:
    """
    ¿Puede quien hace la petición CAMBIAR los datos de `persona_id`? Es la propia persona, o
    su RESPONSABLE si `persona_id` es una persona a cargo (G-43, R-99) — la mitad de "cambiar"
    de la regla G-43 ("lo de una persona lo cambia solo ella, o su responsable si es una
    persona a cargo"), nunca 403 (Q-20): quien llama decide qué hacer con el `False` (404,
    siempre — ver `persona_editable_o_404` de aquí abajo).

    Unidad 025 — puerta ÚNICA del proyecto para esta pregunta. Antes vivía duplicada en
    espíritu en `perfiles/acceso.py` (`_es_su_responsable`, que además consultaba `Perfil` en
    vez de `Persona.responsable` — el defecto que R7 de la especificación viene a cerrar), y
    no existía en absoluto en `entrenos/` ni en `cierres/` (autoescritura estrictamente
    propia hasta esta unidad). `perfiles/`, `entrenos/` y `cierres/` delegan aquí.

    Se decide sobre `Persona.responsable` (R7), NUNCA sobre `Perfil`: una persona a cargo sin
    `Perfil` todavía (un estado que la base de datos no prohíbe, aunque el alta de hoy
    siempre cree uno) no debe dar ni un 500 ni un `DoesNotExist` — la pregunta que responde
    esta función no necesita que exista ningún `Perfil` en absoluto.
    """
    persona_que_pregunta = persona_actual(request)
    if persona_que_pregunta is None:
        return False
    if str(persona_que_pregunta.id) == str(persona_id):
        return True
    return Persona.objects.filter(pk=persona_id, responsable_id=persona_que_pregunta.id).exists()


def persona_editable_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si quien pregunta puede CAMBIARLA
    (`puede_cambiar_lo_de`): ella misma, o su responsable. 404 en cualquier otro caso —
    también si `persona_id` no existe, o si tiene cuenta propia y quien pregunta es "solo"
    otro miembro del hogar sin ser su responsable— nunca 403 (Q-20/Q-175): ni siquiera
    llamando aquí con el id exacto, saltándose la pantalla.
    """
    if puede_cambiar_lo_de(request, persona_id):
        return get_object_or_404(Persona, pk=persona_id)
    raise Http404("No existe.")


def persona_del_hogar_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si está en el MISMO hogar que quien pregunta (puede ser
    cualquiera del hogar, incluida ella misma). 404 si `persona_id` es de otro hogar, si quien
    pregunta no tiene hogar todavía (R14), o si no existe — nunca 403 (Q-11, Q-20): una
    persona de otro hogar es indistinguible desde fuera de una que no existe.

    Unidad 010 — consolidado aquí desde `planes/acceso.py` (unidad 005), que fue el primero
    en necesitarlo: la misma comprobación ("¿este id es de alguien del MISMO hogar que quien
    pregunta?") vivía duplicada en espíritu entre `planes/acceso.py` y la rama "ajena" de
    `perfiles/acceso.py:perfil_visible_o_404`. `progreso/acceso.py` es la TERCERA aparición —
    la señal de que tocaba subirlo a la puerta única del hogar en vez de escribirlo una cuarta
    vez. Los tres sitios llaman ahora a esta misma función.
    """
    hogar = hogar_actual(request)
    if hogar is None:
        raise Http404("No existe.")
    return get_object_or_404(Persona, pk=persona_id, hogar=hogar)
