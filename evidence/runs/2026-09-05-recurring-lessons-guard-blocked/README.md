# Codex history-guard blocked attempt

- Producer revision: `d707597e3b2e89ff485ef6e2c1fd6e105efbeaa9`
- Command: `uv run whygame-reboot examples/recurring-lessons/question.yaml --output evidence/runs/2026-09-05-recurring-lessons-live --run-id whygame-reboot/2026-09-05-recurring-lessons --codex-home <dedicated-profile-root>`
- Requested route: `codex/gpt-5.6-luna`, medium reasoning
- Result: terminal `error` before proposal, checkpoint, token usage, call
  receipt, or cost. The Codex subprocess exited 127 before any model request.
- Local message: `Codex history guard: real Codex executable missing:
  <profile>/.codex/packages/standalone/current/bin/codex`
- Automatic retries: zero
- Fallback: none
- `run.json` SHA-256: `fea7605ad5711e9770c6c270d35199b19223e21744ef11cc45a29dbaa450e902`
- `report.html` SHA-256: `ff2724e6b0abb32df72e561ef8f2f62a3c694f72fa07cc8f71cafd4171e8b337`

This is environment failure evidence, not a model, route, or profile
rejection. The `ecosystem-ops` Codex history guard installed on this machine
on 2026-09-01 (after Plan 1's 2026-08-23 run) resolves the real Codex binary
under `$CODEX_HOME/packages/...`. The shared client sets `CODEX_HOME` to the
caller-owned profile, which holds credentials and state but no package tree,
so every non-default profile failed the same way.

Recovery: a symlink from the profile's `.codex/packages` to the default
`~/.codex/packages` install. No credential was copied, printed, or moved; the
guard remains in place; the profile binding is unchanged. The live run was
then started fresh in `../2026-09-05-recurring-lessons-live/` because no
digest-valid checkpoint existed to resume from.
