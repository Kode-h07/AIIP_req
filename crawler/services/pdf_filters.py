# crawler/services/pdf_filters.py
from urllib.parse import urlparse


JUNK_PDF_TOKENS = [
    "media-kit", "mediakit", "press-kit", "presskit",
    "flyer", "brochure", "catalog", "infographic",
    "agenda", "schedule", "form", "application", "template",
    "pricing", "rate-card", "ratecard",
    "newsletter", "magazine",
    "slides", "deck", "presentation",
    "minutes", "transcript",
]


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def is_junk_pdf(pdf_url: str, context: str = "") -> bool:
    u = (pdf_url or "").lower()
    c = (context or "").lower()
    for tok in JUNK_PDF_TOKENS:
        if tok in u or tok in c:
            return True
    return False


def is_cross_domain_pdf(landing_url: str, pdf_url: str) -> bool:
    """
    Return True if PDF is from a totally different host than the landing page.
    We treat cross-domain as suspicious and usually skip.
    """
    h1 = _host(landing_url)
    h2 = _host(pdf_url)
    if not h1 or not h2:
        return False
    if h1 == h2:
        return False

    # allow common "cdn" patterns (same org but different host) - keep these lenient
    allow_substrings = [
        h1.replace("www.", ""),
    ]
    h2_base = h2.replace("www.", "")
    if any(s and s in h2_base for s in allow_substrings):
        return False

    return True
