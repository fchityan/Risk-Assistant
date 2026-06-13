"""HTTP client for the FastAPI screening backend."""

import json
import time
import urllib.error
import urllib.request
from typing import Any


class ClarificationRequired(Exception):
    def __init__(self, run_id: str, payload: dict):
        self.run_id = run_id
        self.payload = payload
        super().__init__(f"Run {run_id} requires analyst clarification")


SUBJECT_TYPE_MAP = {
    "company": "organization",
    "private company": "organization",
    "vendor": "organization",
    "individual": "individual",
    "hnw prospect": "individual",
    "key person": "individual",
}


def map_subject_type(ui_label: str) -> str:
    return SUBJECT_TYPE_MAP.get(ui_label.strip().lower(), "organization")


def build_screen_request(
    name: str,
    subject_type_label: str,
    country: str | None = None,
    industry: str | None = None,
    known_associations: list[str] | None = None,
    input_notes: str | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "subject_type": map_subject_type(subject_type_label),
        "primary_name": name.strip(),
    }
    if country and country.strip():
        payload["country"] = country.strip()
    if industry and industry.strip():
        payload["industry"] = industry.strip()
    if known_associations:
        payload["known_associations"] = known_associations
    if input_notes and input_notes.strip():
        payload["input_notes"] = input_notes.strip()
    return payload


def _request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 60.0,
) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("detail", detail)
        except json.JSONDecodeError:
            message = detail or exc.reason
        raise RuntimeError(f"HTTP {exc.code} from {url}: {message}") from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Could not reach {url}: {exc.reason}") from exc


def start_screening(backend_url: str, payload: dict) -> str:
    result = _request(f"{backend_url}/screen", method="POST", body=payload)
    return result["run_id"]


def get_screen_status(backend_url: str, run_id: str) -> dict:
    return _request(f"{backend_url}/screen/{run_id}")


def submit_clarification(backend_url: str, run_id: str, clarification: dict) -> dict:
    return _request(
        f"{backend_url}/screen/{run_id}/clarify",
        method="POST",
        body=clarification,
    )


def poll_until_complete(
    backend_url: str,
    run_id: str,
    poll_interval: float = 5.0,
    timeout: float = 900.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = get_screen_status(backend_url, run_id)
        state = status.get("status")
        if state == "complete":
            return status
        if state == "clarification_required":
            raise ClarificationRequired(run_id, status)
        if state == "error":
            raise RuntimeError(status.get("error") or "Pipeline failed")
        time.sleep(poll_interval)
    raise TimeoutError(f"Screening run {run_id} did not complete within {timeout}s")
