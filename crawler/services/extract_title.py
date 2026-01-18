# crawler/services/extract_title.py
from bs4 import BeautifulSoup


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # Prefer H1
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(" ", strip=True)
        if t:
            return t[:600]

    # og:title
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()[:600]

    # <title>
    if soup.title and soup.title.string:
        return soup.title.string.strip()[:600]

    return ""
