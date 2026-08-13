from django.urls import path

from . import views

app_name = "planes"

urlpatterns = [
    path("<int:persona_id>/apuntar/", views.apuntar_plan, name="apuntar"),
]
