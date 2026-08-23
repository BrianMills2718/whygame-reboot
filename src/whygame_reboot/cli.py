"""Command-line entrypoint for one immutable graph-adversary run."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

from whygame_reboot.contracts import QuestionPacket
from whygame_reboot.engine import sha256_value
from whygame_reboot.render import render_report
from whygame_reboot.runner import run_loop


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="YAML question packet")
    parser.add_argument("--output", type=Path, required=True, help="Immutable run directory")
    parser.add_argument("--run-id", help="Stable run ID; generated when omitted")
    parser.add_argument("--dry-run", action="store_true", help="Validate without model calls")
    parser.add_argument("--no-resume", action="store_true", help="Ignore an existing checkpoint")
    return parser


def _producer_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    args = _parser().parse_args()
    packet = QuestionPacket.model_validate(yaml.safe_load(args.packet.read_text(encoding="utf-8")))
    run = run_loop(
        packet,
        output_dir=args.output,
        producer_revision=_producer_revision(),
        dry_run=args.dry_run,
        run_id=args.run_id,
        resume=not args.no_resume,
    )
    report = render_report(run)
    report_sha256 = sha256_value(report)
    run = run.model_copy(update={"report_sha256": report_sha256})
    (args.output / "run.json").write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output / "report.html").write_text(report, encoding="utf-8")
    print(args.output / "report.html")
    return 0 if run.status in {"accepted", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
