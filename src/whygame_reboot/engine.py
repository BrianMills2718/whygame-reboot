"""Deterministic commit, stress-test, revision, and replay operators."""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from typing import Any

from whygame_reboot.contracts import (
    ActiveProjection,
    CommittedClaim,
    CommittedProposal,
    Finding,
    ModelClaim,
    PlannedDecision,
    QuestionPacket,
    ReplacementClaim,
    RevisionEvent,
    RevisionPlan,
    RevisionResponse,
)


def canonical_json(value: Any) -> str:
    """Return stable compact JSON for hashing and immutable artifacts."""

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_node(value: str) -> str:
    """Normalize only identity noise; do not infer semantic equivalence.

    Identity noise is letter case and whitespace layout. Punctuation is kept
    because it can carry identity ("C++" versus "C#").
    """

    return " ".join(value.casefold().split())


def _commit_claim(claim: ModelClaim | ReplacementClaim, *, local_id: str) -> CommittedClaim:
    payload = {
        "subject": claim.subject.strip(),
        "relation": claim.relation,
        "object": claim.object.strip(),
        "rationale": claim.rationale.strip(),
        "observation_ids": sorted(set(claim.observation_ids)),
        "confidence": claim.confidence,
    }
    content_sha256 = sha256_value(payload)
    return CommittedClaim(
        claim_id=f"claim-{content_sha256[:16]}",
        proposal_local_id=local_id,
        subject=payload["subject"],
        normalized_subject=normalize_node(payload["subject"]),
        relation=payload["relation"],
        object=payload["object"],
        normalized_object=normalize_node(payload["object"]),
        rationale=payload["rationale"],
        observation_ids=tuple(payload["observation_ids"]),
        confidence=payload["confidence"],
        content_sha256=content_sha256,
    )


def commit_proposal(response: Any, packet: QuestionPacket) -> CommittedProposal:
    """Validate model-local references and assign all durable identities."""

    observation_ids = {item.id for item in packet.observations}
    local_ids = [item.local_id for item in response.claims]
    if len(local_ids) != len(set(local_ids)):
        raise ValueError("proposal local claim IDs must be unique")
    if {
        response.competing_pair.left_local_id,
        response.competing_pair.right_local_id,
    } - set(local_ids):
        raise ValueError("model competing pair references an unknown local claim")
    if response.competing_pair.left_local_id == response.competing_pair.right_local_id:
        raise ValueError("model competing pair must reference two distinct claims")
    for claim in response.claims:
        unknown = set(claim.observation_ids) - observation_ids
        if unknown:
            raise ValueError(f"claim {claim.local_id!r} cites unknown observations: {sorted(unknown)}")

    claims = tuple(_commit_claim(item, local_id=item.local_id) for item in response.claims)
    if len({item.claim_id for item in claims}) != len(claims):
        raise ValueError("proposal contains duplicate claim content")
    body = {
        "answer": response.answer,
        "claims": [item.model_dump(mode="json") for item in claims],
        "model_competing_pair": response.competing_pair.model_dump(mode="json"),
        "unresolved_questions": list(response.unresolved_questions),
    }
    return CommittedProposal(
        answer=response.answer,
        claims=claims,
        model_competing_pair=response.competing_pair,
        unresolved_questions=response.unresolved_questions,
        proposal_sha256=sha256_value(body),
    )


def select_finding(proposal: CommittedProposal) -> Finding | None:
    """Select the first exact direct causal conflict, independent of model choice."""

    candidates: list[tuple[CommittedClaim, CommittedClaim]] = []
    for left, right in combinations(sorted(proposal.claims, key=lambda item: item.claim_id), 2):
        same_endpoints = (
            left.normalized_subject == right.normalized_subject
            and left.normalized_object == right.normalized_object
        )
        if same_endpoints and {left.relation, right.relation} == {"causes", "prevents"}:
            candidates.append((left, right))
    if not candidates:
        return None
    left, right = candidates[0]
    body = {
        "kind": "direct_causal_conflict",
        "left_claim_id": left.claim_id,
        "right_claim_id": right.claim_id,
        "proposal_sha256": proposal.proposal_sha256,
        "explanation": (
            "The committed claims use the same normalized subject and object but make "
            "opposed direct causal assertions (causes versus prevents)."
        ),
    }
    digest = sha256_value(body)
    return Finding(
        finding_id=f"finding-{digest[:16]}",
        finding_sha256=digest,
        **body,
    )


