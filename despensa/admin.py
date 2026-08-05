from django.contrib import admin

from .models import ProductoDespensa


@admin.register(ProductoDespensa)
class ProductoDespensaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "cantidad", "unidad", "categoria", "hogar", "en_casa_desde"]
    list_filter = ["categoria", "unidad"]
    search_fields = ["nombre", "hogar__codigo"]
    ordering = ["categoria", "nombre"]
