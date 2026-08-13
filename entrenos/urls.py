from django.urls import path

from . import views

app_name = "entrenos"

urlpatterns = [
    path("", views.ver_entrenos, name="ver_mios"),
    path("<int:persona_id>/", views.ver_entrenos, name="ver"),
    path("<int:persona_id>/apuntar/", views.apuntar, name="apuntar"),
    path("<int:persona_id>/<int:entreno_id>/corregir/", views.corregir, name="corregir"),
    path("<int:persona_id>/<int:entreno_id>/borrar/", views.borrar, name="borrar"),
]
