from datetime import timedelta
from django.utils import timezone

from crawler.services.fetch_httpx import fetch_html, fetch_pdf
from crawler.services.extract_date import extract_published_at_with_evidence
from crawler.services.pdf_extract import extract_pdf_text_first_pages
from crawler.services.llm_gemini import gemini_validate
from crawler.services.llm_openai import openai_validate

def _has_court_litigation_signal(text: str) -> bool:
    blob = (text or "").lower()
    court_tokens = [
        " v. ", " vs. ", "lawsuit", "court", "judge", "ruling", "verdict",
        "litigation", "appeal", "supreme court", "district court",
        "complaint", "plaintiff", "defendant", "injunction",
        "class action", "settlement",
    ]
    return any(tok in blob for tok in court_tokens)

def validate_candidate_recent_aiip(
    *,
    title: str,
    source_name: str,
    landing_page_url: str,
    pdf_url: str,
    recency_days: int = 10,
) -> dict:
    """
    New policy:
      - Recency is determined ONLY by our parser evidence (not LLM).
      - LLMs are used ONLY for topical relevance (AI×IP), and gating is LIGHTER.

    Keep if:
      - We can find a credible date (landing-page evidence) AND it is within recency_days
      - AND topical relevance passes via (Gemini OR OpenAI OR keyword fallback)
    """

    # 1) Fetch landing page HTML (date evidence preferred from website HTML)
    code, html = fetch_html(landing_page_url)
    if code >= 400 or not html:
        return {
            "keep": False,
            "published_at": None,
            "published_at_source": "",
            "published_at_raw": "",
            "gemini": None,
            "openai": None,
            "reason": f"landing page fetch failed HTTP {code}",
        }

    ev = extract_published_at_with_evidence(html)
    if not ev:
        # Relaxation option (optional): you could try PDF-based date extraction later.
        # For now, keep predictable: if no landing-page date evidence, skip.
        return {
            "keep": False,
            "published_at": None,
            "published_at_source": "",
            "published_at_raw": "",
            "gemini": None,
            "openai": None,
            "reason": "no publish date evidence on landing page",
        }

    cutoff = timezone.now() - timedelta(days=recency_days)
    if ev.dt < cutoff:
        return {
            "keep": False,
            "published_at": ev.dt,
            "published_at_source": ev.source,
            "published_at_raw": ev.raw,
            "gemini": None,
            "openai": None,
            "reason": f"landing page date older than {recency_days}d",
        }

    # 2) Fetch PDF and extract excerpt (helps topical classifier)
    pcode, pdf_bytes = fetch_pdf(pdf_url)
    pdf_text = ""
    if pcode < 400 and pdf_bytes:
        pdf_text = extract_pdf_text_first_pages(pdf_bytes, max_pages=2)

    # 3) Build evidence
    today_iso = timezone.localtime(timezone.now()).date().isoformat()
    evidence = {
        "today_iso": today_iso,
        "title": title,
        "source_name": source_name,
        "landing_page_url": landing_page_url,
        "pdf_url": pdf_url,
        "landing_page_date_iso": ev.dt.date().isoformat(),
        "landing_page_date_source": ev.source,
        "landing_page_date_raw": ev.raw,
        "pdf_text_excerpt": (pdf_text or "")[:2000],
    }

    # Optional: keyword pre-signal fallback (strongly recommended)
    keyword_hits = []
    text_blob = (title + " " + (pdf_text or "")).lower()
    # --- Court / litigation filter (hard exclusion, BEFORE LLM) ---
    court_tokens = [
        " v. ",
        " vs. ",
        " lawsuit",
        " court",
        " judge",
        " ruling",
        " verdict",
        " litigation",
        " appeal",
        " supreme court",
        " district court",
        " complaint",
        " plaintiff",
        " defendant",
    ]

    

    for kw in [
        "copyright",
        "patent",
        "inventorship",
        "trademark",
        "trade secret",
        "licensing",
        "royalty",
        "infringement",
        "fair use",
        "fair dealing",
        "text and data mining",
        "tdm",
        "database right",
        "scraping",
        "training data",
        "dataset",
        "model output",
        "ai-generated",
        "generative ai",
        "deepfake",
        "synthetic media",
    ]:
        if kw in text_blob:
            keyword_hits.append(kw)
    evidence["keyword_hits"] = keyword_hits[:25]

    # 4) LLM topical verification (LIGHTER gating; content-only)
    try:
        g = gemini_validate(evidence)  # expects {is_ai_ip_report, confidence, reason}
    except Exception as e:
        g = {
            "is_ai_ip_report": False,
            "confidence": 0.0,
            "reason": f"Gemini error: {e}",
        }

    try:
        o = openai_validate(evidence)  # expects {is_ai_ip_report, confidence, reason}
    except Exception as e:
        o = {
            "is_ai_ip_report": False,
            "confidence": 0.0,
            "reason": f"OpenAI error: {e}",
        }

    # LIGHTER decision:
    # - pass if either LLM says AI×IP
    # - OR if keyword fallback shows strong IP signals + AI signal
    gemini_ok = bool(g.get("is_ai_ip_report", False))
    openai_ok = bool(o.get("is_ai_ip_report", False))

    # keyword fallback: require at least 2 hits AND at least one AI signal
    has_ai_signal = any(
        x in text_blob
        for x in [
            " ai ",
            "artificial intelligence",
            "generative ai",
            "foundation model",
            "training data",
            "model output",
        ]
    )
    keyword_ok = (len(keyword_hits) >= 2) and has_ai_signal

    if not (gemini_ok or openai_ok or keyword_ok):
        return {
            "keep": False,
            "published_at": ev.dt,
            "published_at_source": ev.source,
            "published_at_raw": ev.raw,
            "gemini": g,
            "openai": o,
            "reason": "not AI×IP (gemini/openai/keywords all failed)",
            "tags": [],
        }

    text_blob = " ".join([
        title or "",
        (evidence.get("pdf_text_excerpt") or ""),
    ])
    is_litigation = _has_court_litigation_signal(text_blob)

    return {
        "keep": True,
        "published_at": ev.dt,
        "published_at_source": ev.source,
        "published_at_raw": ev.raw,
        "gemini": g,
        "openai": o,
        "reason": "ok",
        "tags": (["court/litigation"] if is_litigation else []),
    }
