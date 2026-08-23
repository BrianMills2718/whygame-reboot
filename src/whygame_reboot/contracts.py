"""Strict durable contracts for the graph-adversary loop."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    """Reject silent contract drift at every durable boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Observation(Contract):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    text: str = Field(min_length=10, max_length=4_000)
    source_ref: str = Field(min_length=3, max_length=500)
    source_revision: str = Field(min_length=7, max_length=200)


class QuestionPacket(Contract):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    question: str = Field(min_length=20, max_length=2_000)
    observations: tuple[Observation, ...] = Field(min_length=2, max_length=12)


Relation = Literal["causes", "prevents", "contributes_to", "constrains"]
Confidence = Literal["asserted", "provisional", "contested"]


class ModelClaim(Contract):
    local_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    subject: str = Field(min_length=3, max_length=300)
    relation: Relation
    object: str = Field(min_length=3, max_length=300)
    rationale: str = Field(min_length=20, max_length=2_000)
    observation_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    confidence: Confidence


class CompetingPair(Contract):
    left_local_id: str
    right_local_id: str
    disagreement: str = Field(min_length=20, max_length=1_000)


class ProposalResponse(Contract):
    answer: str = Field(min_length=40, max_length=4_000)
    claims: tuple[ModelClaim, ...] = Field(min_length=2, max_length=8)
    competing_pair: CompetingPair
    unresolved_questions: tuple[str, ...] = Field(min_length=1, max_length=8)


class CommittedClaim(Contract):
    claim_id: str = Field(pattern=r"^claim-[0-9a-f]{16}$")
    proposal_local_id: str
    subject: str
    normalized_subject: str
    relation: Relation
    object: str
    normalized_object: str
    rationale: str
    observation_ids: tuple[str, ...]
    confidence: Confidence
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CommittedProposal(Contract):
    answer: str
    claims: tuple[CommittedClaim, ...]
    model_competing_pair: CompetingPair
    unresolved_questions: tuple[str, ...]
    proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Finding(Contract):
    finding_id: str = Field(pattern=r"^finding-[0-9a-f]{16}$")
    kind: Literal["direct_causal_conflict"] = "direct_causal_conflict"
    left_claim_id: str
    right_claim_id: str
    proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    explanation: str
    finding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReplacementClaim(Contract):
    subject: str = Field(min_length=3, max_length=300)
    relation: Relation
    object: str = Field(min_length=3, max_length=300)
    rationale: str = Field(min_length=20, max_length=2_000)
    observation_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    confidence: Literal["provisional", "contested"]


class RevisionDecision(Contract):
    target_claim_id: str
    action: Literal["retain", "supersede"]
    rationale: str = Field(min_length=20, max_length=2_000)
    replacement: ReplacementClaim | None = None

    @model_validator(mode="after")
    def _replacement_matches_action(self) -> RevisionDecision:
        if (self.action == "supersede") != (self.replacement is not None):
            raise ValueError("supersede requires a replacement and retain forbids one")
        return self


class RevisionResponse(Contract):
    revised_answer: str = Field(min_length=40, max_length=4_000)
    decisions: tuple[RevisionDecision, ...] = Field(min_length=2, max_length=2)
    unresolved_questions: tuple[str, ...] = Field(min_length=1, max_length=8)


class PlannedDecision(Contract):
    target_claim_id: str
    action: Literal["retain", "supersede"]
    rationale: str
    replacement: CommittedClaim | None = None


class RevisionPlan(Contract):
    revised_answer: str
    proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finding_id: str
    finding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[PlannedDecision, ...]
    unresolved_questions: tuple[str, ...]
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RevisionEvent(Contract):
    event_id: str = Field(pattern=r"^event-[0-9a-f]{16}$")
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    superseded_claim_ids: tuple[str, ...]
    added_claims: tuple[CommittedClaim, ...]
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActiveProjection(Contract):
    active_claims: tuple[CommittedClaim, ...]
    superseded_claim_ids: tuple[str, ...]
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CallReceipt(Contract):
    trace_id: str
    logical_call_id: str | None = None
    requested_model: str
    resolved_model: str
    reasoning_effort: Literal["medium"]
    latency_s: float = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(gt=0)
    retry_count: int = Field(ge=0)
    fallback_used: bool
    cost_usd: float = Field(ge=0)
    cost_source: str
    billing_mode: str
    request_fingerprint: str | None = None
    response_sha256: str | None = None


class OuterRunReceipt(Contract):
    run_id: str
    root_trace_id: str
    status: Literal[
        "completed",
        "failed_before_call_start",
        "failed_after_call_start",
        "cancelled",
    ]
    linked_call_count: int = Field(ge=0)
    runtime_revision: str | None
    config_sha256: str | None
    requested_model: str | None
    reasoning_effort: str | None
    max_budget: float | None
    error_type: str | None
    error_phase: str | None


class LoopRun(Contract):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    status: Literal["dry_run", "accepted", "blocked", "error"]
    question: str
    observations: tuple[Observation, ...]
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_revision: str
    proposal: CommittedProposal | None = None
    finding: Finding | None = None
    revision_plan: RevisionPlan | None = None
    revision_events: tuple[RevisionEvent, ...] = ()
    active_projection: ActiveProjection | None = None
    receipts: tuple[CallReceipt, ...] = ()
    outer_runs: tuple[OuterRunReceipt, ...] = ()
    issues: tuple[str, ...] = ()
    resumed_stages: tuple[str, ...] = ()
    report_sha256: str | None = None
