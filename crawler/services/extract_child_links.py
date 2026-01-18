# crawler/services/extract_child_links.py
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from crawler.services.canonicalize import canonicalize

# Paths that often contain publication/article pages
POSITIVE_PATH = re.compile(
    r"(news|press|publication|publications|reports|report|insights|guidance|consultation|consultations|resources|research|blog|article|articles)",
    re.IGNORECASE,
)

# Avoid obvious junk links
NEGATIVE_PATH = re.compile(
    r"(#|javascript:|mailto:|tel:|login|signin|signup|account|privacy|terms|cookies|contact|careers|jobs)",
    re.IGNORECASE,
)


def _abs(base_url: str, href: str) -> str:
    return canonicalize(urljoin(base_url, href.strip()))


def _same_site(base_url: str, u: str) -> bool:
    try:
        b = urlparse(base_url)
        c = urlparse(u)
        return b.netloc.lower() == c.netloc.lower()
    except Exception:
        return False


def extract_child_links(base_url: str, html: str, max_links: int = 25) -> list[str]:
    """
    Extract candidate child pages from a hub page.
    We prefer same-domain URLs with publication-like paths.
    """
    soup = BeautifulSoup(html, "lxml")

    links = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if NEGATIVE_PATH.search(href):
            continue
        u = _abs(base_url, href)

        # Same domain strongly preferred
        if not _same_site(base_url, u):
            continue

        # Prefer publication-like paths
        path = urlparse(u).path or ""
        if not POSITIVE_PATH.search(path):
            continue

        links.append(u)

    # Deduplicate while preserving order
    seen = set()
    out = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= max_links:
            break
    return out
