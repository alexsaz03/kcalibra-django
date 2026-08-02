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

_ETIQUETAS_ACTIVIDAD = {
    "sedentario": "Sedentario/a (poco o ningún ejercicio)",
    "ligero": "Actividad ligera (ejercicio 1-3 días/semana)",
    "moderado": "Actividad moderada (ejercicio 3-5 días/semana)",
    "activo": "Activo/a (ejercicio 6-7 días/semana)",
    "muy_activo": "Muy activo/a (ejercicio intenso a diario, o trabajo físico)",
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
