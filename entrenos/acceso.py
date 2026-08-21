"""
La puerta de Entrenos (R10, apuntar-un-entreno.md; "Qué NO debe poder jamás: apuntar ni
corregir entrenos de otra persona con cuenta propia", §8 del plano).

Unidad 036 (R1-R9 de su especificación, R-23/G-43 del mapa) — abre la mitad de VER que
faltaba: cualquiera del hogar ve los entrenos de cualquiera de dentro (`persona_visible_o_404`,
copiado del patrón de `progreso/acceso.py`), pero solo los CAMBIA su dueña o su responsable
(`persona_propia_o_404`, sin tocar). `puede_editar_entrenos` **no reimplementa** esa regla:
delega ENTERA en `hogares.acceso.puede_cambiar_lo_de` (mismo patrón que
`progreso/acceso.py:puede_editar_progreso` y `perfiles/acceso.py:puede_editar_perfil`), para
que la plantilla nunca ofrezca algo que el servidor va a rechazar.

Unidad 025 — `persona_propia_o_404` (el NOMBRE se conserva, para no tocar cada sitio que la
llama en `entrenos/views.py`; lo que cambia es a quién deja pasar) ya no compara "soy yo" a
mano: delega ENTERA en `hogares.acceso.persona_editable_o_404`, la puerta única del proyecto
para "¿puedo cambiar lo de esta persona?" (G-43). Antes de esta unidad la regla ni existía
aquí (autoescritura estrictamente propia); ahora vive en un solo sitio y este módulo solo la
USA.
"""

from hogares.acceso import (
    persona_actual,
    persona_del_hogar_o_404,
    persona_editable_o_404,
    puede_cambiar_lo_de,
)


def persona_propia_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si quien pregunta puede cambiar sus datos (R10 y R2/G-43
    de la unidad 025): ella misma, o su responsable si es una persona a cargo. 404 en
    cualquier otro caso —incluido "existe, pero es de otra persona con cuenta propia", del
    mismo hogar o de otro—, nunca 403: mismo principio que `hogares/acceso.py`.
    """
    return persona_editable_o_404(request, persona_id)


def persona_visible_o_404(request, persona_id):
    """
    La `Persona` `persona_id`: la PROPIA siempre es visible; la de OTRA persona, solo si está
    en el MISMO hogar que quien pregunta (R1/R7/R-23/G-43: "todo el hogar ve los entrenos de
    todos"). 404 si es de otro hogar (R8), o si no existe — nunca 403 (Q-20). Copiado de
    `progreso/acceso.py:persona_visible_o_404`.
    """
    persona = persona_actual(request)
    if persona is not None and str(persona.id) == str(persona_id):
        return persona
    return persona_del_hogar_o_404(request, persona_id)


def puede_editar_entrenos(request, persona_id):
    """¿Quien pregunta puede CAMBIAR los entrenos de `persona_id` (apuntar, corregir, borrar)?
    Es la propia dueña, o su responsable (R6/R7/G-43) — delegado ENTERO en
    `hogares.acceso.puede_cambiar_lo_de`, la puerta única del proyecto para esta pregunta. La
    usa `ver_entrenos` para decidir si la plantilla enseña el formulario y los enlaces de
    corregir/borrar (R2/R4/R6): una sola fuente, para que la pantalla y la puerta de escritura
    nunca puedan divergir."""
    return puede_cambiar_lo_de(request, persona_id)
