# Plan #2: A second question through the graph adversary

**Status:** Delivered — run observed 2026-09-05; Brian's judgement from the
report is still pending
**Status ID:** delivered
**Type:** standard product vertical
**Priority:** High
**Blocked By:** Nothing. Delivered; only Brian's judgement remains.
**Created:** 2026-09-05
**Updated:** 2026-09-05 (delivered)
`trace_evaluable: true`

## Authority and handoff

Plan 1 delivered the first vertical on one fixed question and is complete.
This plan is the next product goal, chosen by Brian on 2026-09-05 when he named
WhyGame Reboot as the first consumer project for the Agentic Engineering
System's Plan #8 (`agentic-engineering-system/docs/plans/08_one-consumer-run-one-lesson-that-binds.md`).
That AES plan observes this run from the outside and owns the run record and
the AES-side consequences. This plan owns the product work and nothing about
AES.

Brian plans; a different agent implements. The implementing agent starts from
`roadmap/README.md`, reaches this plan through `docs/plans/CLAUDE.md`, and needs
nothing from the planning conversation. The machine-consumed local unit is
[`WGR-WU02`](2_second-question-recurring-lessons_work_graph.json).

## Outcome and boundary

Run a second, different question end to end through the existing
propose → commit → stress-test → revise → persist loop, using the same two-call
contract, and let Brian judge from the static report alone whether the graph
changed the explanation. The question and its source observations are the
packet at [`examples/recurring-lessons/question.yaml`](../../examples/recurring-lessons/question.yaml):

> Why do recorded lessons in an agentic engineering system recur without ever
> binding?

Six observations, all from `agentic-engineering-system` at revision
`e7ca726df3cacf31b8671f96672e52200031bf66`, each carrying its source reference
and revision as the packet contract requires.

The question is not arbitrary. It is the problem AES Plan #8 exists to act on,
so a useful revision here is also input to that plan's slice 2. That is a
convenience, not a claim: this plan does not assert anything about AES.

Boundary, unchanged from Plan 1 and the normative topic: no world model, no
truth discovery, no independent critic, no general contradiction detection, no
third call, no retry, no fallback, no server, no legacy replacement claim.

## What is new, and what is not

The engine, contracts, evaluator, renderer, CLI, and tests are Plan 1's and are
not expected to change. A second question is the first test of whether the
loop generalises past the example it was built on. Three things are new:

1. **A second packet.** Different subject matter, six observations instead of
   four, and one observation (`meta-level-must-be-same-mechanism`) phrased as a
   constraint rather than an event, which the proposal stage has not seen before.
2. **A comparison.** The report for this run is read beside Plan 1's accepted
   report. The question Brian answers is whether the challenge and revision were
   specific to this question or were the same shape as before with the nouns
   swapped. The second outcome is a real finding about the loop and is recorded,
   not hidden.
3. **An outside observer.** The run is executed under a claimed lane while AES
   Plan #8 records which governance mechanisms touched it. The implementing
   agent does nothing extra for this except work through the sanctioned lane
   route and record lessons through the ordinary register.

If the engine does need to change to accept the packet, that is a finding
about generalisation and belongs in the report and the closeout, with the exact
change and why; it does not license widening the contract.

## Canonical journey

