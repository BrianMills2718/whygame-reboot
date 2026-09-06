# Recurring-lessons live run (Plan 2, second question)

- Producer revision: `d707597e3b2e89ff485ef6e2c1fd6e105efbeaa9`
- Command: `uv run whygame-reboot examples/recurring-lessons/question.yaml --output evidence/runs/2026-09-05-recurring-lessons-live --run-id whygame-reboot/2026-09-05-recurring-lessons --codex-home <default-profile-root>`
- Packet: `examples/recurring-lessons/question.yaml`, unchanged from Git HEAD;
  input SHA-256 `333dc81c653282dc7098615b06daeae8f1204ddea4bfb8069e6135c68ff8fb0c`
- Requested and resolved route: `codex/gpt-5.6-luna`, medium reasoning
- Result: `accepted` after exactly two completed model calls
- Automatic retries: zero
- Fallback inside the run: none
- Billing: subscription included; settled marginal cost USD 0.00
- `run.json` SHA-256: `4a1b1fccf86bd579c5551e0ea2cb8bf3032923f2bee9cbcd1f933263dded280f`
- `report.html` SHA-256: `1929bafa8361a868f017c9433bc41c4553beab771e03a5a990bae0700d27d7b1`

Accepted-artifact conditions, each verified by replaying the retained
`run.json` through the engine after the run (recorded in `inspection.md`):
strict contracts validate; the finding reproduces from the committed proposal;
the revision plan and event bind the exact proposal, finding, and plan digests;
replay reproduces the active projection digest; re-rendering reproduces the
`report.html` bytes; the checkpoint manifest digests match.

Two attempts preceded this one and are retained beside it as failure
evidence, not acceptance:
`../2026-09-05-recurring-lessons-guard-blocked/` (local Codex history guard
could not find the binary under the dedicated profile) and
`../2026-09-05-recurring-lessons-auth-revoked/` (the dedicated profile's
refresh token was revoked). Neither reached a model request or a cost.

Profile: Plan 2 named the dedicated profile root and required any fallback to
the default profile to be recorded. This run used the default profile root as
an explicit `--codex-home`. [`lifecycle-account-binding.json`](lifecycle-account-binding.json)
is the privacy-bounded projection of the shared-client lifecycle rows: both
public call boundaries used one explicit binding whose account digest equals
the digest Plan 1 retained, so the run is bound to the same ChatGPT account as
the accepted first vertical. It retains no profile path, raw account ID, or
credential.

[`inspection.md`](inspection.md) is the implementing agent's direct-inspection
record, written after opening `report.html` and reading it as a user would,
with the comparison against Plan 1's report.
