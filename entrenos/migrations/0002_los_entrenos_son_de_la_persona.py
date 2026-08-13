"""
Unidad 023, paso 5 de 8 — los entrenos dejan de colgar de la cuenta.

Mismo patrón de tres pasos que `perfiles.0004` (léelo: allí está escrito entero, incluido por
qué está prohibido un `AlterField` cambiando el `to=`). Aquí, además, el índice
`(usuario, fecha)` se sustituye por `(persona, fecha)`: es el índice que sostiene "los
entrenos de esta persona en este día", la consulta más repetida de la app.
"""

from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

import django.db.models.deletion

MOTIVO_IRREVERSIBLE = (
    "La unidad 023 (separar la persona de la cuenta) no se puede deshacer con una migración "
    "inversa: en cuanto exista una persona SIN cuenta —que es justo para lo que nace "
    "`hogares.Persona`— sus entrenos no tienen ningún `Usuario` al que volver, y una inversa "
    "tendría que inventárselo o tirar esos datos. El rollback real es restaurar desde la copia "
    "de las seis tablas tomada ANTES de migrar (`pg_dump`), no una migración inversa."
)


def traducir_el_dueno(apps, schema_editor):
    Persona = apps.get_model("hogares", "Persona")
    Entreno = apps.get_model("entrenos", "Entreno")
    persona_de_la_cuenta = dict(
        Persona.objects.exclude(usuario=None).values_list("usuario_id", "id")
    )
    for usuario_id, persona_id in persona_de_la_cuenta.items():
        Entreno.objects.filter(usuario_id=usuario_id).update(persona_id=persona_id)
    sin_dueno = Entreno.objects.filter(persona__isnull=True).count()
    if sin_dueno:
        raise RuntimeError(
            f"{sin_dueno} entreno(s) apuntan a un usuario que no tiene Persona. No se sigue: "
            "revisa `hogares.0003_una_persona_por_cada_cuenta`."
        )


def _irreversible(apps, schema_editor):
    raise IrreversibleError(MOTIVO_IRREVERSIBLE)


class Migration(migrations.Migration):

    dependencies = [
        ("entrenos", "0001_initial"),
        ("hogares", "0003_una_persona_por_cada_cuenta"),
    ]

    operations = [
        migrations.AddField(
            model_name="entreno",
            name="persona",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="entrenos",
                to="hogares.persona",
            ),
        ),
        migrations.RunPython(traducir_el_dueno, _irreversible),
        migrations.AlterField(
            model_name="entreno",
            name="persona",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="entrenos",
                to="hogares.persona",
            ),
        ),
        # El índice va antes del `RemoveField`: el viejo nombra la columna que se va.
        migrations.RemoveIndex(model_name="entreno", name="entrenos_en_usuario_fa18be_idx"),
        migrations.RemoveField(model_name="entreno", name="usuario"),
        migrations.AddIndex(
            model_name="entreno",
            index=models.Index(fields=["persona", "fecha"], name="entrenos_en_persona_e6f56c_idx"),
        ),
        # Guarda de irreversibilidad (R4). Va la ÚLTIMA a propósito: Django deshace las
        # operaciones en orden INVERSO, así que esta es la PRIMERA que se encuentra quien
        # intente retroceder — y choca con el motivo escrito antes de que el `RemoveField` de
        # arriba intente resucitar una columna obligatoria que ya no tiene con qué rellenarse
        # (que es lo que pasaba antes de esta guarda: un `IntegrityError` en crudo, correcto
        # pero mudo, que no decía ni por qué ni cuál es el rollback de verdad).
        migrations.RunPython(migrations.RunPython.noop, _irreversible),
    ]
