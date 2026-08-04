"""
Las etiquetas en español de las listas cerradas del perfil (sexo, actividad, objetivo), para
los `<select>` de los formularios (el de alta y el de "tus datos").

Las CLAVES (lo que se guarda en la base de datos) salen SIEMPRE de `servicios.metabolismo`
—nunca se repiten aquí a mano—: así no hay manera de que este fichero y el catálogo de la
fórmula se desincronicen (por ejemplo, alguien añade un sexto objetivo en `metabolismo.py` y
se le olvida añadirlo aquí: con esta construcción, el `<select>` lo recoge solo).
"""

from servicios import metabolismo

SEXO_CHOICES = [
    ("hombre", "Hombre"),
    ("mujer", "Mujer"),
]


# R11 (unidad 011, apuntar-un-entreno.md) — estas cinco etiquetas hablan del DÍA A DÍA (el
# trabajo, cómo te mueves normalmente), SIN contar los entrenos: desde esta unidad, los
# entrenos apuntados a mano tienen su propio hueco (la app `entrenos/`) y se suman aparte al
# objetivo del día (R7/R-2 de generar-el-plan.md) — si esta lista también hablara de "días de
# ejercicio", el mismo entreno contaría dos veces: una aquí, y otra al apuntarlo. Coincide con
# lo que el plano de `crear-cuenta` ya prometía ("eligió su nivel de actividad DEL DÍA A DÍA")
# y con el episodio real que destapó la incoherencia: Alejandro, triatleta, eligió "ligera"
# porque su día a día (delante de un ordenador) es poco activo, aunque entrene mucho.
_ETIQUETAS_ACTIVIDAD = {
    "sedentario": "Sedentario/a (trabajo de oficina, te mueves poco en tu día a día)",
    "ligero": "Algo activo/a (tu día a día tiene cierto movimiento: caminas, subes escaleras)",
    "moderado": "Activo/a (tu día a día tiene bastante movimiento: de pie, caminando, tareas físicas)",
    "activo": "Muy activo/a (tu día a día exige esfuerzo físico constante)",
    "muy_activo": "Extremadamente activo/a (trabajo físico intenso o mucho movimiento todo el día)",
}
ACTIVIDAD_CHOICES = [(clave, _ETIQUETAS_ACTIVIDAD[clave]) for clave in metabolismo.ACTIVIDADES]

_ETIQUETAS_OBJETIVO = {
    "mantener": "Mantener mi peso",
    "perder_grasa": "Perder grasa",
    "ganar_musculo": "Ganar músculo",
    "rendimiento": "Rendimiento deportivo",
    "recomposicion_corporal": "Recomposición corporal (ganar músculo y perder grasa a la vez)",
}
OBJETIVO_CHOICES = [(clave, _ETIQUETAS_OBJETIVO[clave]) for clave in metabolismo.OBJETIVOS]

# Salvaguarda barata: si alguien añade una clave nueva a metabolismo.py y se olvida de darle
# etiqueta aquí, que falle AHORA (al importar el módulo) y no en producción con un <select>
# a medias.
assert set(_ETIQUETAS_ACTIVIDAD) == set(metabolismo.ACTIVIDADES), (
    "Falta una etiqueta de actividad: revisa constantes.py contra servicios/metabolismo.py"
)
assert set(_ETIQUETAS_OBJETIVO) == set(metabolismo.OBJETIVOS), (
    "Falta una etiqueta de objetivo: revisa constantes.py contra servicios/metabolismo.py"
)
