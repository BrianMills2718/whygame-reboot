from __future__ import annotations

from whygame_reboot.contracts import ProposalResponse, QuestionPacket, RevisionResponse
from whygame_reboot.engine import (
    apply_revision,
    build_revision_plan,
    commit_proposal,
    replay,
    select_finding,
)


def packet() -> QuestionPacket:
    return QuestionPacket.model_validate(
        {
            "id": "drift",
            "question": "Why can a drift-prevention system drift away from its mission?",
            "observations": [
                {
                    "id": "narrow",
                    "text": "A narrow implementation boundary became the product identity.",
                    "source_ref": "decision-0003#context",
                    "source_revision": "ce866ef",
                },
                {
                    "id": "green",
                    "text": "Registered relationships stayed green while intent was omitted.",
                    "source_ref": "decision-0003#context",
                    "source_revision": "ce866ef",
                },
            ],
        }
    )


def proposal(*, reverse: bool = False) -> ProposalResponse:
    return ProposalResponse.model_validate(
        {
            "answer": "A local optimization can either cause or prevent mission drift depending on authority coverage.",
            "claims": [
                {
                    "local_id": "cause",
                    "subject": "narrow gate optimization",
                    "relation": "causes",
                    "object": "mission drift",
                    "rationale": "The narrow implementation displaced the complete mission in active authority.",
                    "observation_ids": ["narrow"],
                    "confidence": "asserted",
                },
                {
                    "local_id": "prevent",
                    "subject": "mission drift" if reverse else "narrow gate optimization",
                    "relation": "prevents",
                    "object": "narrow gate optimization" if reverse else "mission drift",
                    "rationale": "A bounded gate can prevent uncontrolled scope when mission authority stays registered.",
                    "observation_ids": ["green"],
                    "confidence": "asserted",
                },
            ],
            "competing_pair": {
                "left_local_id": "cause",
                "right_local_id": "prevent",
                "disagreement": "The same bounded optimization is proposed as both causing and preventing drift.",
            },
            "unresolved_questions": ["Which authority surface actually controlled successor work?"],
        }
    )


def revision(left: str, right: str) -> RevisionResponse:
    return RevisionResponse.model_validate(
        {
            "revised_answer": "A narrow gate contributes to drift when its temporary boundary is promoted into product identity without mission coverage.",
            "decisions": [
                {
                    "target_claim_id": left,
                    "action": "supersede",
                    "rationale": "The direct causal claim overstates a conditional authority-migration mechanism.",
                    "replacement": {
                        "subject": "narrow gate optimization",
                        "relation": "contributes_to",
                        "object": "mission drift",
                        "rationale": "It contributes when registered checks cover the slice but omit the mission authority.",
                        "observation_ids": ["narrow", "green"],
                        "confidence": "provisional",
                    },
                },
                {
                    "target_claim_id": right,
                    "action": "retain",
                    "rationale": "A bounded gate still prevents scope drift when its boundary remains explicitly temporary.",
                },
            ],
            "unresolved_questions": ["How often does the same authority migration fail in other projects?"],
        }
    )


def test_direct_conflict_becomes_append_only_revision() -> None:
    original = commit_proposal(proposal(), packet())
    finding = select_finding(original)
    assert finding is not None
    plan = build_revision_plan(
        revision(finding.left_claim_id, finding.right_claim_id),
        proposal=original,
        finding=finding,
        packet=packet(),
    )
    event, projection = apply_revision(original, finding, plan)

    assert len(original.claims) == 2
    assert len(event.superseded_claim_ids) == 1
    assert len(event.added_claims) == 1
    assert event.added_claims[0].confidence == "provisional"
    assert replay(original, (event,)) == projection
    assert set(projection.superseded_claim_ids).isdisjoint(
        claim.claim_id for claim in projection.active_claims
    )


def test_reverse_edge_is_feedback_not_a_conflict() -> None:
    committed = commit_proposal(proposal(reverse=True), packet())
    assert select_finding(committed) is None


def test_model_local_reference_must_exist() -> None:
    invalid = proposal().model_copy(
        update={
            "competing_pair": proposal().competing_pair.model_copy(
                update={"right_local_id": "missing"}
            )
        }
    )
    try:
        commit_proposal(invalid, packet())
    except ValueError as exc:
        assert "unknown local claim" in str(exc)
    else:
        raise AssertionError("unknown model-local IDs must fail")


def test_wrong_finding_digest_cannot_be_applied() -> None:
    original = commit_proposal(proposal(), packet())
    finding = select_finding(original)
    assert finding is not None
    plan = build_revision_plan(
        revision(finding.left_claim_id, finding.right_claim_id),
        proposal=original,
        finding=finding,
        packet=packet(),
    ).model_copy(update={"finding_sha256": "0" * 64})
    try:
        apply_revision(original, finding, plan)
    except ValueError as exc:
        assert "finding digest mismatch" in str(exc)
    else:
        raise AssertionError("mismatched evidence binding must fail")
