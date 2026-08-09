# Corpus research batch 2 — 24 apps

Execute this brief in a fresh Claude Code session on chrbailey/saas-rebuild.
Goal: extend the extraction-recipe corpus (see
`skills/saas-rebuild/corpus/README.md`) with one recipe per app below.

## Setup — read before writing anything

1. `skills/saas-rebuild/templates/extraction-recipe.schema.json` — the
   contract. Requires `schema_version: "0.7.0"`; additionalProperties is
   false everywhere; sources must be unique https URLs with ISO retrieved
   dates; a non-null `export_rights.tos_url` must also appear in sources.
2. `skills/saas-rebuild/corpus/README.md` — the corpus philosophy.
3. Two existing recipes (e.g. `salesforce.json`, `netsuite.json`) as
   exemplars of depth and tone.

## Per app

Research the vendor's own documentation and write
`skills/saas-rebuild/corpus/extraction-recipes/<slug>.json` covering:
whole-account export/backup; per-entity UI exports; report builders;
REST/bulk APIs (auth style, rate limits); attachment/file bulk export;
audit-log export and documented retention; configuration export as
restorable artifacts; the terms/DPA export-rights statement and any
documented post-termination retrieval window.

## Budget discipline

Session WebSearch budgets are ~200 calls. Spend at most 7 searches per
app; prefer WebFetch directly against vendor help-center and API-doc URLs
once the domain is known. If the egress proxy blocks a vendor's domains,
skip that app honestly (no file) and record it in the PR body — do not
burn budget retrying blocked domains.

## Honesty rules (outrank completeness)

Never invent endpoints, nav paths, SKU names, or limits — omit what you
cannot cite. `null` means "docs don't say". `verification` =
`doc-derived-unverified`. `last_reviewed` and `retrieved` = the actual
working date. Honest unknowns go in `notes`.

## Before pushing

- Validate every file against the schema with jsonschema.
- Update the "v0.7, N" recipe count in BOTH `README.md` and
  `skills/saas-rebuild/corpus/README.md` to match the number of files in
  `extraction-recipes/` in your tree (a test pins this).
- Run the full suite green:
  `python3 -m pip install -r requirements-dev.txt && python3 -m pytest tests/ -q`
- Touch nothing else: recipe files plus those two count strings only.

## Ship

Commit, push to branch `claude/corpus-batch-2`, open a DRAFT PR titled
"corpus: batch 2 — 24 extraction recipes" listing written vs
skipped apps with reasons, subscribe to its PR activity, and drive it to
green. Sibling batches may land first; on README-count conflicts, merge
main, recount, push the resolution.

## The apps

| slug | name | vendor | category |
|---|---|---|---|
| adp-workforce-now | ADP Workforce Now | ADP | hr-payroll |
| paychex-flex | Paychex Flex | Paychex | hr-payroll |
| slack | Slack | Salesforce | communication |
| ringcentral | RingCentral | RingCentral | communication |
| monday | monday.com | monday.com | project-management |
| notion | Notion | Notion | knowledge-management |
| wrike | Wrike | Wrike | project-management |
| freshdesk | Freshdesk | Freshworks | customer-support |
| servicenow | ServiceNow | ServiceNow | itsm |
| mailchimp | Mailchimp | Intuit | marketing |
| klaviyo | Klaviyo | Klaviyo | marketing |
| braze | Braze | Braze | marketing |
| bigcommerce | BigCommerce | BigCommerce | ecommerce |
| dropbox | Dropbox Business | Dropbox | file-storage |
| adobe-acrobat-sign | Adobe Acrobat Sign | Adobe | esignature |
| power-bi | Power BI | Microsoft | analytics-bi |
| mixpanel | Mixpanel | Mixpanel | analytics-bi |
| gitlab | GitLab | GitLab | dev-tools |
| canva | Canva | Canva | design |
| typeform | Typeform | Typeform | forms-surveys |
| 1password | 1Password Business | 1Password | security |
| procore | Procore | Procore | construction-field |
| yardi-voyager | Yardi Voyager | Yardi | property-management |
| zapier | Zapier | Zapier | automation |
