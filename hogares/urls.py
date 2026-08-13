from django.urls import path

from . import views

app_name = "hogares"

urlpatterns = [
    path("mi-hogar/", views.mi_hogar, name="mi_hogar"),
    path(
        "mi-hogar/solicitudes/<int:pk>/aceptar/",
        views.aceptar_solicitud,
        name="aceptar_solicitud",
    ),
    path(
        "mi-hogar/solicitudes/<int:pk>/rechazar/",
        views.rechazar_solicitud,
        name="rechazar_solicitud",
    ),
    path(
        "mi-hogar/dar-de-alta/",
        views.dar_de_alta_persona_a_cargo,
        name="dar_de_alta_persona_a_cargo",
    ),
]
