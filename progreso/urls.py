from django.urls import path

from . import views

app_name = "progreso"

urlpatterns = [
    path("", views.ver_progreso, name="ver_mio"),
    path("<int:persona_id>/", views.ver_progreso, name="ver"),
]
