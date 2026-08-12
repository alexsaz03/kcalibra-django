from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    El `UserAdmin` de Django asume que hay un `username`. Como aquí no lo hay (el correo hace
    ese papel, ver `models.py`), hay que decirle explícitamente con qué campos trabajar.

    Unidad 023 — `Usuario` ya no tiene `hogar`: la columna de la lista se calcula desde su
    persona (`hogar_de_la_persona`, aquí abajo) para que esta pantalla siga enseñando lo mismo
    que enseñaba, y el hogar se EDITA donde vive ahora, en el admin de `hogares.Persona`.
    """

    ordering = ["email"]
    list_display = ["email", "hogar_de_la_persona", "is_staff", "is_active"]
    search_fields = ["email"]

    @admin.display(description="hogar", ordering="persona__hogar")
    def hogar_de_la_persona(self, obj):
        persona = getattr(obj, "persona", None)
        return persona.hogar if persona is not None else None

    def get_queryset(self, request):
        # Sin esto, pintar la columna del hogar sería una consulta por fila de la lista.
        return super().get_queryset(request).select_related("persona__hogar")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name")}),
        ("Hogar", {"fields": ("codigo_hogar_pendiente",)}),
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
