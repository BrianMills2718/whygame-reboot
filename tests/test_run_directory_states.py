"""Table-driven audit of the run-directory state machine.

Every row is a combination of files a run directory can hold after a kill at
some write, or after a completed run in some mode. For each row and each mode
(dry run, ``--no-resume``, resume) the table asserts the admission decision,
that a refusal leaves the directory byte-for-byte untouched, that an admission
removes exactly the uncommitted files, and that a run which then completes
(including one that stops before writing its own checkpoint) leaves a
consistent directory: every file present is committed by the manifest or by
``run.json``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tests.test_engine import packet, proposal, revision
from tests.test_runner import ObservedRunStub, observed_runs, result  # noqa: F401
from whygame_reboot.cli import publish_terminal_record
from whygame_reboot.contracts import LoopRun, ProposalResponse, RevisionResponse
from whygame_reboot.engine import commit_proposal, select_finding
from whygame_reboot.runner import (
    RUN_LOCK_FILE,
    _prepare_output_dir,
    _write_json,
    hold_run_directory,
    run_loop,
    sha256_value,
)

pytestmark = pytest.mark.usefixtures("observed_runs")

RUN_ID = "whygame-reboot/test-states"
REVISION = "k" * 40
DATA = ("proposal.json", "finding.json", "proposal-receipt.json")
MANIFEST = "checkpoint-manifest.json"
ATTEMPTS = "attempts.json"
PLAN, EVENT = "revision-plan.json", "revision-event.json"
MODES = {"dry": (True, False), "fresh": (False, False), "resume": (False, True)}
FRESH, RESUME, REFUSE = "fresh", "resume", "refuse"
A, P, F, R, M = ATTEMPTS, *DATA, MANIFEST
D = (P, F, R)

# (id, checkpoint files, run.json status or None, report: None | "committed" |
#  "stale", decision for dry / --no-resume / resume)
STATES: tuple[tuple[str, tuple[str, ...], str | None, str | None, tuple[str, str, str]], ...] = (
    # A live run killed at each write, in publication order.
    ("empty", (), None, None, (FRESH, FRESH, FRESH)),
    ("ledger", (A,), None, None, (REFUSE, REFUSE, FRESH)),
    ("ledger+proposal", (A, P), None, None, (REFUSE, REFUSE, FRESH)),
    ("ledger+proposal+finding", (A, P, F), None, None, (REFUSE, REFUSE, FRESH)),
    ("ledger+all-data", (A, *D), None, None, (REFUSE, REFUSE, FRESH)),
    ("checkpoint", (A, *D, M), None, None, (REFUSE, REFUSE, RESUME)),
    ("checkpoint+plan", (A, *D, M, PLAN), None, None, (REFUSE, REFUSE, RESUME)),
    ("checkpoint+revision", (A, *D, M, PLAN, EVENT), None, None, (REFUSE, REFUSE, RESUME)),
    ("checkpoint+revision+report", (A, *D, M, PLAN, EVENT), None, "stale", (REFUSE, REFUSE, RESUME)),
    ("accepted", (A, *D, M, PLAN, EVENT), "accepted", "committed", (REFUSE, REFUSE, REFUSE)),
    # The proposal call failed.
    ("proposal-error-bare", (A,), "error", None, (REFUSE, REFUSE, REFUSE)),
    ("proposal-error-stale-report", (A,), "error", "stale", (REFUSE, REFUSE, REFUSE)),
    ("proposal-error", (A,), "error", "committed", (REFUSE, REFUSE, REFUSE)),
    # The proposal had no deterministic conflict.
    ("no-conflict-bare", (A,), "blocked", None, (REFUSE, REFUSE, REFUSE)),
    ("no-conflict", (A,), "blocked", "committed", (REFUSE, REFUSE, REFUSE)),
    # The revision call failed after the checkpoint committed.
    ("revision-error-bare", (A, *D, M), "error", None, (REFUSE, REFUSE, RESUME)),
    ("revision-error-stale-report", (A, *D, M), "error", "stale", (REFUSE, REFUSE, RESUME)),
    ("revision-error", (A, *D, M), "error", "committed", (REFUSE, REFUSE, RESUME)),
    # A resume of that error record killed at each of its own writes.
    ("resume+plan", (A, *D, M, PLAN), "error", "committed", (REFUSE, REFUSE, RESUME)),
    ("resume+revision", (A, *D, M, PLAN, EVENT), "error", "committed", (REFUSE, REFUSE, RESUME)),
    ("resume+revision+report", (A, *D, M, PLAN, EVENT), "error", "stale", (REFUSE, REFUSE, RESUME)),
    ("resumed-accepted", (A, *D, M, PLAN, EVENT), "accepted", "committed", (REFUSE, REFUSE, REFUSE)),
    # A dry run killed between its report and its terminal record, and completed.
    ("dry-run-report-only", (), None, "stale", (FRESH, FRESH, FRESH)),
    ("dry-run", (), "dry_run", "committed", (REFUSE, REFUSE, REFUSE)),
    # Duplicate observation IDs block before any attempt is recorded.
    ("duplicate-ids-bare", (), "blocked", None, (REFUSE, REFUSE, REFUSE)),
    ("duplicate-ids", (), "blocked", "committed", (REFUSE, REFUSE, REFUSE)),
    # Directories written before the attempt ledger existed.
    ("legacy-proposal", (P,), None, None, (FRESH, FRESH, FRESH)),
    ("legacy-all-data", D, None, None, (FRESH, FRESH, FRESH)),
    ("legacy-checkpoint", (*D, M), None, None, (REFUSE, REFUSE, RESUME)),
    # A file no run writes is never adopted or removed.
    ("foreign-file", ("notes.txt",), None, None, (REFUSE, REFUSE, REFUSE)),
)


def _caller(*, conflict: bool, revision_fails: bool):
    first = proposal(reverse=not conflict)
    committed = commit_proposal(proposal(), packet())
    finding = select_finding(committed)
    assert finding is not None
    second = revision(finding.left_claim_id, finding.right_claim_id)
    calls: list[str] = []

    def caller(model, messages, response_model, **kwargs):
        calls.append(response_model.__name__)
        if response_model is ProposalResponse:
            return first, result(len(calls))
        assert response_model is RevisionResponse
        if revision_fails:
            raise RuntimeError("revision route unavailable")
        return second, result(len(calls))

    return caller, calls


def _template(root: Path) -> tuple[Path, LoopRun]:
    """Produce every checkpoint and revision file from one real accepted run."""

    template = root / "template"
    caller, _ = _caller(conflict=True, revision_fails=False)
    accepted = run_loop(
        packet(),
        output_dir=template,
        producer_revision=REVISION,
        observed_run=ObservedRunStub("attempt-1"),
        caller=caller,
        run_id=RUN_ID,
        codex_home=root / "codex-profile",
    )
    assert accepted.status == "accepted", accepted.issues
    return template, accepted


def _record(accepted: LoopRun, status: str, checkpointed: bool) -> LoopRun:
    body = accepted.model_dump(mode="json")
    body.update(status=status, revision_plan=None, revision_events=[], active_projection=None)
    body["resumed_stages"] = []
    if status == "accepted":
        return accepted
    if status == "dry_run" or not checkpointed:
        body.update(proposal=None, finding=None, receipts=[])
    else:
        body["receipts"] = body["receipts"][:1]
    body["issues"] = [] if status == "dry_run" else [f"{status} for the state table"]
    return LoopRun.model_validate(body)


def _build(root: Path, row) -> Path:
    _, files, status, report, _ = row
    template, accepted = _template(root)
    directory = root / "run"
    directory.mkdir()
    for name in files:
        source = template / name
        if source.exists():
            (directory / name).write_bytes(source.read_bytes())
        else:
            (directory / name).write_text("foreign\n", encoding="utf-8")
    if status is not None:
        record = _record(accepted, status, checkpointed=M in files)
        if report == "committed":
            publish_terminal_record(directory, record)
        else:
            _write_json(directory / "run.json", record)
    if report == "stale":
        (directory / "report.html").write_text("<html>dead attempt</html>", encoding="utf-8")
    return directory


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {
        item.name: item.read_bytes()
        for item in directory.iterdir()
        if item.name != RUN_LOCK_FILE
    }


def _committed(directory: Path) -> set[str]:
    """Return the files a commit point vouches for; everything else is uncommitted."""

    names = set(_snapshot(directory))
    committed = names & {ATTEMPTS, "run.json", "notes.txt"}
    if MANIFEST in names:
        manifest = json.loads((directory / MANIFEST).read_text())
        committed.add(MANIFEST)
        for name in DATA:
            if name in names:
                assert manifest["files"][name] == sha256_value(
                    json.loads((directory / name).read_text())
                ), f"{name} does not match its manifest"
                committed.add(name)
    if "run.json" in names:
        run = json.loads((directory / "run.json").read_text())
        report = directory / "report.html"
        if report.exists() and run.get("report_sha256") == hashlib.sha256(
            report.read_bytes()
        ).hexdigest():
            committed.add("report.html")
        if run["status"] == "accepted":
            committed |= names & {PLAN, EVENT}
    return committed


def _assert_consistent_terminal(directory: Path, run: LoopRun) -> None:
    names = set(_snapshot(directory))
    assert not [name for name in names if name.endswith(".tmp")]
    assert names == _committed(directory), sorted(names - _committed(directory))
    assert {"run.json", "report.html"} <= names
    assert (MANIFEST in names) == bool(names & set(DATA))
    if MANIFEST in names:
        assert set(DATA) <= names
        manifest = json.loads((directory / MANIFEST).read_text())
        if run.proposal is not None:
            assert sha256_value(run.proposal) == manifest["files"]["proposal.json"]
    assert bool(names & {PLAN, EVENT}) == (run.status == "accepted")
    if run.status == "accepted":
        assert json.loads((directory / PLAN).read_text()) == run.revision_plan.model_dump(
            mode="json"
        )
    if run.status == "dry_run":
        assert names == {"run.json", "report.html"}


def _run(directory: Path, root: Path, *, mode: str, accept: bool) -> LoopRun:
    dry_run, resume = MODES[mode]
    caller, _ = _caller(conflict=accept, revision_fails=not accept)
    with hold_run_directory(directory) as lock:
        run = run_loop(
            packet(),
            output_dir=directory,
            producer_revision=REVISION,
            observed_run=None if dry_run else ObservedRunStub("attempt-2"),
            dry_run=dry_run,
            caller=caller,
            run_id=RUN_ID,
            resume=resume,
            codex_home=None if dry_run else root / "codex-profile",
            run_lock=lock,
        )
        return publish_terminal_record(directory, run)


CASES = [
    pytest.param(row, mode, id=f"{row[0]}-{mode}")
    for row in STATES
    for mode in MODES
]


@pytest.mark.parametrize(("row", "mode"), CASES)
def test_admission_decision_and_cleanup(tmp_path: Path, row, mode: str) -> None:
    directory = _build(tmp_path, row)
    before = _snapshot(directory)
    expected = row[4][list(MODES).index(mode)]
    dry_run, resume = MODES[mode]

    if expected == REFUSE:
        with pytest.raises(FileExistsError):
            _prepare_output_dir(directory, dry_run=dry_run, resume=resume)
        assert _snapshot(directory) == before
        return

    committed_before = _committed(directory)
    _, attempt = _prepare_output_dir(directory, dry_run=dry_run, resume=resume)
    after = _snapshot(directory)
    # Admission removes exactly the uncommitted files and changes no committed byte.
    assert set(after) == committed_before, sorted(set(after) ^ committed_before)
    assert all(after[name] == before[name] for name in after)
    assert (attempt is not None) == (expected == RESUME)
    if expected == FRESH:
        assert set(after) <= {ATTEMPTS}


@pytest.mark.parametrize("accept", [False, True], ids=["stops-early", "accepted"])
@pytest.mark.parametrize(("row", "mode"), [case for case in CASES if case.values[0][4][
    list(MODES).index(case.values[1])
] != REFUSE])
def test_admitted_run_ends_in_a_consistent_directory(
    tmp_path: Path, row, mode: str, accept: bool
) -> None:
    directory = _build(tmp_path, row)
    run = _run(directory, tmp_path, mode=mode, accept=accept)
    expected = "dry_run" if mode == "dry" else ("accepted" if accept else None)
    if expected is not None:
        assert run.status == expected, run.issues
    else:
        assert run.status in {"blocked", "error"}, run.issues
    _assert_consistent_terminal(directory, run)


@pytest.mark.parametrize("crash_after", range(3))
def test_cleanup_killed_midway_is_recovered_by_the_next_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crash_after: int
) -> None:
    from whygame_reboot import runner

    row = next(item for item in STATES if item[0] == "ledger+all-data")
    directory = _build(tmp_path, row)
    real_unlink = Path.unlink
    removed: list[str] = []

    class _Killed(BaseException):
        pass

    def dying_unlink(self: Path, *args: Any, **kwargs: Any) -> None:
        if self.parent == directory and len(removed) == crash_after:
            raise _Killed()
        real_unlink(self, *args, **kwargs)
        removed.append(self.name)

    monkeypatch.setattr(runner.Path, "unlink", dying_unlink)
    with pytest.raises(_Killed):
        _prepare_output_dir(directory, dry_run=False, resume=True)
    monkeypatch.setattr(runner.Path, "unlink", real_unlink)
    assert ATTEMPTS in _snapshot(directory)

    run = _run(directory, tmp_path, mode="resume", accept=False)
    assert run.status == "blocked"
    _assert_consistent_terminal(directory, run)
