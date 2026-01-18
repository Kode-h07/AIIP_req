import os
import json
import httpx
from dataclasses import dataclass


@dataclass
class VerifyResult:
    is_ai_ip_report: bool
    score: int
    reason: str


def _gemini_endpoint(model: str) -> str:
    # v1beta is commonly used; keep simple and stable
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def verify_ai_ip_report(
    *,
    title: str,
    source_name: str,
    landing_page_url: str,
    report_url: str,
    published_date_iso: str | None,
    page_excerpt: str,
) -> VerifyResult:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Prompt: classifier with strict JSON output
    prompt = f"""
You are a strict classifier for a weekly digest system.
Decide whether this item is an AI-related intellectual property (IP) report/policy/guidance document.

Definition: "AI × IP report" includes documents about AI and at least one of:
copyright, patents, trademarks, trade secrets, licensing of training data, text and data mining, inventorship, ownership, infringement, right of publicity, deepfakes/IP, policy/legal guidance, consultations.

Reject:
- generic AI news with no IP focus
- random PDFs (forms, brochures, meeting agendas) not about AI×IP
- pure privacy/data protection without IP angle unless clearly about training data licensing/IP

Return ONLY JSON with keys:
is_ai_ip_report (boolean),
score (integer 0-100),
reason (short string, <= 200 chars).

Item:
title: {title}
source: {source_name}
landing_page_url: {landing_page_url}
report_url: {report_url}
published_date: {published_date_iso or "unknown"}
page_excerpt: {page_excerpt[:1200]}
""".strip()

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 300,
        },
    }

    url = _gemini_endpoint(model)
    params = {"key": api_key}

    with httpx.Client(timeout=40.0, follow_redirects=True) as client:
        r = client.post(url, params=params, json=payload)
        r.raise_for_status()
        data = r.json()

    # Extract Gemini text
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}")

    # Parse JSON strictly (Gemini sometimes wraps with ```json)
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    try:
        obj = json.loads(cleaned)
    except Exception:
        # fallback: try to locate JSON object substring
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(cleaned[start : end + 1])
        else:
            raise RuntimeError(f"Gemini did not return JSON: {text}")

    is_ok = bool(obj.get("is_ai_ip_report", False))
    score = int(obj.get("score", 0))
    reason = str(obj.get("reason", ""))[:200]

    # clamp
    if score < 0:
        score = 0
    if score > 100:
        score = 100

    return VerifyResult(is_ai_ip_report=is_ok, score=score, reason=reason)
