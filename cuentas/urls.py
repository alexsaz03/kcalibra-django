from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path(
        "esperando-verificacion/",
        views.esperando_verificacion,
        name="esperando_verificacion",
    ),
    path(
        "esperando-verificacion/reenviar/",
        views.reenviar_verificacion,
        name="reenviar_verificacion",
    ),
    path(
        "esperando-verificacion/corregir/",
        views.corregir_correo,
        name="corregir_correo",
    ),
    path("borrar/", views.borrar_cuenta, name="borrar_cuenta"),
]
