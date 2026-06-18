import os
import json
import re
from openai import OpenAI

from env_shared import load_shared_env

load_shared_env()

KIMI_API_KEY = os.getenv("KIMI_API_KEY")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-auto")

client = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL) if KIMI_API_KEY else None


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _normalize_analysis(payload: dict) -> dict:
    risk_summary = payload.get("riskSummary")
    if isinstance(risk_summary, str):
        payload["riskSummary"] = {
            "overallRiskScore": 65,
            "riskCategory": "Moderate Risk",
            "confidenceScore": 72,
            "recommendation": "Proceed with Conditions",
            "summary": risk_summary,
        }

    findings = payload.get("keyFindings")
    if isinstance(findings, list) and findings and isinstance(findings[0], str):
        payload["keyFindings"] = [
            {
                "title": f"Finding {idx + 1}",
                "category": "Adverse Media",
                "severity": "Moderate",
                "confidence": 70,
                "description": item,
            }
            for idx, item in enumerate(findings)
        ]

    steps = payload.get("recommendedNextSteps")
    if isinstance(steps, list) and steps and isinstance(steps[0], str):
        payload["recommendedNextSteps"] = [
            {
                "priority": "High" if idx == 0 else "Medium",
                "action": item,
                "reason": "Generated from public-source due diligence reasoning.",
            }
            for idx, item in enumerate(steps)
        ]

    return payload


def analyze_with_llm(subject, public_sources):
    """
    LLM reasoning layer.
    Uses Kimi if KIMI_API_KEY exists.
    Otherwise returns mock analysis.
    """

    if client is None or KIMI_API_KEY == "your_kimi_api_key_here":
        return {
            "riskSummary": {
                "overallRiskScore": 58,
                "riskCategory": "Moderate Risk",
                "confidenceScore": 72,
                "recommendation": "Proceed with Conditions",
                "summary": "Mock moderate-risk assessment requiring human compliance review."
            },
            "keyFindings": [
                {
                    "title": "Mock finding: entity match requires verification",
                    "category": "Entity Matching",
                    "severity": "Moderate",
                    "confidence": 82,
                    "description": "The subject appears to match reviewed public sources, but official registration should be verified."
                }
            ],
            "recommendedNextSteps": [
                {
                    "priority": "High",
                    "action": "Request official company registration documents.",
                    "reason": "Public-source data alone is insufficient for final onboarding approval."
                }
            ]
        }

    prompt = f"""
You are a careful compliance due diligence reasoning agent.

Subject:
{json.dumps(subject, indent=2)}

Public-source evidence:
{json.dumps(public_sources, indent=2)}

Return valid JSON only with:
riskSummary, keyFindings, recommendedNextSteps.

Rules:
- Do not make final accusations.
- Use cautious language.
- Say "potential", "requires verification", and "public-source signal" where appropriate.
- Human compliance review is required.
"""

    response = client.chat.completions.create(
        model=KIMI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a careful due diligence compliance analyst. Return valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content

    try:
        return _normalize_analysis(json.loads(_strip_json_fence(content or "{}")))
    except json.JSONDecodeError:
        return {
            "error": "Model did not return valid JSON.",
            "rawResponse": content
        }
