from django.urls import path

from . import views

app_name = "cierres"

urlpatterns = [
    path("<int:persona_id>/responder/", views.responder, name="responder"),
    path("<int:persona_id>/saltar/", views.saltar, name="saltar"),
    path("<int:persona_id>/", views.cerrar, name="cerrar"),
]
