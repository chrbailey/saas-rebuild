# Corpus re-review backlog

The extraction-recipe corpus was researched in one pass on 2026-08-08, in an
environment whose egress proxy blocked most vendor documentation domains. All
29 recipes carry an honest `research_caveats` entry saying so. Twenty-eight of
them still rest on that degraded provenance: vendor-published OpenAPI specs
read from GitHub mirrors, search-engine renderings of pages that could not be
fetched, and doc snapshots years older than the live product.

This brief is the worklist for replacing that provenance with current vendor
pages, worst-first. It is written to be executed one entry at a time by a
fresh session, the same way [`corpus-batches/batch-1.md`](corpus-batches/batch-1.md)
was written for the apps that have no recipe yet.

**Re-review is not verification.** Reading a current vendor page upgrades how
fresh a documentary claim is. It does not exercise a route against a tenant,
so `verification` stays `doc-derived-unverified` no matter how good the
sources get. Promotion to `community-verified` or `tenant-verified` comes only
from tenant evidence submitted through the recipe-verification issue form.

## Run this where the vendor domains resolve

This is the operational constraint that has blocked the work twice, so check
it before spending a session on it.

Both the original 2026-08-08 research pass and the 2026-09-21 continuation ran
in sandboxes whose egress proxy refused every vendor documentation host —
`documentation.bamboohr.com`, `developer.squareup.com`, `developer.deel.com`,
`developer.paylocity.com`, `support.greenhouse.io` and the rest all fail
closed, through both `WebFetch` and plain `curl`. Web search still returns
snippets, but rebuilding a recipe from snippets reproduces exactly the
provenance this backlog exists to remove, while stamping it with a fresh
`last_reviewed` date — strictly worse than leaving the recipe alone, because
it hides the staleness instead of recording it.

The Asana entry was refreshed on 2026-09-05 from a workstation with
unrestricted network access. Run these entries the same way, or from a
sandbox whose allowlist covers the vendor's documentation hosts. Before
starting an entry, fetch one of its vendor URLs and confirm you get a page
back. If the domain is blocked, stop and leave the recipe untouched.

## The standard to hit

[`asana.json`](../skills/saas-rebuild/corpus/extraction-recipes/asana.json) is
the worked example of a completed re-review. That pass:

- replaced a bibliography of 7 sources built from a 2024 developer-docs
  snapshot with 15 sources retrieved from current developer and Help Center
  pages, each carrying its real retrieval date;
- added a `config-export` route (connected-app inventory and 90-day activity
  CSV) that the blocked research had missed entirely;
- corrected plan gating that had drifted — `Enterprise` became `Enterprise+`,
  and the audit-log tiers were restated against the current access table;
- replaced guesses inferred from audit-event names with documented UI
  navigation paths, and dropped the ones that stayed unconfirmed;
- rewrote `research_caveats` from one entry about a blocked network into two
  honest scope limits that survive the refresh: the customer agreement and DPA
  were still not reviewed, and no live tenant was used.

Note the last point. A refresh does not empty `research_caveats`; it narrows
them to what is still genuinely unconsulted. A recipe whose caveats vanish
entirely is a recipe that stopped being honest.

## Tier 1 — reconstructed from mirrors and snippets

Four recipes where almost nothing came from a vendor page. These have the
thinnest bibliographies in the corpus and the largest blocks of declared
unknowns; they are the entries most likely to mislead someone under a
termination deadline, and they are the reason this backlog is ordered by
provenance rather than by app popularity.

### [`bamboohr`](../skills/saas-rebuild/corpus/extraction-recipes/bamboohr.json) — 3 sources, 5 routes

Rests on the vendor's GitHub-published SDK spec plus an unofficial mirror of
the legacy gateway API docs. Every `bamboohr.com` property was blocked.

Close: any whole-account export or backup feature; admin-UI per-entity
CSV/XLSX export and the report builder's in-UI export; audit-trail export and
its retention; numeric API rate limits; and the export-rights language in the
ToS (`www.bamboohr.com/terms-of-service/`) and API terms
(`partners.bamboohr.com/bamboohr-api-terms-of-use/`), neither consulted.
Start from `documentation.bamboohr.com/docs`.

### [`square`](../skills/saas-rebuild/corpus/extraction-recipes/square.json) — 3 sources, 3 routes

API claims come from the official OpenAPI spec on GitHub and are sound;
every Dashboard-export claim came from support-article titles and search
snippets. `squareup.com`, `developer.squareup.com` and `web.archive.org` were
all blocked.

