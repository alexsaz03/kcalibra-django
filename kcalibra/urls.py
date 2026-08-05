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
from django.urls import include, path, re_path

from cuentas import views as cuentas_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Alta, entrada y salida: las trae "allauth" (decisión del curso, ver bias.md) — pero
    # SOLO las rutas que esta unidad especifica y prueba (H3 de la revisión de la 2ª ronda):
    # `include("allauth.urls")` monta de más, entre otras cosas la gestión de direcciones de
    # correo (`account_email`: añadir, cambiar y quitar — la misma superficie que H1), sin
    # especificación ni tests en esta unidad. "Fuera de alcance" significa que ese
    # comportamiento no se entrega: no basta con no escribirle vistas propias si `allauth` ya
    # las expone solas.
    #
    # La recuperación de contraseña (R-22) SÍ entra, desde la unidad 008 — ver el bloque de
    # rutas justo debajo de las de siempre, montadas una a una con el mismo criterio.
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
    # Recuperar la contraseña (unidad 008, R2-R4/R-22). Las mismas cuatro rutas que trae
    # `allauth.account.urls` para este flujo (con `ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED` en
    # su valor por defecto, False: el enlace por correo, no un código de 6 dígitos), montadas
    # una a una con el mismo criterio que el resto de este fichero.
    path(
        "cuentas/password/reset/",
        allauth_views.password_reset,
        name="account_reset_password",
    ),
    path(
        "cuentas/password/reset/done/",
        allauth_views.password_reset_done,
        name="account_reset_password_done",
    ),
    # El enlace del correo apunta aquí: `uidb36` identifica a quién, `key` es el token que
    # demuestra que el enlace es el de verdad (allauth lo firma con HMAC, igual que el de
    # verificación de correo — no se guarda en ninguna tabla). Mismo patrón que trae
    # `allauth.account.urls`, copiado tal cual: la parte "-(?P<key>.+)" es la que hace que un
    # token caducado o ya usado no case con nada y caiga en la rama `token_fail` de la vista.
    re_path(
        r"^cuentas/password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
        allauth_views.password_reset_from_key,
        name="account_reset_password_from_key",
    ),
    path(
        "cuentas/password/reset/key/done/",
        allauth_views.password_reset_from_key_done,
        name="account_reset_password_from_key_done",
    ),
    # Las pantallas propias de esta unidad que allauth no cubre (esperar la verificación,
    # pedir otro correo, corregir la dirección — ver cuentas/views.py).
    path("cuentas/", include("cuentas.urls")),
    # El hogar: su código, quién está dentro, las peticiones pendientes.
    path("hogares/", include("hogares.urls")),
    # Los datos físicos, el objetivo y las calorías del día de cada persona (unidad 004).
    path("perfiles/", include("perfiles.urls")),
    # El plan de comidas del día, apuntado a mano (unidad 005).
    path("planes/", include("planes.urls")),
    # La evolución de peso, grasa y cintura de cada persona (unidad 010).
    path("progreso/", include("progreso.urls")),
    # Lo que has entrenado, apuntado a mano, y cuánto le suma al objetivo del día (unidad 011).
    path("entrenos/", include("entrenos.urls")),
    # Cerrar el día: si se siguió el plan, con la pregunta al abrir la app (unidad 012).
    path("cierres/", include("cierres.urls")),
    # Lo que hay en casa, agrupado por categorías: añadir, corregir y quitar productos a
    # mano (unidad 014). Es DEL HOGAR entero, no de una persona: sin ningún usuario_id en
    # sus rutas.
    path("despensa/", include("despensa.urls")),
    # La portada y sus rutas viven en la app "paginas" (paginas/urls.py).
    path("", include("paginas.urls")),
]
