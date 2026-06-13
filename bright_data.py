import os
from dotenv import load_dotenv

load_dotenv()

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")


def collect_public_data(subject_name: str, country: str):
    """
    Mock Bright Data service for hackathon demo.
    Later, replace this with the real Bright Data API endpoint.
    """

    if not BRIGHTDATA_API_KEY:
        return [
            {
                "sourceType": "Company Website",
                "sourceName": "Mock company website",
                "sourceUrl": "https://example.com/company",
                "sourceSnippet": f"{subject_name} appears as a company operating in {country}."
            },
            {
                "sourceType": "Public Review Page",
                "sourceName": "Mock review page",
                "sourceUrl": "https://example.com/reviews",
                "sourceSnippet": "Several public reviews mention delayed responses and communication issues."
            },
            {
                "sourceType": "Public Web Search",
                "sourceName": "Mock public search result",
                "sourceUrl": "https://example.com/search",
                "sourceSnippet": "A similarly named entity appears in another jurisdiction."
            }
        ]

    return [
        {
            "sourceType": "Bright Data Placeholder",
            "sourceName": "Bright Data API",
            "sourceUrl": "https://brightdata.com",
            "sourceSnippet": "Bright Data API key detected. Replace placeholder with actual Bright Data endpoint."
        }
    ]
