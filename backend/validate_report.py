"""Validate a report against Pydantic models and JSON schema."""

import json
import sys
from pathlib import Path

import jsonschema

from schemas.report import ReputationScreeningReport

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "schemas" / "reputation-screening-report-rubric.schema.v1.json"


def validate_report_file(report_path: Path) -> None:
    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)

    report = ReputationScreeningReport.model_validate(data)
    print(f"Pydantic validation OK: {report.report_metadata.report_id}")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=data, schema=schema)
    print("JSON Schema validation OK")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "backend" / "runs" / "DEMO-ORION-001" / "final_report.json"
    validate_report_file(path)
