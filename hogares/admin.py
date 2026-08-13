from django.contrib import admin

from .models import Hogar, Persona, SolicitudEntrada


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    """Unidad 023 — quién vive en cada casa. Aquí es donde se edita ahora el hogar de alguien:
    antes era un campo de `cuentas.Usuario`, y dejó de serlo.

    Unidad 024 — `nombre` y `responsable` (R-98/R-99): quien administra ve de un vistazo quién
    es cada cual y quién está a cargo de quién, sin tener que abrir cada ficha."""

    list_display = ["nombre", "hogar", "usuario", "responsable"]
    list_select_related = ["hogar", "usuario", "responsable"]
    search_fields = ["nombre", "usuario__email", "hogar__codigo"]


@admin.register(Hogar)
class HogarAdmin(admin.ModelAdmin):
    list_display = ["codigo", "creado_en"]
    search_fields = ["codigo"]
    readonly_fields = ["codigo", "creado_en"]


@admin.register(SolicitudEntrada)
class SolicitudEntradaAdmin(admin.ModelAdmin):
    list_display = ["usuario", "hogar", "estado", "creada_en", "resuelta_en"]
    list_filter = ["estado"]
    search_fields = ["usuario__email", "hogar__codigo"]
