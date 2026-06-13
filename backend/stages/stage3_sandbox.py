"""Stage 3: Sandbox processing via Daytona (with local fallback)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from config import get_settings

PROCESSING_DIR = Path(__file__).resolve().parent.parent / "processing"
PROCESS_SCRIPT = PROCESSING_DIR / "process.py"


def _process_locally(raw_items: list[dict], subject: dict) -> dict:
    """Fallback when Daytona is unavailable or API key is missing."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("process", PROCESS_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load processing script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.process_items(raw_items, subject)


def _process_in_daytona(raw_items: list[dict], subject: dict) -> dict:
    from daytona_sdk import Daytona, CreateSandboxParams

    settings = get_settings()
    daytona = Daytona(api_key=settings.daytona_api_key)
    sandbox = daytona.create(CreateSandboxParams(language="python"))

    try:
        sandbox.fs.upload_file("process.py", PROCESS_SCRIPT.read_bytes())
        input_payload = json.dumps({"raw_items": raw_items, "subject": subject}).encode()
        sandbox.fs.upload_file("input_data.json", input_payload)

        config_path = Path(__file__).resolve().parent.parent / "config" / "source_tiers.json"
        sandbox.fs.upload_file("source_tiers.json", config_path.read_bytes())

        result = sandbox.process.code_run("python process.py")
        if result.exit_code != 0:
            raise RuntimeError(f"Sandbox processing failed: {result.result}")

        output = sandbox.fs.download_file("processed_items.json")
        return json.loads(output)
    finally:
        daytona.remove(sandbox)


def run_stage3(checkpoint2: dict) -> dict:
    raw_items = checkpoint2.get("raw_items", [])
    subject = checkpoint2.get("subject", {})
    settings = get_settings()

    if not raw_items:
        processing_result = {
            "processed_items": [],
            "items_flagged_adverse": 0,
            "items_retained": 0,
            "items_discarded": 0,
        }
        mode = "empty_input"
    elif settings.daytona_api_key and settings.daytona_api_key != "YOUR_DAYTONA_API_KEY_HERE":
        try:
            processing_result = _process_in_daytona(raw_items, subject)
            mode = "daytona"
        except Exception:
            processing_result = _process_locally(raw_items, subject)
            mode = "local_fallback"
    else:
        processing_result = _process_locally(raw_items, subject)
        mode = "local"

    return {
        "run_id": checkpoint2["run_id"],
        "stage": "sandbox_processing",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": checkpoint2.get("screening_scope"),
        "processing_mode": mode,
        "total_sources_reviewed": len(raw_items),
        **processing_result,
    }
