# Account-bound authentic run

- Producer revision: `0f07a07c81cde9624a036d1f91f384a4299b4598`
- Command: `uv run whygame-reboot examples/aes-mission-drift/question.yaml --output evidence/runs/2026-08-23-account-bound-live --run-id whygame-reboot/2026-08-23-aes-mission-drift-account-bound --codex-home <dedicated-profile-root>`
- Requested and resolved route: `codex/gpt-5.6-luna`, medium reasoning
- Result: `accepted` after exactly two completed model calls
- Automatic retries: zero
- Fallback: none
- Billing: subscription included; settled marginal cost USD 0.00
- `run.json` SHA-256: `bc8b0348cff345937e4992fbd11425ec694ea4238628c9676f256e224b0c3231`
- `report.html` SHA-256: `93b5adc2f0ea578557421d25f637db5046b7ac0687d6cf8489230d22d9eec7ec`

Direct inspection confirmed that the report leads with the bounded answer,
shows the exact causes-versus-prevents challenge, identifies the superseded
claim and its `contributes_to` replacement, retains the surviving claim, lists
the two source-bound uncertainties, and includes both call receipts. It also
retains the explicit nonclaim that the result does not certify truth, a world
model, independent criticism, or general contradiction detection.

[`lifecycle-account-binding.json`](lifecycle-account-binding.json) is a
privacy-bounded projection of the shared-client lifecycle rows for this run.
It proves that both public call boundaries used one explicit account binding;
it deliberately retains no profile path, raw account ID, or credential.
