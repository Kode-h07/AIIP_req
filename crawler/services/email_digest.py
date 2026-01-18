from datetime import timedelta
from collections import defaultdict
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives

from crawler.models import ReportItem


def _section(item: ReportItem) -> str:
    host = (urlparse(item.landing_page_url or "").netloc or "").lower()
    src = (item.source_name or "").lower()

    if any(x in host for x in ["wipo.int", "oecd.org", "wto.org", "unesco.org"]) or any(
        x in src for x in ["wipo", "oecd", "wto", "unesco"]
    ):
        return "IGO / Multilateral"
    if (
        host.endswith(".gov.uk")
        or "intellectual-property-office" in (item.landing_page_url or "")
        or "uk" in src
    ):
        return "UK"
    if (
        any(
            x in host
            for x in ["europa.eu", "euipo.europa.eu", "epo.org", "edpb.europa.eu"]
        )
        or "europe" in src
        or "eu" in src
    ):
        return "EU"
    if (
        any(
            x in host
            for x in [
                "uspto.gov",
                "copyright.gov",
                "commerce.gov",
                "whitehouse.gov",
                "congress.gov",
            ]
        )
        or "united states" in src
        or src.startswith("us ")
    ):
        return "US"
    return "General / Other"


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_digest_queryset(days: int = 10, limit: int = 40):
    cutoff = timezone.now() - timedelta(days=days)
    return ReportItem.objects.filter(
        sent_at__isnull=True,
        published_at__isnull=False,
        published_at__gte=cutoff,
        ai_ip_verified=True,
    ).order_by("-ai_ip_score", "-published_at", "-id")[:limit]


def render_digest(items, days: int = 10) -> tuple[str, str]:
    now_kst = timezone.localtime(timezone.now())
    subject = (
        f"AI × IP Weekly Digest (last {days} days) — {now_kst.strftime('%Y-%m-%d')}"
    )

    if not items:
        html = f"<h2>{_escape(subject)}</h2><p>No new recent report PDFs found (or all already sent).</p>"
        return subject, html

    buckets = defaultdict(list)
    for it in items:
        buckets[_section(it)].append(it)

    order = ["General / Other", "US", "EU", "UK", "IGO / Multilateral"]
    sections = [s for s in order if s in buckets] + [
        s for s in buckets.keys() if s not in order
    ]

    parts = [f"<h2>{_escape(subject)}</h2>"]
    parts.append("<p>Each item includes Source, Date, Landing Page, and PDF link.</p>")

    for sec in sections:
        parts.append(f"<h3>{_escape(sec)}</h3><ul>")
        for it in buckets[sec]:
            title = _escape(it.title or "(untitled)")
            source = _escape(it.source_name or "Unknown source")
            date = it.published_at.date().isoformat() if it.published_at else "N/A"
            page = _escape(it.landing_page_url or "")
            pdf = _escape(it.report_url or "")

            parts.append(
                "<li>"
                f"<b>{title}</b><br/>"
                f"Source: {source}<br/>"
                f"Date: {date}<br/>"
                f"Page: <a href='{page}'>{page}</a><br/>"
                f"PDF: <a href='{pdf}'>{pdf}</a>"
                "</li>"
            )
        parts.append("</ul>")

    return subject, "\n".join(parts)


def send_weekly_digest(days: int = 10, limit: int = 40) -> int:
    to_email = getattr(settings, "DIGEST_TO_EMAIL", "")
    if not to_email:
        raise RuntimeError("DIGEST_TO_EMAIL is not set (.env / settings).")

    items = list(build_digest_queryset(days=days, limit=limit))
    subject, html = render_digest(items, days=days)

    msg = EmailMultiAlternatives(
        subject=subject,
        body="HTML-only digest. Please use an HTML-capable email client.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html, "text/html")
    msg.send()

    # Mark sent to avoid duplicates next week
    now = timezone.now()
    for it in items:
        it.sent_at = now
    if items:
        ReportItem.objects.bulk_update(items, ["sent_at"])

    return len(items)
