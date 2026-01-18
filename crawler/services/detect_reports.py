# crawler/services/detect_reports.py
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from crawler.services.fetch import head
from crawler.services.canonicalize import canonicalize

PDF_EXT_RE = re.compile(r"\.pdf(\?|$)", re.IGNORECASE)

# 아이콘/자산/스프라이트/썸네일 등 "보고서 PDF"가 아닌 경우가 매우 많아서 기본 제외
ASSET_HINT_RE = re.compile(
    r"(icon|logo|sprite|thumb|thumbnail|svg|png|jpg|jpeg|webp|gif|badge|button)",
    re.IGNORECASE,
)

# 보고서/정책 문서 힌트 (점수 가산)
POSITIVE_TEXT_RE = re.compile(
    r"(report|white\s*paper|guidance|consultation|policy|law|framework|working\s*paper|brief|analysis|memorandum|submission|proposal|study)",
    re.IGNORECASE,
)

# 뉴스/홍보/블로그성 힌트 (점수 감산; 니치 소스는 막지 않되 랭킹에서 밀리게)
NEGATIVE_TEXT_RE = re.compile(
    r"(press|press\s*release|news|newsletter|blog|podcast|video|webinar|promo|advert|marketing)",
    re.IGNORECASE,
)


def _abs(base_url: str, u: str) -> str:
    return canonicalize(urljoin(base_url, u.strip()))


def _same_domain(base_url: str, candidate_url: str) -> bool:
    try:
        b = urlparse(base_url)
        c = urlparse(candidate_url)
        return b.netloc.lower() == c.netloc.lower()
    except Exception:
        return False


def _confirm_pdf(url: str) -> bool:
    """
    가능한 경우 HEAD로 content-type 확인.
    막히면 .pdf 확장자 기반으로 수용.
    """
    if PDF_EXT_RE.search(url):
        return True
    try:
        status, headers = head(url)
        if status >= 400:
            return False
        ct = (headers.get("content-type") or "").lower()
        return "application/pdf" in ct
    except Exception:
        return False


def _score_context(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    s = 0
    if POSITIVE_TEXT_RE.search(t):
        s += 6
    if NEGATIVE_TEXT_RE.search(t):
        s -= 5
    # 너무 짧으면 정보량이 적어 감점
    if len(t) < 6:
        s -= 1
    return s


def detect_pdf_links(base_url: str, html: str) -> list[dict]:
    """
    href/src에서 .pdf 후보를 추출하고 점수화하여 반환.
    반환 형태:
      {report_url, report_format, evidence, score, context}
    """
    soup = BeautifulSoup(html, "lxml")
    candidates = []

    # A) href 기반 (대부분의 보고서 PDF)
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        u = _abs(base_url, href)
        if not PDF_EXT_RE.search(u):
            continue
        if not _confirm_pdf(u):
            continue

        ctx = a.get_text(" ", strip=True)
        score = 10
        score += 2 if _same_domain(base_url, u) else -1
        score += _score_context(ctx)

        candidates.append(
            {
                "report_url": u,
                "report_format": "pdf",
                "evidence": "href",
                "score": score,
                "context": ctx[:200],
            }
        )

    # B) src 기반 (요청 반영: src 안에 .pdf가 있으면 수집)
    # 단, 아이콘/자산 PDF (예: pdf.svg 같은 것)는 강하게 제외
    for tag in soup.find_all(src=True):
        src = (tag.get("src") or "").strip()
        if not src:
            continue
        u = _abs(base_url, src)
        if not PDF_EXT_RE.search(u):
            continue

        # 자산/아이콘/이미지류면 스킵 (보고서 PDF일 확률 매우 낮음)
        if ASSET_HINT_RE.search(u):
            continue

        if not _confirm_pdf(u):
            continue

        ctx = " ".join(
            [
                (tag.get("alt") or ""),
                (tag.get("title") or ""),
                (tag.get("aria-label") or ""),
                " ".join(tag.get("class") or []),
            ]
        ).strip()

        score = 6
        score += 1 if _same_domain(base_url, u) else -1
        score += _score_context(ctx)

        candidates.append(
            {
                "report_url": u,
                "report_format": "pdf",
                "evidence": "src",
                "score": score,
                "context": ctx[:200],
            }
        )

    # Deduplicate by report_url (keep best score)
    best = {}
    for c in candidates:
        u = c["report_url"]
        if u not in best or c["score"] > best[u]["score"]:
            best[u] = c

    return sorted(best.values(), key=lambda x: x["score"], reverse=True)


# ---- Backward-compatible wrappers (for crawl_seeds.py) ----


def detect_report_links(base_url: str, html: str) -> list[dict]:
    """
    Backward-compatible alias used by older code.
    Returns list of dicts with keys including report_url/report_format.
    """
    return detect_pdf_links(base_url, html)


def detect_pdf_src_markers(base_url: str, html: str) -> list[dict]:
    """
    Older code sometimes called a separate src-marker function.
    We now unify detection in detect_pdf_links(); keep this for compatibility.
    """
    # Only return those discovered via src, if you want strict compatibility:
    items = detect_pdf_links(base_url, html)
    return [x for x in items if x.get("evidence") == "src"]


def is_junk_pdf(url: str, context: str = "") -> bool:
    u = (url or "").lower()
    c = (context or "").lower()

    bad_tokens = [
        "media-kit",
        "mediakit",
        "media_kit",
        "press-kit",
        "presskit",
        "advertis",
        "sponsor",
        "rate-card",
        "brochure",
        "catalog",
        "flyer",
        "newsletter",
        "promo",
        "terms",
        "privacy",
        "cookie",
        "form-",
        "application-form",
    ]
    return any(t in u or t in c for t in bad_tokens)
