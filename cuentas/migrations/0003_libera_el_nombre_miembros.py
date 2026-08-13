"""
Unidad 023, paso 1 de 8 — libera el nombre `hogar.miembros` para que se lo quede `Persona`.

Esto NO toca la base de datos: `related_name` es cómo se llama la relación DESDE el otro lado
(`hogar.miembros`), no una columna. Existe por una razón muy concreta: entre esta migración y
`cuentas.0004` conviven dos claves ajenas a `Hogar` —la vieja de `Usuario` y la nueva de
`Persona`— y las dos querían llamarse `miembros`. Dos relaciones no pueden compartir nombre
inverso ni un instante, así que la que se va cede el nombre primero.

`Usuario.hogar` desaparece en `cuentas.0004`; este nombre provisional no llega a leerlo nadie.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0002_initial"),
        ("hogares", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="hogar",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="miembros_cuenta_provisional",
                to="hogares.hogar",
            ),
        ),
    ]
