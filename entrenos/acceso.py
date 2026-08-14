"""
La puerta de Entrenos (R10, apuntar-un-entreno.md; "Qué NO debe poder jamás: apuntar ni
corregir entrenos de otra persona con cuenta propia", §8 del plano).

A diferencia de `perfiles/acceso.py` o `progreso/acceso.py`, aquí NO hay una mitad "se ve,
pero no se toca" abierta a todo el hogar: esta unidad (025) no abre ninguna lectura del hogar
sobre entrenos ajenos (R-23 la nombra, pero esa mitad de VER queda fuera de alcance — llegará
con R-79 en Progreso, otra unidad) ni "cadenas de responsables" (una persona a cargo nunca
tiene cuenta, así que nunca hace una petición: no hace falta recursividad de ningún tipo). Ver,
apuntar, corregir y borrar son sobre uno mismo, O sobre una persona a cargo de quien pregunta
(unidad 025, R2/G-43) — nunca sobre otra persona con cuenta propia, ni sobre la persona a
cargo de OTRO miembro del hogar.

Unidad 025 — `persona_propia_o_404` (el NOMBRE se conserva, para no tocar cada sitio que la
llama en `entrenos/views.py`; lo que cambia es a quién deja pasar) ya no compara "soy yo" a
mano: delega ENTERA en `hogares.acceso.persona_editable_o_404`, la puerta única del proyecto
para "¿puedo cambiar lo de esta persona?" (G-43). Antes de esta unidad la regla ni existía
aquí (autoescritura estrictamente propia); ahora vive en un solo sitio y este módulo solo la
USA.
"""

from hogares.acceso import persona_editable_o_404


def persona_propia_o_404(request, persona_id):
    """
    La `Persona` `persona_id`, SOLO si quien pregunta puede cambiar sus datos (R10 y R2/G-43
    de la unidad 025): ella misma, o su responsable si es una persona a cargo. 404 en
    cualquier otro caso —incluido "existe, pero es de otra persona con cuenta propia", del
    mismo hogar o de otro—, nunca 403: mismo principio que `hogares/acceso.py`.
    """
    return persona_editable_o_404(request, persona_id)
