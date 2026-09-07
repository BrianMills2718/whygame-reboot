# Plan #3: let the deterministic evaluator find a real conflict, not a planted one

**Status:** In progress — code change and unit tests done; live diagnostic run
blocked on account usage limit, retry after 2026-09-08 08:03 (America time zone
of the ChatGPT account, per the error message)
**Type:** diagnostic slice for AES, not a WhyGame product commitment
**Priority:** Medium
**Blocked By:** ChatGPT/Codex account usage limit (`ThreadRunError: You've hit
your usage limit... try again at Sep 8th, 2026 8:03 AM`)
**Created:** 2026-09-07

## Why this exists

Chosen deliberately as the next AES diagnostic case rather than reusing an
already-queued candidate (Agent Ecology 3 / Plan 23): Plan 1 and Plan 2 both
ran a rigid two-call pipeline where the proposal prompt explicitly instructed
the model to plant a `causes`/`prevents` contradiction on purpose
(`inspection.md` for Plan 2: "the conflict is solicited, not discovered").
That left no room for an agent to drift, and no room for a rule to have to
catch anything. This is the first task in this repository with a genuine
design decision in it, small enough to bound, and real (not invented for the
test) -- it is the natural next problem this repository's own evidence
already named.

## What changed

`src/whygame_reboot/runner.py::PROPOSAL_PROMPT` no longer instructs the model
to manufacture a competing pair. It now asks the model to name a competing
pair only if it believes two of its own claims may genuinely disagree, and
states plainly that the model's own labelling is not authoritative.

**Nothing about the evaluator changed**, and this matters for `CLAUDE.md`'s
non-goal ("do not claim ... independent criticism ... a deliberately bounded
conflict"): `select_finding()` was already fully independent of the model's
self-reported `competing_pair` -- it is a deterministic scan over the
committed claims for matching normalized subject/object with opposed
`causes`/`prevents` relations, unchanged by this plan. This slice removes an
artificial guarantee that the scan will always find something; it does not
add general contradiction detection or independent reasoning. The bounded
conflict check itself is exactly as bounded as before.

## What this run is meant to show

Whether, once the model is not told to plant a contradiction, the same
existing deterministic check finds a real one among the organically proposed
claims, or the run legitimately reports `blocked: "proposal contains no
deterministic direct causal conflict"` (an existing, already-handled code
path in `run_loop`). Either outcome is a real result; neither is a defect
in this slice.

## Status

- [x] `PROPOSAL_PROMPT` edited; `select_finding` unchanged (verified by
      reading `engine.py::select_finding`, which never reads
      `model_competing_pair`).
- [x] Unit suite: 24 passed (`.venv/bin/python -m pytest -q`, run from the
      canonical checkout's venv; a fresh `uv run` in this worktree fails on
      an unrelated stale git dependency pin, `agentic-engineering-system` at
      an old AES commit no longer served as an anonymous fetch -- not this
      slice's concern).
- [ ] Live run on `examples/recurring-lessons/question.yaml`: attempted
      2026-09-07, recorded a genuine `error` status --
      `evidence/runs/plan3-organic/recurring-lessons/run.json` --
      `ThreadRunError: You've hit your usage limit`. Not a code defect; the
      account (`--codex-home /home/brian`, the only profile on this machine --
      Plan 2's dedicated profile has a revoked token and was already proven to
      share the same account digest) is rate-limited until the stated reset
      time. Retry after that.
- [ ] Live run on `examples/aes-mission-drift/question.yaml`: not attempted,
      to avoid spending a second call against the same exhausted limit for no
      new information.

## Non-goals

Does not build a general conflict-discovery mechanism, retrieval step, or new
evaluator. Does not commit to a WhyGame product direction. Does not retry
against a different model or provider to route around the usage limit --
Plan 1's contract ("no retry, silent fallback, third critic, or random
strategy") still governs this pipeline.
