"""
URL configuration for kcalibra project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Alta, entrada y salida: las trae "allauth" (decisión del curso, ver bias.md). Da las
    # URLs con nombre "account_signup", "account_login", "account_logout"... que se usan en
    # las plantillas y en los tests.
    path("cuentas/", include("allauth.urls")),
    # Las pantallas propias de esta unidad que allauth no cubre (esperar la verificación,
    # pedir otro correo, corregir la dirección — ver cuentas/views.py).
    path("cuentas/", include("cuentas.urls")),
    # El hogar: su código, quién está dentro, las peticiones pendientes.
    path("hogares/", include("hogares.urls")),
    # La portada y sus rutas viven en la app "paginas" (paginas/urls.py).
    path("", include("paginas.urls")),
]
