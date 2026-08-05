from django.urls import path

from . import views

app_name = "cierres"

urlpatterns = [
    path("<int:usuario_id>/responder/", views.responder, name="responder"),
    path("<int:usuario_id>/saltar/", views.saltar, name="saltar"),
    path("<int:usuario_id>/", views.cerrar, name="cerrar"),
]
