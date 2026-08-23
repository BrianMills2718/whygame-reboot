# Graph-Adversary Product Contract

Status: adopted for the first vertical.  
Portfolio authority: Project Meta Plan 246, design revision
`plan-246-whygame-graph-adversary-rewrite-design@1`.

## User-visible outcome

Given a bounded question and source observations, WhyGame produces a causal
proposal, commits it as typed claims, selects a direct conflict using a
deterministic evaluator, asks a model to revise the proposal in response, and
persists an append-only revision history. A static report must let a reader see
what was proposed, what challenged it, what changed, and which claims remain
active without reading logs or source code.

The stable first question is:

> Why can an agentic engineering system designed to prevent drift drift away
> from its own mission?

The source observations come from AES decision 0003 and are copied into the run
input with source revision and digest.

## Durable contracts

- A question packet contains the question, bounded observations, and provenance.
- A proposal contains model-local typed causal claims and a competing pair.
- The system validates the proposal and assigns stable claim IDs and digests.
- A finding identifies two committed claims with the same normalized endpoints
  and opposed causal polarity. Reversing endpoints alone is not a conflict.
- A revision plan cites the finding and exact input digests and declares an
  append-only decision for each affected claim.
- A revision event records application of the validated plan. Active state is a
  replayed projection of the immutable proposal and revision events.
- Call receipts retain shared-client run and trace provenance without embedding
  secrets.
- A loop-run manifest records stage states and artifact digests, enabling loud
  failure and safe resume from completed immutable checkpoints.

## First-vertical execution

The vertical makes exactly two serial calls through the pinned shared
`llm_client`, both using Luna at medium reasoning effort:

1. produce the bounded causal proposal and an explicit competing pair;
2. revise that committed proposal in response to the selected finding.

There are zero automatic retries and no fallback model or random strategy. A
failed call or invalid contract stops the run with its prior receipts intact.
The deterministic evaluator validates and selects a bounded conflict; it is not
claimed to discover novel truth.

## Acceptance

The product artifact is accepted before policy admission when all of these are
true:

- both authentic calls have durable outer-run trace references;
- all committed and revised records validate against strict typed contracts;
- the selected finding is reproducible from the committed proposal;
- the revision plan is bound to the exact proposal and finding digests;
- replay produces the same active graph and artifact digest;
- the static report visibly explains proposal, challenge, change, and outcome;
- focused tests cover rejection of reverse-edge, mismatched-digest, invalid
  local-ID, and partial-application cases.

AES then evaluates the immutable accepted baseline. Its separate admission
receipt must demonstrate a meaningful BLOCK followed by ALLOW after an explicit
in-scope repair; neither result mutates the judged product artifact.

## Explicit nonclaims

This vertical does not establish a world model, truth discovery, independent
criticism, unique symbolic knowledge, general contradiction detection, a live
collaborative UI, or replacement of legacy WhyGame. Those claims require later
evidence and their own authority.
