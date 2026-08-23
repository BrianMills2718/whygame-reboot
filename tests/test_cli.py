from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_dry_run_manifest_binds_exact_report_bytes(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "whygame_reboot.cli",
            "examples/aes-mission-drift/question.yaml",
            "--output",
            str(output_dir),
            "--dry-run",
            "--run-id",
            "whygame-reboot/test-cli-report-digest",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    manifest = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    report_bytes = (output_dir / "report.html").read_bytes()

    assert result.stdout.strip() == str(output_dir / "report.html")
    assert manifest["status"] == "dry_run"
    assert manifest["receipts"] == []
    assert manifest["report_sha256"] == hashlib.sha256(report_bytes).hexdigest()
