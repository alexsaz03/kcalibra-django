"""
La puerta de Progreso (R7, R8, R9 de la especificación de la unidad 010; G-1, R-23, G-171 del
mapa): cualquiera del hogar VE el progreso de cualquiera de dentro, uno cada vez — nadie de
fuera, tampoco llamando al servidor con el id exacto (R9, Q-20).

Es la misma "puerta doble" que ya usa `perfiles/acceso.py:perfil_visible_o_404` (la PROPIA
siempre es visible, esté o no esté todavía en un hogar — H2 de la unidad 004, el estado
"esperando que le acepten"; la de OTRA persona, solo si comparte hogar) pero devolviendo la
`Persona` en sí, no un `Perfil`: `progreso/` necesita las `MedicionPeso` de esa persona
directamente (`persona.mediciones_peso`), no sus datos físicos.

La rama "ajena" reutiliza `hogares.acceso.persona_del_hogar_o_404` (unidad 010: consolidado
desde `planes/acceso.py`, su tercera aparición) en vez de repetir el `if hogar is None /
get_object_or_404(..., hogar=hogar)` una cuarta vez.

Esta puerta es SOLO de lectura: Progreso no tiene ninguna vista de escritura propia (apuntar y
borrar el peso siguen siendo cosa de `perfiles/`, con su propia puerta sin cambios — R8).
"""

from hogares.acceso import persona_actual, persona_del_hogar_o_404


def persona_visible_o_404(request, persona_id):
    """
    La `Persona` `persona_id`: la PROPIA siempre es visible (R7, aunque todavía no tenga
    hogar asignado); la de OTRA persona, solo si está en el MISMO hogar que quien pregunta
    (R7/R-23/G-171: "se ve el de todos, pero uno cada vez"). 404 si es de otro hogar (R9), o
    si no existe — nunca 403 (Q-20).
    """
    persona = persona_actual(request)
    if persona is not None and str(persona.id) == str(persona_id):
        return persona
    return persona_del_hogar_o_404(request, persona_id)
