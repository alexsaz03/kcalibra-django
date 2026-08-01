from django.urls import path

from . import views

app_name = "paginas"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("hora-servidor/", views.hora_servidor, name="hora_servidor"),
]
