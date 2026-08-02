from django.contrib import admin

from .models import Hogar, SolicitudEntrada


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
