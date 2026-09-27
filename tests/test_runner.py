from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_engine import packet, proposal, revision
from whygame_reboot.cli import _attach_outer_custody
from whygame_reboot.contracts import OuterRunReceipt, ProposalResponse, RevisionResponse
from whygame_reboot.engine import commit_proposal, select_finding
from whygame_reboot.render import render_report
from whygame_reboot.runner import run_loop

pytestmark = pytest.mark.usefixtures("observed_runs")


def killed_attempt_record(run_id: str, **overrides: object) -> SimpleNamespace:
    fields = {
        "run_id": run_id,
        "root_trace_id": f"{run_id}/outer",
        "status": "running",
        "linked_call_count": 1,
        "runtime_revision": None,
        "config_sha256": None,
        "requested_model": "codex/gpt-5.6-luna",
        "reasoning_effort": "medium",
        "max_budget": 0.5,
        "error_type": None,
        "error_phase": None,
    }
    return SimpleNamespace(**{**fields, **overrides})


@pytest.fixture
def observed_runs(monkeypatch: pytest.MonkeyPatch) -> dict[str, SimpleNamespace]:
    """Stand in for llm_client's durable observed-run store (no live database or calls).

    An attempt killed mid-run never reaches its terminal lifecycle write, so its
    durable record keeps status ``running`` with the calls it had linked.
    """

    records: dict[str, SimpleNamespace] = {}

    def get_observed_run(run_id: str) -> SimpleNamespace:
        return records.get(run_id) or killed_attempt_record(run_id)

    monkeypatch.setattr(
        "whygame_reboot.runner.get_observed_run", get_observed_run, raising=False
    )
    return records


class ObservedRunStub:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.root_trace_id = f"{run_id}/outer"

    def child_trace_id(self, segment: str) -> str:
        return f"{self.root_trace_id}/{segment}"


def result(number: int) -> SimpleNamespace:
    return SimpleNamespace(
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        cost=0.0,
        logical_call_id=f"call-{number}",
        resolved_model="codex/gpt-5.6-luna",
        model="codex/gpt-5.6-luna",
        cost_source="subscription_included",
        billing_mode="subscription_included",
    )


def outputs() -> tuple[ProposalResponse, RevisionResponse]:
    first = proposal()
    committed = commit_proposal(first, packet())
    finding = select_finding(committed)
    assert finding is not None
    return first, revision(finding.left_claim_id, finding.right_claim_id)


def caller_for(values):
    calls = []

    def caller(*args, **kwargs):
        calls.append((args, kwargs))
        value = values[len(calls) - 1]
        if isinstance(value, BaseException):
            raise value
        return value, result(len(calls))

    return caller, calls


def test_two_call_run_is_accepted_and_report_is_stable(tmp_path) -> None:
    caller, calls = caller_for(outputs())
    codex_home = tmp_path / "codex-profile"
    run = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="a" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-accepted"),
        caller=caller,
        run_id="whygame-reboot/test-accepted",
        codex_home=codex_home,
    )
    assert run.status == "accepted"
    assert len(calls) == 2
    assert len(run.receipts) == 2
    assert all(item.trace_id.startswith("whygame-reboot/test-accepted/outer/") for item in run.receipts)
    assert all(call[1]["num_retries"] == 0 for call in calls)
    assert all(call[1]["fallback_models"] == [] for call in calls)
    assert all(call[1]["codex_home"] == str(codex_home) for call in calls)
    assert run.active_projection
    report = render_report(run)
    assert report == render_report(run)
    assert run.question in report
    assert "Selected challenge" in report
    assert "Applied revision" in report
    assert "does not certify truth" in report

    missing_lifecycle = OuterRunReceipt(
        run_id="attempt-missing-lifecycle",
        root_trace_id="whygame-reboot/test-accepted/outer",
        status="completed",
        linked_call_count=0,
        runtime_revision="a" * 40,
        config_sha256="sha256:" + "b" * 64,
        requested_model="codex/gpt-5.6-luna",
        reasoning_effort="medium",
        max_budget=0.5,
        error_type=None,
        error_phase=None,
    )
    with pytest.raises(ValueError, match="lifecycle custody"):
        _attach_outer_custody(run, missing_lifecycle)

    retained = _attach_outer_custody(
        run,
        missing_lifecycle.model_copy(update={"linked_call_count": 2}),
    )
    assert retained.outer_runs[0].linked_call_count == 2


def test_second_call_failure_retains_and_resumes_checkpoint(tmp_path) -> None:
    first, second = outputs()
    failing, first_calls = caller_for((first, RuntimeError("revision route unavailable")))
    failed = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="b" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-resume-attempt-1"),
        caller=failing,
        run_id="whygame-reboot/test-resume",
        codex_home=tmp_path / "codex-profile",
    )
    assert failed.status == "error"
    assert len(first_calls) == 2
    assert (tmp_path / "proposal.json").exists()
    assert (tmp_path / "finding.json").exists()

    resumed_caller, resumed_calls = caller_for((second,))
    resumed = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="b" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-resume-attempt-2"),
        caller=resumed_caller,
        run_id="whygame-reboot/test-resume",
        codex_home=tmp_path / "codex-profile",
    )
    assert resumed.status == "accepted"
    assert len(resumed_calls) == 1
    assert resumed.resumed_stages == ("proposal_and_finding",)
    assert len(resumed.receipts) == 2


