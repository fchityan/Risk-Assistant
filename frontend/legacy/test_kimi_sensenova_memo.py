import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

KIMI_API_KEY = os.getenv("KIMI_API_KEY")
SENSENOVA_API_KEY = os.getenv("SENSENOVA_API_KEY")

if not KIMI_API_KEY:
    raise ValueError("KIMI_API_KEY not found in .env")

if not SENSENOVA_API_KEY:
    raise ValueError("SENSENOVA_API_KEY not found in .env")


# Kimi / Moonshot OpenAI-compatible client
kimi_client = OpenAI(
    base_url="https://api.moonshot.ai/v1",
    api_key=KIMI_API_KEY
)

# SenseNova OpenAI-compatible client
sensenova_client = OpenAI(
    base_url="https://api.velaalpha.cc/v1",
    api_key=SENSENOVA_API_KEY
)


subject = {
    "name": "ABC Holdings Pte Ltd",
    "type": "Private Company",
    "country": "Singapore",
    "screeningPurpose": "Vendor onboarding review",
    "role": "Potential vendor"
}

mock_evidence = [
    {
        "sourceType": "Company Website",
        "sourceName": "ABC Holdings public website",
        "sourceUrl": "https://example.com/abc-holdings",
        "sourceSnippet": "ABC Holdings Pte Ltd describes itself as a Singapore-based business consulting and supply-chain advisory firm."
    },
    {
        "sourceType": "Business Directory",
        "sourceName": "Singapore business directory",
        "sourceUrl": "https://example.com/business-directory",
        "sourceSnippet": "Listing shows ABC Holdings Pte Ltd operating in Singapore, but ownership information is not publicly shown."
    },
    {
        "sourceType": "Public Review Page",
        "sourceName": "Public review page",
        "sourceUrl": "https://example.com/reviews",
        "sourceSnippet": "Several reviews mention delayed responses and communication issues."
    },
    {
        "sourceType": "Public Web Search",
        "sourceName": "Search result",
        "sourceUrl": "https://example.com/search",
        "sourceSnippet": "A similarly named ABC Holdings entity appears in Malaysia."
    }
]


print("Step 1: Sending mock evidence to Kimi for risk reasoning...")

kimi_prompt = f"""
You are a careful compliance due diligence analyst.

Analyse the subject and public-source evidence below.

Subject:
{json.dumps(subject, indent=2)}

Evidence:
{json.dumps(mock_evidence, indent=2)}

Return valid JSON only with this exact structure:
{{
  "entityMatch": {{
    "score": 0,
    "level": "",
    "rationale": "",
    "ambiguities": []
  }},
  "riskSummary": {{
    "overallRiskScore": 0,
    "riskCategory": "",
    "confidenceScore": 0,
    "recommendation": "",
    "summary": ""
  }},
  "keyFindings": [
    {{
      "title": "",
      "category": "",
      "severity": "",
      "confidence": 0,
      "description": ""
    }}
  ],
  "missingInformation": [
    {{
      "item": "",
      "status": "",
      "recommendedAction": ""
    }}
  ],
  "recommendedNextSteps": [
    {{
      "priority": "",
      "action": "",
      "reason": ""
    }}
  ]
}}

Rules:
- Do not make final accusations.
- Use cautious language.
- Say "potential", "requires verification", and "public-source signal" where appropriate.
- Human compliance review is required.
"""

kimi_response = kimi_client.chat.completions.create(
    model="moonshot-v1-8k",
    messages=[
        {
            "role": "system",
            "content": "You are a careful compliance due diligence analyst. Return valid JSON only."
        },
        {
            "role": "user",
            "content": kimi_prompt
        }
    ],
    temperature=0.2
)

kimi_text = kimi_response.choices[0].message.content

print("\nKimi raw response:")
print(kimi_text)

try:
    kimi_analysis = json.loads(kimi_text)
except json.JSONDecodeError:
    print("\nKimi did not return valid JSON. Using raw response inside memo.")
    kimi_analysis = {
        "rawKimiResponse": kimi_text,
        "riskSummary": {
            "recommendation": "Human Review Required"
        }
    }


print("\nStep 2: Sending Kimi analysis to SenseNova for memo generation...")

sensenova_prompt = f"""
You are a compliance due diligence memo writer.

Write a concise due diligence memo based on the subject, evidence, and Kimi analysis.

Subject:
{json.dumps(subject, indent=2)}

Evidence:
{json.dumps(mock_evidence, indent=2)}

Kimi Analysis:
{json.dumps(kimi_analysis, indent=2)}

Memo format:
1. Subject and purpose
2. Entity match summary
3. Key risk signals
4. Missing information
5. Recommended next steps
6. Overall recommendation
7. Human review disclaimer

Rules:
- Use cautious compliance language.
- Do not make final accusations.
- Mention that this is AI-assisted public-source screening.
- Mention that human compliance review is required.
- Keep it suitable for vendor onboarding.
"""

sensenova_response = sensenova_client.chat.completions.create(
    model="sensenova-6.7-flash-lite",
    messages=[
        {
            "role": "system",
            "content": "You are a careful compliance due diligence memo writer."
        },
        {
            "role": "user",
            "content": sensenova_prompt
        }
    ],
    temperature=0.2
)

memo = sensenova_response.choices[0].message.content

print("\nFinal SenseNova Memo:")
print("=" * 80)
print(memo)
print("=" * 80)


output = {
    "subject": subject,
    "evidence": mock_evidence,
    "kimiAnalysis": kimi_analysis,
    "sensenovaMemo": memo
}

os.makedirs("agent/output", exist_ok=True)

with open("agent/output/kimi_sensenova_memo_test.json", "w") as f:
    json.dump(output, f, indent=2)

print("\nSaved output to agent/output/kimi_sensenova_memo_test.json")
