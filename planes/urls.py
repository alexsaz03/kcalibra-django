from django.urls import path

from . import views

app_name = "planes"

urlpatterns = [
    path("<int:usuario_id>/apuntar/", views.apuntar_plan, name="apuntar"),
]