def test_corrupt_checkpoint_fails_before_dispatch(tmp_path) -> None:
    first, _ = outputs()
    failing, _ = caller_for((first, RuntimeError("stop after checkpoint")))
    run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="c" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-corrupt-attempt-1"),
        caller=failing,
        run_id="whygame-reboot/test-corrupt",
        codex_home=tmp_path / "codex-profile",
    )
    payload = json.loads((tmp_path / "proposal.json").read_text())
    payload["answer"] = "Changed bytes that do not match the retained digest."
    (tmp_path / "proposal.json").write_text(json.dumps(payload))

    def should_not_call(*args, **kwargs):
        raise AssertionError("corrupt checkpoint must fail before dispatch")

    corrupted = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="c" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-corrupt-attempt-2"),
        caller=should_not_call,
        run_id="whygame-reboot/test-corrupt",
        codex_home=tmp_path / "codex-profile",
    )
    assert corrupted.status == "error"
    assert "checkpoint digest mismatch" in corrupted.issues[0]


def test_checkpoint_cannot_be_rebound_to_another_run_id(tmp_path) -> None:
    first, _ = outputs()
    failing, _ = caller_for((first, RuntimeError("stop after checkpoint")))
    run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="e" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-rebind-attempt-1"),
        caller=failing,
        run_id="whygame-reboot/original-run",
        codex_home=tmp_path / "codex-profile",
    )

    def should_not_call(*args, **kwargs):
        raise AssertionError("identity mismatch must fail before dispatch")

    with pytest.raises(ValueError, match="checkpoint identity differs"):
        run_loop(
            packet(),
            output_dir=tmp_path,
            producer_revision="e" * 40,
            observed_run=ObservedRunStub("whygame-reboot/test-rebind-attempt-2"),
            caller=should_not_call,
            run_id="whygame-reboot/different-run",
            codex_home=tmp_path / "codex-profile",
        )


def test_dry_run_dispatches_no_call_and_renders_stopped_state(tmp_path) -> None:
    def should_not_call(*args, **kwargs):
        raise AssertionError("dry run must not dispatch")

    run = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="d" * 40,
        caller=should_not_call,
        run_id="whygame-reboot/test-dry",
        dry_run=True,
    )
    assert run.status == "dry_run"
    assert "pending" in render_report(run)


def test_live_run_without_explicit_codex_home_fails_before_dispatch(tmp_path) -> None:
    def should_not_call(*args, **kwargs):
        raise AssertionError("missing explicit account binding must fail before dispatch")

    run = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="f" * 40,
        observed_run=ObservedRunStub("whygame-reboot/test-missing-codex-home"),
        caller=should_not_call,
        run_id="whygame-reboot/test-missing-codex-home",
    )

    assert run.status == "error"
    assert run.receipts == ()
    assert run.issues == ("non-dry execution requires an explicit codex_home",)


class _Killed(BaseException):
    """Simulates SIGKILL/power loss: nothing after the fault point runs, not even except."""


def _current_attempt(run_id: str, linked_call_count: int) -> OuterRunReceipt:
    return OuterRunReceipt(
        run_id=run_id,
        root_trace_id=f"{run_id}/outer",
        status="completed",
        linked_call_count=linked_call_count,
        runtime_revision="a" * 40,
        config_sha256="sha256:" + "b" * 64,
        requested_model="codex/gpt-5.6-luna",
        reasoning_effort="medium",
        max_budget=0.5,
        error_type=None,
        error_phase=None,
    )


def _resume_to_acceptance(tmp_path, *, expected_calls: int):
    first, second = outputs()
    values = (first, second) if expected_calls == 2 else (second,)
    caller, calls = caller_for(values)
    resumed = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="k" * 40,
        observed_run=ObservedRunStub("attempt-2"),
        caller=caller,
        run_id="whygame-reboot/test-kill",
        codex_home=tmp_path / "codex-profile",
    )
    assert resumed.status == "accepted", resumed.issues
    assert len(calls) == expected_calls
    # The CLI attaches the current attempt; every retained receipt must be in custody.
    return _attach_outer_custody(resumed, _current_attempt("attempt-2", expected_calls))


def test_abrupt_kill_after_checkpoint_resumes_with_proposal_custody(tmp_path) -> None:
    first, _ = outputs()
    killing, _ = caller_for((first, _Killed()))
    with pytest.raises(_Killed):
        run_loop(
            packet(),
            output_dir=tmp_path,
            producer_revision="k" * 40,
            observed_run=ObservedRunStub("attempt-1"),
            caller=killing,
            run_id="whygame-reboot/test-kill",
            codex_home=tmp_path / "codex-profile",
        )
    assert not (tmp_path / "run.json").exists()
    assert (tmp_path / "checkpoint-manifest.json").exists()

    retained = _resume_to_acceptance(tmp_path, expected_calls=1)

    assert retained.resumed_stages == ("proposal_and_finding",)
    assert [item.run_id for item in retained.outer_runs] == ["attempt-1", "attempt-2"]
    assert retained.outer_runs[0].status == "running"
    assert retained.receipts[0].trace_id.startswith("attempt-1/outer/")


