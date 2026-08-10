"""
La lógica de negocio de las recetas (R1-R7 de la especificación de la unidad 021): montar las
filas de ingredientes que trae el formulario, validar el mínimo obligatorio (R2), guardar/
actualizar la receta entera en una sola transacción, y el texto legible de "para qué comidas
vale". Vive separada de las vistas, igual que `despensa/logica.py` y `planes/logica.py` (regla
del proyecto, "las vistas no calculan; llaman").

**Por qué los ingredientes no usan un `ModelForm`/formset de Django:** el formulario real añade
filas de ingredientes con Alpine.js clonando un bloque con los MISMOS `name` (`ingrediente_nombre`,
`ingrediente_cantidad`, `ingrediente_unidad`) en vez de índices numerados — no hace falta
gestionar un "management form" de formset en el cliente. El navegador manda esos campos como
listas paralelas, y `filas_de_ingredientes` las recompone aquí.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import IngredienteDeReceta, Receta, MOMENTOS_DEL_DIA, UNIDADES

_ETIQUETA_DE_MOMENTO = dict(MOMENTOS_DEL_DIA)
_UNIDADES_VALIDAS = {clave for clave, _ in UNIDADES}


def filas_de_ingredientes(post):
    """
    A partir de un `QueryDict` de POST, las filas de ingredientes que trajo el formulario:
    lee las listas paralelas `ingrediente_nombre[]`/`ingrediente_cantidad[]`/
    `ingrediente_unidad[]` (mismo índice = misma fila) y descarta en silencio las filas
    completamente vacías (la fila "extra" que nadie llegó a rellenar, o la que quedó vacía tras
    quitar un ingrediente en el cliente) — eso no es un error, R2 solo exige que quede AL MENOS
    UNA fila con datos.
    """
    nombres = post.getlist("ingrediente_nombre")
    cantidades = post.getlist("ingrediente_cantidad")
    unidades = post.getlist("ingrediente_unidad")
    filas = []
    for nombre, cantidad_texto, unidad in zip(nombres, cantidades, unidades):
        nombre = (nombre or "").strip()
        cantidad_texto = (cantidad_texto or "").strip()
        unidad = (unidad or "").strip()
        if not nombre and not cantidad_texto and not unidad:
            continue
        filas.append({"nombre": nombre, "cantidad_texto": cantidad_texto, "unidad": unidad})
    return filas


def validar_ingredientes(filas):
    """
    R2/G-140 — hace falta AL MENOS UN ingrediente completo (nombre, cantidad positiva, unidad
    de la lista). Devuelve `(ingredientes_limpios, errores)`: `errores` es una lista de frases
    en cristiano; `ingredientes_limpios` (dicts con `nombre`/`cantidad` ya `Decimal`/`unidad`)
    solo es de fiar cuando `errores` está vacía.

    R5 — la cantidad se parsea con `Decimal(texto)` directamente sobre lo que mandó el
    `<input>` (formato de máquina, con punto): nunca se pasa por `float` de por medio, que sí
    podría perder precisión.
    """
    if not filas:
        return [], ["Añade al menos un ingrediente."]

    limpios = []
    errores = []
    for indice, fila in enumerate(filas, start=1):
        etiqueta = fila["nombre"] or f"fila {indice}"
        if not fila["nombre"]:
            errores.append(f"Ingrediente {indice}: escribe su nombre.")
            continue
        try:
            cantidad = Decimal(fila["cantidad_texto"])
        except (InvalidOperation, ValueError):
            errores.append(f"{etiqueta}: la cantidad tiene que ser un número.")
            continue
        if cantidad <= 0:
            errores.append(f"{etiqueta}: la cantidad tiene que ser mayor que cero.")
            continue
        if fila["unidad"] not in _UNIDADES_VALIDAS:
            errores.append(f"{etiqueta}: elige una unidad.")
            continue
        limpios.append({"nombre": fila["nombre"], "cantidad": cantidad, "unidad": fila["unidad"]})

    if errores:
        return [], errores
    return limpios, []


def comidas_legibles(comidas):
    """R2 — el texto de "para qué comidas vale": las etiquetas elegidas, separadas por coma, o
    "Cualquier comida" si la lista está vacía (nunca se enseña como "ninguna")."""
    if not comidas:
        return "Cualquier comida"
    return ", ".join(_ETIQUETA_DE_MOMENTO.get(clave, clave) for clave in comidas)


@transaction.atomic
def crear_receta(hogar, datos, ingredientes):
    """R1/R2 — crea la receta y sus ingredientes en una sola transacción: o se guarda todo, o
    no se guarda nada."""
    receta = Receta.objects.create(
        hogar=hogar,
        nombre=datos["nombre"],
        raciones=datos["raciones"],
        comidas=datos.get("comidas") or [],
        preparacion=datos.get("preparacion") or "",
    )
    _guardar_ingredientes(receta, ingredientes)
    return receta


@transaction.atomic
def actualizar_receta(receta, datos, ingredientes):
    """
    R4 — corrige nombre/raciones/comidas/preparación y REEMPLAZA la lista de ingredientes
    entera (se borran los que había y se crean los nuevos): tan simple como "volver a
    escribirla", coherente con "apuntar una receta tiene que ser tan fácil como escribirla en
    una nota" del "Qué" de la especificación — no hace falta emparejar cada fila enviada con la
    fila que ya existía en la base de datos.
    """
    receta.nombre = datos["nombre"]
    receta.raciones = datos["raciones"]
    receta.comidas = datos.get("comidas") or []
    receta.preparacion = datos.get("preparacion") or ""
    receta.save()
    receta.ingredientes.all().delete()
    _guardar_ingredientes(receta, ingredientes)
    return receta


def _guardar_ingredientes(receta, ingredientes):
    IngredienteDeReceta.objects.bulk_create(
        IngredienteDeReceta(
            receta=receta, nombre=fila["nombre"], cantidad=fila["cantidad"], unidad=fila["unidad"]
        )
        for fila in ingredientes
    )


def recetas_del_hogar(hogar):
    """R7/§8 — todas las recetas de `hogar`, con sus ingredientes precargados (se listan y se
    abren mucho, R1) y el texto legible de "para qué comidas vale" ya calculado, NUNCA guardado
    en el modelo (mismo patrón que `despensa.logica.productos_por_categoria` con
    `cantidad_mostrada`)."""
    recetas = list(
        Receta.del_hogar(hogar).prefetch_related("ingredientes").order_by("nombre")
    )
    for receta in recetas:
        receta.comidas_texto = comidas_legibles(receta.comidas)
    return recetas


def con_comidas_legibles(receta):
    """La misma anotación que `recetas_del_hogar`, para UNA receta ya obtenida (vista de
    detalle/editar)."""
    receta.comidas_texto = comidas_legibles(receta.comidas)
    return receta
