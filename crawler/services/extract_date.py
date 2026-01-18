import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from bs4 import BeautifulSoup
from django.utils import timezone


@dataclass
class DateEvidence:
    dt: datetime
    source: str  # where we found it (meta/jsonld/text/time)
    raw: str  # the raw string we parsed


# --- parsing helpers ---


_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _to_aware(dt: datetime) -> datetime:
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _parse_iso_like(s: str) -> Optional[datetime]:
    """
    Parse common formats:
      - 2026-01-15
      - 2026/01/15
      - 2026.01.15
      - 2026-01-15T12:34:56Z
    """
    if not s:
        return None
    s = s.strip()

    # ISO datetime
    try:
        # handle Z
        if s.endswith("Z"):
            s2 = s[:-1] + "+00:00"
            return datetime.fromisoformat(s2)
        return datetime.fromisoformat(s)
    except Exception:
        pass

    # date only variants
    m = re.search(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d)
    return None


def _parse_month_name_date(s: str) -> Optional[datetime]:
    """
    Parse:
      - January 15, 2026
      - Jan 15 2026
      - 15 January 2026
    """
    if not s:
        return None
    t = " ".join(s.strip().split())
    # normalize ordinals: 1st/2nd/3rd/4th -> 1/2/3/4
    t = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", t, flags=re.IGNORECASE)

    # January 15, 2026
    m = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:,)?\s+(20\d{2})\b", t)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            return datetime(int(m.group(3)), mon, int(m.group(2)))

    # 15 January 2026
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})(?:,)?\s+(20\d{2})\b", t)
    if m:
        mon = _MONTHS.get(m.group(2).lower())
        if mon:
            return datetime(int(m.group(3)), mon, int(m.group(1)))

    return None


def _best_of(dts: List[Tuple[datetime, str, str]]) -> Optional[DateEvidence]:
    """
    Pick the most sensible date (prefer latest not in far future).
    """
    if not dts:
        return None

    now = timezone.now()
    cleaned = []
    for dt, source, raw in dts:
        dt2 = _to_aware(dt)
        # reject absurd futures (> 2 days ahead) - avoids "copyright 2099"
        if dt2 > now + timedelta(days=2):
            continue
        # reject extremely old garbage (before 1990)
        if dt2.year < 1990:
            continue
        cleaned.append((dt2, source, raw))

    if not cleaned:
        return None

    cleaned.sort(key=lambda x: x[0], reverse=True)
    best = cleaned[0]
    return DateEvidence(dt=best[0], source=best[1], raw=best[2])


# --- extraction strategies ---


def _extract_from_meta(soup: BeautifulSoup) -> List[Tuple[datetime, str, str]]:
    out = []
    meta_keys = [
        ("property", "article:published_time"),
        ("property", "article:modified_time"),
        ("name", "pubdate"),
        ("name", "publish-date"),
        ("name", "publishdate"),
        ("name", "date"),
        ("name", "dc.date"),
        ("name", "dc.date.issued"),
        ("name", "DC.date.issued"),
        ("itemprop", "datePublished"),
        ("itemprop", "dateModified"),
    ]

    for attr, key in meta_keys:
        tag = soup.find("meta", attrs={attr: key})
        if not tag:
            continue
        content = tag.get("content") or tag.get("value") or ""
        dt = _parse_iso_like(content) or _parse_month_name_date(content)
        if dt:
            out.append((dt, f"meta[{attr}={key}]", content))

    return out


def _extract_from_time_tags(soup: BeautifulSoup) -> List[Tuple[datetime, str, str]]:
    out = []
    for t in soup.find_all("time"):
        raw = (t.get("datetime") or t.get_text(" ", strip=True) or "").strip()
        dt = _parse_iso_like(raw) or _parse_month_name_date(raw)
        if dt:
            out.append((dt, "time_tag", raw))
    return out


def _extract_from_jsonld(soup: BeautifulSoup) -> List[Tuple[datetime, str, str]]:
    out = []
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for sc in scripts:
        txt = (sc.string or "").strip()
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            # sometimes multiple JSON objects; try to salvage
            continue

        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for k in ["datePublished", "dateModified", "uploadDate"]:
                v = node.get(k)
                if isinstance(v, str):
                    dt = _parse_iso_like(v) or _parse_month_name_date(v)
                    if dt:
                        out.append((dt, f"jsonld.{k}", v))
    return out


def _extract_from_text_year_first(
    soup: BeautifulSoup,
) -> List[Tuple[datetime, str, str]]:
    """
    Year-first scan in visible text:
    1) If current-ish year appears, try to extract full dates near it.
    Supports ISO-like (YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD) and English month-name dates.
    """
    out: List[Tuple[datetime, str, str]] = []
    now = timezone.localtime(timezone.now())
    years = {now.year, now.year - 1, now.year + 1}  # tolerant window

    # Always define text safely
    try:
        text = soup.get_text(" ", strip=True) or ""
    except Exception:
        text = ""

    if not text:
        return out

    # Normalize ordinals: 1st/2nd/3rd/4th -> 1/2/3/4
    text = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)

    # Quick year presence check
    if not any(str(y) in text for y in years):
        return out

    # Regex patterns
    iso_pat = re.compile(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b")
    mon1_pat = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:,)?\s+(20\d{2})\b")
    mon2_pat = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})(?:,)?\s+(20\d{2})\b")

    candidates: List[Tuple[int, datetime, str]] = []

    for m in iso_pat.finditer(text):
        raw = m.group(0)
        dt = _parse_iso_like(raw)
        if dt and dt.year in years:
            candidates.append((m.start(), dt, raw))

    for m in mon1_pat.finditer(text):
        raw = m.group(0)
        dt = _parse_month_name_date(raw)
        if dt and dt.year in years:
            candidates.append((m.start(), dt, raw))

    for m in mon2_pat.finditer(text):
        raw = m.group(0)
        dt = _parse_month_name_date(raw)
        if dt and dt.year in years:
            candidates.append((m.start(), dt, raw))

    if not candidates:
        return out

    boost_tokens = [
        "published",
        "updated",
        "posted",
        "date",
        "released",
        "last updated",
    ]

    for pos, dt, raw in candidates:
        left = max(0, pos - 80)
        right = min(len(text), pos + 80)
        window = text[left:right].lower()

        source = "text_year_scan"
        if any(tok in window for tok in boost_tokens):
            source = "text_year_scan_near_pubtoken"

        out.append((dt, source, raw))

    return out


def extract_published_at_with_evidence(
    html: str, url: str = None
) -> Optional[DateEvidence]:
    """
    Robust date extraction with evidence.
    Priority:
      1) meta tags
      2) JSON-LD
      3) <time> tags
      4) year-first visible text scan (your requested enhancement)
    """
    if not html:
        return None

    soup = BeautifulSoup(
        html, "lxml"
    )  # requires lxml; fallback handled by bs4 if missing

    candidates: List[Tuple[datetime, str, str]] = []
    candidates += _extract_from_meta(soup)
    candidates += _extract_from_jsonld(soup)
    candidates += _extract_from_time_tags(soup)
    candidates += _extract_from_text_year_first(soup)

    return _best_of(candidates)


# Backward-compatible helpers used by your crawlers


def extract_published_at(html: str) -> Optional[datetime]:
    ev = extract_published_at_with_evidence(html)
    return ev.dt if ev else None


def is_recent(published_at: Optional[datetime], days: int = 10) -> bool:
    if not published_at:
        return False
    cutoff = timezone.now() - timedelta(days=days)
    dt = _to_aware(published_at)
    return dt >= cutoff
