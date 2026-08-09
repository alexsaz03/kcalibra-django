"""
La lógica de negocio de la despensa (R-55, R-56, unidad 014; R-96/R-97, unidad 017): sumar en
vez de duplicar (C-57, G-110), corregir fundiendo si hace falta (Q-92) y quitar sin preguntar
nada (C-62). Vive separada de las vistas, igual que el resto de la app (`planes/logica.py`,
`entrenos/logica.py`...): las vistas reciben la petición HTTP y llaman aquí (regla del
proyecto, "las vistas no calculan; llaman").

No hay nada aquí que merezca un módulo aparte en `servicios/` (el "Cómo" de la especificación
lo permite expresamente: "si aquí no hay más que sumar dos cantidades, no montes un módulo
por montarlo") — sumar y fundir son operaciones sobre el propio modelo, con su propia base de
datos detrás (necesitan `save()`, `delete()`, una consulta al hogar), no un cálculo puro
reutilizable fuera de Django como sí lo son `servicios/metabolismo.py` o `servicios/progreso.py`.

**Unidad 017 (G-110 reescrita, G-194, R-96/R-97, C-105→C-110, aprobado 2026-08-09):** "arroz,
1 kg" y "arroz, 500 g" pasan a ser LA MISMA línea. La idea, en una frase: **se guarda SIEMPRE
en la unidad pequeña (g, ml) y se usa kg/l solo para enseñar.** `FAMILIA_DE_UNIDAD` decide qué
se puede sumar sin inventar nada: el peso (g, kg) se funde consigo mismo, el líquido (ml, l)
se funde consigo mismo, y las unidades a piezas (ud, paquete, lata, bote) son CADA UNA su
propia familia — nunca se funden con nada que no sea exactamente la misma, porque nadie sabe
de verdad cuánto pesa un paquete (R4/C-108: la app NO estima al sumar, nunca, ni siquiera "por
si acaso" — estimar al DESCONTAR es otra promesa, de R-57/G-111, y no se toca aquí).

El regalo (ver el "Cómo" de la especificación): `ProductoDespensa` ya lleva un
`UniqueConstraint` sobre `(hogar, nombre_normalizado, unidad)` EN LA BASE DE DATOS. Guardando
todos los pesos con `unidad="g"` y todos los líquidos con `unidad="ml"`, esa restricción que ya
existía pasa a impedir sola las dos líneas de arroz — no hace falta vigilancia nueva.
"""

from collections import defaultdict
from decimal import Decimal

from .models import CATEGORIAS, ProductoDespensa

# R-97/"Cómo" punto 1 — la tabla de familias: qué unidades se pueden sumar entre sí SIN
# ESTIMAR nada. El peso y el líquido tienen dos unidades cada uno (grande y pequeña); las
# unidades a piezas son cada una su propia familia, de una sola unidad, porque convertirlas a
# cualquier otra cosa significaría inventarse un peso que nadie ha dicho.
FAMILIA_DE_UNIDAD = {
    "g": "peso",
    "kg": "peso",
    "ml": "liquido",
    "l": "liquido",
    "ud": "ud",
    "paquete": "paquete",
    "lata": "lata",
    "bote": "bote",
}

# La unidad PEQUEÑA de cada familia: en la que se guarda siempre por dentro (R-96, "Cómo"
# punto 2). Para las familias de una sola unidad, la canónica es ella misma (no hay nada que
# convertir).
UNIDAD_CANONICA_DE_FAMILIA = {
    "peso": "g",
    "liquido": "ml",
    "ud": "ud",
    "paquete": "paquete",
    "lata": "lata",
    "bote": "bote",
}

# Cuánto vale UNA unidad de entrada en su unidad canónica. Son factores EXACTOS (1.000), nunca
# estimaciones — es la frontera con R4/G-111: aquí solo se convierte lo que se puede convertir
# sin inventar nada; "paquete", "lata", "bote" y "ud" valen 1 de sí mismas y punto, porque no
# tienen conversión posible.
FACTOR_A_CANONICA = {
    "g": Decimal(1),
    "kg": Decimal(1000),
    "ml": Decimal(1),
    "l": Decimal(1000),
    "ud": Decimal(1),
    "paquete": Decimal(1),
    "lata": Decimal(1),
    "bote": Decimal(1),
}


def convertir_a_canonica(cantidad, unidad):
    """
    Función pura (R-96/R-97, "Cómo" punto 1): dada una cantidad en la unidad que haya escrito
    la persona, devuelve `(cantidad, unidad)` ya en la unidad CANÓNICA (pequeña) de su
    familia — 1 kg -> (1000, "g"); 500 g -> (500, "g"); 1 paquete -> (1, "paquete"). Multiplica
    por un factor exacto, nunca estima: por eso vive aparte y se prueba sola, sin tocar la
    base de datos ni una vista.
    """
    familia = FAMILIA_DE_UNIDAD[unidad]
    unidad_canonica = UNIDAD_CANONICA_DE_FAMILIA[familia]
    return cantidad * FACTOR_A_CANONICA[unidad], unidad_canonica


