import os
import httpx


def google_search(query: str, num: int = 15, recency_days: int = 10) -> list[str]:
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is not set (check .env and load_dotenv).")

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": min(num, 15),
        "hl": "en",
        "gl": "us",
        # bias to last N days
        "tbs": f"qdr:d{int(recency_days)}",
    }
    params.update(
        {
            "hl": "en",
            "gl": "us",
            # recency bias already set via tbs
            # additional: de-emphasize news packs sometimes
            "safe": "active",
        }
    )

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get("https://serpapi.com/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    urls = []
    for item in data.get("organic_results", [])[:num]:
        link = item.get("link")
        if link:
            urls.append(link)

    # dedupe preserving order
    seen = set()
    out = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out
