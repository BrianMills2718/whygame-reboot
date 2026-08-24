# WhyGame Reboot Roadmap

This page is the canonical entry point. It routes to authority; it does not
replace it.

## Product outcome

Turn a graph from passive storage into an adversary inside a visible reasoning
loop:

`propose -> commit -> stress-test -> revise -> persist`

The first vertical must show one causal proposal, one deterministic conflict,
one model-authored revision plan, one applied append-only revision, and the
resulting active graph in both immutable JSON and a readable static report.

## Current state

The first product vertical is observed: the exact two-call Luna run produced a
digest-bound append-only revision and a directly inspected static report, and
installed AES discriminated `BLOCK` from `ALLOW` against that immutable result.
Replacement of the legacy WhyGame remains unobserved and belongs to Project
Meta. See [current claims](../policy/current-claims.json) for the
machine-readable statement.

## Authority map

- [Normative graph-adversary contract](../docs/topics/graph-adversary.md)
- [Adopted first-vertical plan](../docs/plans/1_graph-adversary-vertical.md)
- [Machine-consumed local work graph](../docs/plans/1_graph-adversary-vertical_work_graph.json)
- [Current claims](../policy/current-claims.json)
- [Evidence policy](../evidence/README.md)
- [Documentation relationships](../scripts/relationships.yaml)

## Gate sequence

1. Establish canonical private-repository custody and fresh-install proof.
2. Execute the two-call graph-adversary vertical in a claimed worktree.
3. Accept the product artifact on its own contract.
4. Evaluate its immutable baseline through installed AES and retain a separate
   BLOCK-to-ALLOW admission receipt.
5. Let Project Meta adjudicate AES Gate 2 and legacy replacement claim by claim.
