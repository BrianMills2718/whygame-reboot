# WhyGame Reboot Instructions

This is the canonical instruction surface for the Brian-owned private
`BrianMills2718/whygame-reboot` repository.

## Outcome and authority

Build a clean rewrite of WhyGame in which a typed graph challenges a proposed
causal explanation and produces an inspectable, append-only revision. The
adopted product design is `docs/plans/1_graph-adversary-vertical.md`; the normative
contract is `docs/topics/graph-adversary.md`.

The first stable example asks why a system intended to prevent engineering
drift can drift away from its own mission. Preserve that example until the
first vertical is authentically observed.

Project Meta Plan 246 owned portfolio selection and promotion. Project Meta has
accepted the replacement evidence, and `PROJECT_GRAPH.json` now records this
repository as the active canonical WhyGame generation that supersedes
`whygame4`. The legacy repository remains read-only salvage with its own Git
history; do not merge, rewrite, or delete it as cleanup. Supersession establishes
current product direction, not feature parity with every legacy capability or a
broader truth-discovery claim.

## Documentation lineage

- `roadmap/README.md` is the human and agent entry point.
- `docs/topics/` is normative product and architecture authority.
- `docs/plans/` contains adopted execution designs and current work ownership.
- `policy/current-claims.json` is the machine-readable present-tense claim set.
- `evidence/` stores immutable receipts; evidence does not define policy.
- Generated views are derived and must identify their source. They are never
  independent authority.
- `scripts/relationships.yaml` declares documentation coupling and regeneration
  expectations. Update the owning source before any derived surface.

## Work isolation

Before editing, inspect `git status --short` and the shared Enforced Planning
claim registry. Product implementation occurs in a claimed linked worktree at
`<repo>/worktrees/<branch>/`. Until this repository earns a local entry point,
use the canonical Enforced Planning operator route named by workspace policy;
do not copy the planning substrate into this repository merely to create a
claim. Bootstrap custody changes are the only exception.

Keep claims and mailbox dispositions truthful. Close a lane only after its
commit is on canonical `main` or a durable recovery ref exists, then release the
claim and remove the worktree through the sanctioned close procedure.

## Implementation constraints

- Use strict Pydantic contracts for model proposals, claims, findings, revision
  plans, revision events, call receipts, and run state.
- Model-local identifiers are untrusted. The system assigns durable IDs and
  content digests.
- A reverse edge is feedback, not automatically a contradiction. The first
  evaluator recognizes only explicit opposed causal polarity over the same
  normalized subject and object.
- Revision is append-only. Compute the active graph by replaying events; never
  overwrite the history that explains why a claim changed.
- Feedback counts only after it is transformed into a digest-bound revision
  plan and that exact plan is applied.
- The first vertical uses exactly two serial Luna-medium calls: proposal, then
  revision. No retry, silent fallback, third critic, or random strategy.
- Product acceptance precedes AES admission. Store the AES result as a separate
  receipt so a policy decision cannot circularly alter the artifact it judges.
- The first report is deterministic static HTML plus immutable JSON. The report
  has since proved useful, so `src/whygame_reboot/web.py` adds one public-hosting
  front door (default-deny, `WHYGAME_PUBLIC=1`, OpenRouter Luna route, per-visitor
  sessions and spend caps) served at why.brianmills.dev. Still no SSE or
  generalized graph infrastructure; the CLI and Codex route are unchanged.
- Do not claim a world model, truth discovery, independent criticism, or unique
  symbolic reasoning. The evaluator checks a deliberately bounded conflict.

Maintained LLM calls use the pinned shared `llm_client` contract and must retain
outer-run observability. Inspect traces before attributing failure to a model.
No mock-only result completes the first vertical.

## Verification

The canonical development checks are:

```bash
uv run python -m pytest -q
uv run ruff check .
```

Use the cheapest focused check that can invalidate changed behavior. Before
promotion, prove one fully traced live run and inspect the generated report from
the same entry point a user will use.
