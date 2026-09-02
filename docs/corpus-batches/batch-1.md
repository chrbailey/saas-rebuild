# Corpus research batch 1 — 24 apps

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
- Update the "v0.8, N" recipe count in BOTH `README.md` and
  `skills/saas-rebuild/corpus/README.md` to match the number of files in
  `extraction-recipes/` in your tree (a test pins this).
- Run the full suite green:
  `python3 -m pip install -r requirements-dev.txt && python3 -m pytest tests/ -q`
- Touch nothing else: recipe files plus those two count strings only.

## Ship

Commit, push to branch `claude/corpus-batch-1`, open a DRAFT PR titled
"corpus: batch 1 — 24 extraction recipes" listing written vs
skipped apps with reasons, subscribe to its PR activity, and drive it to
green. Sibling batches may land first; on README-count conflicts, merge
main, recount, push the resolution.

## The apps

| slug | name | vendor | category |
|---|---|---|---|
| workday | Workday HCM | Workday | hr-payroll |
| rippling | Rippling | Rippling | hr-payroll |
| workable | Workable | Workable | recruiting |
| webex | Webex | Cisco | communication |
| confluence | Confluence | Atlassian | knowledge-management |
| clickup | ClickUp | ClickUp | project-management |
| smartsheet | Smartsheet | Smartsheet | project-management |
| zendesk | Zendesk | Zendesk | customer-support |
| help-scout | Help Scout | Help Scout | customer-support |
| jira-service-management | Jira Service Management | Atlassian | itsm |
| account-engagement | Account Engagement (Pardot) | Salesforce | marketing |
| constant-contact | Constant Contact | Constant Contact | marketing |
| shopify | Shopify | Shopify | ecommerce |
| wix | Wix | Wix | ecommerce |
| docusign | Docusign | Docusign | esignature |
| tableau | Tableau Cloud | Salesforce | analytics-bi |
| google-analytics | Google Analytics 4 | Google | analytics-bi |
| github | GitHub | GitHub/Microsoft | dev-tools |
| figma | Figma | Figma | design |
| surveymonkey | SurveyMonkey | SurveyMonkey | forms-surveys |
| jotform | Jotform | Jotform | forms-surveys |
| gainsight | Gainsight CS | Gainsight | customer-success |
| appfolio | AppFolio Property Manager | AppFolio | property-management |
| clio | Clio Manage | Clio | legal |
