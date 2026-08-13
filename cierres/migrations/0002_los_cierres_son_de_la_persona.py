"""
Unidad 023, paso 7 de 8 — los cierres del día y el día saltado dejan de colgar de la cuenta.

Mismo patrón de tres pasos que `perfiles.0004` (allí está escrito entero, incluido por qué
está prohibido un `AlterField` cambiando el `to=`).
"""

from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

import django.db.models.deletion

MOTIVO_IRREVERSIBLE = (
    "La unidad 023 (separar la persona de la cuenta) no se puede deshacer con una migración "
    "inversa: en cuanto exista una persona SIN cuenta —que es justo para lo que nace "
    "`hogares.Persona`— sus cierres no tienen ningún `Usuario` al que volver, y una inversa "
    "tendría que inventárselo o tirar esos datos. El rollback real es restaurar desde la copia "
    "de las seis tablas tomada ANTES de migrar (`pg_dump`), no una migración inversa."
)


def traducir_el_dueno(apps, schema_editor):
    Persona = apps.get_model("hogares", "Persona")
    persona_de_la_cuenta = dict(
        Persona.objects.exclude(usuario=None).values_list("usuario_id", "id")
    )
    for nombre in ("CierreDeDia", "DiaSaltado"):
        modelo = apps.get_model("cierres", nombre)
        for usuario_id, persona_id in persona_de_la_cuenta.items():
            modelo.objects.filter(usuario_id=usuario_id).update(persona_id=persona_id)
        sin_dueno = modelo.objects.filter(persona__isnull=True).count()
        if sin_dueno:
            raise RuntimeError(
                f"{sin_dueno} fila(s) de cierres.{nombre} apuntan a un usuario que no tiene "
                "Persona. No se sigue: revisa `hogares.0003_una_persona_por_cada_cuenta`."
            )


def _irreversible(apps, schema_editor):
    raise IrreversibleError(MOTIVO_IRREVERSIBLE)


class Migration(migrations.Migration):

    dependencies = [
        ("cierres", "0001_initial"),
        ("hogares", "0003_una_persona_por_cada_cuenta"),
    ]

    operations = [
        migrations.AddField(
            model_name="cierrededia",
            name="persona",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cierres_de_dia",
                to="hogares.persona",
            ),
        ),
        migrations.AddField(
            model_name="diasaltado",
            name="persona",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="dia_saltado_cierre",
                to="hogares.persona",
            ),
        ),
        migrations.RunPython(traducir_el_dueno, _irreversible),
        migrations.AlterField(
            model_name="cierrededia",
            name="persona",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cierres_de_dia",
                to="hogares.persona",
            ),
        ),
        migrations.AlterField(
            model_name="diasaltado",
            name="persona",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="dia_saltado_cierre",
                to="hogares.persona",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="cierrededia",
            name="un_cierre_por_persona_y_dia",
        ),
        migrations.AddConstraint(
            model_name="cierrededia",
            constraint=models.UniqueConstraint(
                fields=("persona", "fecha"), name="un_cierre_por_persona_y_dia"
            ),
        ),
        migrations.RemoveField(model_name="cierrededia", name="usuario"),
        migrations.RemoveField(model_name="diasaltado", name="usuario"),
        # Guarda de irreversibilidad (R4). Va la ÚLTIMA a propósito: Django deshace las
        # operaciones en orden INVERSO, así que esta es la PRIMERA que se encuentra quien
        # intente retroceder — y choca con el motivo escrito antes de que el `RemoveField` de
        # arriba intente resucitar una columna obligatoria que ya no tiene con qué rellenarse
        # (que es lo que pasaba antes de esta guarda: un `IntegrityError` en crudo, correcto
        # pero mudo, que no decía ni por qué ni cuál es el rollback de verdad).
        migrations.RunPython(migrations.RunPython.noop, _irreversible),
    ]
