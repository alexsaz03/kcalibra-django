from decimal import Decimal

import django.core.validators
import django.utils.timezone
from django.db import migrations, models

import perfiles.models


def _dejar_solo_la_ultima_medicion_por_dia(apps, schema_editor):
    """
    Paso extra del plan de la unidad 006 (docs/05-trabajo/006-apuntar-el-peso/especificacion.md):
    antes de que la restricción de unicidad de más abajo pueda aplicarse sobre datos que ya
    existan, hay que resolver los duplicados que pudiera haber — si alguna persona ya tenía
    más de una medición apuntada el mismo día (algo que hasta esta migración el modelo
    permitía), esta función se queda con la ÚLTIMA que se apuntó (la de mayor id: no hay
    ningún otro campo de fecha de creación en este modelo) y borra las demás, en vez de dejar
    que la restricción reviente al aplicarse.
    """
    MedicionPeso = apps.get_model("perfiles", "MedicionPeso")
    vistos = set()
    ids_a_borrar = []
    # Orden descendente de id DENTRO de cada (usuario, fecha): la primera vez que aparece una
    # clave es la de mayor id (la última apuntada), así que esa se conserva; el resto de esa
    # misma clave se marca para borrar.
    consulta = MedicionPeso.objects.order_by("usuario_id", "fecha", "-id")
    for medicion in consulta:
        clave = (medicion.usuario_id, medicion.fecha)
        if clave in vistos:
            ids_a_borrar.append(medicion.id)
        else:
            vistos.add(clave)
    if ids_a_borrar:
        MedicionPeso.objects.filter(id__in=ids_a_borrar).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("perfiles", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="medicionpeso",
            name="grasa_pct",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=4,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
                verbose_name="grasa corporal (%)",
            ),
        ),
        migrations.AddField(
            model_name="medicionpeso",
            name="cintura_cm",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=5,
                null=True,
                verbose_name="cintura (cm)",
            ),
        ),
        migrations.AlterField(
            model_name="medicionpeso",
            name="fecha",
            field=models.DateField(
                default=django.utils.timezone.localdate,
                validators=[perfiles.models._fecha_no_futura],
            ),
        ),
        # Dedupe ANTES de la restricción: si esta base ya tenía duplicados, se resuelven aquí
        # (se queda con el último) en vez de que la migración reviente al añadir la
        # restricción de abajo.
        migrations.RunPython(
            _dejar_solo_la_ultima_medicion_por_dia, migrations.RunPython.noop
        ),
        migrations.AddConstraint(
            model_name="medicionpeso",
            constraint=models.UniqueConstraint(
                fields=("usuario", "fecha"), name="una_medicion_por_persona_y_dia"
            ),
        ),
    ]
