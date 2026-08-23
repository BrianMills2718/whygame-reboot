"""Execute exactly one bounded proposal-stress-revision loop."""

from __future__ import annotations

import json
import math
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar

from llm_client import call_llm_structured, get_llm_call_receipts
from pydantic import BaseModel

from whygame_reboot.contracts import (
    CallReceipt,
    CommittedProposal,
    Finding,
    LoopRun,
    ProposalResponse,
    QuestionPacket,
    RevisionResponse,
)
from whygame_reboot.engine import (
    apply_revision,
    build_revision_plan,
    canonical_json,
    commit_proposal,
    select_finding,
    sha256_value,
)

MODEL = "codex/gpt-5.6-luna"
REASONING_EFFORT = "medium"
MAX_PROMPT_TOKENS = 20_000
MAX_OUTPUT_TOKENS = 4_000
MAX_STAGE_BUDGET_USD = 0.25
MAX_RUN_BUDGET_USD = 0.50
MODEL_JUSTIFICATION = (
    "Brian selected Luna medium for the personal-project rewrite program; this is one "
    "bounded WhyGame graph-adversary proposal or revision stage."
)

StructuredCaller = Callable[..., tuple[Any, Any]]
StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class ObservedRunLike(Protocol):
    run_id: str
    root_trace_id: str

    def child_trace_id(self, segment: str) -> str: ...

PROPOSAL_PROMPT = """You are the proposal stage in a bounded causal reasoning loop.
Use only the supplied observations. Return 2-6 typed claims. Include at least one
deliberate direct competing pair over the exact same subject and object: one relation
must be causes and the other prevents. The pair is a proposal for deterministic
stress-testing, not a declaration of truth. Cite observation IDs exactly. Keep
uncertainty visible and do not claim a world model, independent criticism, or factual
certification."""

REVISION_PROMPT = """You are the revision stage in a bounded causal reasoning loop.
The supplied proposal is already committed and the system selected one exact finding.
Return exactly two decisions covering the finding's two claim IDs: retain one and
supersede the other. The superseded claim requires a materially changed replacement
with provisional or contested confidence. Prefer a qualified relation such as
contributes_to or constrains so the direct causes-versus-prevents conflict is resolved.
Bind your reasoning to supplied observations, preserve unresolved uncertainty, and do
not claim truth, independence, or general contradiction detection."""


