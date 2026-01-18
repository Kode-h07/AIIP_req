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


def _is_llm_error(resp: dict | None) -> bool:
    if not resp:
        return True
    reason = (resp.get("reason") or "").lower()
    return ("error" in reason) or ("404" in reason) or ("unexpected keyword" in reason)


def build_evidence(it: ReportItem, html: str, pdf_text: str, today_iso: str) -> dict:
    # date evidence from landing page (strict)
    ev = extract_published_at_with_evidence(html)
    landing_date_iso = ev.dt.date().isoformat() if ev else None
    landing_source = ev.source if ev else None
    landing_raw = ev.raw if ev else None

    return {
        "today_iso": today_iso,
        "title": it.title,
        "source_name": it.source_name,
        "landing_page_url": it.landing_page_url,
        "pdf_url": it.report_url,
        "landing_page_date_iso": landing_date_iso,
        "landing_page_date_source": landing_source,
        "landing_page_date_raw": landing_raw,
        "pdf_text_excerpt": pdf_text[:2000],
    }


class Command(BaseCommand):
    help = "Validate AI×IP relevance + recency via Gemini + OpenAI; delete outdated if either says outdated."

    def handle(self, *args, **options):
        days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)
        cutoff = timezone.now() - timedelta(days=days)
        today_iso = timezone.localtime(timezone.now()).date().isoformat()

        # validate only unsent recent-ish candidates (or all unsent if you prefer)
        qs = ReportItem.objects.filter(sent_at__isnull=True).order_by(
            "-published_at", "-id"
        )[:200]
        items = list(qs)

        self.stdout.write(f"[VALIDATE] candidates={len(items)}")

        deleted = 0
        kept = 0

        for it in items:
            # Fetch landing page
            try:
                code, html = fetch_html(it.landing_page_url or "")
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP(landing fetch error): {it.landing_page_url} | {e}"
                    )
                )
                continue

            if code >= 400 or not html:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP(landing fetch HTTP {code}): {it.landing_page_url}"
                    )
                )
                continue

            if code >= 400 or not html:
                # no evidence -> delete (cannot verify recency)
                it.delete()
                deleted += 1
                self.stdout.write(
                    f"DELETE (no landing page) {it.landing_page_url} HTTP {code}"
                )
                continue

            # Strict: must find landing-page date evidence
            ev = extract_published_at_with_evidence(html)
            if not ev:
                it.delete()
                deleted += 1
                self.stdout.write(
                    f"DELETE (no landing-page date evidence) {it.landing_page_url}"
                )
                continue

            # Optional: prefilter by your extracted date (fast gate)
            if ev.dt < cutoff:
                it.delete()
                deleted += 1
                self.stdout.write(
                    f"DELETE (landing page date older than {days}d) {it.landing_page_url}"
                )
                continue

            # Fetch PDF and extract some text evidence
            try:
                try:
                    pcode, pdf_bytes = fetch_pdf(it.report_url or "")
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"SKIP(pdf fetch error): {it.report_url} | {e}"
                        )
                    )
                    continue

                if pcode >= 400 or not pdf_bytes:
                    self.stdout.write(
                        self.style.WARNING(
                            f"SKIP(pdf fetch HTTP {pcode}): {it.report_url}"
                        )
                    )
                    continue

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"SKIP(pdf fetch): {it.report_url} | {e}")
                )
                continue

            pdf_text = (
                extract_pdf_text_first_pages(pdf_bytes, max_pages=2)
                if (pcode < 400 and pdf_bytes)
                else ""
            )

            evidence = build_evidence(it, html, pdf_text, today_iso)

            # Dual LLM validation (CONTENT-ONLY; no recency judgement here)
            try:
                g = gemini_validate(
                    evidence
                )  # expects: {is_ai_ip_report, confidence?, reason}
            except Exception as e:
                g = {
                    "is_ai_ip_report": False,
                    "confidence": 0.0,
                    "reason": f"Gemini error: {e}",
                }

            try:
                o = openai_validate(
                    evidence
                )  # expects: {is_ai_ip_report, confidence?, reason}
            except Exception as e:
                o = {
                    "is_ai_ip_report": False,
                    "confidence": 0.0,
                    "reason": f"OpenAI error: {e}",
                }

            def _is_llm_error(resp: dict | None) -> bool:
                if not resp:
                    return True
                r = (resp.get("reason") or "").lower()
                return (
                    "gemini error" in r
                    or "openai error" in r
                    or "unexpected keyword" in r
                    or "404" in r
                    or "not found" in r
                )

            g_err = _is_llm_error(g)
            o_err = _is_llm_error(o)

            # If BOTH LLMs errored, DO NOT delete (unknown). Keep item.
            if g_err and o_err:
                it.ai_ip_verified = False
                it.ai_ip_score = 0
                it.ai_ip_reason = f"G:{g.get('reason','')} | O:{o.get('reason','')}"[
                    :500
                ]
                it.verified_at = timezone.now()
                it.save(
                    update_fields=[
                        "ai_ip_verified",
                        "ai_ip_score",
                        "ai_ip_reason",
                        "verified_at",
                    ]
                )
                kept += 1
                self.stdout.write(f"KEEP (llm_failed) {it.report_url}")
                continue

            # CONTENT decision (lighter gate):
            # - If any successful LLM explicitly says NOT AI×IP -> delete
            # - Otherwise keep if either LLM says AI×IP
            gemini_ok = None if g_err else bool(g.get("is_ai_ip_report", False))
            openai_ok = None if o_err else bool(o.get("is_ai_ip_report", False))

            if (gemini_ok is False) or (openai_ok is False):
                it.delete()
                deleted += 1
                self.stdout.write(
                    f"DELETE (not AI×IP) {it.report_url}\n  Gemini: {g}\n  OpenAI: {o}"
                )
                continue

            keep_aiip = (gemini_ok is True) or (openai_ok is True)

            # Keep: mark verification fields
            it.ai_ip_verified = bool(keep_aiip)
            it.ai_ip_score = int(
                (50 if gemini_ok is True else 0) + (50 if openai_ok is True else 0)
            )
            it.ai_ip_reason = f"G:{g.get('reason','')} | O:{o.get('reason','')}"[:500]
            it.verified_at = timezone.now()
            it.save(
                update_fields=[
                    "ai_ip_verified",
                    "ai_ip_score",
                    "ai_ip_reason",
                    "verified_at",
                ]
            )

            kept += 1
            self.stdout.write(f"KEEP {it.report_url}")
