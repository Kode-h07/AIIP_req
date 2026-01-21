# crawler/management/commands/validate_and_prune.py
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from crawler.models import ReportItem
from crawler.services.fetch_httpx import fetch_html, fetch_pdf
from crawler.services.extract_date import extract_published_at_with_evidence
from crawler.services.pdf_extract import extract_pdf_text_first_pages
from crawler.services.llm_gemini import gemini_validate
from crawler.services.llm_openai import openai_validate


class Command(BaseCommand):
    help = "Validate candidates via LLM and prune outdated ones. Never crash on network errors."

    def handle(self, *args, **options):
        days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)
        cutoff = timezone.now() - timedelta(days=days)

        qs = ReportItem.objects.filter(sent_at__isnull=True).order_by("-id")[:200]
        self.stdout.write(f"[VALIDATE] candidates={qs.count()}")

        kept = 0
        deleted = 0
        skipped = 0

        for it in qs:
            # If there's a published_at and it's already old, prune quickly
            if it.published_at and it.published_at < cutoff:
                it.delete()
                deleted += 1
                self.stdout.write(f"DELETE (db published_at older than {days}d) {it.report_url}")
                continue

            landing_url = (it.landing_page_url or "").strip()
            pdf_url = (it.report_url or "").strip()

            # 1) Fetch landing page HTML for date evidence (strict, but do not crash)
            try:
                code, html = fetch_html(landing_url)
            except Exception as e:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP(landing fetch error): {landing_url} | {e}"))
                continue

            if code >= 400 or not html:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP(landing fetch HTTP {code}): {landing_url}"))
                continue

            ev = extract_published_at_with_evidence(html)
            if not ev:
                # Do NOT delete; keep but mark that date evidence not found
                kept += 1
                self.stdout.write(f"KEEP (no_date_evidence) {pdf_url}")
                continue

            if ev.dt < cutoff:
                it.delete()
                deleted += 1
                self.stdout.write(f"DELETE (landing page date older than {days}d) {landing_url}")
                continue

            # 2) Fetch PDF (optional) for text excerpt; do not crash on errors
            pdf_text = ""
            try:
                pcode, pdf_bytes = fetch_pdf(pdf_url)
            except Exception as e:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP(pdf fetch error): {pdf_url} | {e}"))
                continue

            if pcode >= 400 or not pdf_bytes:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP(pdf fetch HTTP {pcode}): {pdf_url}"))
                continue

            try:
                pdf_text = extract_pdf_text_first_pages(pdf_bytes, max_pages=2)
            except Exception:
                pdf_text = ""

            evidence = {
                "today_iso": timezone.localtime(timezone.now()).date().isoformat(),
                "title": it.title or "",
                "source_name": it.source_name or "",
                "landing_page_url": landing_url,
                "pdf_url": pdf_url,
                "landing_page_date_iso": ev.dt.date().isoformat(),
                "landing_page_date_source": ev.source,
                "landing_page_date_raw": ev.raw,
                "pdf_text_excerpt": (pdf_text or "")[:2000],
            }

            # 3) Dual LLM validation — but NEVER delete solely because LLM failed
            g_err = None
            o_err = None

            try:
                g = gemini_validate(evidence)
            except Exception as e:
                g_err = str(e)
                g = {
                    "is_ai_ip_report": False,
                    "is_recent_10d": False,
                    "best_date_iso": None,
                    "reason": f"Gemini error: {e}",
                }

            try:
                o = openai_validate(evidence)
            except Exception as e:
                o_err = str(e)
                o = {
                    "is_ai_ip_report": False,
                    "is_recent_10d": False,
                    "best_date_iso": None,
                    "reason": f"OpenAI error: {e}",
                }

            # --- UPDATED DECISION RULE (fix your 'items_sent=0' situation) ---
            # Authoritative recency gate is the landing page evidence we already extracted.
            # LLM is used as topical check and as a secondary signal; never hard-delete on LLM failure.

            llm_failed = bool(g_err or o_err) or ("non-JSON" in (g.get("reason", "") + o.get("reason", "")))

            # Filter out litigation/court-heavy content softly (keywords); keep conservative
            text_blob = (it.title or "").lower() + " " + (pdf_text or "").lower()
            court_tokens = [
                "v.", "vs.", "lawsuit", "court", "judge", "ruling", "verdict",
                "litigation", "appeal", "supreme court", "district court",
                "complaint", "plaintiff", "defendant"
            ]
            if any(tok in text_blob for tok in court_tokens):
                # Not deleting; just skip inclusion logic by marking as not AI×IP
                it.ai_ip_verified = False
                it.ai_ip_reason = "filtered: court/litigation-focused content"
                it.verified_at = timezone.now()
                it.save(update_fields=["ai_ip_verified", "ai_ip_reason", "verified_at"])
                kept += 1
                self.stdout.write(f"KEEP (court_filtered) {pdf_url}")
                continue

            # If LLM failed, keep item but do not mark verified
            if llm_failed:
                it.ai_ip_verified = False
                it.ai_ip_reason = f"llm_failed | G:{g.get('reason','')} | O:{o.get('reason','')}"[:500]
                it.verified_at = timezone.now()
                it.save(update_fields=["ai_ip_verified", "ai_ip_reason", "verified_at"])
                kept += 1
                self.stdout.write(f"KEEP (llm_failed) {pdf_url}")
                continue

            # If either says NOT recent, do NOT delete (recency already proven by landing date).
            # We only use LLM recency as advisory now.
            is_aiip = bool(g.get("is_ai_ip_report", False) or o.get("is_ai_ip_report", False))  # generous OR
            if not is_aiip:
                it.ai_ip_verified = False
                it.ai_ip_reason = f"not_ai_ip | G:{g.get('reason','')} | O:{o.get('reason','')}"[:500]
                it.verified_at = timezone.now()
                it.save(update_fields=["ai_ip_verified", "ai_ip_reason", "verified_at"])
                kept += 1
                self.stdout.write(f"KEEP (not_ai_ip) {pdf_url}")
                continue

            # Mark verified
            it.ai_ip_verified = True
            it.ai_ip_reason = f"ok | G:{g.get('reason','')} | O:{o.get('reason','')}"[:500]
            it.verified_at = timezone.now()
            it.save(update_fields=["ai_ip_verified", "ai_ip_reason", "verified_at"])
            kept += 1
            self.stdout.write(f"KEEP (verified) {pdf_url}")

        self.stdout.write(self.style.SUCCESS(f"[VALIDATE] kept={kept} deleted={deleted} skipped={skipped}"))
