# Risk Assistant

<!-- portfolio-summary:start -->
## Portfolio Snapshot

**Problem:** Public-source reputational screening can be slow, inconsistent, and difficult to audit.

**Method:** Risk Assistant collects public-source evidence, addresses subject ambiguity, classifies findings against a defined rubric, and applies transparent rules to risk outcomes.

**Output:** Structured findings with supporting evidence, an audit trail, and reviewer-ready summaries.

**Evidence:** **Top 10 finalist team out of 55 teams** at Agent Forge Hackathon 2026.
<!-- portfolio-summary:end -->

## Project Overview

Risk Assistant is an AI-assisted prototype for public-source reputational screening of organizations and individuals. It was developed as a **collaborative hackathon project** to help reviewers organize background information for compliance and onboarding decisions.

## Key Features

- Collects and organizes relevant public-source findings
- Supports subject resolution when names are ambiguous
- Classifies findings using a defined evidence rubric
- Applies rule-based risk assessments for consistent decisions
- Produces supporting evidence, audit information, and memo-style reports
- Provides a web interface for reviewing screening results

## Outcome and Limitations

The project was selected as a **Top 10 finalist from 55 teams** at Agent Forge Hackathon 2026. This recognition relates to the hackathon submission; it is not a measured detection-accuracy or commercial-deployment result. The prototype is intended to **support human review**, not replace verification or compliance judgment.

## Technology Stack

- **Language and interface:** Python, Streamlit, pandas, custom CSS
- **Backend and data contracts:** FastAPI, Uvicorn, Pydantic, pydantic-settings, HTTPX, python-dotenv, JSON Schema validation (`jsonschema`)
- **Research and browser access:** Bright Data SERP and Browser APIs, Playwright/Chromium
- **AI/LLM integration:** OpenAI-compatible Python SDK with configurable TokenRouter, OpenRouter, or Kimi; SenseNova with Kimi fallback for memos
- **Workflow and decision logic:** Daytona SDK sandbox integration, structured evidence processing, deterministic rule-based scoring

## Explore the Project

- [Backend and screening workflow](backend/README.md)
- [Frontend and user interface](frontend/README.md)
- [Architecture and integration documentation](docs/README.md)

This repository is preserved as an archive of the collaborative hackathon prototype.
