from django.contrib import admin

from .models import ComidaDelPlan, PlanDeDia


class ComidaDelPlanInline(admin.TabularInline):
    model = ComidaDelPlan
    extra = 0


@admin.register(PlanDeDia)
class PlanDeDiaAdmin(admin.ModelAdmin):
    list_display = ["persona", "fecha", "hogar"]
    list_filter = ["fecha"]
    search_fields = ["persona__usuario__email"]
    inlines = [ComidaDelPlanInline]
