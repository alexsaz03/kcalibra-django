"""
Unidad 023, paso 3 de 8 — a cada cuenta que ya existía se le da SU persona, con su hogar.

Es el paso que convierte "una fila de `cuentas_usuario` es una persona" en "una persona es una
fila de `hogares_persona`". Después de esto, los cuatro pasos siguientes pueden traducir los
dueños de los datos personales sin adivinar nada: cada `usuario_id` tiene ya su `persona_id`.

Irreversible A PROPÓSITO — ver `_irreversible` más abajo, y el precedente de la unidad 017
(`despensa/migrations/0002_funde_pesos_y_liquidos_en_su_unidad_pequena.py`).
"""

from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

MOTIVO_IRREVERSIBLE = (
    "La unidad 023 (separar la persona de la cuenta) no se puede deshacer con una migración "
    "inversa: en cuanto exista una persona SIN cuenta —que es justo para lo que nace "
    "`hogares.Persona`— sus pesadas, entrenos, planes y cierres no tienen ningún `Usuario` al "
    "que volver, y una inversa tendría que inventárselo o tirar esos datos. El rollback real "
    "es restaurar desde la copia de las seis tablas tomada ANTES de migrar (`pg_dump` de "
    "perfiles_perfil, perfiles_medicionpeso, entrenos_entreno, planes_plandedia, "
    "cierres_cierrededia y cierres_diasaltado, más cuentas_usuario), no una migración inversa."
)


def una_persona_por_cada_cuenta(apps, schema_editor):
    """
    Una `Persona` por cada `Usuario`, heredando su hogar tal cual — incluido el `None` de quien
    está esperando que le acepten (R5/R14 de la unidad 003): ese estado se copia, no se
    "arregla".

    `bulk_create` en vez de un `create` por fila: son pocas cuentas, pero así la migración es
    una sola escritura y no depende de que ningún `save()` dispare señales (las señales de la
    app apuntan al modelo REAL, no al histórico que se usa aquí, así que no se disparan — y es
    lo que se quiere: quien decide lo que hay que crear es esta función, no un enganche).
    """
    Usuario = apps.get_model("cuentas", "Usuario")
    Persona = apps.get_model("hogares", "Persona")

    ya_tienen = set(Persona.objects.exclude(usuario=None).values_list("usuario_id", flat=True))
    Persona.objects.bulk_create(
        [
            Persona(usuario_id=usuario.id, hogar_id=usuario.hogar_id)
            for usuario in Usuario.objects.all().order_by("id")
            if usuario.id not in ya_tienen
        ]
    )


def _irreversible(apps, schema_editor):
    """
    Unidad 017, lección heredada: dejar `reverse_code` sin poner ya hace que Django levante un
    `IrreversibleError`, pero con un mensaje genérico que no explica nada ni dice qué hacer.
    Escribir la función a mano permite decir el motivo Y el rollback de verdad.
    """
    raise IrreversibleError(MOTIVO_IRREVERSIBLE)


class Migration(migrations.Migration):

    dependencies = [
        ("hogares", "0002_persona"),
    ]

    operations = [
        migrations.RunPython(una_persona_por_cada_cuenta, _irreversible),
    ]
