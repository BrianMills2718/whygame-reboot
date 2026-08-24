from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
EVIDENCE = ROOT / "evidence" / "runs" / "2026-08-23-account-bound-live"


def _copy_evidence(tmp_path: Path) -> tuple[Path, Path, Path]:
    run = tmp_path / "run.json"
    report = tmp_path / "report.html"
    lifecycle = tmp_path / "lifecycle.json"
    run.write_bytes((EVIDENCE / "run.json").read_bytes())
    report.write_bytes((EVIDENCE / "report.html").read_bytes())
    lifecycle.write_bytes((EVIDENCE / "lifecycle-account-binding.json").read_bytes())
    return run, report, lifecycle


def _judge(run: Path, report: Path, lifecycle: Path) -> dict[str, str]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "checks" / "coherent_loop.py"),
            "--run",
            str(run),
            "--report",
            str(report),
            "--lifecycle",
            str(lifecycle),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_exact_accepted_loop_passes(tmp_path: Path) -> None:
    assert _judge(*_copy_evidence(tmp_path))["status"] == "PASS"


def test_missing_revision_plan_is_a_violation(tmp_path: Path) -> None:
    run, report, lifecycle = _copy_evidence(tmp_path)
    payload = json.loads(run.read_text(encoding="utf-8"))
    payload["revision_plan"] = None
    run.write_text(json.dumps(payload), encoding="utf-8")
    result = _judge(run, report, lifecycle)
    assert result["status"] == "VIOLATION"
    assert "revision_plan" in result["summary"]


def test_changed_report_is_a_violation(tmp_path: Path) -> None:
    run, report, lifecycle = _copy_evidence(tmp_path)
    report.write_text(report.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    result = _judge(run, report, lifecycle)
    assert result["status"] == "VIOLATION"
    assert "report digest binding" in result["summary"]


def test_ambient_account_binding_is_a_violation(tmp_path: Path) -> None:
    run, report, lifecycle = _copy_evidence(tmp_path)
    payload = json.loads(lifecycle.read_text(encoding="utf-8"))
    payload["auth_binding"] = "ambient"
    lifecycle.write_text(json.dumps(payload), encoding="utf-8")
    result = _judge(run, report, lifecycle)
    assert result["status"] == "VIOLATION"
    assert "explicit Codex account binding" in result["summary"]


def test_missing_evidence_is_not_judged(tmp_path: Path) -> None:
    run, report, lifecycle = _copy_evidence(tmp_path)
    run.unlink()
    result = _judge(run, report, lifecycle)
    assert result["status"] == "ERROR"
    assert "cannot read immutable loop evidence" in result["summary"]
