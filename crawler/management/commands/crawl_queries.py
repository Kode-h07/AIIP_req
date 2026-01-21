from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.conf import settings

from crawler.data.queries import QUERIES
from crawler.services.search_serpapi import google_search
from crawler.services.fetch import fetch_html
from crawler.services.extract_title import extract_title
from crawler.services.detect_reports import detect_pdf_links
from crawler.services.source_infer import infer_source
from crawler.services.validate_candidate import validate_candidate_recent_aiip
from crawler.services.store import upsert_recent_report
from crawler.models import ReportItem
from crawler.services.pdf_filters import is_cross_domain_pdf, is_junk_pdf


# -------------------------
# Niche scoring (no allowlist)
# -------------------------


def _tld_bonus(host: str) -> int:
    h = (host or "").lower()
    if h.endswith(".gov") or h.endswith(".gov.uk") or ".gov." in h:
        return 7
    if h.endswith(".int"):
        return 6
    if h.endswith(".edu"):
        return 5
    if h.endswith(".org"):
        return 3
    return 0


def _path_score(path: str) -> int:
    p = (path or "").lower()
    s = 0
    for tok in [
        "report",
        "reports",
        "publication",
        "publications",
        "guidance",
        "consultation",
        "policy",
        "law",
        "framework",
        "working-paper",
        "research",
        "whitepaper",
        "white-paper",
    ]:
        if tok in p:
            s += 2
    for tok in ["press", "news", "media", "blog", "podcast", "video", "webinar"]:
        if tok in p:
            s -= 2
    return s


def _page_score(url: str, title: str) -> int:
    host = (urlparse(url).netloc or "").lower()
    path = urlparse(url).path or ""
    s = 0
    s += _tld_bonus(host)
    s += _path_score(path)

    t = (title or "").lower()
    for kw in [
        "report",
        "white paper",
        "guidance",
        "consultation",
        "policy",
        "framework",
        "analysis",
        "memorandum",
        "submission",
        "working paper",
    ]:
        if kw in t:
            s += 2
    for kw in ["press release", "newsletter", "blog", "podcast", "video", "webinar"]:
        if kw in t:
            s -= 2
    return s


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
    help = (
        "Query discovery via SerpAPI Google: for each query, find PDFs on top results "
        "(including print/export versions), validate (date evidence + content), save FIRST valid PDF."
    )

    def handle(self, *args, **options):
        days = getattr(settings, "CRAWLER_RECENCY_DAYS", 10)
        top_per_query = 15
        max_pdfs_per_result = 12  # safety cap

        grand_saved = 0

        # Import here to avoid hard failure if your print-link service isn't ready

        for qi, q in enumerate(QUERIES, start=1):
            self.stdout.write(f"\n[QUERY {qi}/{len(QUERIES)}] {q}")

            try:
                result_urls = google_search(q, num=top_per_query, recency_days=days)
                self.stdout.write(
                    f"  SEARCH: results={len(result_urls)} (top {top_per_query}, bias={days}d)"
                )

                found_for_query = False

                for ri, result_url in enumerate(result_urls, start=1):
                    self.stdout.write(
                        f"    [RESULT {ri}/{len(result_urls)}] {result_url}"
                    )

                    try:
                        status, html, _ = fetch_html(result_url)
                        if status >= 400 or not html:
                            self.stdout.write(
                                self.style.WARNING(f"      FETCH: HTTP {status}")
                            )
                            continue

                        title = extract_title(html) or ""
                        base_score = _page_score(result_url, title)
                        source_name, source_type = infer_source(result_url)

                        # -------------------------
                        # (B) Detect PDFs (href/src)
                        # -------------------------
                        pdf_candidates = detect_pdf_links(result_url, html) or []
                        if not pdf_candidates:
                            self.stdout.write(
                                "      NOTE: No PDF links detected on this page."
                            )
                            continue

                        # Rank candidates: page score + candidate score (if available)
                        def cand_score(c: dict) -> int:
                            return int(base_score) + int(c.get("score", 0))

                        pdf_candidates = sorted(
                            pdf_candidates, key=cand_score, reverse=True
                        )[:max_pdfs_per_result]
                        self.stdout.write(
                            f"      PDF CANDIDATES: {len(pdf_candidates)}"
                        )

                        # -------------------------
                        # (C) Validate + save FIRST passing PDF for this query
                        # -------------------------
                        for c in pdf_candidates:
                            pdf_url = c["report_url"]
                            context = (c.get("context") or "") + " " + (c.get("evidence") or "")

                            if is_junk_pdf(pdf_url, context):
                                self.stdout.write(f"      SKIP(junk_pdf): {pdf_url}")
                                continue

                            if is_cross_domain_pdf(result_url, pdf_url):
                                self.stdout.write(f"      SKIP(cross_domain_pdf): {pdf_url}")
                                continue


                            if ReportItem.objects.filter(report_url=pdf_url).exists():
                                self.stdout.write(f"      SKIP(dup): {pdf_url}")
                                continue

                            ver = validate_candidate_recent_aiip(
                                title=title,
                                source_name=source_name,
                                landing_page_url=result_url,  # authoritative landing page
                                pdf_url=pdf_url,
                                recency_days=days,
                            )
                            tags = ver.get("tags") or []
                            tag_str = ("[" + ",".join(tags) + "] ") if tags else ""
                            note = f"{tag_str}{ver.get('reason','')}"


                            if not ver.get("keep", False):
                                self.stdout.write(
                                    f"      SKIP(validate): {pdf_url} | {ver.get('reason','')}"
                                )
                                continue

                            obj, changed = upsert_recent_report(
                                source_name=source_name,
                                source_type=source_type,
                                title=title,
                                landing_page_url=result_url,
                                report_url=pdf_url,
                                report_format=c.get("report_format", "pdf"),
                                published_at=ver["published_at"],
                                published_at_source=ver["published_at_source"],
                                published_at_raw=ver["published_at_raw"],
                                days=days,
                            )

                            if obj and changed:
                                grand_saved += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"      SAVED: {pdf_url}")
                                )
                            else:
                                self.stdout.write(
                                    f"      SAVED/EXISTS(nochange): {pdf_url}"
                                )

                            found_for_query = True
                            break

                        if found_for_query:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    "  QUERY DONE: found 1 validated PDF; moving to next query"
                                )
                            )
                            break

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"      ERROR: {e}"))
                        continue

                if not found_for_query:
                    self.stdout.write(
                        "  QUERY DONE: no validated recent AI×IP PDF found."
                    )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  QUERY ERROR: {e}"))
                continue

        self.stdout.write(
            f"\nDone. total_new_saved={grand_saved} (DB dedup by report_url)"
        )
