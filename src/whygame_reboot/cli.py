"""Command-line entrypoint for one immutable graph-adversary run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import yaml
from llm_client import ObservedRun

from whygame_reboot.contracts import LoopRun, OuterRunReceipt, QuestionPacket
from whygame_reboot.render import render_report
from whygame_reboot.runner import (
    MAX_RUN_BUDGET_USD,
    MODEL,
    REASONING_EFFORT,
    RunDirectoryLock,
    RunDirectoryLockedError,
    checkpoint_run_id,
    config_sha256,
    hold_run_directory,
    observed_outer_receipt,
    run_loop,
    write_atomic_text,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="YAML question packet")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New run directory, or an exact failed proposal checkpoint to resume",
    )
    parser.add_argument(
        "--run-id",
        help="Stable run ID; a resumed checkpoint keeps its own, otherwise generated",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without model calls")
    parser.add_argument("--no-resume", action="store_true", help="Ignore an existing checkpoint")
    parser.add_argument(
        "--codex-home",
        type=Path,
        help="Caller-owned profile root containing .codex/auth.json; required for live runs",
    )
    return parser


def _producer_revision() -> str:
    source_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _attach_outer_custody(
    run: LoopRun,
    receipt: OuterRunReceipt,
) -> LoopRun:
    outer_runs = (*run.outer_runs, receipt)
    if run.status == "accepted":
        if receipt.status != "completed" or len(run.receipts) != 2:
            raise ValueError("accepted run requires a completed outer attempt and two call receipts")
        roots = tuple(item.root_trace_id + "/" for item in outer_runs)
        if any(not item.trace_id.startswith(roots) for item in run.receipts):
            raise ValueError("accepted call receipt is not rooted in retained outer-run custody")
        for outer in outer_runs:
            retained_receipts = sum(
                item.trace_id.startswith(outer.root_trace_id + "/") for item in run.receipts
            )
            if outer.linked_call_count < retained_receipts:
                raise ValueError("accepted call receipt lacks matching outer-run lifecycle custody")
    elif run.status == "dry_run":
        if receipt.status != "completed" or receipt.linked_call_count != 0:
            raise ValueError("dry run requires one completed zero-call outer attempt")
    return run.model_copy(update={"outer_runs": outer_runs})


def publish_terminal_record(output_dir: Path, run: LoopRun) -> LoopRun:
    """Publish the report, then ``run.json`` naming its digest, and return that record.

    run.json is the terminal commit point, so it is published last: a kill before
    it leaves the checkpoint resumable rather than a record whose report_sha256
    names a report that was never written.
    """

    report = render_report(run)
    run = run.model_copy(
        update={"report_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest()}
    )
    write_atomic_text(output_dir / "report.html", report)
    write_atomic_text(
        output_dir / "run.json",
        json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
    )
    return run


class _TerminalRunError(RuntimeError):
    def __init__(self, run: LoopRun) -> None:
        super().__init__(f"run ended with status {run.status}")
        self.run = run


def main() -> int:
    args = _parser().parse_args()
    codex_home: Path | None = None
    if not args.dry_run:
        if args.codex_home is None:
            print("live runs require --codex-home for an explicit Codex account", file=sys.stderr)
            return 2
        codex_home = args.codex_home.expanduser().resolve()
        if not (codex_home / ".codex" / "auth.json").is_file():
            print("--codex-home must contain .codex/auth.json", file=sys.stderr)
            return 2
    revision = _producer_revision()
    try:
        # One exclusive lock covers reading checkpoint identity, the loop, and
        # publishing the terminal record; a concurrent run fails here untouched.
        with hold_run_directory(args.output) as run_lock:
            return _run_locked(args, codex_home=codex_home, revision=revision, run_lock=run_lock)
    except (RunDirectoryLockedError, FileExistsError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def _run_locked(
    args: argparse.Namespace,
    *,
    codex_home: Path | None,
    revision: str,
    run_lock: RunDirectoryLock,
) -> int:
    # Resuming a checkpoint keeps its run ID unless the caller names one explicitly.
    product_run_id = (
        args.run_id
        or (None if args.no_resume or args.dry_run else checkpoint_run_id(args.output))
        or f"whygame-reboot/{uuid.uuid4().hex}"
    )
    attempt_token = uuid.uuid4().hex
    os.environ["LLM_CLIENT_REQUIRE_OBSERVED_RUN"] = "1"
    observed = ObservedRun(
        project="whygame-reboot",
        operation="graph_adversary_loop",
        executable="whygame-reboot",
        run_id=f"whygame-reboot-attempt-{attempt_token}",
        root_trace_id=(
            "whygame-reboot:"
            f"{hashlib.sha256(product_run_id.encode('utf-8')).hexdigest()[:16]}:"
            f"{attempt_token}"
        ),
        runtime_revision=revision,
        config_sha256=f"sha256:{config_sha256()}",
        requested_model=MODEL,
        reasoning_effort=REASONING_EFFORT,
        max_budget=MAX_RUN_BUDGET_USD,
    )
    run: LoopRun | None = None
    try:
        with observed:
            observed.set_phase("input_validation")
            packet = QuestionPacket.model_validate(
                yaml.safe_load(args.packet.read_text(encoding="utf-8"))
            )
            observed.set_phase("dry_run" if args.dry_run else "proposal_and_revision")
            run = run_loop(
                packet,
                output_dir=args.output,
                producer_revision=revision,
                observed_run=observed,
                dry_run=args.dry_run,
                run_id=product_run_id,
                resume=not args.no_resume,
                codex_home=codex_home,
                run_lock=run_lock,
            )
            if run.status not in {"accepted", "dry_run"}:
                raise _TerminalRunError(run)
    except _TerminalRunError as exc:
        run = exc.run
    except Exception as exc:  # noqa: BLE001 - outer run retains exact failure chronology
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    assert run is not None
    try:
        run = _attach_outer_custody(run, observed_outer_receipt(observed.run_id))
        publish_terminal_record(args.output, run)
    except Exception as exc:  # noqa: BLE001 - never leave a success manifest without custody
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(args.output / "report.html")
    return 0 if run.status in {"accepted", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
