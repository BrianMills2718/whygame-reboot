#!/usr/bin/env python3
"""Judge whether the retained WhyGame result contains one complete coherent loop."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_MODEL = "codex/gpt-5.6-luna"
EXPECTED_PRODUCER_REVISION = "0f07a07c81cde9624a036d1f91f384a4299b4598"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def judge(run_path: Path, report_path: Path, lifecycle_path: Path) -> tuple[str, str]:
    """Return the AES checker status and a concise owner-defined summary."""

    try:
        run = _read_json(run_path)
        lifecycle = _read_json(lifecycle_path)
        report = report_path.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return "ERROR", f"cannot read immutable loop evidence: {exc}"

    violations: list[str] = []
    if run.get("schema_version") != "1.0" or run.get("status") != "accepted":
        violations.append("accepted v1 run")
    if run.get("producer_revision") != EXPECTED_PRODUCER_REVISION:
        violations.append("exact producer revision")
    if run.get("issues"):
        violations.append("empty issues")
    for field in (
        "proposal",
        "finding",
        "revision_plan",
        "active_projection",
        "revision_events",
    ):
        if not run.get(field):
            violations.append(field)

    receipts = run.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != 2:
        violations.append("exactly two call receipts")
        receipts = []
    for receipt in receipts:
        if receipt.get("requested_model") != EXPECTED_MODEL:
            violations.append("requested Luna route")
        if receipt.get("resolved_model") != EXPECTED_MODEL:
            violations.append("resolved Luna route")
        if receipt.get("reasoning_effort") != "medium":
            violations.append("medium reasoning")
        if receipt.get("retry_count") != 0:
            violations.append("zero retries")
        if receipt.get("fallback_used") is not False:
            violations.append("no fallback")
        if not isinstance(receipt.get("total_tokens"), int) or receipt["total_tokens"] <= 0:
            violations.append("observable token usage")

    outer_runs = run.get("outer_runs")
    if not isinstance(outer_runs, list) or len(outer_runs) != 1:
        violations.append("one outer-run receipt")
        root_trace_id = None
    else:
        outer = outer_runs[0]
        root_trace_id = outer.get("root_trace_id")
        if outer.get("status") != "completed" or outer.get("linked_call_count") != 2:
            violations.append("completed two-call outer custody")
    if receipts and root_trace_id:
        expected_traces = {f"{root_trace_id}/proposal", f"{root_trace_id}/revision"}
        if {receipt.get("trace_id") for receipt in receipts} != expected_traces:
            violations.append("rooted proposal and revision traces")

    report_sha256 = hashlib.sha256(report.encode("utf-8")).hexdigest()
    if run.get("report_sha256") != report_sha256:
        violations.append("report digest binding")
    for text in (
        "Selected challenge",
        "Applied revision",
        "Unresolved uncertainty",
        "Execution receipts",
        "does not certify truth",
    ):
        if text not in report:
            violations.append(f"report section: {text}")

    if lifecycle.get("auth_binding") != "explicit":
        violations.append("explicit Codex account binding")
    account_digest = lifecycle.get("account_id_sha256")
    if not isinstance(account_digest, str) or not account_digest.startswith("sha256:"):
        violations.append("one-way account digest")
    if lifecycle.get("account_digest_consistent") is not True:
        violations.append("consistent account digest")
    privacy = lifecycle.get("privacy_checks")
    if not isinstance(privacy, dict) or any(privacy.values()):
        violations.append("privacy-bounded lifecycle receipt")
    events = lifecycle.get("events")
    if not isinstance(events, list) or len(events) != 4:
        violations.append("four account-bound lifecycle boundary events")
    elif receipts:
        receipt_traces = {receipt.get("trace_id") for receipt in receipts}
        event_pairs = {(event.get("trace_id"), event.get("phase")) for event in events}
        expected_pairs = {
            (trace_id, phase)
            for trace_id in receipt_traces
            for phase in ("started", "completed")
        }
        if event_pairs != expected_pairs:
            violations.append("started/completed lifecycle coverage")

    if violations:
        return "VIOLATION", "accepted loop is missing: " + ", ".join(dict.fromkeys(violations))
    return "PASS", "accepted loop retains proposal, challenge, applied revision, report, and two explicit-account call receipts"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    args = parser.parse_args()
    status, summary = judge(args.run, args.report, args.lifecycle)
    print(json.dumps({"schema_version": "1.0", "status": status, "summary": summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
