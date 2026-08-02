from django.contrib import admin

from .models import MedicionPeso, Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ["usuario", "sexo", "actividad", "objetivo", "ajuste_pct"]
    list_filter = ["sexo", "actividad", "objetivo"]
    search_fields = ["usuario__email"]


@admin.register(MedicionPeso)
class MedicionPesoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "fecha", "peso_kg"]
    list_filter = ["fecha"]
    search_fields = ["usuario__email"]
    ordering = ["-fecha"]
