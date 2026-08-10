from django.urls import path

from . import views

app_name = "recetas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.nueva, name="nueva"),
    path("<int:receta_id>/", views.detalle, name="detalle"),
    path("<int:receta_id>/editar/", views.editar, name="editar"),
    path("<int:receta_id>/borrar/", views.borrar, name="borrar"),
]
