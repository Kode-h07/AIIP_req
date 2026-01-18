import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def openai_validate(evidence: dict) -> dict:
    """
    Content-only validation (NO date/recency judgement by LLM).
    More generous AI×IP topicality.
    Excludes court/litigation-focused items.
    Returns JSON dict:
      { "is_ai_ip_report": bool, "confidence": float, "reason": str }
    """
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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

    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        txt = (r.choices[0].message.content or "").strip()
        data = json.loads(txt)
        return {
            "is_ai_ip_report": bool(data.get("is_ai_ip_report", False)),
            "confidence": float(data.get("confidence", 0.0) or 0.0),
            "reason": str(data.get("reason", ""))[:400],
        }
    except Exception as e:
        return {
            "is_ai_ip_report": False,
            "confidence": 0.0,
            "reason": f"OpenAI error: {e}",
        }
