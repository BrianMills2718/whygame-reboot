# Provider-free clean-room rehearsal

This is development evidence, not product acceptance or AES admission.

## Boundary

- Source branch: `plan-1-graph-adversary`
- Fresh clone, fresh `uv sync --frozen`, no sibling checkout reuse
- Entry point: `whygame-reboot ... --dry-run`
- Provider dispatch: forbidden; the retained run contained zero call receipts

## Initial observation

At source revision `f9aa93ef57da89de0cb36821ed92debd59eecd40`, fresh
installation, 13 tests, Ruff, and the dry-run command passed. Inspecting the
same files a user receives exposed an integrity defect: `run.json` recorded
report digest
`39c812c5bed66a8470ee29c380997cdca317cd7c81b37cb7d2bd6c7a103da89a`,
while the exact `report.html` bytes hashed to
`2f4703f023623fb094ec4e0e6ce55f42783ff08764e2b55ce72e5257a4a1b443`.
The implementation had canonical-JSON-hashed the HTML string instead of
hashing the emitted UTF-8 bytes.

## Repaired observation

Revision `c41c61418a0be1f42b5917bd5d17fce24fda5caa` was cloned into a
second empty temporary directory and exercised from scratch:

- dependency sync: pass (`0.46s` observed);
- test suite: `14 passed` (`9.85s` observed including runner startup);
- Ruff: pass (`0.02s` observed);
- provider-free dry run: pass (`3.07s` observed);
- run status: `dry_run` with no issues and zero call receipts;
- input digest: `0cdcf8202f4224591a03c4953ec7cad5e8e9d5d94bebe4e227f4ab0a082ee80c`;
- config digest: `e640aea5daee8995795056706e168dfb4976bb412d2a8a1d3d94b90ee50ae33b`;
- manifest and exact report-byte digest:
  `0e456012fa189c2e327c4a928c2ed0393481012d809faf5f4fbd19f2531d8c0a`.

The fresh clone remained Git-clean. This proves clone portability and the
provider-free integrity boundary only. The two-call Luna observation remains
blocked by the retained capacity receipt until the announced 2026-08-28 reset;
this rehearsal does not satisfy authentic product acceptance.
