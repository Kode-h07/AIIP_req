# crawler/services/store.py
from django.db import transaction
from crawler.models import ReportItem
from crawler.services.extract_date import is_recent


@transaction.atomic
def upsert_recent_report(
    source_name: str,
    source_type: str,
    title: str,
    landing_page_url: str,
    report_url: str,
    report_format: str,
    published_at,
    published_at_source,
    published_at_raw,
    days: int = 10,
):
    # Hard rule: must have published_at AND must be recent
    if not is_recent(published_at, days=days):
        return None, False

    obj, created = ReportItem.objects.get_or_create(
        report_url=report_url,
        defaults={
            "source_name": source_name[:255] if source_name else "",
            "source_type": source_type or "other",
            "title": (title or "")[:600],
            "landing_page_url": landing_page_url or "",
            "report_format": report_format or "",
            "published_at": published_at,
            "published_at_source": published_at_source or "",
            "published_at_raw": published_at_raw or "",
        },
    )

    # If exists but missing fields, update lightly
    updated = False
    if not created:
        if title and not obj.title:
            obj.title = title[:600]
            updated = True
        if landing_page_url and not obj.landing_page_url:
            obj.landing_page_url = landing_page_url
            updated = True
        if published_at and (
            obj.published_at is None or published_at > obj.published_at
        ):
            obj.published_at = published_at
            updated = True
        if source_name and not obj.source_name:
            obj.source_name = source_name[:255]
            updated = True
        if source_type and obj.source_type == "other":
            obj.source_type = source_type
            updated = True
        if report_format and not obj.report_format:
            obj.report_format = report_format
            updated = True
        if updated:
            obj.save()

    return obj, (created or updated)
