from django.urls import path

from . import views

app_name = "perfiles"

urlpatterns = [
    path("", views.ver_perfil, name="ver_mio"),
    path("peso/", views.ver_peso, name="peso_mio"),
    path("<int:persona_id>/", views.ver_perfil, name="ver"),
    path("<int:persona_id>/actualizar/", views.actualizar_perfil, name="actualizar"),
    path("<int:persona_id>/peso/", views.ver_peso, name="peso"),
    path("<int:persona_id>/peso/apuntar/", views.apuntar_peso, name="apuntar_peso"),
    path(
        "<int:persona_id>/peso/<int:medicion_id>/borrar/",
        views.borrar_peso,
        name="borrar_peso",
    ),
]
