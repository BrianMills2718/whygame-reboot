# Direct inspection: recurring-lessons live run

Written by the implementing agent (Claude Code, session
`b5635c8d-aa81-418b-aaa9-3c17a0c4774a`) on 2026-09-05 after opening
`report.html` in this directory and reading it top to bottom as a user would,
then reading Plan 1's accepted report at
`../2026-08-23-account-bound-live/report.html` the same way.

## What the report shows

The page leads with the question, the revised bounded answer, and the word
`accepted`. Then: the five loop stages all marked complete; run identity with
source, input, and config digests; section 1, the committed proposal with four
claim cards, one marked superseded; section 2, the selected challenge naming
the two conflicting claim IDs; section 3, the applied revision with one
retain and one supersede decision and their rationales; section 4, the active
explanation with four cards including the replacement; the six source
observations with their source references and revision; three unresolved
uncertainties; the two execution receipts; and the closing non-claim that the
result does not certify truth, a world model, independent criticism, or
general contradiction detection.

## The four answers

**What was proposed.** Four typed claims and a bounded answer sentence.

1. `claim-92950a7635448632`: recorded lessons without deterministic promotion
   into binding checks *causes* recurrence without binding. Provisional.
   Cites `delivered-then-violated`, `repeats-recorded-not-bound`.
2. `claim-fd2fc2045281fe2b`: the same subject *prevents* the same object.
   Provisional. The model's own text calls it "a deliberate counterfactual
   stress-test proposal, not an observed conclusion". Cites
   `delivered-then-violated`, `promotion-machinery-unfed`.
3. `claim-3c3d4dd427c13db5`: recurrence of a lesson *constrains* the
   assumption that the lesson is readily automatable. Asserted. Cites
   `recurrence-is-not-mechanisability`.
4. `claim-85075dbf05f3e283`: a feedback mechanism that only collects and
   delivers lessons *contributes to* recurrence without binding. Provisional.
   Cites `installer-defect-recurred`, `meta-level-must-be-same-mechanism`.

The proposal's answer: lessons recur because collection and recall do not
transform them into binding checks while the promotion machinery stays unfed.

**What challenged it.** The deterministic evaluator selected one
`direct_causal_conflict`: claims 1 and 2 share the same normalized subject and
object and assert `causes` versus `prevents`. Nothing else was challenged.
Claims 3 and 4 were never tested by anything.

**What changed.** The revision retained claim 1 and superseded claim 2 with
`claim-875edddf1dd2a5fc`: deterministic promotion of recorded lessons into
binding checks *contributes to* interrupting recurrence without binding,
provisional, now citing three observations (`repeats-recorded-not-bound` was
added). The revised answer hedges the mechanism ("may contribute to
interrupting recurrence") and a third unresolved question was added: whether
deterministic promotion would actually interrupt recurrence is unverified.
The active graph after replay has four claims and one superseded ID.

**Was the change specific to this question?** No, at the level that matters.
See the verdict below.

## Comparison with Plan 1's accepted report

| | Plan 1 (`2026-08-23-account-bound-live`) | Plan 2 (this run) |
| --- | --- | --- |
| Question | Why an anti-drift system drifts from its mission | Why recorded lessons recur without binding |
| Observations | 4, from one AES decision record | 6, from two AES documents, one phrased as a constraint |
| Claims proposed | 3 | 4 |
| Planted pair | claim-52b3 `causes` vs claim-1420 `prevents`, same endpoints | claim-9295 `causes` vs claim-fd2f `prevents`, same endpoints |
| Challenge | `direct_causal_conflict` on the planted pair | `direct_causal_conflict` on the planted pair |
| Revision | retain `causes`; supersede `prevents` with `contributes_to`, provisional | retain `causes`; supersede `prevents` with `contributes_to`, provisional |
| Replacement endpoints | identical subject and object to the superseded claim | subject and object both reworded |
| Uncertainties | 2 carried through | 2 carried through, 1 added |
| Untouched claims | 1, never challenged | 2, never challenged |
| Engine change needed | none | none |
| Tokens (proposal / revision) | 17,344 / 18,746 | 25,678 / 25,938 |

## Verdict: same shape with the nouns swapped

The challenge and the revision action in this run are the same shape as Plan
1's. This is a finding about the loop, recorded as the plan requires, not a
defect in the run.

It rests on four facts:

1. The proposal prompt in `src/whygame_reboot/runner.py` instructs the model to
   include "a deliberate direct competing pair over the exact same subject and
   object: one relation must be causes and the other prevents". The conflict
   is solicited, not discovered.
2. The evaluator (`select_finding`) recognizes only that pattern, by design
   and by the normative topic.
3. The revision prompt instructs the model to resolve the pair by replacing
   with `contributes_to` or `constrains`. The direction of the revision is
   prescribed.
4. Both runs did exactly that: retain `causes`, supersede `prevents`, replace
   with `contributes_to` at provisional confidence, and hedge the answer.

What was specific to this question is the content: the claim wording, the
rationales, the observation citations, the reworded endpoints of the
replacement claim, and the added third uncertainty. Those are the nouns. The
verbs were fixed before the question arrived.

Two smaller observations about generalisation:

- The packet with six observations, including the constraint-phrased
  `meta-level-must-be-same-mechanism`, was accepted with no engine, contract,
  evaluator, renderer, or CLI change. The constraint observation was absorbed
  as supporting evidence for a `contributes_to` claim rather than surfacing as
  a `constrains` claim; the one `constrains` claim came from the
  mechanisability observation instead.
- The graph never challenged the claims the model did not plant a pair for.
  For a question with more claims, the share of the explanation that the
  adversary actually touches shrinks.

Whether the revision "changed the explanation" in the sense Brian cares about
is his judgement from `report.html`. The answer text did move: from a
causes-versus-prevents pair to a single hedged mechanism claim with an explicit
new uncertainty. The move was the one the loop always makes.

## Accepted-artifact conditions, verified after the run

Replayed from the retained `run.json` through the installed engine on
2026-09-05, all true:

- strict `LoopRun` contract validates, status `accepted`
- `select_finding(proposal)` reproduces the retained finding and digest
- revision plan binds `proposal_sha256` and `finding_sha256` exactly
- revision event binds `plan_sha256` and `finding_sha256` exactly
- `replay(proposal, events)` reproduces the active projection and its digest
- re-rendering the run reproduces `report_sha256` and the on-disk `report.html`
- checkpoint manifest canonical-JSON digests match `proposal.json`,
  `finding.json`, `proposal-receipt.json`
- packet file unchanged against Git HEAD
- two receipts, both rooted under the outer run trace, `/proposal` then
  `/revision`, zero retries, no fallback, settled cost USD 0.00
- no stage failed; `resumed_stages` is empty; no duplicate first-stage dispatch

## Environment findings on the way to the run

Neither reached a model request or a cost; both are retained beside this
directory.

1. `../2026-09-05-recurring-lessons-guard-blocked/`: the ecosystem-ops Codex
   history guard (installed 2026-09-01, after Plan 1) resolves the real binary
   under `$CODEX_HOME/packages/...`, which a caller-owned profile does not
   have. Fixed with a symlink from the profile's `.codex/packages` to the
   default install. No credential touched.
2. `../2026-09-05-recurring-lessons-auth-revoked/`: the dedicated profile's
   refresh token had been revoked. Before any fallback, the shared client's
   own identity function proved the dedicated profile and the default profile
   carry the same account digest Plan 1 retained. The run then used the
   default profile root explicitly, as Plan 2's fallback clause allows when
   recorded. The "inferred, not proven" note in Plan 2 is now proven.
