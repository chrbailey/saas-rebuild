# DRAFT — FOR HUMAN REVIEW — r/Netsuite post

> Venue notes: best genuine-fit sub — practitioner-heavy, lives with
> implementation regret, historically receptive to free tools posted with
> substance. BUT rules confidence is LOW: **read the sidebar rules
> yourself before posting**, and note it's a small sub (~30–40k) where a
> flop is visible. Disclose authorship in the first line. No AI-tool
> framing in the title — lead with the NetSuite pain.

## Title

I documented NetSuite's actual export routes (saved search, SuiteAnalytics,
REST, files, audit) into an open, cited "extraction recipe" — and built a
protocol around proving what your instance actually uses

## Body

Disclosure up front: I'm an ERP consultant and I built the open-source
(MIT) project this post describes. Nothing for sale.

Two questions I kept meeting on engagements:

1. Renewal is coming — can we prove which modules and workflows this org
   *actually* uses, versus what someone configured in 2019 and abandoned?
2. If we ever migrate off, do we actually know every route to get our data
   out — records, saved searches, files cabinet, audit trail, config — and
   what the retention clocks are?

I got tired of re-deriving the answers, so I wrote them down as a
schema-validated "extraction recipe" for NetSuite: the export-rights
position from the actual Subscription Services Agreement (customer owns
Customer Data, s.5.1) and eight documented extraction routes in preference
order — full account CSV export, bulk analytics access, REST/SuiteQL,
saved-search exports, report builder, file cabinet, system-notes/audit
trail, and configuration/customization export — each with roles, rate
limits, formats, and gotchas, every claim cited to vendor documentation
with a retrieval date.

That recipe is one of 29 (Salesforce, QuickBooks, Sage Intacct, Dynamics,
SAP B1…) in a corpus inside a larger open protocol for evidence-based
tenant teardowns: every feature gets a KEEP/SIMPLIFY/DROP/DEFER verdict
that the JSON Schema rejects unless typed evidence is attached, and
preservation (export everything reachable, checksum it, record accepted
gaps) is deliberately decoupled from the verdicts.

Repo: https://github.com/chrbailey/saas-rebuild — the NetSuite recipe is
`skills/saas-rebuild/corpus/extraction-recipes/netsuite.json`.

The honest catch, and the ask: every recipe is marked
`doc-derived-unverified` — researched from docs, never yet exercised
against a live account. If you administer a NetSuite instance, I'd
genuinely value someone trying the documented routes against reality and
filing corrections (or a confirmation) — the schema has a
`tenant-verified` status that only real admins can earn. Docs drift;
entitlements gate routes; you all know NetSuite's docs-vs-reality gap
better than any document can.

Also useful even if you never touch the protocol: the recipe reads as a
checklist of what to export before any migration conversation gets real.

## Reviewer notes (delete before posting)

- Route list and s.5.1 export-rights claim were checked against
  `netsuite.json` in this repo at drafting time (8 route types:
  account-export, bulk-api, api, entity-export, report-builder,
  file-storage, audit-log-export, config-export). Re-check if the recipe
  changes before posting.
- Verify sidebar rules and whether tool posts need mod pre-approval.
- If a launch post feels too promotional for the sub's mood that week,
  the fallback is the same content as a comment in a live
  "leaving NetSuite / export" thread (see reddit-reply-templates.md).
