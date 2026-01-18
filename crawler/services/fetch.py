# crawler/services/fetch.py
import httpx
from django.conf import settings

DEFAULT_HEADERS = {
    "User-Agent": getattr(
        settings, "CRAWLER_USER_AGENT", "Mozilla/5.0 (compatible; AIIpDigestBot/1.0)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_client() -> httpx.Client:
    timeout = httpx.Timeout(getattr(settings, "CRAWLER_HTTP_TIMEOUT", 20.0))
    return httpx.Client(timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS)


def fetch_html(url: str) -> tuple[int, str, dict]:
    with get_client() as client:
        r = client.get(url)
        return r.status_code, r.text, dict(r.headers)


def head(url: str) -> tuple[int, dict]:
    with get_client() as client:
        r = client.head(url)
        return r.status_code, dict(r.headers)
