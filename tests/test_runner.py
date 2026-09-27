from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.test_engine import packet, proposal, revision
from whygame_reboot.cli import _attach_outer_custody
from whygame_reboot.contracts import OuterRunReceipt, ProposalResponse, RevisionResponse
from whygame_reboot.engine import commit_proposal, select_finding
from whygame_reboot.render import render_report
from whygame_reboot.runner import run_loop


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
        if isinstance(value, Exception):
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
