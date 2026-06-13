from services.bright_data import collect_public_data
from services.llm_reasoning import analyze_with_llm

subject = {
    "name": "ABC Holdings Pte Ltd",
    "type": "Private Company",
    "country": "Singapore",
    "screeningPurpose": "Vendor onboarding review",
    "role": "Potential vendor"
}

public_sources = collect_public_data(subject["name"], subject["country"])
analysis = analyze_with_llm(subject, public_sources)

print(analysis)
