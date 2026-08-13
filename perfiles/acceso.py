"""
La puerta del perfil de una persona (R9, G-43): todo el hogar VE el perfil de cualquier
miembro, pero solo su propia dueña puede CAMBIARLO — nadie más, tampoco llamando al servidor
con el id exacto (R9, Q-20).

Mismo principio que `hogares/acceso.py` (la puerta única del aislamiento por hogar de la
unidad 003): la ruta de ESCRITURA responde 404 si no es el perfil de quien pregunta, nunca
403 — un 403 confirmaría "existe, pero no es tuyo"; un 404 es indistinguible de "no existe".
Aquí la VISIBILIDAD es más amplia que en `hogares/acceso.py` (cualquiera del hogar ve
cualquier perfil del hogar, no solo el suyo): son dos puertas distintas a propósito.

Unidad 010 — la rama "es de OTRA persona" de `perfil_visible_o_404` reutiliza AHORA
`hogares.acceso.persona_del_hogar_o_404` (consolidado desde `planes/acceso.py`) en vez de
repetir su propio `if hogar is None / get_object_or_404(..., hogar=hogar)`: era la misma
comprobación escrita dos veces.

Unidad 023 — "soy yo" ya no se decide comparando ids de cuenta, sino de PERSONA
(`hogares.acceso.persona_actual`). El comportamiento es idéntico: hoy cada cuenta es una
persona y solo una.

Unidad 024 (R4/G-43) — una tercera puerta, `perfil_editable_o_404`: además de la propia dueña,
su RESPONSABLE también puede cambiar su perfil, si es una persona a cargo (R-99). Es la puerta
que usa `actualizar_perfil`; `perfil_propio_o_404` sigue existiendo tal cual para lo que sigue
siendo estrictamente de uno mismo (apuntar y borrar el peso, sin cambios en esta unidad — ver
hallazgos.md para el porqué de no ampliar también esas dos).
"""

from django.http import Http404
from django.shortcuts import get_object_or_404

from hogares.acceso import persona_actual, persona_del_hogar_o_404

from .models import Perfil


def _es_la_propia(request, persona_id):
    """¿`persona_id` es la persona de quien está haciendo la petición?"""
    persona = persona_actual(request)
    return persona is not None and str(persona.id) == str(persona_id)


def _es_su_responsable(request, persona_id):
    """¿Quien pregunta es el `responsable` de `persona_id` (R-99, persona a cargo)?"""
    persona = persona_actual(request)
    if persona is None:
        return False
    return Perfil.objects.filter(
        persona_id=persona_id, persona__responsable_id=persona.id
    ).exists()


def puede_editar_perfil(request, persona_id):
    """¿Quien pregunta puede CAMBIAR el perfil de `persona_id`? Es la propia dueña, o su
    responsable (R4/R-99). Único sitio donde vive esta regla — la usan tanto `ver_perfil`
    (para decidir si enseña el formulario) como `perfil_editable_o_404` (para la puerta de
    escritura), así que las dos SIEMPRE están de acuerdo."""
    return _es_la_propia(request, persona_id) or _es_su_responsable(request, persona_id)


def perfil_visible_o_404(request, persona_id):
    """
    El `Perfil` de `persona_id`: el PROPIO siempre es visible, esté o no esté todavía en un
    hogar; el de OTRA persona, solo si está en el MISMO hogar que quien pregunta (R9: "todo
    el hogar lo ve"). 404 si es de otro hogar, o si no existe.

    Hueco H2 de la revisión: antes esto exigía tener hogar incluso para el PROPIO perfil, y
    devolvía 404. Eso rompía R1/R7 en el estado exacto que describe el episodio de C-16/C-104
    (crear-cuenta.md): alguien que se registra CON el código de otro hogar queda "esperando
    que le acepten", sin hogar, hasta que alguien la acepta — y en ese estado sigue teniendo
    que ver SUS PROPIAS calorías (R1: "al verificar su correo entra y ve 1.894 kcal"). El
    perfil propio no es "una cosa del hogar" (G-43): es de la persona, y se ve exista o no
    exista todavía un hogar de por medio. Solo el perfil de OTRA exige hogar compartido — eso
    sigue igual.
    """
    if _es_la_propia(request, persona_id):
        return get_object_or_404(Perfil, persona_id=persona_id)

    # Sin hogar propio todavía (R14 de la unidad 003), no hay ningún perfil AJENO que ver —
    # pero el propio ya se resolvió arriba, antes de llegar aquí. `persona_del_hogar_o_404` ya
    # hace exactamente esta comprobación (404 si no hay hogar, o si es de otro).
    persona_ajena = persona_del_hogar_o_404(request, persona_id)
    return get_object_or_404(Perfil, persona_id=persona_ajena.id)


def perfil_propio_o_404(request, persona_id):
    """
    El `Perfil` de `persona_id`, SOLO si es el de quien pregunta (R9: nadie más puede
    cambiarlo). 404 en cualquier otro caso — incluido "existe, pero es de otra persona": no
    se distingue de "no existe" (mismo principio que `hogares/acceso.py`).
    """
    if not _es_la_propia(request, persona_id):
        raise Http404("No existe.")
    return get_object_or_404(Perfil, persona_id=persona_id)


def perfil_editable_o_404(request, persona_id):
    """
    El `Perfil` de `persona_id`, si quien pregunta puede CAMBIARLO (R4/R-99/G-43): es la
    propia dueña, o su RESPONSABLE si es una persona a cargo. 404 en cualquier otro caso —
    también si `persona_id` tiene cuenta propia y quien pregunta es "solo" otro miembro del
    hogar con cuenta (Q-20/Q-175: ni siquiera llamando aquí con el id exacto, saltándose la
    pantalla).
    """
    if puede_editar_perfil(request, persona_id):
        return get_object_or_404(Perfil, persona_id=persona_id)
    raise Http404("No existe.")
