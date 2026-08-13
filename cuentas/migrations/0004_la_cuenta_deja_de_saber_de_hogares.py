"""
Unidad 023, paso 8 de 8 — la cuenta deja de saber de hogares.

Va la ÚLTIMA a propósito: `hogares.0003` lee `usuario.hogar_id` para dárselo a cada persona,
así que la columna tiene que seguir ahí hasta que las seis tablas personales estén traducidas.

`codigo_hogar_pendiente` NO se va: es un dato del ALTA (el código que alguien tecleó al
registrarse, antes de verificar su correo), no de la pertenencia al hogar.
"""

from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

MOTIVO_IRREVERSIBLE = (
    "La unidad 023 (separar la persona de la cuenta) no se puede deshacer con una migración "
    "inversa. Deshacer ESTE paso concreto sería peor que fallar: `Usuario.hogar` volvería a "
    "existir, pero VACÍO para todo el mundo —quién vive en qué casa vive ahora en "
    "`hogares.Persona`—, y la app arrancaría como si nadie tuviera hogar. El rollback real es "
    "restaurar desde la copia de las seis tablas tomada ANTES de migrar (`pg_dump`), no una "
    "migración inversa."
)


def _irreversible(apps, schema_editor):
    raise IrreversibleError(MOTIVO_IRREVERSIBLE)


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0003_libera_el_nombre_miembros"),
        ("perfiles", "0004_el_perfil_y_las_pesadas_son_de_la_persona"),
        ("entrenos", "0002_los_entrenos_son_de_la_persona"),
        ("planes", "0002_el_plan_es_de_la_persona"),
        ("cierres", "0002_los_cierres_son_de_la_persona"),
    ]

    operations = [
        migrations.RemoveField(model_name="usuario", name="hogar"),
        # Guarda de irreversibilidad (R4). Esta migración es la ÚLTIMA de la unidad, así que es
        # la PRIMERA que se deshace en un `migrate` hacia atrás: aquí es donde tiene que sonar
        # la alarma. Sin ella, el paso de arriba se deshace SIN error —resucita la columna,
        # vacía— y quien lo intente se cree que ha vuelto atrás cuando lo que ha hecho es
        # dejar la app sin saber quién vive dónde.
        migrations.RunPython(migrations.RunPython.noop, _irreversible),
    ]
