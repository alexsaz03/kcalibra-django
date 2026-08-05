"""
La lógica de negocio de "cerrar el día" (unidad 012, decir-si-cumpliste.md): guardar el cierre
sustituyendo el de antes si lo había (R3), guardar la foto del menú solo cuando toca (R4/R5), y
decidir si hay que preguntar al abrir la app y por qué día (R6-R9). Vive separada de las
vistas, igual que el resto de la app (`entrenos/logica.py`, `planes/logica.py`...).
"""

from datetime import timedelta

from django.utils import timezone

from planes.logica import obtener_plan_de
from servicios.cierres import calcular_dia_pendiente

from .models import CierreDeDia, ComidaSeguida, DiaSaltado, MenuSeguido


def _guardar_foto_del_menu(cierre):
    """
    R4/G-161/Q-142 — congela las comidas del `PlanDeDia` de `cierre.usuario` en `cierre.fecha`
    dentro de un `MenuSeguido` nuevo. Borra primero cualquier foto anterior de ESTE cierre (R3:
    si se está SUSTITUYENDO un cierre que ya tenía foto —por ejemplo, se cambió la respuesta de
    "a medias" a "lo seguí"— la foto vieja no debe quedar huérfana ni duplicada).

    R5 (caso límite) — sin ningún plan puesto ese día, no hay nada que fotografiar: no se crea
    ningún `MenuSeguido` (una foto vacía no aporta nada y complicaría distinguir "sin plan" de
    "plan con cero comidas"), y la pantalla no se rompe por ello.
    """
    MenuSeguido.objects.filter(cierre=cierre).delete()

    plan = obtener_plan_de(cierre.usuario, cierre.fecha)
    if plan is None:
        return
    comidas = list(plan.comidas.all())
    if not comidas:
        return

    menu = MenuSeguido.objects.create(cierre=cierre)
    ComidaSeguida.objects.bulk_create(
        [
            ComidaSeguida(
                menu=menu,
                nombre=comida.nombre,
                momento_del_dia=comida.momento_del_dia,
                calorias=comida.calorias,
                proteina_g=comida.proteina_g,
                grasa_g=comida.grasa_g,
                carbos_g=comida.carbos_g,
            )
            for comida in comidas
        ]
    )


def cerrar_dia(usuario, datos):
    """
    R3 — cierra (o SUSTITUYE, si `usuario` ya tenía un cierre en `datos["fecha"]`) el día de
    `usuario`. `datos` trae al menos "fecha" y "respuesta"; "calorias_comidas" y "nota" son
    opcionales (R1/R2), y en su ausencia quedan en blanco (`None` y `""`, nunca reventando por
    una clave que falta).

    R4/G-161/Q-142 — la foto del menú SOLO se guarda (o se re-guarda, por si el plan cambió
    entre un cierre y su sustitución) cuando la respuesta es "lo seguí" ENTERO; con "a medias"
    o "no lo seguí" cualquier foto que hubiera de un cierre anterior de ese mismo día se borra
    (si se venía de "lo seguí" y se cambia de opinión, la foto deja de tener sentido: el
    registro del día queda, pero el menú NO).
    """
    cierre, _creado = CierreDeDia.objects.update_or_create(
        usuario=usuario,
        fecha=datos["fecha"],
        defaults={
            "respuesta": datos["respuesta"],
            "calorias_comidas": datos.get("calorias_comidas"),
            "nota": datos.get("nota") or "",
        },
    )
    if cierre.respuesta == CierreDeDia.LO_SEGUI:
        _guardar_foto_del_menu(cierre)
    else:
        MenuSeguido.objects.filter(cierre=cierre).delete()
    return cierre


def dia_pendiente_de_preguntar(usuario):
    """
    R6/R7/R8/R9 — envuelve `servicios.cierres.calcular_dia_pendiente` (la función pura) con
    los datos reales de `usuario`: si "ayer" ya está cerrado, y si "ayer" ya se saltó. Ninguna
    otra fecha entra en la cuenta (R7): comprobar solo "ayer", nunca "el cierre más reciente en
    general", es lo que evita que un cierre de HOY (R9, hecho a mano desde Progreso) tape por
    error la pregunta pendiente de AYER si ayer sigue sin cerrar.
    """
    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    cerrado_ayer = CierreDeDia.objects.filter(usuario=usuario, fecha=ayer).exists()
    salto = DiaSaltado.objects.filter(usuario=usuario).first()
    saltado_ayer = salto is not None and salto.fecha >= ayer
    return calcular_dia_pendiente(hoy, cerrado_ayer, saltado_ayer)


def saltar_dia_pendiente(usuario):
    """
    R8/Q-141 — registra que el día pendiente ACTUAL de `usuario` (si lo hay) se saltó, para que
    `dia_pendiente_de_preguntar` no lo vuelva a ofrecer jamás. Si no hay ningún día pendiente
    ahora mismo (ya se cerró, o ya se había saltado antes), no hace nada: no hay nada que
    saltar, y sobrescribir `DiaSaltado` con `None` sería un dato falso.
    """
    dia = dia_pendiente_de_preguntar(usuario)
    if dia is None:
        return None
    DiaSaltado.objects.update_or_create(usuario=usuario, defaults={"fecha": dia})
    return dia
