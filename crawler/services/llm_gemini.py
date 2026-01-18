import json
import os
import httpx


def gemini_validate(evidence: dict) -> dict:
    """
    Content-only validation (NO date/recency judgement by LLM).
    More generous AI×IP topicality.
    Excludes court/litigation-focused items.
    Returns:
      { "is_ai_ip_report": bool, "confidence": float, "reason": str }
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "is_ai_ip_report": False,
            "confidence": 0.0,
            "reason": "Gemini error: GEMINI_API_KEY missing",
        }

    # Allow overriding model via env; choose a safer default.
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")

    prompt = f"""
Return ONLY valid JSON:
{{
  "is_ai_ip_report": boolean,
  "confidence": number,
  "reason": string
}}

Goal: Decide if this is an AI × Intellectual Property (IP) POLICY/GUIDANCE/REPORT type item.
Be GENEROUS.

Mark true if it meaningfully relates to:
- AI / generative AI / ML / training data / model outputs / synthetic media
AND
- IP or adjacent policy topics: copyright, patents (inventorship/eligibility),
  trademarks, trade secrets, licensing/collective licensing, TDM/database rights,
  regulatory guidance, agency frameworks, consultations, white papers.

IMPORTANT EXCLUDE:
- Court cases, lawsuits, litigation summaries, rulings/verdicts, case-law analysis.
If the item is primarily about a specific court case or lawsuit, return false.

Do NOT judge recency or dates.

Evidence:
{json.dumps(evidence, ensure_ascii=False)}
""".strip()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

    try:
        with httpx.Client(timeout=25) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        # Extract text output
        text = ""
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            text = ""

        text = (text or "").strip()
        parsed = json.loads(text)

        return {
            "is_ai_ip_report": bool(parsed.get("is_ai_ip_report", False)),
            "confidence": float(parsed.get("confidence", 0.0) or 0.0),
            "reason": str(parsed.get("reason", ""))[:400],
        }

    except Exception as e:
        return {
            "is_ai_ip_report": False,
            "confidence": 0.0,
            "reason": f"Gemini error: {e}",
        }
