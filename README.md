# Risk Assistant

<!-- portfolio-summary:start -->
## Portfolio Snapshot

**Problem:** Public-source reputational screening can be slow, inconsistent, and difficult to audit.

**Method:** Built a FastAPI + Streamlit workflow that gathers public-source evidence, resolves subject ambiguity, classifies evidence against a fixed rubric, and computes final risk outcomes with deterministic rules.

**Output:** Reviewer-ready findings, supporting evidence, risk assessment, audit trail, and memo-style reporting for more consistent compliance decisions.

**Evidence:** Agent Forge Hackathon 2026 — **Top 10 finalist team out of 55 teams**.

**Portfolio stack:** Python · FastAPI · Streamlit · Rule-Based Scoring · Public-Source Research

<!-- portfolio-summary:end -->

This repository documents the final collaborative hackathon prototype built during Agent Forge Hackathon. The project was selected as one of the Top 10 finalist teams out of 55 teams.

This repo is kept as a portfolio archive of the collaborative project.

Risk Assistant is an AI-assisted public-source reputational screening system for organizations and individuals. It combines evidence collection, rubric-based risk scoring, and reviewer-ready output to support compliance and onboarding workflows.

The project includes:

- `backend/`: FastAPI pipeline for screening orchestration, classification, rule evaluation, and report generation.
- `frontend/`: Streamlit interface for running screenings and reviewing findings, evidence, and memo output.
- `docs/`: architecture, integration notes, schema references, and examples.

For setup and usage details, see:

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [docs/README.md](docs/README.md)
