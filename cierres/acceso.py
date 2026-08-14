"""
La puerta de Cerrar el día (R12, decir-si-cumpliste.md; §8 "Qué NO debe poder jamás: cerrar el
día de otra persona con cuenta propia").

Copiado de `entrenos/acceso.py` (unidad 011): igual que los entrenos, esto NO abre ninguna
lectura del hogar sobre cierres ajenos ni "cadenas de responsables" (una persona a cargo nunca
tiene cuenta, así que nunca hace una petición). Cerrar y cambiar un cierre son sobre uno mismo,
O sobre una persona a cargo de quien pregunta (unidad 025, R3/G-43).

Unidad 025 — `persona_propia_o_404` (el NOMBRE se conserva; lo que cambia es a quién deja
pasar) delega ENTERA en `hogares.acceso.persona_editable_o_404`, la puerta única del proyecto
para "¿puedo cambiar lo de esta persona?" (G-43) — mismo cambio que `entrenos/acceso.py`.
"""

from hogares.acceso import persona_editable_o_404


def persona_propia_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si quien pregunta puede cambiar sus datos (R12 y R3/G-43
    de la unidad 025): ella misma, o su responsable si es una persona a cargo. 404 en
    cualquier otro caso —incluido "existe, pero es de otra persona con cuenta propia", del
    mismo hogar o de otro—, nunca 403: mismo principio que `entrenos/acceso.py` y
    `hogares/acceso.py`.
    """
    return persona_editable_o_404(request, persona_id)
