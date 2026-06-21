from env_shared import get_config_value, load_shared_env

load_shared_env()

SENSENOVA_API_KEY = get_config_value("SENSENOVA_API_KEY")


def generate_memo(subject, analysis):
    """
    Mock SenseNova memo generation layer.
    Later, replace this with the real SenseNova API endpoint.
    """

    recommendation = analysis.get("riskSummary", {}).get(
        "recommendation",
        "Human Review Required"
    )

    return {
        "title": "Due Diligence Memo",
        "subject": subject.get("name"),
        "purpose": subject.get("screeningPurpose"),
        "overallRecommendation": recommendation,
        "body": (
            f"{subject.get('name')} was screened using AI-assisted public-source due diligence. "
            "The reviewed public-source evidence indicates that the entity requires further verification before final onboarding. "
            f"The current recommendation is: {recommendation}. "
            "A human compliance reviewer should verify identity, beneficial ownership, and supporting documents before making a final decision."
        ),
        "humanReviewRequired": True,
        "disclaimer": "AI-assisted public-source screening only. Findings require human compliance review before any onboarding or risk decision."
    }
