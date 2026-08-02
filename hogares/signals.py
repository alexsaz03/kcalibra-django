"""
El enganche con `allauth`: en cuanto una dirección de correo queda verificada, si esa persona
tenía un código de hogar pendiente, aquí es donde se convierte en una `SolicitudEntrada` de
verdad (R5, G-37). Ver `hogares.logica.procesar_codigo_al_verificar` para el porqué del
momento exacto.
"""

from allauth.account.signals import email_confirmed
from django.dispatch import receiver

from .logica import procesar_codigo_al_verificar


@receiver(email_confirmed)
def al_confirmar_correo(request, email_address, **kwargs):
    procesar_codigo_al_verificar(email_address.user)
