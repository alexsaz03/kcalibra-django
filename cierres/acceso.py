"""
La puerta de Cerrar el día (R12, decir-si-cumpliste.md; §8 "Qué NO debe poder jamás: cerrar el
día de otra persona con cuenta propia").

Copiado de `entrenos/acceso.py` (unidad 011): igual que los entrenos, esto NO abre ninguna
lectura del hogar sobre cierres ajenos ni "cadenas de responsables" (una persona a cargo nunca
tiene cuenta, así que nunca hace una petición). Cerrar y cambiar un cierre son sobre uno mismo,
O sobre una persona a cargo de quien pregunta (unidad 025, R3/G-43).

Unidad 036 (R4/R5/R6/R9 de su especificación, R-23/G-43 del mapa) — abre la mitad de VER: todo
el hogar ve el histórico de cierres de cualquiera (`persona_visible_o_404`, mismo patrón que
`entrenos/acceso.py`), pero solo lo CAMBIA su dueña o su responsable
(`persona_propia_o_404`/`puede_editar_cierres`, delegado ENTERO en
`hogares.acceso.puede_cambiar_lo_de`, sin reimplementar la regla).

Unidad 025 — `persona_propia_o_404` (el NOMBRE se conserva; lo que cambia es a quién deja
pasar) delega ENTERA en `hogares.acceso.persona_editable_o_404`, la puerta única del proyecto
para "¿puedo cambiar lo de esta persona?" (G-43) — mismo cambio que `entrenos/acceso.py`.
"""

from hogares.acceso import (
    persona_actual,
    persona_del_hogar_o_404,
    persona_editable_o_404,
    puede_cambiar_lo_de,
)


def persona_propia_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si quien pregunta puede cambiar sus datos (R12 y R3/G-43
    de la unidad 025): ella misma, o su responsable si es una persona a cargo. 404 en
    cualquier otro caso —incluido "existe, pero es de otra persona con cuenta propia", del
    mismo hogar o de otro—, nunca 403: mismo principio que `entrenos/acceso.py` y
    `hogares/acceso.py`.
    """
    return persona_editable_o_404(request, persona_id)


def persona_visible_o_404(request, persona_id):
    """
    La `Persona` `persona_id`: la PROPIA siempre es visible; la de OTRA persona, solo si está
    en el MISMO hogar que quien pregunta (R4/R7/R-23/G-43: "todo el hogar ve el histórico de
    cierres de todos"). 404 si es de otro hogar (R8), o si no existe — nunca 403 (Q-20).
    Copiado de `entrenos/acceso.py:persona_visible_o_404`.
    """
    persona = persona_actual(request)
    if persona is not None and str(persona.id) == str(persona_id):
        return persona
    return persona_del_hogar_o_404(request, persona_id)


def puede_editar_cierres(request, persona_id):
    """¿Quien pregunta puede CAMBIAR los cierres de `persona_id` (cerrar, responder, saltar)?
    Es la propia dueña, o su responsable (R6/R7/G-43) — delegado ENTERO en
    `hogares.acceso.puede_cambiar_lo_de`, la puerta única del proyecto para esta pregunta. La
    usa `cerrar` para decidir si la plantilla enseña el formulario y los enlaces de "Cambiar"
    (R4/R6), y para el guarda de servidor del POST (R5): una sola fuente, para que la pantalla
    y la puerta de escritura nunca puedan divergir."""
    return puede_cambiar_lo_de(request, persona_id)