def build_revision_plan(
    response: RevisionResponse,
    *,
    proposal: CommittedProposal,
    finding: Finding,
    packet: QuestionPacket,
) -> RevisionPlan:
    """Bind semantic feedback to exact committed inputs and system identities."""

    if finding.proposal_sha256 != proposal.proposal_sha256:
        raise ValueError("finding is not bound to this proposal")
    expected_targets = {finding.left_claim_id, finding.right_claim_id}
    decisions = response.decisions
    if {item.target_claim_id for item in decisions} != expected_targets:
        raise ValueError("revision decisions must cover exactly the selected finding claims")
    if {item.action for item in decisions} != {"retain", "supersede"}:
        raise ValueError("revision must retain one side and supersede the other")
    observation_ids = {item.id for item in packet.observations}
    original_by_id = {item.claim_id: item for item in proposal.claims}
    planned: list[PlannedDecision] = []
    for item in decisions:
        replacement = None
        if item.replacement is not None:
            unknown = set(item.replacement.observation_ids) - observation_ids
            if unknown:
                raise ValueError(f"replacement cites unknown observations: {sorted(unknown)}")
            replacement = _commit_claim(
                item.replacement,
                local_id=f"revision:{item.target_claim_id}",
            )
            if replacement.content_sha256 == original_by_id[item.target_claim_id].content_sha256:
                raise ValueError("replacement claim must differ from the superseded claim")
        planned.append(
            PlannedDecision(
                target_claim_id=item.target_claim_id,
                action=item.action,
                rationale=item.rationale,
                replacement=replacement,
            )
        )
    planned.sort(key=lambda item: item.target_claim_id)
    body = {
        "revised_answer": response.revised_answer,
        "proposal_sha256": proposal.proposal_sha256,
        "finding_id": finding.finding_id,
        "finding_sha256": finding.finding_sha256,
        "decisions": [item.model_dump(mode="json") for item in planned],
        "unresolved_questions": list(response.unresolved_questions),
    }
    return RevisionPlan(
        decisions=tuple(planned),
        plan_sha256=sha256_value(body),
        **{key: value for key, value in body.items() if key != "decisions"},
    )


def apply_revision(
    proposal: CommittedProposal,
    finding: Finding,
    plan: RevisionPlan,
) -> tuple[RevisionEvent, ActiveProjection]:
    """Apply one digest-bound plan without mutating proposal history."""

    if plan.proposal_sha256 != proposal.proposal_sha256:
        raise ValueError("revision plan proposal digest mismatch")
    if plan.finding_id != finding.finding_id or plan.finding_sha256 != finding.finding_sha256:
        raise ValueError("revision plan finding digest mismatch")
    superseded = tuple(
        sorted(item.target_claim_id for item in plan.decisions if item.action == "supersede")
    )
    added = tuple(
        item.replacement
        for item in plan.decisions
        if item.replacement is not None
    )
    event_body = {
        "plan_sha256": plan.plan_sha256,
        "finding_sha256": finding.finding_sha256,
        "superseded_claim_ids": list(superseded),
        "added_claims": [item.model_dump(mode="json") for item in added],
    }
    event_digest = sha256_value(event_body)
    event = RevisionEvent(
        event_id=f"event-{event_digest[:16]}",
        event_sha256=event_digest,
        superseded_claim_ids=superseded,
        added_claims=added,
        plan_sha256=plan.plan_sha256,
        finding_sha256=finding.finding_sha256,
    )
    projection = replay(proposal, (event,))
    projected = CommittedProposal(
        answer=plan.revised_answer,
        claims=projection.active_claims,
        model_competing_pair=proposal.model_competing_pair,
        unresolved_questions=plan.unresolved_questions,
        proposal_sha256=proposal.proposal_sha256,
    )
    if select_finding(projected) is not None:
        raise ValueError("revision leaves a direct causal conflict active")
    return event, projection


def replay(
    proposal: CommittedProposal,
    events: tuple[RevisionEvent, ...],
) -> ActiveProjection:
    """Replay append-only events into one deterministic active projection."""

    active = {item.claim_id: item for item in proposal.claims}
    superseded: set[str] = set()
    for event in events:
        body = {
            "plan_sha256": event.plan_sha256,
            "finding_sha256": event.finding_sha256,
            "superseded_claim_ids": list(event.superseded_claim_ids),
            "added_claims": [item.model_dump(mode="json") for item in event.added_claims],
        }
        if sha256_value(body) != event.event_sha256:
            raise ValueError("revision event digest mismatch")
        for claim_id in event.superseded_claim_ids:
            if claim_id not in active:
                raise ValueError(f"cannot supersede inactive claim {claim_id}")
            active.pop(claim_id)
            superseded.add(claim_id)
        for claim in event.added_claims:
            if claim.claim_id in active or claim.claim_id in superseded:
                raise ValueError(f"revision adds duplicate claim {claim.claim_id}")
            active[claim.claim_id] = claim
    ordered = tuple(sorted(active.values(), key=lambda item: item.claim_id))
    body = {
        "active_claims": [item.model_dump(mode="json") for item in ordered],
        "superseded_claim_ids": sorted(superseded),
    }
    return ActiveProjection(
        active_claims=ordered,
        superseded_claim_ids=tuple(body["superseded_claim_ids"]),
        projection_sha256=sha256_value(body),
    )
