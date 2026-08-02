from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    El `UserAdmin` de Django asume que hay un `username`. Como aquí no lo hay (el correo hace
    ese papel, ver `models.py`), hay que decirle explícitamente con qué campos trabajar.
    """

    ordering = ["email"]
    list_display = ["email", "hogar", "is_staff", "is_active"]
    search_fields = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name")}),
        ("Hogar", {"fields": ("hogar", "codigo_hogar_pendiente")}),
        (
            "Permisos",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
