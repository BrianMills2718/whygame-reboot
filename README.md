# WhyGame Reboot

WhyGame Reboot is a clean rewrite of WhyGame's reasoning loop around one
testable product idea: a graph is useful when it acts as an adversary that
forces a proposed causal explanation to be revised, not when it merely stores
and expands claims.

Start at the [project roadmap](roadmap/README.md). The first vertical is not yet
implemented; this repository currently establishes canonical custody and the
contracts that will govern that work.

## Development

```bash
uv sync
uv run python -m pytest -q
uv run ruff check .
```

The legacy `whygame4` repository is a read-only salvage source. It remains the
incumbent until the first replacement vertical is accepted.
