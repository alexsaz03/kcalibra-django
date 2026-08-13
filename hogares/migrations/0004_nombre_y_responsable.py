"""
Unidad 024 (darle-cuenta-propia-a-los-de-casa.md, R-98/R-99) — paso 1 de 2: el esquema.

`nombre` nace NULLABLE a propósito, aunque el modelo (`hogares/models.py`) ya lo declara
obligatorio: las filas que ya existen no tienen ningún nombre todavía, y una columna NOT NULL
sin valor por defecto no se puede añadir a una tabla con datos. La migración 0005 rellena un
nombre provisional para cada una (R7) y SOLO ENTONCES la vuelve NOT NULL de verdad — el patrón
seguro para añadir un campo obligatorio a una tabla que ya tiene filas (lección de
docs/conocimiento/migraciones-de-datos-en-django.md: no adivines el dato, primero rellénalo).

`responsable` no tiene este problema (nace vacía para todo el mundo, R-99: casi nadie está a
cargo de nadie), así que se añade aquí directamente en su forma final.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hogares", "0003_una_persona_por_cada_cuenta"),
    ]

    operations = [
        migrations.AddField(
            model_name="persona",
            name="nombre",
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="persona",
            name="responsable",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="personas_a_cargo",
                to="hogares.persona",
            ),
        ),
    ]
