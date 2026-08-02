from django.urls import path

from . import views

app_name = "perfiles"

urlpatterns = [
    path("", views.ver_perfil, name="ver_mio"),
    path("<int:usuario_id>/", views.ver_perfil, name="ver"),
    path("<int:usuario_id>/actualizar/", views.actualizar_perfil, name="actualizar"),
]
