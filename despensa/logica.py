"""
La lógica de negocio de la despensa (R-55, R-56, unidad 014): sumar en vez de duplicar
(R1-R3, C-57, G-110), corregir fundiendo si hace falta (R5/R7, Q-92) y quitar sin preguntar
nada (R6, C-62). Vive separada de las vistas, igual que el resto de la app (`planes/logica.py`,
`entrenos/logica.py`...): las vistas reciben la petición HTTP y llaman aquí (regla del
proyecto, "las vistas no calculan; llaman").

No hay nada aquí que merezca un módulo aparte en `servicios/` (el "Cómo" de la especificación
lo permite expresamente: "si aquí no hay más que sumar dos cantidades, no montes un módulo
por montarlo") — sumar y fundir son operaciones sobre el propio modelo, con su propia base de
datos detrás (necesitan `save()`, `delete()`, una consulta al hogar), no un cálculo puro
reutilizable fuera de Django como sí lo son `servicios/metabolismo.py` o `servicios/progreso.py`.
"""

from collections import defaultdict

from .models import CATEGORIAS, ProductoDespensa


def productos_por_categoria(hogar):
    """
    R8 (§8 del plano, "Qué ve nada más entrar") — todo lo que hay en `hogar`, agrupado por
    categoría. Devuelve una lista de `(clave, etiqueta, productos)` EN EL ORDEN del catálogo
    de categorías (`despensa.models.CATEGORIAS`, no alfabético ni de aparición), y omite las
    categorías sin ningún producto — una despensa con solo verduras no enseña catorce
    cabeceras vacías detrás.
    """
    productos = ProductoDespensa.del_hogar(hogar)
    por_clave = defaultdict(list)
    for producto in productos:
        por_clave[producto.categoria].append(producto)
    return [
        (clave, etiqueta, por_clave[clave])
        for clave, etiqueta in CATEGORIAS
        if por_clave[clave]
    ]


def anadir_producto(hogar, datos):
    """
    R1/R2/R3 (R-55, C-57, G-110, Q-92) — añade `datos` a la despensa de `hogar`. Si YA había
    una línea del mismo producto —mismo nombre normalizado: ignora mayúsculas y espacios de
    sobra (R2)— CON LA MISMA UNIDAD (R3: la unidad forma parte de la igualdad, así que "arroz,
    1 kg" y "arroz, 500 g" son dos líneas distintas), suma la cantidad a esa línea en vez de
    crear otra. Si no, crea la línea nueva, con la categoría que trajo el formulario.

    La comparación usa `nombre.strip().lower()` a mano (no hace falta tocar la base de datos
    para saberlo): es la MISMA normalización que `ProductoDespensa.save()` aplica siempre a
    `nombre_normalizado`, así que basta con filtrar por ese campo ya calculado.
    """
    nombre = datos["nombre"].strip()
    normalizado = nombre.lower()
    unidad = datos["unidad"]

    existente = ProductoDespensa.objects.filter(
        hogar=hogar, nombre_normalizado=normalizado, unidad=unidad
    ).first()
    if existente:
        existente.cantidad = existente.cantidad + datos["cantidad"]
        existente.save()
        return existente

    return ProductoDespensa.objects.create(
        hogar=hogar,
        nombre=nombre,
        cantidad=datos["cantidad"],
        unidad=unidad,
        categoria=datos["categoria"],
    )


def corregir_producto(producto, datos, unidad_antes):
    """
    R5/R7 — corrige la cantidad, la unidad y la categoría de `producto`. Caso límite de R7:
    si el cambio de unidad hace que `producto` choque con OTRA línea que YA tenía el mismo
    producto con esa unidad nueva, Q-92 es absoluta ("la despensa nunca muestra dos líneas
    del mismo producto con la misma unidad") — las dos se FUNDEN sumando las cantidades en la
    línea que YA existía (la "gemela"), que se queda además con la categoría recién corregida,
    y `producto` (la línea de origen, que ya no puede seguir existiendo sin duplicar) se
    borra. Nunca quedan dos líneas iguales ni un error a medias: o se guarda la corrección
    sola, o se funde entera, nunca las dos cosas a la vez.

    `unidad_antes` tiene que venir de FUERA, capturada por quien llama ANTES de construir el
    `ModelForm` con `instance=producto`: `BaseModelForm._post_clean()` muta la instancia EN
    SITIO durante `form.is_valid()` (llama a `construct_instance`, para poder correr
    `full_clean()` del modelo con los valores nuevos) — así que para cuando esta función se
    ejecuta, `producto.unidad` YA es la unidad NUEVA, no la que tenía antes de corregir. Sin
    este dato aparte, la comparación de abajo siempre daría "no ha cambiado" y R7 no se
    dispararía nunca (se descubrió exactamente así: un test de R7 reventaba con un
    `IntegrityError` real en vez de fundir, la primera vez que se ejecutó la suite).
    """
    nueva_unidad = datos["unidad"]

    if nueva_unidad != unidad_antes:
        gemela = (
            ProductoDespensa.objects.filter(
                hogar=producto.hogar,
                nombre_normalizado=producto.nombre_normalizado,
                unidad=nueva_unidad,
            )
            .exclude(pk=producto.pk)
            .first()
        )
        if gemela is not None:
            gemela.cantidad = gemela.cantidad + datos["cantidad"]
            gemela.categoria = datos["categoria"]
            gemela.save()
            producto.delete()
            return gemela

    producto.cantidad = datos["cantidad"]
    producto.unidad = nueva_unidad
    producto.categoria = datos["categoria"]
    producto.save()
    return producto


def quitar_producto(producto):
    """R6/C-62 — borrado definitivo y sin preguntar nada: deja de contar para los menús y
    para la lista de la compra, y punto. El plano excluye expresamente "recuperar un producto
    borrado" (misma familia de exclusión que `entrenos.logica.borrar_entreno`): no hace falta
    ningún estado intermedio ni papelera."""
    producto.delete()