def _sin_ceros_de_mas(valor):
    """
    Quita los ceros decimales que sobran SOLO para enseñar (1.50 -> 1.5, 1.00 -> 1), sin tocar
    el valor guardado (esta función nunca se llama sobre lo que se guarda, solo sobre lo que
    se enseña). No usa `Decimal.normalize()` a pelo porque para un entero grande cambiaría a
    notación científica (100 -> 1E+2, que en pantalla o en un `value=` de un `<input>` sale
    literalmente "1E+2"): se fuerza la notación de coma fija con `format(..., "f")` antes de
    volver a envolverlo en `Decimal`.
    """
    return Decimal(format(valor.normalize(), "f"))


def formatear_cantidad(cantidad, unidad):
    """
    R-96/G-194, "Cómo" punto 3 — cómo se ENSEÑA una cantidad que ya está guardada en su unidad
    canónica: por debajo de mil, en la unidad pequeña tal cual; de mil para arriba, convertida
    a la grande, con el corte EN el mil (1.000 g clavados se enseñan "1 kg", no "1.000 g").
    Las unidades a piezas nunca cruzan esta frontera (no hay "una tonelada de latas").

    NUNCA redondea el dato: dividir un `Decimal` entre 1.000 es una división exacta (solo
    desplaza la coma), así que 1.383 g se enseñan "1,383 kg" y siguen siendo 1.383 g exactos
    (Q-174, la lección de la 011 — un número redondeado al guardarlo es un número muerto; aquí
    ni siquiera se guarda nada nuevo, esto es puro cálculo de presentación sobre lo que ya
    hay).
    """
    if unidad == "g" and cantidad >= 1000:
        return _sin_ceros_de_mas(cantidad / Decimal(1000)), "kg"
    if unidad == "ml" and cantidad >= 1000:
        return _sin_ceros_de_mas(cantidad / Decimal(1000)), "l"
    return _sin_ceros_de_mas(cantidad), unidad


def productos_por_categoria(hogar):
    """
    R8 (§8 del plano, "Qué ve nada más entrar") — todo lo que hay en `hogar`, agrupado por
    categoría. Devuelve una lista de `(clave, etiqueta, productos)` EN EL ORDEN del catálogo
    de categorías (`despensa.models.CATEGORIAS`, no alfabético ni de aparición), y omite las
    categorías sin ningún producto — una despensa con solo verduras no enseña catorce
    cabeceras vacías detrás.

    Unidad 017 — a cada producto se le añaden `cantidad_mostrada` y `unidad_mostrada` (R-96,
    G-194): atributos calculados, NO campos del modelo, que la plantilla usa para enseñar la
    cantidad como la diría una persona sin tocar lo que hay guardado.
    """
    productos = ProductoDespensa.del_hogar(hogar)
    por_clave = defaultdict(list)
    for producto in productos:
        producto.cantidad_mostrada, producto.unidad_mostrada = formatear_cantidad(
            producto.cantidad, producto.unidad
        )
        por_clave[producto.categoria].append(producto)
    return [
        (clave, etiqueta, por_clave[clave])
        for clave, etiqueta in CATEGORIAS
        if por_clave[clave]
    ]


def anadir_producto(hogar, datos):
    """
    R1/R2/R3 (R-55, C-57, G-110, Q-92; unidad 017: C-105→C-107, R-96/R-97) — añade `datos` a
    la despensa de `hogar`. Primero convierte la cantidad escrita a la unidad CANÓNICA de su
    familia (`convertir_a_canonica`): así "1 kg" y "500 g" de arroz llegan aquí ya como
    (1000, "g") y (500, "g"), la MISMA unidad, y el resto de la función no necesita saber nada
    de kilos ni de litros.

    Si YA había una línea del mismo producto —mismo nombre normalizado: ignora mayúsculas y
    espacios de sobra (R2)— con esa unidad canónica, suma la cantidad a esa línea en vez de
    crear otra. Si no, crea la línea nueva, con la categoría que trajo el formulario. Las
    unidades a piezas (paquete, lata, bote, ud) son su propia familia canónica: dos latas más
    dos latas siguen sumando cuatro latas (C-57) exactamente igual que siempre, y una lata
    nunca suma con un peso (R4/C-108).

    La comparación de nombre usa `nombre.strip().lower()` a mano (no hace falta tocar la base
    de datos para saberlo): es la MISMA normalización que `ProductoDespensa.save()` aplica
    siempre a `nombre_normalizado`, así que basta con filtrar por ese campo ya calculado.
    """
    nombre = datos["nombre"].strip()
    normalizado = nombre.lower()
    cantidad_canonica, unidad_canonica = convertir_a_canonica(datos["cantidad"], datos["unidad"])

    existente = ProductoDespensa.objects.filter(
        hogar=hogar, nombre_normalizado=normalizado, unidad=unidad_canonica
    ).first()
    if existente:
        existente.cantidad = existente.cantidad + cantidad_canonica
        existente.save()
        return existente

    return ProductoDespensa.objects.create(
        hogar=hogar,
        nombre=nombre,
        cantidad=cantidad_canonica,
        unidad=unidad_canonica,
        categoria=datos["categoria"],
    )


