from django.db import models


class ReportItem(models.Model):
    SOURCE_TYPES = [
        ("government", "Government"),
        ("intergovernmental", "Intergovernmental"),
        ("regulator", "Regulator"),
        ("court", "Court"),
        ("research_center", "Research Center"),
        ("university", "University"),
        ("law_firm", "Law Firm"),
        ("consulting_firm", "Consulting Firm"),
        ("think_tank", "Think Tank"),
        ("standards_body", "Standards Body"),
        ("other", "Other"),
    ]

    source_name = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPES, default="other")

    title = models.CharField(max_length=600, blank=True)

    landing_page_url = models.URLField(max_length=2000, blank=True)
    report_url = models.URLField(max_length=2000, blank=True)
    report_format = models.CharField(max_length=16, blank=True)  # pdf/html/docx/other

    published_at = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField(auto_now_add=True)

    content_hash = models.CharField(max_length=64, blank=True)
    summary_json = models.JSONField(null=True, blank=True)
    published_at_source = models.CharField(
        max_length=64, blank=True, default=""
    )  # e.g., meta:article:published_time
    published_at_raw = models.CharField(
        max_length=128, blank=True, default=""
    )  # raw string found in HTML

    sent_at = models.DateTimeField(null=True, blank=True)

    ai_ip_verified = models.BooleanField(null=True, blank=True)  # None=not checked yet
    ai_ip_score = models.IntegerField(null=True, blank=True)  # 0-100
    ai_ip_reason = models.TextField(blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["sent_at"]),
            models.Index(fields=["source_type"]),
            models.Index(fields=["published_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["report_url"],
                name="uq_report_url_nonempty",
                condition=~models.Q(report_url=""),
            )
        ]

    def __str__(self):
        base = self.title or "(untitled)"
        src = self.source_name or "Unknown"
        return f"{src} | {base}"
