from django.urls import path

from . import views

app_name = "despensa"

urlpatterns = [
    path("", views.ver_despensa, name="ver"),
    path("anadir/", views.anadir, name="anadir"),
    path("<int:producto_id>/corregir/", views.corregir, name="corregir"),
    path("<int:producto_id>/quitar/", views.quitar, name="quitar"),
]