def corregir_producto(producto, datos, unidad_antes):
    """
    R5/R7 — corrige la cantidad, la unidad y la categoría de `producto`. Igual que en
    `anadir_producto`, lo primero es convertir lo que trae el formulario a la unidad CANÓNICA
    de su familia (unidad 017): así corregir "500 g" a "0,5 kg" se guarda igual que estaba,
    500 g, no como "0.5"/"kg" — R-96 manda también al corregir, no solo al añadir.

    Caso límite de R7: si la unidad canónica nueva es DISTINTA de `unidad_antes` (que, al
    guardarse siempre en canónica, ya es en sí misma la unidad canónica de la línea antes de
    tocarla) y choca con OTRA línea que YA tenía esa unidad canónica, Q-92 es absoluta ("la
    despensa nunca muestra dos líneas del mismo producto con la misma unidad") — las dos se
    FUNDEN sumando las cantidades (ya canónicas) en la línea que YA existía (la "gemela"), que
    se queda además con la categoría recién corregida, y `producto` (la línea de origen, que
    ya no puede seguir existiendo sin duplicar) se borra. Nunca quedan dos líneas iguales ni
    un error a medias: o se guarda la corrección sola, o se funde entera, nunca las dos cosas
    a la vez.

    Con el cambio de la 017, este choque deja de poder darse NUNCA entre peso y líquido (ya no
    hay dos líneas de peso ni dos de líquido del mismo producto para empezar: se fundieron al
    añadir o en una corrección anterior) — pero sigue vivo, intacto, entre unidades que no se
    convierten: por ejemplo, corregir a mano una "lata" mal apuntada a "gramos" cuando ya hay
    una línea de peso de ese producto. Es una decisión de la PERSONA, no una estimación de la
    app (R4/G-110 sigue sin tocarse: la app nunca lo hace sola).

    `unidad_antes` tiene que venir de FUERA, capturada por quien llama ANTES de construir el
    `ModelForm` con `instance=producto`: `BaseModelForm._post_clean()` muta la instancia EN
    SITIO durante `form.is_valid()` (llama a `construct_instance`, para poder correr
    `full_clean()` del modelo con los valores nuevos) — así que para cuando esta función se
    ejecuta, `producto.unidad` YA es la unidad NUEVA, no la que tenía antes de corregir. Sin
    este dato aparte, la comparación de abajo siempre daría "no ha cambiado" y R7 no se
    dispararía nunca (se descubrió exactamente así: un test de R7 reventaba con un
    `IntegrityError` real en vez de fundir, la primera vez que se ejecutó la suite en la 014 —
    ver `conocimiento/tests-que-no-fallan-cuando-deben.md`, la undécima cara).
    """
    cantidad_canonica, unidad_canonica = convertir_a_canonica(datos["cantidad"], datos["unidad"])

    if unidad_canonica != unidad_antes:
        gemela = (
            ProductoDespensa.objects.filter(
                hogar=producto.hogar,
                nombre_normalizado=producto.nombre_normalizado,
                unidad=unidad_canonica,
            )
            .exclude(pk=producto.pk)
            .first()
        )
        if gemela is not None:
            gemela.cantidad = gemela.cantidad + cantidad_canonica
            gemela.categoria = datos["categoria"]
            gemela.save()
            producto.delete()
            return gemela

    producto.cantidad = cantidad_canonica
    producto.unidad = unidad_canonica
    producto.categoria = datos["categoria"]
    producto.save()
    return producto


def quitar_producto(producto):
    """R6/C-62 — borrado definitivo y sin preguntar nada: deja de contar para los menús y
    para la lista de la compra, y punto. El plano excluye expresamente "recuperar un producto
    borrado" (misma familia de exclusión que `entrenos.logica.borrar_entreno`): no hace falta
    ningún estado intermedio ni papelera."""
    producto.delete()
