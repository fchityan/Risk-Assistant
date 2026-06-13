import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def analyze_with_llm(subject, public_sources):
    """
    LLM reasoning layer.
    Uses OpenAI if OPENAI_API_KEY exists.
    Otherwise returns mock analysis.
    """

    if client is None or OPENAI_API_KEY == "your_openai_api_key_here":
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
        model="gpt-4.1-mini",
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
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "error": "Model did not return valid JSON.",
            "rawResponse": content
        }
