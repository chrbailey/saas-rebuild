# DRAFT — FOR HUMAN REVIEW — r/ClaudeCode launch post

> Venue notes: plugin writeups are a native genre here and an inline repo
> link is normal. The noise floor is high (dozens of plugin announcements
> weekly) — the differentiators carry the post: machine-checked evidence
> protocol, preservation manifest, recipe corpus, replay validation, and
> the fact that it's a *non-coding* use of Claude Code. Verify current
> sidebar rules and flair conventions before posting. Optional secondary
> crosspost to r/ClaudeAI under a showcase-type flair.

## Title

I built a plugin that tears down a SaaS tenant with evidence — schemas
reject verdicts without citations, exports get checksummed, rebuilds get
replay-tested

## Body

I'm an ERP consultant, and this is the least "coding assistant" thing I've
done with Claude Code.

The problem: companies pay for big SaaS/ERP products, use a fraction, and
can't prove which fraction. And when they finally leave or rebuild, the
data export starts after the contract decision instead of before it.

**saas-rebuild** (MIT, repo: https://github.com/chrbailey/saas-rebuild) is
a skill + machine contracts for running an evidence-based teardown of a
tenant you administer. What makes it different from "ask the model to
audit my SaaS":

- **The skill is subordinate to JSON Schemas.** Feature verdicts
  (KEEP/SIMPLIFY/DROP/DEFER) are rejected by the contract if they carry no
  typed evidence citation. The model can't hand-wave a verdict into the
  artifact set — CI runs a cross-artifact validator that also catches
  duplicate identities, dataset lineage crossing roles, path escapes, and
  digest drift.
- **Preservation is decoupled from judgment.** The preservation manifest
  wants every reachable data class exported and checksummed, or an
  explicitly accepted gap — verdicts decide what gets rebuilt, never what
  gets preserved.
- **An extraction-recipe corpus** (29 of a 100-app target list: NetSuite,
  Salesforce, QuickBooks, HubSpot, M365…) documents export rights, routes,
  rate limits, and retention clues from vendor docs. Every recipe is marked
  `doc-derived-unverified` until someone verifies it against a live tenant
  — the schema has `community-verified`/`tenant-verified` statuses waiting
  to be earned, which is the contribution I most want help with.
- **Rebuilds are accepted by replaying historical behavior**, with lineage
  rules so acceptance cases can't leak into development examples.
- **A reference rebuild ships in the repo** (restricted-party screening):
  deterministic Python core, ~270 stdlib tests, model adjudication optional
  and unable to overrule an exact match. That's the target architecture the
  protocol pushes toward — the skill as orchestration, not as a database.

There's a synthetic worked example so you can inspect every artifact
without tenant data, and the whole thing installs as a plugin:

```
/plugin marketplace add chrbailey/saas-rebuild
/plugin install saas-rebuild@chrbailey-plugins
```

Honest limits: recipes are documentary research, not proof a route works in
your tenant; the bibliography is recipe-level, not claim-addressable; and
replay acceptance is only as good as its case coverage, which the contracts
force you to state rather than solve.

If you administer any B2B SaaS tenant, verifying one recipe against your
live account is a bounded afternoon and exactly the evidence the corpus
lacks. CONTRIBUTING.md has the loop.

## Reviewer notes (delete before posting)

- Numbers pinned to v0.7: 29/100, all doc-derived-unverified, 302 tests
  (rounded to ~270 in the draft to keep it casual — restore the exact
  number if you prefer).
- If the sub requires flair, "Showcase"/"Plugin" equivalents fit.
- Expect "why not just a spreadsheet/SAM tool" comments — the answer is
  the preservation manifest + replay acceptance, not the usage report.
