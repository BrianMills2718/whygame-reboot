# Lockstep is pinned through uvx (not pyproject): see docs/decisions/0001. `lockstep check` runs below.
.PHONY: fast check full docs-specs
LOCKSTEP = uvx --from "git+https://github.com/BrianMills2718/agentic-engineering-system-canonical@05ee80c1a9cc77f692954b6de09a81ab0d9bdb0a" lockstep
unexport GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_COMMON_DIR GIT_OBJECT_DIRECTORY
docs-specs:
	@mkdir -p docs/specs/revision-replay
	@ln -sfn ../../../openspec/specs/revision-replay/spec.md docs/specs/revision-replay/spec.md
fast:
	$(LOCKSTEP) check trace
	$(LOCKSTEP) check sources
	$(LOCKSTEP) check project --check
	openspec validate --all --strict --no-interactive
check: docs-specs fast
	uv run pytest tests/test_engine.py
	PYTHONPATH=src $(LOCKSTEP) check arch check
full: check
	uv run python -m pytest -q
	uv run ruff check .