1. From a claimed lane (created from the workspace root with
   `enforced-planning/scripts/claim_bootstrap.py`, as `CLAUDE.md` requires;
   AES Plan #8's handoff quotes the exact request), validate the packet
   without spend:
   `uv run whygame-reboot examples/recurring-lessons/question.yaml --output artifacts/recurring-lessons-dry-run --dry-run`.
   A contract rejection here ends the slice `LEARNED` with the exact error.
2. Run the adopted two-call Luna-medium journey bound to the caller-owned
   Codex profile. `README.md` shows the shape with a placeholder; the concrete
   command on this machine is:
   `uv run whygame-reboot examples/recurring-lessons/question.yaml --output evidence/runs/<YYYY-MM-DD>-recurring-lessons-live --run-id whygame-reboot/<YYYY-MM-DD>-recurring-lessons --codex-home /home/brian/.codex-profiles/dfc316ae7b16c90f`.
   The `--codex-home` value is a profile root containing `.codex/auth.json`
   (a path, not a credential; never copy or print the file it points at). It
   is the only dedicated profile on this machine and is inferred, not proven,
   to be the one Plan 1 used, because Plan 1's evidence deliberately retains
   no path. If the CLI rejects it, stop and report; do not fall back to the
   default `~/.codex` profile without recording that you did.
3. Confirm the accepted-artifact conditions from the normative topic: two
   rooted child traces, strict contracts validate, the finding reproduces from
   the committed proposal, the revision plan binds to the exact digests, replay
   reproduces the active graph and artifact digest.
4. Retain `run.json`, `report.html`, and the call receipts immutably under
   `evidence/runs/<date>-recurring-lessons-live/`, with a direct-inspection
   record written by the implementing agent after opening `report.html` and
   reading it as a user would.
5. Write the comparison: one short section in the inspection record answering,
   for this run and Plan 1's, what was proposed, what challenged it, what
   changed, and whether the change was specific to the question.
6. Update `policy/current-claims.json` with one new claim,
   `second-question-observed`, `observed` or `unobserved`, with the evidence
   path or the reason.

Installed AES admission of this baseline is not required by this plan. AES
Plan #8 decides separately whether to evaluate it.

## Failure and cost contract

Two serial Luna-medium calls, no retries, no fallback, ceiling USD 0.25 per
stage and USD 0.50 for the run, the same contract Plan 1 carried. A different
model or higher spend requires Brian. The dry run costs nothing and comes
first. A failed stage stops visibly and retains every earlier digest-valid
checkpoint; a changed or corrupted checkpoint requires a new run.

**Spend authority:** Brian approved this plan, its packet, and the two live
calls at the USD 0.50 ceiling on 2026-09-05 in the planning conversation that
produced it. The implementing agent may run the live journey after the dry run
passes; no further approval is needed unless the ceiling or model changes.

## Non-goals

Everything in Plan 1's non-goals, plus: no packet schema change to accommodate
this question, no second revision round, no batch of further questions, no
generic question-authoring tool. If the second question exposes a limitation,
record it; do not build around it inside this plan.

## Trace evaluation

Unchanged from Plan 1: two rooted shared-client child traces with requested and
resolved model, effort, tokens, latency, attempts, fallback state, billing mode,
and settled cost, bound in `run.json` and the report to the exact input,
source, proposal, finding, revision-plan, and replay digests.

## Acceptance

The plan is `DELIVERED` when all of these are observed, not asserted:

- the dry run accepts the packet unchanged, or the exact rejection is recorded
  and the slice ends `LEARNED`;
- both live calls complete under the cost contract with rooted receipts;
- the accepted-artifact conditions above hold and are recorded;
- `report.html` was opened and read by the implementing agent, and the
  inspection record says in plain words what changed and whether it was
  specific to the question;
- the comparison with Plan 1's report is written;
- `policy/current-claims.json` carries `second-question-observed` with evidence;
- `uv run python -m pytest -q` and `uv run ruff check .` pass in the lane.

A green suite with no live run is not acceptance. A live run whose report was
never read by a person or agent is not acceptance either.

## Completion and handoff

On completion the implementing agent records the evidence path and the terminal
state here, updates `docs/plans/CLAUDE.md` and `roadmap/README.md` through the
declared couplings, and closes the lane through the sanctioned route. The
judgement of whether the graph changed the explanation is Brian's, made from
`report.html`; the plan records his answer when he gives it.

## Completion record

**Terminal state:** `DELIVERED`, 2026-09-05, by the implementing agent
(Claude Code) in lane `plan-2-run`.

**Evidence:** `evidence/runs/2026-09-05-recurring-lessons-live/` holds
`run.json` (SHA-256 `4a1b1fcc…dded280f`), `report.html` (SHA-256
`1929bafa…0d27d7b1`), the checkpoint files and both call receipts,
`lifecycle-account-binding.json`, and `inspection.md`, which carries the four
answers, the Plan 1 comparison, and the replay verification.

**Acceptance, observed:** the dry run accepted the packet unchanged; both live
calls completed at USD 0.00 settled cost with rooted receipts, zero retries, no
fallback; every accepted-artifact condition reproduced from the retained run;
the report was opened and read; the comparison is written;
`policy/current-claims.json` carries `second-question-observed` as `observed`;
`uv run python -m pytest -q` (23 passed) and `uv run ruff check .` pass in the
lane. No engine, contract, evaluator, renderer, or CLI change was needed.

**Comparison verdict:** same shape with the nouns swapped. The proposal prompt
solicits the causes-versus-prevents pair, the evaluator recognizes only that
pair, and the revision prompt prescribes the `contributes_to` or `constrains`
replacement; both runs did exactly that. What differed was content: claim
wording, citations, reworded endpoints on the replacement claim, and one added
uncertainty. This is recorded, not softened, in `inspection.md`.

**Deviations, recorded:** two attempts failed before any model request and are
retained as `…-guard-blocked/` and `…-auth-revoked/`. The first was a local
Codex history guard that cannot find the binary under a caller-owned profile,
fixed with a symlink. The second was the dedicated profile's revoked refresh
token; the run then used the default profile root as an explicit
`--codex-home`, the recorded fallback this plan permits, after the shared
client's identity function proved both profiles carry the account digest Plan
1 retained. The "inferred, not proven" profile note above is now proven.

**Brian's judgement:** pending. When given, record it here.
