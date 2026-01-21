import os
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone

from crawler.models import ReportItem


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _get_to_email() -> str:
    to_email = _env("DIGEST_TO_EMAIL")
    if not to_email:
        raise ValueError("DIGEST_TO_EMAIL is not set in .env")
    return to_email


def _get_from_email() -> str:
    from_email = _env("DIGEST_FROM_EMAIL") or _env("EMAIL_HOST_USER")
    if not from_email:
        raise ValueError("DIGEST_FROM_EMAIL (or EMAIL_HOST_USER) is not set in .env")
    return from_email


def send_raw_email(*, subject: str, body: str, to_email: str, from_email: str | None = None) -> None:
    """
    Low-level email sender used by send_test_email and the digest.
    Uses env vars (DIGEST_FROM_EMAIL/EMAIL_HOST_USER) if from_email not provided.
    """
    sender = (from_email or _get_from_email()).strip()
    send_mail(
        subject,
        body,
        sender,
        [to_email],
        fail_silently=False,
    )


def send_weekly_digest(*, days: int = 10, limit: int = 40) -> int:
    """
    Sends a digest email and marks sent_at for included items.
    Reads email addresses DIRECTLY from env:
      - DIGEST_TO_EMAIL
      - DIGEST_FROM_EMAIL (fallback EMAIL_HOST_USER)
    """

    cutoff = timezone.now() - timedelta(days=days)

    qs = (
        ReportItem.objects.filter(
            sent_at__isnull=True,
            published_at__isnull=False,
            published_at__gte=cutoff,
        )
        .order_by("-published_at", "-id")[:limit]
    )

    items = list(qs)

    # Reason field is ai_ip_reason in your project (ReportItem has no .note)
    def reason(it) -> str:
        return (getattr(it, "ai_ip_reason", "") or "").strip()

    # Exclude llm_failed items from the email (optional)
    items = [it for it in items if not reason(it).startswith("llm_failed")]

    if not items:
        return 0

    to_email = _get_to_email()
    from_email = _get_from_email()

    subject = f"AI × IP Recent Reports Digest (last {days} days)"
    lines = [
        subject,
        f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ]

    for idx, it in enumerate(items, start=1):
        r = reason(it)
        tag = " [COURT/LITIGATION]" if r.startswith("[court/litigation]") else ""

        title = (it.title or "").strip() or "(no title)"
        source = (it.source_name or "").strip() or "(unknown source)"
        date_str = it.published_at.date().isoformat() if it.published_at else "(no date)"
        page = (it.landing_page_url or "").strip()
        pdf = (it.report_url or "").strip()

        lines.append(f"{idx}. {title}{tag}")
        lines.append(f"   Source: {source}")
        lines.append(f"   Date:   {date_str}")
        if page:
            lines.append(f"   Page:   {page}")
        if pdf:
            lines.append(f"   PDF:    {pdf}")
        if r:
            lines.append(f"   Note:   {r}")
        lines.append("")

    body = "\n".join(lines)

    send_raw_email(subject=subject, body=body, to_email=to_email, from_email=from_email)

    now = timezone.now()
    ReportItem.objects.filter(id__in=[it.id for it in items]).update(sent_at=now)

    return len(items)
