"""
R6 de la unidad 017 (caso límite del arranque, NO está en los planos, responsabilidad propia
de esta unidad): convierte las filas que YA existen de "kg" a "g" y de "l" a "ml" — pero NO se
limita a cambiar la unidad, porque eso reventaría contra el `UniqueConstraint`
`una_linea_por_hogar_producto_y_unidad` en cuanto un hogar tuviera, como el del episodio real
de esta unidad, "arroz, 1 kg" Y "arroz, 500 g" a la vez (dos líneas que el propio esquema
permitía hasta hoy, porque la unidad formaba parte de la igualdad). Esta migración FUNDE
sumando las dos en una sola antes de guardar, para que ningún hogar se quede con un
`IntegrityError` a mitad de camino ni con una de las dos líneas borrada sin sumar.

Solo hace falta mirar las filas en "kg" y en "l": las de "g" y "ml" ya están en su unidad
canónica y no se tocan; las de "ud", "paquete", "lata" y "bote" no tienen conversión posible
(son su propia familia, R4/G-110) y tampoco se tocan. Por construcción del `UniqueConstraint`
ANTERIOR a esta migración, un hogar solo puede tener COMO MUCHO una fila en "kg" y COMO MUCHO
una en "g" por producto (y lo mismo para "l"/"ml"): nunca hace falta fundir más de dos filas a
la vez para el mismo producto.

**Sobre el rollback (obligatorio en la especificación, R6):** esta migración de datos es
IRREVERSIBLE a propósito, y se declara así CON un `reverse_code` explícito (`_irreversible`,
más abajo) que LEVANTA `IrreversibleError` a mano en vez de intentar deshacer nada (corregido
tras la revisión: esta frase decía antes "sin `reverse_code`", que describía el mecanismo al
revés — la instrucción operativa siempre fue la correcta, escribir la función y pasarla a
`reverse_code=`, pero el mecanismo que describía esta frase no era ese): una vez que dos
líneas se han fundido sumando, ya no queda ningún rastro de qué parte del total venía de la
que estaba en "kg" y cuál de la que estaba en "g" — no hay forma matemática de deshacer una
suma. Intentar
`python manage.py migrate despensa 0001_initial` con esta migración ya aplicada lo dice
explícitamente (Django la marca como no reversible y para con `IrreversibleError`, en vez de
fingir que deshace algo que no puede deshacer). El rollback real, el que sí funciona, es
operativo y anterior a la migración, no una migración inversa: una copia de la tabla
(`pg_dump`/`dumpdata` de `despensa_productodespensa`) tomada ANTES de migrar. Ver
`hallazgos.md` de la unidad 017 para el output de la prueba con datos que ya colisionaban
(antes y después) y la comprobación de que retroceder falla con el mensaje esperado.
"""

from decimal import Decimal

from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError


def fundir_pesos_y_liquidos_en_su_unidad_pequena(apps, schema_editor):
    ProductoDespensa = apps.get_model("despensa", "ProductoDespensa")

    # `list(...)` materializa la consulta ANTES de empezar a mutar/borrar filas: iterar un
    # queryset mientras se borran filas de la propia tabla que ese queryset consulta es la
    # clase de cosa que conviene no arriesgar en una migración de datos irreversible.
    filas_a_convertir = list(
        ProductoDespensa.objects.filter(unidad__in=["kg", "l"]).order_by("id")
    )

    for producto in filas_a_convertir:
        unidad_canonica = "g" if producto.unidad == "kg" else "ml"
        cantidad_canonica = producto.cantidad * Decimal(1000)  # factor EXACTO, no se estima

        gemela = (
            ProductoDespensa.objects.filter(
                hogar_id=producto.hogar_id,
                nombre_normalizado=producto.nombre_normalizado,
                unidad=unidad_canonica,
            )
            .exclude(pk=producto.pk)
            .first()
        )
        if gemela is not None:
            # El caso que da nombre a R6: "arroz, 1 kg" (esta fila) y "arroz, 500 g" (la
            # gemela) YA colisionaban en el negocio, aunque el esquema viejo las dejara
            # convivir. Se funden sumando, nunca se elige una y se descarta la otra.
            gemela.cantidad = gemela.cantidad + cantidad_canonica
            gemela.save()
            producto.delete()
        else:
            producto.cantidad = cantidad_canonica
            producto.unidad = unidad_canonica
            producto.save()


def _irreversible(apps, schema_editor):
    # Se declara EXPLÍCITAMENTE en vez de dejar `reverse_code` sin poner: con esto, quien
    # intente `manage.py migrate despensa 0001_initial` con esta migración ya aplicada ve un
    # error que EXPLICA por qué (en vez del genérico de Django, o peor, un `noop` silencioso
    # que dejara creer que los datos volvieron a como estaban sin haberlo hecho — "evidencia,
    # no afirmación" vale también para lo que un rollback dice que ha hecho).
    raise IrreversibleError(
        "La migración 0002 de despensa (fusión de pesos y líquidos) no se puede deshacer: "
        "una vez fundidas dos líneas sumando sus cantidades, no queda ningún rastro de qué "
        "parte del total venía de cuál. El rollback real es restaurar desde una copia de la "
        "tabla despensa_productodespensa tomada ANTES de migrar (pg_dump/dumpdata), no una "
        "migración inversa."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("despensa", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            fundir_pesos_y_liquidos_en_su_unidad_pequena,
            reverse_code=_irreversible,
        ),
    ]