def test_error_record_without_outer_custody_still_resumes_to_acceptance(tmp_path) -> None:
    # Kill between run_loop's error run.json and the CLI's custody rewrite: the
    # retained error record carries no outer run for the proposal's attempt.
    first, _ = outputs()
    failing, _ = caller_for((first, RuntimeError("revision route unavailable")))
    failed = run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="k" * 40,
        observed_run=ObservedRunStub("attempt-1"),
        caller=failing,
        run_id="whygame-reboot/test-kill",
        codex_home=tmp_path / "codex-profile",
    )
    assert failed.outer_runs == ()

    retained = _resume_to_acceptance(tmp_path, expected_calls=1)

    assert [item.run_id for item in retained.outer_runs] == ["attempt-1", "attempt-2"]


def test_resume_rejects_checkpoint_attempt_with_foreign_trace_root(
    tmp_path, observed_runs
) -> None:
    first, _ = outputs()
    killing, _ = caller_for((first, _Killed()))
    with pytest.raises(_Killed):
        run_loop(
            packet(),
            output_dir=tmp_path,
            producer_revision="k" * 40,
            observed_run=ObservedRunStub("attempt-1"),
            caller=killing,
            run_id="whygame-reboot/test-kill",
            codex_home=tmp_path / "codex-profile",
        )
    observed_runs["attempt-1"] = killed_attempt_record("attempt-1", root_trace_id="someone-else")

    def should_not_call(*args, **kwargs):
        raise AssertionError("custody mismatch must fail before dispatch")

    with pytest.raises(ValueError, match="outer-run custody"):
        run_loop(
            packet(),
            output_dir=tmp_path,
            producer_revision="k" * 40,
            observed_run=ObservedRunStub("attempt-2"),
            caller=should_not_call,
            run_id="whygame-reboot/test-kill",
            codex_home=tmp_path / "codex-profile",
        )


# Every durable write in a live run, in order. A kill "at" a write lands after the
# temporary bytes are written but before the atomic rename publishes them.
LIVE_WRITES = (
    "proposal.json",
    "finding.json",
    "proposal-receipt.json",
    "checkpoint-manifest.json",
    "revision-plan.json",
    "revision-event.json",
)


@pytest.mark.parametrize("kill_at", range(len(LIVE_WRITES)))
def test_kill_at_every_write_leaves_fresh_or_resumable_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch, kill_at: int
) -> None:
    from whygame_reboot import runner

    real_replace = runner.os.replace
    published: list[str] = []

    def faulty_replace(src, dst):
        if len(published) == kill_at:
            raise _Killed()
        real_replace(src, dst)
        published.append(Path(dst).name)

    monkeypatch.setattr(runner.os, "replace", faulty_replace)
    first, second = outputs()
    caller, _ = caller_for((first, second))
    with pytest.raises(_Killed):
        run_loop(
            packet(),
            output_dir=tmp_path,
            producer_revision="k" * 40,
            observed_run=ObservedRunStub("attempt-1"),
            caller=caller,
            run_id="whygame-reboot/test-kill",
            codex_home=tmp_path / "codex-profile",
        )
    assert published == list(LIVE_WRITES[:kill_at])
    # No published file is ever partial: each is absent or complete JSON.
    for name in LIVE_WRITES:
        if (tmp_path / name).exists():
            json.loads((tmp_path / name).read_text())
    monkeypatch.setattr(runner.os, "replace", real_replace)

    committed = kill_at > LIVE_WRITES.index("checkpoint-manifest.json")
    retained = _resume_to_acceptance(tmp_path, expected_calls=1 if committed else 2)

    if committed:
        assert retained.resumed_stages == ("proposal_and_finding",)
        assert [item.run_id for item in retained.outer_runs] == ["attempt-1", "attempt-2"]
    else:
        assert retained.resumed_stages == ()
        assert [item.run_id for item in retained.outer_runs] == ["attempt-2"]
    assert not [path.name for path in tmp_path.iterdir() if path.name.endswith(".tmp")]


def test_killed_accepted_attempt_before_terminal_record_resumes(tmp_path) -> None:
    # The CLI writes report.html before run.json, so a kill between them leaves
    # an uncommitted report beside the committed checkpoint.
    caller, _ = caller_for(outputs())
    run_loop(
        packet(),
        output_dir=tmp_path,
        producer_revision="k" * 40,
        observed_run=ObservedRunStub("attempt-1"),
        caller=caller,
        run_id="whygame-reboot/test-kill",
        codex_home=tmp_path / "codex-profile",
    )
    (tmp_path / "report.html").write_text("<html>uncommitted</html>", encoding="utf-8")

    retained = _resume_to_acceptance(tmp_path, expected_calls=1)

    assert [item.run_id for item in retained.outer_runs] == ["attempt-1", "attempt-2"]
