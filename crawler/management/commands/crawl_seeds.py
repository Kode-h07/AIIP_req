from django.core.management.base import BaseCommand
from django.conf import settings

from crawler.data.seeds import SEEDS
from crawler.services.fetch import fetch_html
from crawler.services.extract_child_links import extract_child_links
from crawler.services.extract_title import extract_title
from crawler.services.detect_reports import detect_report_links
from crawler.services.validate_candidate import validate_candidate_recent_aiip
from crawler.services.store import upsert_recent_report
from crawler.models import ReportItem


def _is_junk_pdf(pdf_url: str, context: str = "") -> bool:
    u = (pdf_url or "").lower()
    c = (context or "").lower()
    bad_tokens = [
        "media-kit",
        "mediakit",
        "media_kit",
        "press-kit",
        "presskit",
        "rate-card",
        "ratecard",
        "advertis",
        "sponsor",
        "brochure",
        "catalog",
        "flyer",
        "newsletter",
        "promo",
        "terms",
        "privacy",
        "cookie",
        "application-form",
        "form-",
    ]
    return any(t in u or t in c for t in bad_tokens)


class Command(BaseCommand):
    help = "Crawl seed hubs and 1-hop child pages; detect PDFs (including print/export), validate, store recent AI×IP reports."

    def handle(self, *args, **options):
        days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)
        max_children = 20  # per seed
        max_reports_per_child = 8  # per child page

        total_saved = 0
        total_children_visited = 0

        # Import here to avoid hard failure if print-link service not ready
        try:
            from crawler.services.detect_print_links import detect_print_or_export_links
        except Exception:
            detect_print_or_export_links = None

        for seed in SEEDS:
            hub_url = seed["url"]
            source_name = seed["source_name"]
            source_type = seed["source_type"]

            self.stdout.write(f"\n[SEED HUB] {source_name} -> {hub_url}")

            try:
                status, hub_html, _ = fetch_html(hub_url)
                if status >= 400 or not hub_html:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  HUB RESULT: HTTP {status} (blocked/not found)"
                        )
                    )
                    continue

                child_links = extract_child_links(
                    hub_url, hub_html, max_links=max_children
                )
                self.stdout.write(
                    f"  HUB RESULT: fetched OK | child_links={len(child_links)}"
                )

                if not child_links:
                    self.stdout.write(
                        "  NOTE: No child links extracted from hub (JS-heavy hubs may yield 0)."
                    )
                    continue

                for i, child_url in enumerate(child_links, start=1):
                    self.stdout.write(f"    [CHILD {i}/{len(child_links)}] {child_url}")

                    try:
                        st, child_html, _h = fetch_html(child_url)
                        total_children_visited += 1
                        if st >= 400 or not child_html:
                            self.stdout.write(
                                self.style.WARNING(f"      CHILD RESULT: HTTP {st}")
                            )
                            continue

                        title = extract_title(child_html) or ""

                        # -------------------------
                        # (B) Detect report links (PDFs etc.)
                        # -------------------------
                        candidates = candidates = (
                            detect_report_links(child_url, child_html) or []
                        )
                        self.stdout.write(
                            f"      DETECTION: report_link_candidates={len(candidates)}"
                        )

                        if not candidates:
                            self.stdout.write(
                                "      NOTE: No report links detected on this child page."
                            )
                            continue

                        saved_here = 0

                        for c in candidates[:max_reports_per_child]:
                            pdf_url = c.get("report_url")
                            if not pdf_url:
                                continue

                            context = c.get("context", "") or ""
                            if _is_junk_pdf(pdf_url, context):
                                self.stdout.write(f"      SKIP(junk pdf): {pdf_url}")
                                continue

                            if ReportItem.objects.filter(report_url=pdf_url).exists():
                                self.stdout.write(f"      SKIP(dup): {pdf_url}")
                                continue

                            ver = validate_candidate_recent_aiip(
                                title=title,
                                source_name=source_name,
                                landing_page_url=child_url,  # authoritative landing page = child URL
                                pdf_url=pdf_url,
                                recency_days=days,
                            )

                            if not ver.get("keep", False):
                                self.stdout.write(
                                    f"      SKIP(validate): {pdf_url} | {ver.get('reason','')}"
                                )
                                continue

                            obj, changed = upsert_recent_report(
                                source_name=source_name,
                                source_type=source_type,
                                title=title,
                                landing_page_url=child_url,
                                report_url=pdf_url,
                                report_format=c.get("report_format", "pdf"),
                                published_at=ver["published_at"],
                                published_at_source=ver["published_at_source"],
                                published_at_raw=ver["published_at_raw"],
                                days=days,
                            )

                            if obj and changed:
                                saved_here += 1
                                total_saved += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"      SAVED: {pdf_url}")
                                )
                            else:
                                self.stdout.write(
                                    f"      SAVED/EXISTS(nochange): {pdf_url}"
                                )

                        self.stdout.write(f"      CHILD SUMMARY: saved={saved_here}")

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"      CHILD ERROR: {e}"))
                        continue

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  HUB ERROR: {e}"))
                continue

        self.stdout.write(
            f"\nDone. children_visited={total_children_visited} total_saved={total_saved}"
        )
