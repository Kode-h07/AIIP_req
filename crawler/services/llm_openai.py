# crawler/services/llm_openai.py
import json
import os
from typing import Dict, Any

from openai import OpenAI


def openai_validate(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns dict like:
      {
        "is_ai_ip_report": bool,
        "is_recent_10d": bool,
        "best_date_iso": "YYYY-MM-DD"|None,
        "reason": str
      }
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    prompt = f"""
You are validating whether a candidate PDF/report is:
(1) AI + Intellectual Property policy/law/guidance/report (NOT court cases/litigation-heavy),
(2) Recent within 10 days of today.

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
Landing page date (evidence): {evidence.get("landing_page_date_iso")} ({evidence.get("landing_page_date_source")} | {evidence.get("landing_page_date_raw")})

PDF excerpt:
{(evidence.get("pdf_text_excerpt") or "")[:2000]}
""".strip()

    resp = client.responses.create(
        model=model,
        input=prompt,
        # no response_format here (avoid SDK mismatch)
    )

    # The SDK returns text in output[0].content[0].text in many cases.
    text = ""
    try:
        # robust extraction
        for out in resp.output:
            for c in getattr(out, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    text += getattr(c, "text", "") or ""
    except Exception:
        text = ""

    text = (text or "").strip()
    # try parse JSON
    try:
        return json.loads(text)
    except Exception:
        # fallback: keep conservative but not crash
        return {
            "is_ai_ip_report": False,
            "is_recent_10d": False,
            "best_date_iso": None,
            "reason": f"OpenAI returned non-JSON: {text[:180]}",
        }
