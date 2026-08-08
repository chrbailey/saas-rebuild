# Extraction-recipe corpus

This corpus reduces the blank-page cost of authorized SaaS extraction. It is
a set of documented route hypotheses to verify, not a connector library and
not tenant evidence.

`apps.json` is a curated research backlog of 100 B2B SaaS applications across
roughly 30 categories. Its `rank` is prioritization metadata, not a measured
market-adoption result. At v0.7, 29 entries have recipes. For each implemented
entry, `extraction-recipes/<app>.json` records, per
`../templates/extraction-recipe.schema.json`:

- **export_rights** — what the consulted terms or documentation say the
  customer may export, plus any documented post-termination retrieval window;
- **routes** — candidate extraction routes in preference order, including
  steps or endpoints, roles/SKUs, rate limits, and gotchas;
- **preservation_notes** — documented routes or gaps for attachments, audit
  logs, and restorable configuration artifacts;
- **sources** — a recipe-level bibliography with URL and retrieval date.
  Primary vendor documentation is preferred, but a few negative or gap claims
  use vendor-community or independent secondary material and must be treated
  accordingly. `null` means the consulted material did not establish an
  answer; it does not prove that the capability is absent.

**Trust the `verification` field, not the prose.** Every recipe starts
`doc-derived-unverified`: researched from documents and never exercised
against a live tenant. Treat it as a starting hypothesis for Phase 0 preflight
and the Phase 4/4b route maps, then verify it against current documentation,
entitlements, region, and the authorized tenant.

Promote to `community-verified` only when reviewable shared evidence confirms
the main routes, and to `tenant-verified` only after the routes were exercised
end-to-end in at least one authorized tenant. Neither status establishes that
another tenant, region, SKU, or future vendor version behaves the same. Submit
corrections with the evidence that motivated them. `last_reviewed` signals how
stale the documentary research might be.

`tests/test_extraction_recipes.py` checks every recipe against its schema, its
filename, the target list, and bibliography URL/date/uniqueness constraints.
It does **not** fetch URLs, prove that a source supports a sentence, or
establish tenant completeness. The v0.7 bibliography is recipe-level rather
than claim-addressable; that is a declared assurance limitation, not hidden
provenance.
