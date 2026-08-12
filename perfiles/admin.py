from django.contrib import admin

from .models import MedicionPeso, Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ["persona", "sexo", "actividad", "objetivo", "ajuste_pct"]
    list_filter = ["sexo", "actividad", "objetivo"]
    search_fields = ["persona__usuario__email"]


@admin.register(MedicionPeso)
class MedicionPesoAdmin(admin.ModelAdmin):
    list_display = ["persona", "fecha", "peso_kg", "grasa_pct", "cintura_cm"]
    list_filter = ["fecha"]
    search_fields = ["persona__usuario__email"]
    ordering = ["-fecha"]
