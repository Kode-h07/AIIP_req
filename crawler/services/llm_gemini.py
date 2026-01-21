# crawler/services/llm_gemini.py
import json
import os
from typing import Dict, Any, Optional

import httpx


def _list_models(api_key: str) -> list[dict]:
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    with httpx.Client(timeout=20.0) as client:
        r = client.get(url, params={"key": api_key})
    r.raise_for_status()
    return r.json().get("models", []) or []


def _pick_model(models: list[dict]) -> Optional[str]:
    usable = []
    for m in models:
        name = (m.get("name") or "").strip()  # e.g. "models/gemini-1.5-pro"
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" in methods and name.startswith("models/"):
            usable.append(name)

    if not usable:
        return None

    # preference order
    pref = [
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.0-pro",
    ]
    for p in pref:
        if p in usable:
            return p

    return usable[0]


def gemini_validate(evidence: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    # Optional override (if set), otherwise auto-pick
    override = (os.getenv("GEMINI_MODEL") or "").strip()
    if override and not override.startswith("models/"):
        override = "models/" + override

    models = _list_models(api_key)
    picked = _pick_model(models)
    model_name = override or picked

    if not model_name:
        return {
            "is_ai_ip_report": False,
            "is_recent_10d": False,
            "best_date_iso": None,
            "reason": "Gemini: no usable model found (generateContent unsupported)",
        }

    prompt = f"""
You validate whether a candidate PDF/report is (1) AI + Intellectual Property policy/law/guidance/report
and (2) recent within 10 days of today.

Be generous on AI×IP relevance (copyright, patent, trademark, trade secrets, licensing, training data, TDM, IP office guidance).
Court/litigation analyses are allowed if they discuss broader policy/guidance/compliance implications.

Return ONLY JSON with keys:
- is_ai_ip_report (boolean)
- is_recent_10d (boolean)
- best_date_iso (string YYYY-MM-DD or null)
- reason (string, short)

Today: {evidence.get("today_iso")}
Title: {evidence.get("title")}
Source: {evidence.get("source_name")}
Landing page: {evidence.get("landing_page_url")}
PDF: {evidence.get("pdf_url")}
Landing page date evidence: {evidence.get("landing_page_date_iso")} ({evidence.get("landing_page_date_source")} | {evidence.get("landing_page_date_raw")})

PDF excerpt:
{(evidence.get("pdf_text_excerpt") or "")[:2000]}
""".strip()

    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
    }

    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, params={"key": api_key}, json=payload)

    if r.status_code >= 400:
        return {
            "is_ai_ip_report": False,
            "is_recent_10d": False,
            "best_date_iso": None,
            "reason": f"Gemini HTTP {r.status_code} model={model_name}: {r.text[:180]}",
        }

    data = r.json()
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
        or ""
    ).strip()

    try:
        return json.loads(text)
    except Exception:
        return {
            "is_ai_ip_report": False,
            "is_recent_10d": False,
            "best_date_iso": None,
            "reason": f"Gemini non-JSON model={model_name}: {text[:180]}",
        }
