from django.contrib import admin

from .models import IngredienteDeReceta, Receta


class IngredienteDeRecetaInline(admin.TabularInline):
    model = IngredienteDeReceta
    extra = 1


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "raciones", "hogar"]
    search_fields = ["nombre", "hogar__codigo"]
    ordering = ["nombre"]
    inlines = [IngredienteDeRecetaInline]