def _write_json(path: Path, value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _usage_int(usage: dict[str, Any], *names: str) -> int:
    for name in names:
        if usage.get(name) is not None:
            return max(0, int(usage[name]))
    return 0


def _receipt(trace_id: str, result: Any, *, elapsed_s: float) -> CallReceipt:
    canonical = get_llm_call_receipts(trace_id=trace_id)
    retained = canonical[-1] if canonical else None
    usage = result.usage
    if not isinstance(usage, dict):
        raise TypeError("llm_client result usage must be a dictionary")
    prompt_tokens = _usage_int(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _usage_int(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_int(usage, "total_tokens") or prompt_tokens + completion_tokens
    if total_tokens <= 0:
        raise ValueError("llm_client returned no observable token usage")
    cost = float(result.cost)
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("llm_client returned an invalid settled cost")
    latency = retained.latency_s if retained and retained.latency_s is not None else elapsed_s
    retry_count = retained.retry_count if retained and retained.retry_count is not None else 0
    return CallReceipt(
        trace_id=trace_id,
        logical_call_id=getattr(result, "logical_call_id", None),
        requested_model=MODEL,
        resolved_model=(
            getattr(result, "resolved_model", None)
            or getattr(result, "execution_model", None)
            or str(result.model)
        ),
        reasoning_effort=REASONING_EFFORT,
        latency_s=latency,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        retry_count=retry_count,
        fallback_used=False,
        cost_usd=cost,
        cost_source=str(getattr(result, "cost_source", "unspecified")),
        billing_mode=str(getattr(result, "billing_mode", "unknown")),
        request_fingerprint=(retained.request_fingerprint if retained else None),
        response_sha256=(retained.response_sha256 if retained else None),
    )


def _call_stage(
    *,
    caller: StructuredCaller,
    observed_run: ObservedRunLike,
    stage: str,
    system_prompt: str,
    payload: dict[str, Any],
    response_model: type[StructuredResult],
    codex_home: Path,
) -> tuple[StructuredResult, CallReceipt]:
    trace_id = observed_run.child_trace_id(stage)
    started = time.monotonic()
    structured, result = caller(
        MODEL,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
        ],
        response_model,
        timeout=180,
        logical_timeout=240,
        num_retries=0,
        fallback_models=[],
        task=f"whygame_reboot.{stage}",
        trace_id=trace_id,
        max_budget=MAX_STAGE_BUDGET_USD,
        max_prompt_tokens=MAX_PROMPT_TOKENS,
        max_tokens=MAX_OUTPUT_TOKENS,
        model_policy="enforce_allowlist",
        model_justification=MODEL_JUSTIFICATION,
        reasoning_effort=REASONING_EFFORT,
        codex_home=str(codex_home),
    )
    if not isinstance(structured, response_model):
        structured = response_model.model_validate(structured)
    return structured, _receipt(trace_id, result, elapsed_s=time.monotonic() - started)


def config_sha256() -> str:
    return sha256_value(
        {
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "max_prompt_tokens": MAX_PROMPT_TOKENS,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "max_stage_budget_usd": MAX_STAGE_BUDGET_USD,
            "max_run_budget_usd": MAX_RUN_BUDGET_USD,
            "num_retries": 0,
            "fallback_models": [],
        }
    )


def _base_run(
    packet: QuestionPacket,
    *,
    run_id: str,
    status: str,
    input_sha256: str,
    config_sha256: str,
    producer_revision: str,
    **kwargs: Any,
) -> LoopRun:
    return LoopRun(
        run_id=run_id,
        status=status,
        question=packet.question,
        observations=packet.observations,
        input_sha256=input_sha256,
        config_sha256=config_sha256,
        producer_revision=producer_revision,
        **kwargs,
    )


def _checkpoint_manifest(
    *,
    run_id: str,
    packet: QuestionPacket,
    input_sha256: str,
    config_sha256: str,
    producer_revision: str,
    proposal_path: Path,
    finding_path: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "question_id": packet.id,
        "input_sha256": input_sha256,
        "config_sha256": config_sha256,
        "producer_revision": producer_revision,
        "files": {
            proposal_path.name: sha256_value(json.loads(proposal_path.read_text())),
            finding_path.name: sha256_value(json.loads(finding_path.read_text())),
            receipt_path.name: sha256_value(json.loads(receipt_path.read_text())),
        },
    }


def _load_checkpoint(
    output_dir: Path,
    *,
    run_id: str,
    packet: QuestionPacket,
    input_sha256: str,
    config_sha256: str,
    producer_revision: str,
) -> tuple[CommittedProposal, Finding, CallReceipt] | None:
    manifest_path = output_dir / "checkpoint-manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "run_id": run_id,
        "question_id": packet.id,
        "input_sha256": input_sha256,
        "config_sha256": config_sha256,
        "producer_revision": producer_revision,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("checkpoint identity differs from the requested run")
    models = (
        ("proposal.json", CommittedProposal),
        ("finding.json", Finding),
        ("proposal-receipt.json", CallReceipt),
    )
    loaded: list[Any] = []
    for name, model in models:
        path = output_dir / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        if sha256_value(payload) != manifest["files"].get(name):
            raise ValueError(f"checkpoint digest mismatch for {name}")
        loaded.append(model.model_validate(payload))
    return loaded[0], loaded[1], loaded[2]


def _prepare_output_dir(
    output_dir: Path,
    *,
    dry_run: bool,
    resume: bool,
) -> tuple[Any, ...]:
    """Create a new run directory or admit only a digest-checked partial resume."""

    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        return ()
    if not output_dir.is_dir():
        raise FileExistsError(f"run output path exists and is not a directory: {output_dir}")
    if not any(output_dir.iterdir()):
        return ()
    if dry_run or not resume:
        raise FileExistsError(f"run output directory is not empty: {output_dir}")

    run_path = output_dir / "run.json"
    manifest_path = output_dir / "checkpoint-manifest.json"
    if not run_path.is_file() or not manifest_path.is_file():
        raise FileExistsError(
            "existing run directory is not a resumable proposal checkpoint; "
            "choose a new output directory"
        )
    existing = LoopRun.model_validate_json(run_path.read_text(encoding="utf-8"))
    if existing.status not in {"blocked", "error"}:
        raise FileExistsError(
            f"existing run is terminal ({existing.status}); choose a new output directory"
        )
    return existing.outer_runs


def run_loop(
    packet: QuestionPacket,
    *,
    output_dir: Path,
    producer_revision: str,
    observed_run: ObservedRunLike | None = None,
    dry_run: bool = False,
    caller: StructuredCaller = call_llm_structured,
    run_id: str | None = None,
    resume: bool = True,
    codex_home: Path | None = None,
) -> LoopRun:
    """Execute or resume the exact two-call graph-adversary loop."""

    stable_id = run_id or f"whygame-reboot/{uuid.uuid4().hex}"
    prior_outer_runs = _prepare_output_dir(output_dir, dry_run=dry_run, resume=resume)
    input_sha256 = sha256_value(packet)
    resolved_config_sha256 = config_sha256()
    common = {
        "run_id": stable_id,
        "input_sha256": input_sha256,
        "config_sha256": resolved_config_sha256,
        "producer_revision": producer_revision,
        "outer_runs": prior_outer_runs,
    }
    if len({item.id for item in packet.observations}) != len(packet.observations):
        run = _base_run(packet, status="blocked", issues=("observation IDs must be unique",), **common)
        _write_json(output_dir / "run.json", run)
        return run
    if dry_run:
        run = _base_run(packet, status="dry_run", **common)
        return run
    if observed_run is None:
        run = _base_run(
            packet,
            status="error",
            issues=("non-dry execution requires outer-run custody",),
            **common,
        )
        _write_json(output_dir / "run.json", run)
        return run
    if codex_home is None:
        run = _base_run(
            packet,
            status="error",
            issues=("non-dry execution requires an explicit codex_home",),
            **common,
        )
        _write_json(output_dir / "run.json", run)
        return run

    receipts: list[CallReceipt] = []
    proposal: CommittedProposal | None = None
    finding: Finding | None = None
    resumed: list[str] = []
    try:
        checkpoint = (
            _load_checkpoint(
                output_dir,
                run_id=stable_id,
                packet=packet,
                input_sha256=input_sha256,
                config_sha256=resolved_config_sha256,
                producer_revision=producer_revision,
            )
            if resume
            else None
        )
        if checkpoint is not None:
            proposal, finding, receipt = checkpoint
            receipts.append(receipt)
            resumed.append("proposal_and_finding")
        else:
            response, receipt = _call_stage(
                caller=caller,
                observed_run=observed_run,
                stage="proposal",
                system_prompt=PROPOSAL_PROMPT,
                payload={"question_packet": packet.model_dump(mode="json")},
                response_model=ProposalResponse,
                codex_home=codex_home,
            )
            receipts.append(receipt)
            proposal = commit_proposal(response, packet)
            finding = select_finding(proposal)
            if finding is None:
                run = _base_run(
                    packet,
                    status="blocked",
                    proposal=proposal,
                    receipts=tuple(receipts),
                    issues=("proposal contains no deterministic direct causal conflict",),
                    **common,
                )
                _write_json(output_dir / "run.json", run)
                return run
            proposal_path = output_dir / "proposal.json"
            finding_path = output_dir / "finding.json"
            receipt_path = output_dir / "proposal-receipt.json"
            _write_json(proposal_path, proposal)
            _write_json(finding_path, finding)
            _write_json(receipt_path, receipt)
            _write_json(
                output_dir / "checkpoint-manifest.json",
                _checkpoint_manifest(
                    packet=packet,
                    run_id=stable_id,
                    input_sha256=input_sha256,
                    config_sha256=resolved_config_sha256,
                    producer_revision=producer_revision,
                    proposal_path=proposal_path,
                    finding_path=finding_path,
                    receipt_path=receipt_path,
                ),
            )

        revision, receipt = _call_stage(
            caller=caller,
            observed_run=observed_run,
            stage="revision",
            system_prompt=REVISION_PROMPT,
            payload={
                "question_packet": packet.model_dump(mode="json"),
                "committed_proposal": proposal.model_dump(mode="json"),
                "selected_finding": finding.model_dump(mode="json"),
            },
            response_model=RevisionResponse,
            codex_home=codex_home,
        )
        receipts.append(receipt)
        plan = build_revision_plan(revision, proposal=proposal, finding=finding, packet=packet)
        event, projection = apply_revision(proposal, finding, plan)
        if sum(item.cost_usd for item in receipts) > MAX_RUN_BUDGET_USD:
            raise ValueError("settled run cost exceeded the run budget")
        run = _base_run(
            packet,
            status="accepted",
            proposal=proposal,
            finding=finding,
            revision_plan=plan,
            revision_events=(event,),
            active_projection=projection,
            receipts=tuple(receipts),
            resumed_stages=tuple(resumed),
            **common,
        )
        _write_json(output_dir / "revision-plan.json", plan)
        _write_json(output_dir / "revision-event.json", event)
        return run
    except Exception as exc:  # noqa: BLE001 - retain a truthful terminal partial artifact
        run = _base_run(
            packet,
            status="error",
            proposal=proposal,
            finding=finding,
            receipts=tuple(receipts),
            issues=(f"{type(exc).__name__}: {exc}",),
            resumed_stages=tuple(resumed),
            **common,
        )
        _write_json(output_dir / "run.json", run)
        return run


def canonical_packet_text(packet: QuestionPacket) -> str:
    """Expose the exact serialized packet used for the input digest."""

    return canonical_json(packet)
