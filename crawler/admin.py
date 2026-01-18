from django.contrib import admin
from .models import ReportItem


@admin.register(ReportItem)
class ReportItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_name",
        "source_type",
        "title",
        "published_at",
        "sent_at",
    )
    list_filter = ("source_type", "sent_at")
    search_fields = ("title", "source_name", "landing_page_url", "report_url")
    readonly_fields = ("discovered_at",)
