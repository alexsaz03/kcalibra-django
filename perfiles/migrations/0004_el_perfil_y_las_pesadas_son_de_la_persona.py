"""
Unidad 023, paso 4 de 8 — el perfil y las pesadas dejan de colgar de la cuenta.

Los tres pasos que documenta Django para cambiar el dueño de una clave ajena YA POBLADA, en
este orden y nunca de otro:

1. `AddField(persona, null=True)` — aditivo, no rompe nada.
2. `RunPython` que TRADUCE los ids: `usuario_id` -> `persona_id`.
3. `AlterField(null=False)` + el cambio de la restricción única + `RemoveField(usuario)`.

**Lo que está prohibido aquí, y por qué:** un solo `AlterField` cambiando el `to=` de la clave
ajena. `AlterField` cambia la DEFINICIÓN del campo, no su CONTENIDO: la columna `usuario_id`
conservaría sus enteros, ahora leídos como ids de `Persona`. Con dos tablas cuyas secuencias
empiezan las dos en 1, eso no es un riesgo teórico — es una reasignación silenciosa de los
datos de una persona a otra.
"""

from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

import django.db.models.deletion

MOTIVO_IRREVERSIBLE = (
    "La unidad 023 (separar la persona de la cuenta) no se puede deshacer con una migración "
    "inversa: en cuanto exista una persona SIN cuenta —que es justo para lo que nace "
    "`hogares.Persona`— sus pesadas y su perfil no tienen ningún `Usuario` al que volver, y "
    "una inversa tendría que inventárselo o tirar esos datos. El rollback real es restaurar "
    "desde la copia de las seis tablas tomada ANTES de migrar (`pg_dump`), no una migración "
    "inversa."
)


def traducir_el_dueno(apps, schema_editor):
    """Rellena `persona_id` a partir de `usuario_id`, usando las personas que creó
    `hogares.0003`. Si alguna fila se quedara sin dueño, se para AQUÍ con un mensaje que dice
    cuál — mejor que dejar que reviente el `NOT NULL` del paso siguiente sin explicar nada."""
    Persona = apps.get_model("hogares", "Persona")
    persona_de_la_cuenta = dict(
        Persona.objects.exclude(usuario=None).values_list("usuario_id", "id")
    )

    for nombre in ("Perfil", "MedicionPeso"):
        modelo = apps.get_model("perfiles", nombre)
        for usuario_id, persona_id in persona_de_la_cuenta.items():
            modelo.objects.filter(usuario_id=usuario_id).update(persona_id=persona_id)
        sin_dueno = modelo.objects.filter(persona__isnull=True).count()
        if sin_dueno:
            raise RuntimeError(
                f"{sin_dueno} fila(s) de perfiles.{nombre} apuntan a un usuario que no tiene "
                "Persona. No se sigue: revisa `hogares.0003_una_persona_por_cada_cuenta`."
            )


def _irreversible(apps, schema_editor):
    raise IrreversibleError(MOTIVO_IRREVERSIBLE)


class Migration(migrations.Migration):

    dependencies = [
        ("perfiles", "0003_alter_perfil_actividad"),
        ("hogares", "0003_una_persona_por_cada_cuenta"),
    ]

    operations = [
        # 1. Aditivo.
        migrations.AddField(
            model_name="perfil",
            name="persona",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="perfil",
                to="hogares.persona",
            ),
        ),
        migrations.AddField(
            model_name="medicionpeso",
            name="persona",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="mediciones_peso",
                to="hogares.persona",
            ),
        ),
        # 2. Traducción de ids.
        migrations.RunPython(traducir_el_dueno, _irreversible),
        # 3. Cerrar: obligatorio, la restricción por persona, y fuera la columna vieja. La
        # restricción se QUITA antes de borrar `usuario`, porque es ella quien lo usa.
        migrations.AlterField(
            model_name="perfil",
            name="persona",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="perfil",
                to="hogares.persona",
            ),
        ),
        migrations.AlterField(
            model_name="medicionpeso",
            name="persona",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="mediciones_peso",
                to="hogares.persona",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="medicionpeso",
            name="una_medicion_por_persona_y_dia",
        ),
        migrations.AddConstraint(
            model_name="medicionpeso",
            constraint=models.UniqueConstraint(
                fields=("persona", "fecha"), name="una_medicion_por_persona_y_dia"
            ),
        ),
        migrations.RemoveField(model_name="perfil", name="usuario"),
        migrations.RemoveField(model_name="medicionpeso", name="usuario"),
        # Guarda de irreversibilidad (R4). Va la ÚLTIMA a propósito: Django deshace las
        # operaciones en orden INVERSO, así que esta es la PRIMERA que se encuentra quien
        # intente retroceder — y choca con el motivo escrito antes de que el `RemoveField` de
        # arriba intente resucitar una columna obligatoria que ya no tiene con qué rellenarse
        # (que es lo que pasaba antes de esta guarda: un `IntegrityError` en crudo, correcto
        # pero mudo, que no decía ni por qué ni cuál es el rollback de verdad).
        migrations.RunPython(migrations.RunPython.noop, _irreversible),
    ]
