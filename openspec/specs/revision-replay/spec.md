# revision-replay Specification

## Purpose
Characterize the existing deterministic revision engine (`src/whygame_reboot/engine.py`): how a proposal's conflict becomes an append-only, digest-bound revision whose active graph is computed by replay. This scopes one capability that already works; it adds no behaviour.

## Requirements

### Requirement: append-only-revision

The engine SHALL record a revision as an appended event that supersedes the conflicting claim and adds a provisional replacement claim, leaving the original proposal's claims unchanged, and SHALL compute the active graph by replaying events over the original proposal.

Source: inferred by agent, 2026-11-17: restates the repository's own AGENTS.md rule "Revision is append-only. Compute the active graph by replaying events" (Brian, 2026-11-17: "option B is what i want").

#### Scenario: Direct conflict becomes an append-only revision

- **WHEN** a committed proposal has two claims with explicitly opposed polarity over the same normalized subject and object, and a revision plan for that finding is applied
- **THEN** the original proposal still has its two claims, the event supersedes one claim and adds one provisional claim, and replaying the event yields the same active graph

### Requirement: feedback-is-not-conflict

The engine SHALL treat a reverse edge as feedback and SHALL report no finding unless the two claims have opposed causal polarity over the same normalized subject and object.

Source: inferred by agent, 2026-11-17: restates AGENTS.md "A reverse edge is feedback, not automatically a contradiction" (Brian, 2026-11-17: "option B is what i want").

#### Scenario: Reverse edge is feedback

- **WHEN** a proposal's second claim reverses the subject and object of the first
- **THEN** no finding is selected

### Requirement: digest-bound-revision

The engine SHALL refuse to apply a revision plan whose finding digest does not match the finding.

Source: inferred by agent, 2026-11-17: restates AGENTS.md "Feedback counts only after it is transformed into a digest-bound revision plan and that exact plan is applied" (Brian, 2026-11-17: "option B is what i want").

#### Scenario: Wrong finding digest is refused

- **WHEN** a plan carries a finding digest that differs from the finding being applied
- **THEN** applying it raises an error naming a finding digest mismatch
