# WhyGame Reboot

WhyGame Reboot is a clean rewrite of WhyGame's reasoning loop around one
testable product idea: a graph is useful when it acts as an adversary that
forces a proposed causal explanation to be revised, not when it merely stores
and expands claims.

Start at the [project roadmap](roadmap/README.md). The first vertical is under
active proof: its provider-free contracts and recovery checks pass, while the
authentic two-call run and separate AES admission remain acceptance gates.

## Development

```bash
uv sync
uv run python -m pytest -q
uv run ruff check .
```

Run the stable example without spending or dispatching a model call:

```bash
uv run whygame-reboot examples/aes-mission-drift/question.yaml \
  --output artifacts/aes-mission-drift-dry-run --dry-run
```

Omit `--dry-run` only for the adopted two-call Luna-medium journey. The command
writes `run.json` and `report.html`; a failed second stage retains the committed
proposal and finding and can resume only when their digests still match.

The legacy `whygame4` repository is a read-only salvage source. It remains the
incumbent until the first replacement vertical is accepted.
