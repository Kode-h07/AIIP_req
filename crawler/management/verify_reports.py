from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from crawler.models import ReportItem
from crawler.services.fetch import fetch_html
from crawler.services.gemini_verify import verify_ai_ip_report


def _extract_excerpt(html: str) -> str:
    # Keep simple: strip to a short excerpt
    # If you already have a cleaner/extractor, use it here.
    text = html
    # very rough de-tagging if needed:
    for ch in ["\n", "\r", "\t"]:
        text = text.replace(ch, " ")
    text = " ".join(text.split())
    return text[:1500]


class Command(BaseCommand):
    help = "Verify recent unsent items via Gemini to ensure AI×IP report relevance; stores ai_ip_verified/score/reason."

    def handle(self, *args, **options):
        days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)
        limit = int(__import__("os").getenv("GEMINI_VERIFY_LIMIT", "60"))

        cutoff = timezone.now() - timedelta(days=days)

        qs = (
            ReportItem.objects.filter(
                sent_at__isnull=True,
                published_at__isnull=False,
                published_at__gte=cutoff,
            )
            .filter(ai_ip_verified__isnull=True)
            .order_by("-published_at", "-id")[:limit]
        )

        items = list(qs)
        self.stdout.write(
            f"[VERIFY] candidates={len(items)} (limit={limit}, window={days}d)"
        )

        for i, it in enumerate(items, start=1):
            self.stdout.write(f"[VERIFY {i}/{len(items)}] {it.landing_page_url}")

            # 1) Fetch landing page to supply excerpt (verification based on website)
            status, html, _ = fetch_html(it.landing_page_url)
            if status >= 400 or not html:
                it.ai_ip_verified = False
                it.ai_ip_score = 0
                it.ai_ip_reason = f"Could not fetch landing page (HTTP {status})"
                it.verified_at = timezone.now()
                it.save(
                    update_fields=[
                        "ai_ip_verified",
                        "ai_ip_score",
                        "ai_ip_reason",
                        "verified_at",
                    ]
                )
                continue

            excerpt = _extract_excerpt(html)

            # 2) Gemini verify
            try:
                res = verify_ai_ip_report(
                    title=it.title or "",
                    source_name=it.source_name or "",
                    landing_page_url=it.landing_page_url or "",
                    report_url=it.report_url or "",
                    published_date_iso=(
                        it.published_at.date().isoformat() if it.published_at else None
                    ),
                    page_excerpt=excerpt,
                )
                it.ai_ip_verified = res.is_ai_ip_report
                it.ai_ip_score = res.score
                it.ai_ip_reason = res.reason
                it.verified_at = timezone.now()
                it.save(
                    update_fields=[
                        "ai_ip_verified",
                        "ai_ip_score",
                        "ai_ip_reason",
                        "verified_at",
                    ]
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  -> verified={it.ai_ip_verified} score={it.ai_ip_score} reason={it.ai_ip_reason}"
                    )
                )
            except Exception as e:
                it.ai_ip_verified = False
                it.ai_ip_score = 0
                it.ai_ip_reason = f"Gemini error: {e}"[:200]
                it.verified_at = timezone.now()
                it.save(
                    update_fields=[
                        "ai_ip_verified",
                        "ai_ip_score",
                        "ai_ip_reason",
                        "verified_at",
                    ]
                )
                self.stdout.write(self.style.ERROR(f"  -> Gemini error: {e}"))
