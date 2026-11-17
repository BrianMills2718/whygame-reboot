# WhyGame Reboot architecture

The architecture authority is the normative contract [docs/topics/graph-adversary.md](../topics/graph-adversary.md) and the adopted design [docs/plans/1_graph-adversary-vertical.md](../plans/1_graph-adversary-vertical.md). This page adds only the code2-format scope.

Scope: the deterministic engine, `whygame_reboot.engine` (commit, stress-test, revise, replay). [The import model](model.c4) covers the engine and its contracts module only. The runner, CLI, report renderer, LLM calls and AES admission remain described by the topic contract and plans and are not covered by the Lockstep or import checks.

The engine imports only `whygame_reboot.contracts`; the native import contract enforces that direction. Its requirements are in [the revision-replay spec](../../openspec/specs/revision-replay/spec.md).
