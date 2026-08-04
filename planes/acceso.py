"""
La puerta del plan de comidas (R6, R7, G-43): es DEL HOGAR, así que cualquiera de dentro lo ve
y lo cambia —incluido el de otra persona de su misma casa—, pero NADIE de fuera, tampoco
llamando al servidor con la dirección exacta (Q-20).

`usuario_del_hogar_o_404` vivía definida aquí (unidad 005): resuelve "¿a qué persona del hogar
de quien pregunta se refiere este `usuario_id`?" — hace falta porque `Usuario` no es un
`ModeloDeHogar` (lo es `PlanDeDia`), y "apuntar el plan" puede ser la PRIMERA comida del día,
sin ningún `PlanDeDia` todavía que la puerta de `hogares.acceso.obtener_de_mi_hogar_o_404`
pudiera filtrar.

Unidad 010 — consolidada en `hogares/acceso.py` (la puerta única del hogar, unidad 003): esta
misma comprobación se necesitaba también en `perfiles/acceso.py` y, ahora, en
`progreso/acceso.py` (su tercera aparición). Este módulo se queda como RE-EXPORT, para que
`planes/views.py` no tenga que cambiar su import, pero la definición real —y el único sitio
que decide el comportamiento— vive en `hogares/acceso.py`.

Mismo principio que en toda la app: 404, nunca 403 — un objeto de otro hogar es indistinguible
desde fuera de uno que no existe.
"""

from hogares.acceso import usuario_del_hogar_o_404

__all__ = ["usuario_del_hogar_o_404"]
