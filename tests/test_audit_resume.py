"""Resume must keep the checkpoint's identity and never rewrite it on a mismatch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_cli import ROOT, _isolated_env
from tests.test_engine import packet
from tests.test_runner import ObservedRunStub, caller_for, outputs
from whygame_reboot import cli
from whygame_reboot.runner import run_loop

ORIGINAL_RUN_ID = "whygame-reboot/original-run"


def _failed_checkpoint(output_dir: Path, *, producer_revision: str) -> dict[str, bytes]:
    first, _ = outputs()
    failing, _ = caller_for((first, RuntimeError("revision route unavailable")))
    failed = run_loop(
        packet(),
        output_dir=output_dir,
        producer_revision=producer_revision,
        observed_run=ObservedRunStub("attempt-1"),
        caller=failing,
        run_id=ORIGINAL_RUN_ID,
        codex_home=output_dir.parent / "codex-profile",
    )
    assert failed.status == "error"
    return {path.name: path.read_bytes() for path in output_dir.iterdir()}


def _should_not_call(*args, **kwargs):
    raise AssertionError("identity mismatch must fail before dispatch")


def test_mismatched_resume_rejects_without_rewriting_checkpoint(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    before = _failed_checkpoint(output_dir, producer_revision="e" * 40)

    with pytest.raises(ValueError, match="checkpoint identity differs"):
        run_loop(
            packet(),
            output_dir=output_dir,
            producer_revision="e" * 40,
            observed_run=ObservedRunStub("attempt-2"),
            caller=_should_not_call,
            run_id="whygame-reboot/different-run",
            codex_home=tmp_path / "codex-profile",
        )
    with pytest.raises(ValueError, match="checkpoint identity differs"):
        run_loop(
            packet(),
            output_dir=output_dir,
            producer_revision="f" * 40,
            observed_run=ObservedRunStub("attempt-3"),
            caller=_should_not_call,
            run_id=ORIGINAL_RUN_ID,
            codex_home=tmp_path / "codex-profile",
        )

    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == before


def test_resume_without_run_id_adopts_checkpoint_identity(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    _failed_checkpoint(output_dir, producer_revision="e" * 40)
    _, second = outputs()
    resumed_caller, resumed_calls = caller_for((second,))

    resumed = run_loop(
        packet(),
        output_dir=output_dir,
        producer_revision="e" * 40,
        observed_run=ObservedRunStub("attempt-2"),
        caller=resumed_caller,
        codex_home=tmp_path / "codex-profile",
    )

    assert resumed.status == "accepted", resumed.issues
    assert resumed.run_id == ORIGINAL_RUN_ID
    assert len(resumed_calls) == 1


def test_cli_resume_without_run_id_passes_checkpoint_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "run"
    _failed_checkpoint(output_dir, producer_revision="e" * 40)
    codex_home = tmp_path / "codex-profile"
    (codex_home / ".codex").mkdir(parents=True)
    (codex_home / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
    for key, value in _isolated_env(tmp_path).items():
        if key.startswith("LLM_CLIENT_"):
            monkeypatch.setenv(key, value)
    seen: dict[str, object] = {}

    def fake_run_loop(*args, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before any dispatch")

    monkeypatch.setattr(cli, "run_loop", fake_run_loop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "whygame-reboot",
            str(ROOT / "examples" / "aes-mission-drift" / "question.yaml"),
            "--output",
            str(output_dir),
            "--codex-home",
            str(codex_home),
        ],
    )

    assert cli.main() == 1
    assert seen["run_id"] == ORIGINAL_RUN_ID


def test_cli_mismatched_resume_leaves_checkpoint_bytes_unchanged(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    # A checkpoint from another producer revision can never match the CLI's HEAD,
    # so this reaches the identity check without any model dispatch.
    before = _failed_checkpoint(output_dir, producer_revision="0" * 40)
    codex_home = tmp_path / "codex-profile"
    (codex_home / ".codex").mkdir(parents=True)
    (codex_home / ".codex" / "auth.json").write_text("{}", encoding="utf-8")

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
    assert "checkpoint identity differs" in result.stderr
    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == before
