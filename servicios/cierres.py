"""
El cálculo de "cerrar el día" (unidad 012, decir-si-cumpliste.md): qué día hay que preguntar
al abrir la app, si es que hay alguno (R6, R7, R8, R9). Mismo espíritu que el resto de
`servicios/`: función PURA — recibe fechas y booleanos ya resueltos, no toca la base de datos,
no importa Django y no sabe qué es una petición HTTP — así se prueba sola, sin pasar por
ninguna pantalla ("Cómo" punto 2 de la especificación).

`cierres/logica.py` es la única pieza que conecta esto con los modelos (`CierreDeDia`,
`DiaSaltado`) y con `django.utils.timezone.localdate`.
"""

from datetime import timedelta


def calcular_dia_pendiente(hoy, cerrado_ayer, saltado_ayer):
    """
    R6/R7/R8/R9 — qué día hay que preguntar al abrir la app, o `None` si no hay ninguno.

    SIEMPRE es "ayer" relativo a `hoy`, y NUNCA ningún otro día (R7, el episodio de Euridice:
    "lleva cinco días sin apuntar... solo se le pregunta por el día de ayer, no por los
    cinco" — los días más antiguos que ayer no entran en esta cuenta en absoluto, ni aunque
    sigan sin cerrar: se rellenan a mano desde Progreso si se quiere, la app no vuelve a
    ofrecerlos aquí).

    Si `cerrado_ayer` o `saltado_ayer` es `True`, no hay nada que preguntar: un día ya cerrado
    no se vuelve a preguntar (R9, "cerrar hoy no dispara la pregunta por hoy" es un caso
    particular de esto: hoy nunca es "ayer"), y un día ya saltado tampoco, nunca más (R8/Q-141).
    """
    ayer = hoy - timedelta(days=1)
    if cerrado_ayer or saltado_ayer:
        return None
    return ayer
