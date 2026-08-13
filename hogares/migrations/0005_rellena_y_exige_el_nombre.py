"""
Unidad 024 (darle-cuenta-propia-a-los-de-casa.md, R7) — paso 2 de 2: rellenar y exigir.

R7 (caso límite) — "las personas que ya existen en la base de datos salen de la migración CON
NOMBRE, no en blanco": a cada `Persona` de las que ya había (todas con cuenta, hoy no puede
haber ninguna sin ella: esta unidad es la primera que hace posible lo contrario) se le pone
como nombre provisional la parte de su correo anterior a la "@", capitalizada
(`alexsaz03@gmail.com` -> `Alexsaz03`) — visible y corregible desde la pantalla de las
personas de la casa, nunca un hueco en blanco.

Reversible A PROPÓSITO (a diferencia de las migraciones de la unidad 023: aquí no se pierde
ni se funde ningún dato, solo se rellena un campo nuevo): "el nombre se vacía al deshacer" es
la promesa literal de la especificación. Al retroceder, Django deshace primero el
`AlterField` de abajo (la columna vuelve a admitir NULL) y LUEGO el `RunPython` en reversa
(que vacía `nombre` para todo el mundo) — el orden inverso exacto de este fichero.
"""

from django.db import migrations, models


def rellenar_nombres_provisionales(apps, schema_editor):
    Persona = apps.get_model("hogares", "Persona")
    # `select_related("usuario")` para no lanzar una consulta por fila al leer el correo.
    for persona in Persona.objects.select_related("usuario").all():
        if persona.usuario_id:
            local = persona.usuario.email.split("@", 1)[0]
            nombre_provisional = local.capitalize()
        else:
            # Defensivo: hoy no puede darse (nadie sin cuenta existía antes de esta unidad),
            # pero una migración de datos no debe asumir lo que no puede comprobar.
            nombre_provisional = f"Persona {persona.pk}"
        persona.nombre = nombre_provisional
        persona.save(update_fields=["nombre"])


def vaciar_nombres(apps, schema_editor):
    """Reversa: "el nombre se vacía al deshacer" (Cómo, punto 2 de la especificación de la
    024). No se intenta reconstruir qué era provisional y qué se había corregido a mano — no
    hay forma de distinguirlo desde aquí, y fingir que sí sería peor que ser honesto: TODOS
    los nombres vuelven a estar vacíos, exactamente el estado de antes de esta unidad."""
    Persona = apps.get_model("hogares", "Persona")
    Persona.objects.update(nombre="")


class Migration(migrations.Migration):

    dependencies = [
        ("hogares", "0004_nombre_y_responsable"),
    ]

    operations = [
        migrations.RunPython(rellenar_nombres_provisionales, reverse_code=vaciar_nombres),
        migrations.AlterField(
            model_name="persona",
            name="nombre",
            field=models.CharField(max_length=100),
        ),
    ]
