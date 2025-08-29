from django.contrib import admin
from .models import AIJob, AIMetric


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "status", "org_id", "created_by", "created_at")
    list_filter = ("type", "status", "org_id")
    search_fields = ("id", "org_id", "error_text")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIMetric)
class AIMetricAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "model_id", "duration_ms", "tokens_used", "success", "org_id", "created_at")
    list_filter = ("type", "model_id", "success", "org_id")
    search_fields = ("model_id", "org_id", "error_text")
    readonly_fields = ("created_at",)
