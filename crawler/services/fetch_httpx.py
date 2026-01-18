import httpx

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIIPDigestBot/1.0; +https://example.invalid/bot)"
}


def fetch_html(url: str, timeout: float = 25.0) -> tuple[int, str]:
    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS
    ) as client:
        r = client.get(url)
        return r.status_code, (r.text or "")


def fetch_pdf(url: str, timeout: float = 40.0) -> tuple[int, bytes]:
    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS
    ) as client:
        r = client.get(url)
        return r.status_code, (r.content or b"")
