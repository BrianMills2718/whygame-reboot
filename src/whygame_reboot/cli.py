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
from llm_client import ObservedRun, get_observed_run

from whygame_reboot.contracts import LoopRun, OuterRunReceipt, QuestionPacket
from whygame_reboot.render import render_report
from whygame_reboot.runner import (
    MAX_RUN_BUDGET_USD,
    MODEL,
    REASONING_EFFORT,
    config_sha256,
    run_loop,
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
    parser.add_argument("--run-id", help="Stable run ID; generated when omitted")
    parser.add_argument("--dry-run", action="store_true", help="Validate without model calls")
    parser.add_argument("--no-resume", action="store_true", help="Ignore an existing checkpoint")
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


def _outer_receipt(run_id: str) -> OuterRunReceipt:
    record = get_observed_run(run_id)
    return OuterRunReceipt(
        run_id=record.run_id,
        root_trace_id=record.root_trace_id,
        status=record.status,
        linked_call_count=record.linked_call_count,
        runtime_revision=record.runtime_revision,
        config_sha256=record.config_sha256,
        requested_model=record.requested_model,
        reasoning_effort=record.reasoning_effort,
        max_budget=record.max_budget,
        error_type=record.error_type,
        error_phase=record.error_phase,
    )


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


class _TerminalRunError(RuntimeError):
    def __init__(self, run: LoopRun) -> None:
        super().__init__(f"run ended with status {run.status}")
        self.run = run


def main() -> int:
    args = _parser().parse_args()
    revision = _producer_revision()
    product_run_id = args.run_id or f"whygame-reboot/{uuid.uuid4().hex}"
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
        run = _attach_outer_custody(run, _outer_receipt(observed.run_id))
        report = render_report(run)
        report_sha256 = hashlib.sha256(report.encode("utf-8")).hexdigest()
        run = run.model_copy(update={"report_sha256": report_sha256})
        (args.output / "run.json").write_text(
            json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (args.output / "report.html").write_text(report, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - never leave a success manifest without custody
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(args.output / "report.html")
    return 0 if run.status in {"accepted", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
