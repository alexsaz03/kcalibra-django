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

from allauth.account import views as allauth_views
from django.contrib import admin
from django.urls import include, path

from cuentas import views as cuentas_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Alta, entrada y salida: las trae "allauth" (decisión del curso, ver bias.md) — pero
    # SOLO las rutas que esta unidad especifica y prueba (H3 de la revisión de la 2ª ronda):
    # `include("allauth.urls")` monta de más, entre otras cosas la recuperación de contraseña
    # (R-22, fuera de alcance por escrito) y la gestión de direcciones de correo
    # (`account_email`: añadir, cambiar y quitar — la misma superficie que H1), ninguna de las
    # dos con especificación ni tests en esta unidad. "Fuera de alcance" significa que ese
    # comportamiento no se entrega: no basta con no escribirle vistas propias si `allauth` ya
    # las expone solas.
    #
    # `signup` es la ÚNICA vista de las de abajo que NO es la de `allauth` a secas: es
    # `cuentas.views.signup`, que la envuelve para R2/C-14 (ver ese fichero).
    path("cuentas/signup/", cuentas_views.signup, name="account_signup"),
    path("cuentas/login/", allauth_views.login, name="account_login"),
    path("cuentas/logout/", allauth_views.logout, name="account_logout"),
    path("cuentas/inactive/", allauth_views.account_inactive, name="account_inactive"),
    path(
        "cuentas/password/change/",
        allauth_views.password_change,
        name="account_change_password",
    ),
    path(
        "cuentas/confirm-email/<str:key>/",
        allauth_views.confirm_email,
        name="account_confirm_email",
    ),
    # Las pantallas propias de esta unidad que allauth no cubre (esperar la verificación,
    # pedir otro correo, corregir la dirección — ver cuentas/views.py).
    path("cuentas/", include("cuentas.urls")),
    # El hogar: su código, quién está dentro, las peticiones pendientes.
    path("hogares/", include("hogares.urls")),
    # Los datos físicos, el objetivo y las calorías del día de cada persona (unidad 004).
    path("perfiles/", include("perfiles.urls")),
    # La portada y sus rutas viven en la app "paginas" (paginas/urls.py).
    path("", include("paginas.urls")),
]
