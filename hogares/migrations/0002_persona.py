"""
Unidad 023, paso 2 de 8 — nace `Persona`.

Solo esquema: la tabla vacía. Quién la puebla es el paso 3
(`hogares.0003_una_persona_por_cada_cuenta`), que es donde está el riesgo y por eso va aparte.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hogares", "0001_initial"),
        # `cuentas.0003` es quien deja libre el `related_name="miembros"` que reclama la FK de
        # abajo. Sin esta dependencia, el orden de aplicación no está garantizado y las dos
        # relaciones podrían coincidir con el mismo nombre inverso.
        ("cuentas", "0003_libera_el_nombre_miembros"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Persona",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "hogar",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="miembros",
                        to="hogares.hogar",
                    ),
                ),
                (
                    "usuario",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="persona",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
