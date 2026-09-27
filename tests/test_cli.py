from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "LLM_CLIENT_DATA_ROOT": str(tmp_path / "llm-data"),
        "LLM_CLIENT_DB_PATH": str(tmp_path / "observability.db"),
        "LLM_CLIENT_PROJECT": "whygame-reboot-test",
    }


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
        cwd=ROOT,
        env=_isolated_env(tmp_path),
    )

    manifest = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    report_bytes = (output_dir / "report.html").read_bytes()

    assert result.stdout.strip() == str(output_dir / "report.html")
    assert manifest["status"] == "dry_run"
    assert manifest["receipts"] == []
    assert len(manifest["outer_runs"]) == 1
    assert manifest["outer_runs"][0]["status"] == "completed"
    assert manifest["outer_runs"][0]["linked_call_count"] == 0
    assert manifest["report_sha256"] == hashlib.sha256(report_bytes).hexdigest()


def test_existing_terminal_output_is_not_overwritten(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    command = [
        sys.executable,
        "-m",
        "whygame_reboot.cli",
        "examples/aes-mission-drift/question.yaml",
        "--output",
        str(output_dir),
        "--dry-run",
        "--run-id",
        "whygame-reboot/test-cli-immutable",
    ]
    env = _isolated_env(tmp_path)
    first = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    before = {
        name: (output_dir / name).read_bytes()
        for name in ("run.json", "report.html")
    }

    second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)

    assert second.returncode == 1
    assert "run output directory is not empty" in second.stderr
    assert before == {name: (output_dir / name).read_bytes() for name in before}


def test_installed_cli_resolves_source_revision_outside_caller_repo(tmp_path: Path) -> None:
    output_dir = tmp_path / "outside-cwd-run"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "whygame_reboot.cli",
            str(ROOT / "examples" / "aes-mission-drift" / "question.yaml"),
            "--output",
            str(output_dir),
            "--dry-run",
            "--run-id",
            "whygame-reboot/test-cli-source-root",
        ],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    expected_revision = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert result.returncode == 0, result.stderr
    manifest = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["producer_revision"] == expected_revision


def test_live_cli_requires_explicit_codex_home_before_dispatch(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "whygame_reboot.cli",
            "examples/aes-mission-drift/question.yaml",
            "--output",
            str(tmp_path / "run"),
            "--run-id",
            "whygame-reboot/test-cli-missing-codex-home",
        ],
        cwd=ROOT,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "live runs require --codex-home" in result.stderr
    assert not (tmp_path / "run").exists()


def test_cli_publishes_report_before_terminal_run_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from whygame_reboot import cli, runner

    for key, value in _isolated_env(tmp_path).items():
        if key.startswith("LLM_CLIENT_"):
            monkeypatch.setenv(key, value)
    real_replace = runner.os.replace
    published: list[str] = []

    def recording_replace(src, dst):
        real_replace(src, dst)
        published.append(Path(dst).name)

    monkeypatch.setattr(runner.os, "replace", recording_replace)
    output_dir = tmp_path / "run"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "whygame-reboot",
            str(ROOT / "examples" / "aes-mission-drift" / "question.yaml"),
            "--output",
            str(output_dir),
            "--dry-run",
            "--run-id",
            "whygame-reboot/test-cli-publish-order",
        ],
    )

    assert cli.main() == 0
    # run.json is the terminal commit point; a kill before it must not leave a
    # record whose report_sha256 names an unwritten report.
    assert published == ["report.html", "run.json"]
    assert not [path.name for path in output_dir.iterdir() if path.name.endswith(".tmp")]


def test_cli_second_process_fails_fast_while_run_directory_is_held(tmp_path: Path) -> None:
    from tests.test_audit_resume import _failed_checkpoint
    from whygame_reboot.runner import hold_run_directory

    output_dir = tmp_path / "run"
    before = _failed_checkpoint(output_dir, producer_revision="0" * 40)
    codex_home = tmp_path / "codex-profile"
    (codex_home / ".codex").mkdir(parents=True)
    (codex_home / ".codex" / "auth.json").write_text("{}", encoding="utf-8")

    # This test process is the live holder; the CLI is a genuinely separate process.
    with hold_run_directory(output_dir):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "whygame_reboot.cli",
                "examples/aes-mission-drift/question.yaml",
                "--output",
                str(output_dir),
                "--codex-home",
                str(codex_home),
            ],
            cwd=ROOT,
            env=_isolated_env(tmp_path),
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 1
    assert f"locked by pid {os.getpid()}" in result.stderr
    # It failed before the identity check, any outer run, or any write.
    assert "checkpoint identity differs" not in result.stderr
    assert not (tmp_path / "observability.db").exists()
    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == before


def test_killed_holder_releases_run_directory_lock(tmp_path: Path) -> None:
    import signal

    from whygame_reboot.runner import RUN_LOCK_FILE, hold_run_directory

    output_dir = tmp_path / "run"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import sys, time; from pathlib import Path; "
                "from whygame_reboot.runner import hold_run_directory; "
                "lock = hold_run_directory(Path(sys.argv[1])); lock.__enter__(); "
                "print('held', flush=True); time.sleep(60)"
            ),
            str(output_dir),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        assert (output_dir / RUN_LOCK_FILE).read_text().strip() == str(holder.pid)
        holder.send_signal(signal.SIGKILL)
        holder.wait(timeout=10)
    finally:
        if holder.poll() is None:
            holder.kill()
    # SIGKILL runs no cleanup, yet the kernel released the lock at process exit,
    # so an acquirable lock proves any attempt still marked running is dead.
    with hold_run_directory(output_dir) as lock:
        assert lock.held
