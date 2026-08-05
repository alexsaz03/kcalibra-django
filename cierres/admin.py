from django.contrib import admin

from .models import CierreDeDia, ComidaSeguida, DiaSaltado, MenuSeguido


class ComidaSeguidaInline(admin.TabularInline):
    model = ComidaSeguida
    extra = 0


@admin.register(MenuSeguido)
class MenuSeguidoAdmin(admin.ModelAdmin):
    list_display = ["cierre", "creado_en"]
    inlines = [ComidaSeguidaInline]


@admin.register(CierreDeDia)
class CierreDeDiaAdmin(admin.ModelAdmin):
    list_display = ["usuario", "fecha", "respuesta", "calorias_comidas"]
    list_filter = ["respuesta", "fecha"]
    search_fields = ["usuario__email"]
    ordering = ["-fecha"]


@admin.register(DiaSaltado)
class DiaSaltadoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "fecha"]
    search_fields = ["usuario__email"]
