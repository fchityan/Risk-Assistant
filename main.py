import json
from pathlib import Path

from services.bright_data import collect_public_data
from services.llm_reasoning import analyze_with_llm
from services.sensenova import generate_memo


def run_due_diligence_agent():
    subject = {
        "name": "ABC Holdings Pte Ltd",
        "type": "Private Company",
        "country": "Singapore",
        "screeningPurpose": "Vendor onboarding review",
        "role": "Potential vendor"
    }

    public_sources = collect_public_data(
        subject_name=subject["name"],
        country=subject["country"]
    )

    analysis = analyze_with_llm(subject, public_sources)
    memo = generate_memo(subject, analysis)

    result = {
        "subject": subject,
        "publicSources": public_sources,
        "analysis": analysis,
        "memo": memo
    }

    output_path = Path("agent/output/agent_result.json")
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run_due_diligence_agent()
