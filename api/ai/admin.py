from django.contrib import admin
from .models import AIResource, AIChunk, AIJob, AIMetric


@admin.register(AIResource)
class AIResourceAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "title", "source_url", "created_at")
    search_fields = ("title", "source_url", "type", "sha256")
    list_filter = ("type", "created_at")
    date_hierarchy = "created_at"


@admin.register(AIChunk)
class AIChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "resource", "ord", "token_len", "created_at")
    search_fields = ("text", "embedding_key")
    list_filter = ("created_at",)
    raw_id_fields = ("resource",)


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
