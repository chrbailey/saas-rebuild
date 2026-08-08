# Extraction-recipe corpus

Nearly every SaaS contract grants the customer the right to export their
own data. Almost nobody exercises it — not because extraction is hard,
but because nobody knows the exact routes for their exact app until the
renewal is due or the subscription is ending. This corpus front-loads
that knowledge.

`apps.json` is the target list: 100 widely-adopted B2B SaaS applications
across ~30 categories, ordered roughly by adoption. For each,
`extraction-recipes/<app>.json` documents, per
`../templates/extraction-recipe.schema.json`:

- **export_rights** — what the vendor's own terms say the customer may
  export, and the post-termination data-retrieval window (the hardest
  deadline in any migration).
- **routes** — extraction routes in descending preference order
  (account export → entity export → report builder → API → bulk API →
  audit-log/config export → scrape as last resort), each with the
  concrete steps or endpoint, required roles/SKUs, rate limits, and
  gotchas.
- **preservation_notes** — the three answers Phase 4b needs per app:
  how attachments bulk-export, how the audit log exports and how long
  it's retained, and how configuration exports as restorable artifacts.
- **sources** — every claim traces to a vendor-doc citation with URL and
  retrieval date. `null` anywhere means "the docs don't say" — verify
  in-tenant. Nothing here is invented; what couldn't be cited was
  omitted.

**Trust the `verification` field, not the prose.** Every recipe starts
`doc-derived-unverified`: researched from vendor documentation, never
exercised against a live tenant. Treat those as hypotheses that seed
Phase 0 pre-flight and the Phase 4/4b route maps — then verify against
your tenant. When a real teardown confirms (or corrects) a recipe, send
the fix back as a PR and promote it: `community-verified` when a shared
teardown report confirms the main routes, `tenant-verified` when someone
has run them end-to-end. Vendor docs drift; `last_reviewed` tells you
how stale a recipe might be.

Validation: `tests/test_extraction_recipes.py` checks every recipe
against the schema, its filename, the target list, and its citations on
every CI run.
