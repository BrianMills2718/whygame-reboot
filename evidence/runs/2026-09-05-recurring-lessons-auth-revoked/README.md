# Dedicated-profile token-revoked attempt

- Producer revision: `d707597e3b2e89ff485ef6e2c1fd6e105efbeaa9`
- Command: `uv run whygame-reboot examples/recurring-lessons/question.yaml --output evidence/runs/2026-09-05-recurring-lessons-live --run-id whygame-reboot/2026-09-05-recurring-lessons --codex-home <dedicated-profile-root>`
- Requested route: `codex/gpt-5.6-luna`, medium reasoning
- Result: terminal `error` before proposal, checkpoint, token usage, call
  receipt, or cost. Codex reached the auth refresh step and stopped.
- Provider message: access token could not be refreshed because the refresh
  token was revoked; log out and sign in again.
- Automatic retries: zero
- Fallback: none inside the run
- `run.json` SHA-256: `c338bdfb620c3f55e3f56e8aac9c9e9031312985871534089c0a957f697ba2b5`
- `report.html` SHA-256: `382df769e06daa2114a49e503db53da8b4ef47bfde336da74b1fcc13d9d79720`

This is the CLI rejecting the dedicated profile, the case Plan 2 names.

Two facts established before any recovery, both computed with the shared
client's own `resolve_codex_account_identity` so no raw account ID or token
was read into the transcript:

1. The dedicated profile's account digest equals the digest Plan 1 retained in
   `../2026-08-23-account-bound-live/lifecycle-account-binding.json`
   (`sha256:dfc316ae7b16c90f...`). Plan 2 called this profile "inferred, not
   proven" to be Plan 1's; it is now proven. The profile directory name is
   the first sixteen hex characters of that digest.
2. The default `~/.codex` profile's account digest equals the same value. It
   is the same ChatGPT account, and `codex login status` reports it logged in.

Recorded fallback, as Plan 2 requires: the live run was started fresh in
`../2026-09-05-recurring-lessons-live/` with `--codex-home /home/brian`, an
explicit binding to the default profile root. The account digest bound to
that run is identical to Plan 1's, so the account-binding property of the
accepted first vertical is preserved; only the profile directory differs.
No credential was copied, printed, or moved.
