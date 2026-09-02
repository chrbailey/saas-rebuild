# Extraction-recipe corpus

This corpus reduces the blank-page cost of authorized SaaS extraction. It is
a set of documented route hypotheses to verify, not a connector library and
not tenant evidence.

`apps.json` is a curated research backlog of 100 B2B SaaS applications across
roughly 30 categories. Its `rank` is prioritization metadata, not a measured
market-adoption result. At v0.7, 29 entries have recipes; the
[covered applications](#covered-applications) table below lists them. For
each implemented entry, `extraction-recipes/<app>.json` records, per
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
  answer; it does not prove that the capability is absent;
- **research_caveats** — how the documents were consulted, as distinct from
  what they say: vendor hosts the research pass could not fetch, source
  repositories or mirrors read instead of live pages, and which claims rest on
  search-engine excerpts rather than full-page reads. Read these before
  trusting a nav path or a numeric limit. They are provenance, not prose to
  tidy away; a later pass removes one only by consulting the source directly.

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

If you administer one of these applications, the
[recipe verification issue form](https://github.com/chrbailey/saas-rebuild/issues/new?template=recipe-verification.yml)
asks for exactly what a promotion or correction needs: routes tried, what
worked, what differed, vendor documentation links, and the date.

`tests/test_extraction_recipes.py` checks every recipe against its schema, its
filename, the target list, and bibliography URL/date/uniqueness constraints,
and checks that research-session language stays out of `export_rights.summary`
and `notes`. It does **not** fetch URLs, prove that a source supports a
sentence, or establish tenant completeness. The v0.7 bibliography is
recipe-level rather than claim-addressable; that is a declared assurance
limitation, not hidden provenance.

## Covered applications

Generated from the recipe files and `apps.json`; a test fails if this table
and the `extraction-recipes/` directory disagree. Rows follow the backlog
`rank`, which is prioritization metadata only. Every recipe is currently
`doc-derived-unverified` and was last reviewed on the same date, because the
corpus was researched in one pass; the columns exist so that promotions and
re-reviews become visible here as they land.

| App | Recipe | Category | Verification | Last reviewed |
|---|---|---|---|---|
| Salesforce Sales Cloud | [`salesforce`](extraction-recipes/salesforce.json) | crm | doc-derived-unverified | 2026-08-08 |
| HubSpot | [`hubspot`](extraction-recipes/hubspot.json) | crm | doc-derived-unverified | 2026-08-08 |
| Zoho CRM | [`zoho-crm`](extraction-recipes/zoho-crm.json) | crm | doc-derived-unverified | 2026-08-08 |
| Pipedrive | [`pipedrive`](extraction-recipes/pipedrive.json) | crm | doc-derived-unverified | 2026-08-08 |
| Dynamics 365 Sales | [`dynamics-365-sales`](extraction-recipes/dynamics-365-sales.json) | crm | doc-derived-unverified | 2026-08-08 |
| Freshsales | [`freshsales`](extraction-recipes/freshsales.json) | crm | doc-derived-unverified | 2026-08-08 |
| NetSuite | [`netsuite`](extraction-recipes/netsuite.json) | erp-finance | doc-derived-unverified | 2026-08-08 |
| SAP Business One | [`sap-business-one`](extraction-recipes/sap-business-one.json) | erp-finance | doc-derived-unverified | 2026-08-08 |
| Dynamics 365 Business Central | [`dynamics-365-business-central`](extraction-recipes/dynamics-365-business-central.json) | erp-finance | doc-derived-unverified | 2026-08-08 |
| QuickBooks Online | [`quickbooks-online`](extraction-recipes/quickbooks-online.json) | accounting | doc-derived-unverified | 2026-08-08 |
| Xero | [`xero`](extraction-recipes/xero.json) | accounting | doc-derived-unverified | 2026-08-08 |
| Sage Intacct | [`sage-intacct`](extraction-recipes/sage-intacct.json) | accounting | doc-derived-unverified | 2026-08-08 |
| FreshBooks | [`freshbooks`](extraction-recipes/freshbooks.json) | accounting | doc-derived-unverified | 2026-08-08 |
| Zoho Books | [`zoho-books`](extraction-recipes/zoho-books.json) | accounting | doc-derived-unverified | 2026-08-08 |
| BILL (Bill.com) Accounts Payable & Receivable | [`bill-com`](extraction-recipes/bill-com.json) | ap-ar-spend | doc-derived-unverified | 2026-08-08 |
| Expensify | [`expensify`](extraction-recipes/expensify.json) | ap-ar-spend | doc-derived-unverified | 2026-08-08 |
| SAP Concur | [`sap-concur`](extraction-recipes/sap-concur.json) | ap-ar-spend | doc-derived-unverified | 2026-08-08 |
| Ramp | [`ramp`](extraction-recipes/ramp.json) | ap-ar-spend | doc-derived-unverified | 2026-08-08 |
| Brex | [`brex`](extraction-recipes/brex.json) | ap-ar-spend | doc-derived-unverified | 2026-08-08 |
| Stripe | [`stripe`](extraction-recipes/stripe.json) | payments | doc-derived-unverified | 2026-08-08 |
| Square | [`square`](extraction-recipes/square.json) | payments | doc-derived-unverified | 2026-08-08 |
| BambooHR | [`bamboohr`](extraction-recipes/bamboohr.json) | hr-payroll | doc-derived-unverified | 2026-08-08 |
| Paylocity | [`paylocity`](extraction-recipes/paylocity.json) | hr-payroll | doc-derived-unverified | 2026-08-08 |
| Deel | [`deel`](extraction-recipes/deel.json) | hr-payroll | doc-derived-unverified | 2026-08-08 |
| Greenhouse Recruiting | [`greenhouse`](extraction-recipes/greenhouse.json) | recruiting | doc-derived-unverified | 2026-08-08 |
| Microsoft Teams | [`microsoft-teams`](extraction-recipes/microsoft-teams.json) | communication | doc-derived-unverified | 2026-08-08 |
| Google Workspace | [`google-workspace`](extraction-recipes/google-workspace.json) | productivity-suite | doc-derived-unverified | 2026-08-08 |
| Microsoft 365 | [`microsoft-365`](extraction-recipes/microsoft-365.json) | productivity-suite | doc-derived-unverified | 2026-08-08 |
| Asana | [`asana`](extraction-recipes/asana.json) | project-management | doc-derived-unverified | 2026-08-08 |

The remaining 71 backlog entries have research briefs in
[`docs/corpus-batches/`](../../../docs/corpus-batches/) and no recipe yet;
`apps.json` listing an application does not imply that a recipe exists.
