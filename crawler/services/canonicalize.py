from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def canonicalize(url: str) -> str:
    try:
        p = urlparse(url)
        fragment = ""
        q = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if k not in TRACKING_PARAMS
        ]
        query = urlencode(q, doseq=True)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, query, fragment))
    except Exception:
        return url