Close: Customer Directory and Items Library CSV export, both widely referenced
but unconfirmed; whether any whole-account export exists; audit-log retention
beyond the 28-day Events API window; numeric API rate limits; the
post-termination retrieval window; and the vendor-ticket process for migrating
card-on-file data to another PCI-compliant processor, which is currently
recorded as ecosystem lore rather than documentation.

### [`deel`](../skills/saas-rebuild/corpus/extraction-recipes/deel.json) — 4 sources, 4 routes

Built from OpenAPI specs and SDKs obtained through third-party mirrors
(api-evangelist, jentic) plus the official npm package. All Deel-owned domains
were blocked and the search budget was exhausted.

Close: admin-UI per-entity CSV exports and any in-app report builder; any
whole-account export; audit-log export and retention; ToS/DPA export rights
and post-termination window; and numeric rate limits, which mirror metadata
says are documented at `developer.deel.com/docs/rate-limit`. Verify against
`developer.deel.com` and `help.deel.com`.

### [`paylocity`](../skills/saas-rebuild/corpus/extraction-recipes/paylocity.json) — 5 sources, 2 routes

The thinnest route coverage in the corpus, and the most dated sources: GitHub
mirrors of a Swagger 2.0-era spec. The current surface on
`developer.paylocity.com` is almost certainly larger.

Close: reporting and Data Insights exports, attachment/document bulk export,
and audit-log export — all three are absent as routes because nothing citable
could be reached, not because the product lacks them. Also confirm or discard
the third-party (Nango) claim of a newer "NextGen" API behind
`dc1prodgwext.paylocity.com`, including whether API access carries a cost and
requires an access-request form. No terms or DPA statement was consulted.

## Tier 2 — vendor text, but not from vendor pages

Five recipes with usable bibliographies drawn from official GitHub doc
repositories or search renderings of the right pages. The routes are broadly
trustworthy; the gaps are specific and enumerated in each file's `notes`.

### [`google-workspace`](../skills/saas-rebuild/corpus/extraction-recipes/google-workspace.json) — 8 sources, 6 routes

Deliberately omits routes rather than describing them from memory. Add, from
documentation: the Admin console Data Export tool
(`support.google.com/a/answer/100458`), end-user Takeout archive formats,
Chat and Groups exports, and edition/SKU gating such as which editions include
Vault. Every `rate_limits` field is null because no quota page was consulted;
quotas exist and matter before bulk extraction.

### [`greenhouse`](../skills/saas-rebuild/corpus/extraction-recipes/greenhouse.json) — 9 sources, 4 routes

Entirely from `grnhse/greenhouse-api-docs`, the real source of
developers.greenhouse.io, so the API side is solid. Missing: admin-UI and bulk
candidate export, the report builder as an export route, any whole-account
export or BI connector, plan/SKU gating, and MSA/DPA export rights. The audit
log article at `support.greenhouse.io/hc/en-us/articles/15074318933275` is
cited by the vendor docs but was never fetched.

### [`zoho-books`](../skills/saas-rebuild/corpus/extraction-recipes/zoho-books.json) — 9 sources, 7 routes

Route coverage is good; every claim came from search renderings rather than
full page reads, so nav paths and limits need confirming. Audit-trail
retention is undocumented. The ToS documents deletion timing rather than a
retrieval window — keep that distinction when re-reading it.

### [`dynamics-365-business-central`](../skills/saas-rebuild/corpus/extraction-recipes/dynamics-365-business-central.json) — 10 sources, 6 routes

Read from the MicrosoftDocs GitHub repositories that publish the
learn.microsoft.com pages, so the text is vendor-authored and current-ish.
Confirm against the live pages: the report "Send to" PDF/Word/Excel export,
omitted as a route only because its UI steps were unconfirmed; bulk
attachment-only export; per-tenant AL extension source download; and the
BACPAC restore constraints.

### [`hubspot`](../skills/saas-rebuild/corpus/extraction-recipes/hubspot.json) — 10 sources, 8 routes

All claims came from search-engine content quoting the vendor pages. Re-verify
every numeric limit before it enters an evidence base: rate limits, the
30-exports-per-24h cap, ZIP-split thresholds, and the ~90-day audit retention.
Property-history, list, and form-submission exports are believed to exist and
were omitted as unconfirmed; confirm or discard them.

## Tier 3 — blocked fetches, substantial bibliographies

Nineteen recipes whose research also could not fetch vendor pages directly,
but which cite enough material that re-review is a freshness and gap-closing
pass rather than a reconstruction. Work these after tiers 1 and 2. For each:
re-retrieve the cited URLs, update `retrieved` dates to the real working date,
resolve the unknowns listed in `notes`, and narrow `research_caveats` to what
is still unconsulted.

