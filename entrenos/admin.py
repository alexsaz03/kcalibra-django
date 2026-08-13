from django.contrib import admin

from .models import Entreno


@admin.register(Entreno)
class EntrenoAdmin(admin.ModelAdmin):
    list_display = ["persona", "fecha", "deporte", "intensidad", "minutos", "calorias", "origen"]
    list_filter = ["deporte", "intensidad", "origen", "fecha"]
    search_fields = ["persona__usuario__email"]
    ordering = ["-fecha"]
