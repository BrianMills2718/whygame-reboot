---
description: Scope of the code2 format in whygame-reboot and how make check is composed
---

# 0001 Code2 format scoped to the revision engine

Date: 2026-11-17
Status: accepted
Source: inferred by agent, 2026-11-17 (Brian, 2026-11-17: "option B is what i want").

## Context

The repository had no Makefile, no OpenSpec, and its checks were `uv run python -m pytest -q` and `uv run ruff check .` (AGENTS.md "Verification"). Active vision parts adopt the code2 format now.

## Decision

- Scope Lockstep and OpenSpec to one capability that already works, `revision-replay` in `src/whygame_reboot/engine.py`, backed by three existing tests in `tests/test_engine.py` (marked `existing=True`).
- `make check` runs Lockstep, OpenSpec validation, the import contract, and the engine tests. `make full` runs the whole pytest suite and ruff, the previous canonical checks, unchanged.
- Lockstep is pinned through `uvx` in the Makefile (canonical AES rev 05ee80c), not in pyproject: `tests/test_bootstrap.py` asserts the existing direct-URL AES pin (rev 089bc6a), and existing tests are not weakened. `import-linter` is added to the dev group; the arch check runs with `PYTHONPATH=src`. The `req` pytest marker is unregistered (warning only).

## Consequences

Only the engine is covered by Lockstep; other modules are not claimed. Existing `hooks/pre-commit` and `agentic.yaml` are untouched.

## Wrong if

Someone moves the AES pin in pyproject and updates the bootstrap test, making the uvx pin redundant; or an agent treats Lockstep coverage as covering the runner or CLI.
