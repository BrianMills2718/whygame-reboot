#!/usr/bin/env python3
"""Run installed AES BLOCK -> attachment recovery -> ALLOW for WhyGame."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def _decision(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    if not result.stdout.strip():
        raise RuntimeError(f"AES produced no JSON: {result.stderr}")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("AES decision must be a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _installed_revision() -> str:
    distribution = importlib.metadata.distribution("agentic-engineering-system")
    direct_url_text = distribution.read_text("direct_url.json")
    if not direct_url_text:
        raise RuntimeError("installed AES has no direct_url.json revision evidence")
    direct_url = json.loads(direct_url_text)
    revision = direct_url.get("vcs_info", {}).get("commit_id")
    if not isinstance(revision, str) or len(revision) != 40:
        raise RuntimeError("installed AES is not bound to an exact Git revision")
    return revision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--aes", type=Path, required=True)
    parser.add_argument("--expected-aes-revision", required=True)
    parser.add_argument("--evidence-out", type=Path, required=True)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    status = _run(["git", "status", "--porcelain"], cwd=root)
    if status.returncode != 0 or status.stdout:
        raise RuntimeError("AES admission requires an exact clean consumer revision")
    consumer_revision = _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    installed_revision = _installed_revision()
    if installed_revision != args.expected_aes_revision:
        raise RuntimeError(
            f"installed AES revision mismatch: {installed_revision} != {args.expected_aes_revision}"
        )

    attached = root / ".aes" / "evidence" / "coherent-loop.json"
    if attached.exists():
        raise RuntimeError("attached evidence must be absent before the initial BLOCK")

    with tempfile.TemporaryDirectory(prefix="whygame-aes-admission-") as temporary:
        machine = Path(temporary) / "machine.json"
        machine.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "repositories": {"whygame-reboot": str(root)},
                }
            ),
            encoding="utf-8",
        )
        command = [
            str(args.aes.resolve()),
            "codex",
            "admit",
            "--repository-record-id",
            "whygame-reboot",
            "--expected-revision",
            consumer_revision,
            "--machine-config",
            str(machine),
            "--request",
            "policy/promotion.json",
        ]
        blocked_result = _run(command, cwd=root)
        blocked = _decision(blocked_result)
        if blocked_result.returncode != 3 or blocked.get("decision") != "BLOCK":
            raise RuntimeError(f"expected BLOCK/3, got {blocked_result.returncode}: {blocked}")

        recovery_command = blocked.get("recovery", {}).get("command")
        if not isinstance(recovery_command, list) or not recovery_command:
            raise RuntimeError("BLOCK did not return an executable recovery command")
        recovered_result = _run([str(item) for item in recovery_command], cwd=root)
        recovered = _decision(recovered_result)
        if recovered_result.returncode != 0 or recovered.get("status") != "ATTACHED":
            raise RuntimeError(f"returned recovery failed: {recovered_result.stderr}")

        allowed_result = _run(command, cwd=root)
        allowed = _decision(allowed_result)
        if allowed_result.returncode != 0 or allowed.get("decision") != "ALLOW":
            raise RuntimeError(f"expected ALLOW/0, got {allowed_result.returncode}: {allowed}")

    candidate = root / "evidence" / "candidates" / "coherent-loop.json"
    if attached.read_bytes() != candidate.read_bytes():
        raise RuntimeError("attached evidence differs from the candidate bytes")
    run_path = root / "evidence" / "runs" / "2026-08-23-account-bound-live" / "run.json"
    report_path = run_path.with_name("report.html")
    lifecycle_path = run_path.with_name("lifecycle-account-binding.json")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    receipt = {
        "schema_version": "1.0",
        "evidence_kind": "aes_external_behavioral_consumer_admission",
        "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "consumer": {
            "repository_record_id": "whygame-reboot",
            "revision": consumer_revision,
        },
        "installed_aes": {
            "version": importlib.metadata.version("agentic-engineering-system"),
            "revision": installed_revision,
            "installation_kind": "exact_git_pin",
            "source_checkout_used": False,
        },
        "policy_id": "coherent-loop-evidence",
        "request_path": "policy/promotion.json",
        "initial_decision": {
            "decision": blocked["decision"],
            "reason_code": blocked["reason_code"],
            "recovery_returned": True,
        },
        "recovery": {
            "operation": recovered["operation"],
            "status": recovered["status"],
            "attached_path": ".aes/evidence/coherent-loop.json",
            "attached_sha256": _sha256(attached),
        },
        "retry_decision": {
            "decision": allowed["decision"],
            "reason_code": allowed["reason_code"],
            "evidence_ref": allowed["evidence"][0],
        },
        "behavioral_result": {
            "terminal_status": run["status"],
            "producer_revision": run["producer_revision"],
            "run_id": run["run_id"],
            "model": "codex/gpt-5.6-luna",
            "reasoning_effort": "medium",
            "call_count": len(run["receipts"]),
            "retry_count": sum(item["retry_count"] for item in run["receipts"]),
            "run_sha256": _sha256(run_path),
            "report_sha256": _sha256(report_path),
            "account_id_sha256": lifecycle["account_id_sha256"],
            "auth_binding": lifecycle["auth_binding"],
        },
        "verification_replay": {
            "boundary": "same immutable consumer revision and request",
            "without_attached_behavioral_evidence": "BLOCK",
            "with_attached_behavioral_evidence": "ALLOW",
        },
        "nonclaims": [
            "One bounded question does not establish general causal reasoning or truth discovery.",
            "The proposal and revision used the same Luna route and are not independent-model criticism.",
            "This proves adoption of one AES policy seam, not fleet-wide AES operation or legacy replacement.",
        ],
    }
    output = args.evidence_out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