| Recipe | Sources | Routes |
|---|---|---|
| [`xero`](../skills/saas-rebuild/corpus/extraction-recipes/xero.json) | 10 | 6 |
| [`freshbooks`](../skills/saas-rebuild/corpus/extraction-recipes/freshbooks.json) | 11 | 6 |
| [`quickbooks-online`](../skills/saas-rebuild/corpus/extraction-recipes/quickbooks-online.json) | 11 | 7 |
| [`salesforce`](../skills/saas-rebuild/corpus/extraction-recipes/salesforce.json) | 11 | 7 |
| [`dynamics-365-sales`](../skills/saas-rebuild/corpus/extraction-recipes/dynamics-365-sales.json) | 12 | 7 |
| [`expensify`](../skills/saas-rebuild/corpus/extraction-recipes/expensify.json) | 12 | 5 |
| [`freshsales`](../skills/saas-rebuild/corpus/extraction-recipes/freshsales.json) | 12 | 4 |
| [`ramp`](../skills/saas-rebuild/corpus/extraction-recipes/ramp.json) | 12 | 5 |
| [`brex`](../skills/saas-rebuild/corpus/extraction-recipes/brex.json) | 13 | 6 |
| [`pipedrive`](../skills/saas-rebuild/corpus/extraction-recipes/pipedrive.json) | 13 | 6 |
| [`zoho-crm`](../skills/saas-rebuild/corpus/extraction-recipes/zoho-crm.json) | 14 | 7 |
| [`bill-com`](../skills/saas-rebuild/corpus/extraction-recipes/bill-com.json) | 15 | 8 |
| [`netsuite`](../skills/saas-rebuild/corpus/extraction-recipes/netsuite.json) | 15 | 8 |
| [`microsoft-365`](../skills/saas-rebuild/corpus/extraction-recipes/microsoft-365.json) | 16 | 8 |
| [`microsoft-teams`](../skills/saas-rebuild/corpus/extraction-recipes/microsoft-teams.json) | 16 | 6 |
| [`sap-business-one`](../skills/saas-rebuild/corpus/extraction-recipes/sap-business-one.json) | 16 | 8 |
| [`sage-intacct`](../skills/saas-rebuild/corpus/extraction-recipes/sage-intacct.json) | 17 | 8 |
| [`sap-concur`](../skills/saas-rebuild/corpus/extraction-recipes/sap-concur.json) | 20 | 8 |
| [`stripe`](../skills/saas-rebuild/corpus/extraction-recipes/stripe.json) | 22 | 8 |

## Honesty rules (these outrank completeness)

Same rules the original research ran under, because they are what makes the
corpus worth reading:

- Never invent endpoints, nav paths, SKU names, or limits. Omit what you
  cannot cite. `null` means "the consulted documents do not say", never
  "the capability does not exist".
- `verification` stays `doc-derived-unverified`. Re-review never promotes it.
- `last_reviewed` and every `retrieved` date is the real working date.
- Keep a `research_caveats` entry for anything still unconsulted — typically
  the customer agreement and DPA, and always the absence of a live tenant.
- Removing a caveat requires consulting the source it describes. Deleting it
  because the sentence reads badly is falsification.
- If a vendor domain is blocked, leave the recipe alone and say so in the PR
  body. A skipped entry is a correct outcome.

## Before pushing

- Recipes validate against
  [`extraction-recipe.schema.json`](../skills/saas-rebuild/templates/extraction-recipe.schema.json)
  (`schema_version` is `0.9.0`; `additionalProperties` is false everywhere;
  sources are unique https URLs with ISO `retrieved` dates; a non-null
  `export_rights.tos_url` must also appear in `sources`).
- Update the "Last reviewed" cell for each refreshed app in the covered
  applications table in
  [`corpus/README.md`](../skills/saas-rebuild/corpus/README.md) — a test pins
  that table against the recipe files.
- Remove each refreshed app from this backlog. `tests/test_extraction_recipes.py`
  asserts that this file lists exactly the recipes still carrying the
  2026-08-08 research date, so a refresh that forgets this step fails the
  suite.
- Mirror any changed recipe into `web/data/recipes/` — the hosted workspace
  serves its own copies and a test compares them.
- Run the suite green:
  `python3 -m pip install -r requirements-dev.txt && python3 -m pytest tests/ -q`

## Ship

One PR per tier-1 entry (they are near-rewrites and deserve individual
review); tier-2 and tier-3 entries may be batched by category. Draft PRs,
titled `corpus: re-review <app>`, listing refreshed apps, skipped apps with
the reason, and any claim that moved from asserted to unknown — that last
category is a result, not a regression.
