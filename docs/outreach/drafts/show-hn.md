# DRAFT — FOR HUMAN REVIEW — do not post without reading every claim

> Venue: Hacker News (Show HN)
> Poster: the maintainer, from their own account, as themselves.
> Mechanics: Show HN posts must be submitted as a link to the repo with the
> text below as the first comment, or as a text post — check current Show HN
> guidelines (https://news.ycombinator.com/showhn.html) on the day of posting.
> Best posting windows are commonly cited as weekday mornings US Eastern;
> don't over-optimize this.

## Title

Show HN: SaaS Rebuild – map what your SaaS tenant actually uses, then shrink it

*(Alternates, pick one — HN titles get edited by mods if overwrought:)*

- Show HN: An evidence protocol for tearing down SaaS you administer
- Show HN: SaaS Rebuild – teardown protocol with citations, exports, and replay

## Body

I'm an ERP consultant. The pattern I kept hitting: a company pays for a big
SaaS or ERP product, uses a fraction of it, suspects as much, and has no
defensible way to prove which fraction — so renewal season is vibes versus a
vendor deck. And when someone does decide to leave or rebuild, the data
export is an afterthought that starts *after* the contract decision.

SaaS Rebuild is my attempt to make that whole conversation evidence-based.
It's an open protocol plus a Claude Code skill (MIT, nothing for sale) that
runs a teardown of a tenant you administer:

- **Verdicts require citations.** Every feature gets KEEP / SIMPLIFY / DROP /
  DEFER, and the JSON Schemas reject a verdict with no typed evidence behind
  it. Configuration alone doesn't prove use; a short telemetry window doesn't
  prove non-use — the contracts force you to record which kind of evidence
  you actually have.
- **Preservation is decoupled from verdicts.** Verdicts control what gets
  rebuilt; they never control what gets preserved. The preservation manifest
  wants every reachable data class exported and checksummed — records, files,
  audit history, configuration, identities — or an explicitly accepted gap.
  You keep the data even for the features you drop.
- **Extraction recipes lower the blank-page cost.** There's a corpus of
  document-derived extraction recipes (export rights, routes, rate limits,
  retention clues) for common B2B apps — 29 of a 100-app target list so far.
  They're schema-checked route hypotheses built from vendor docs, explicitly
  marked `doc-derived-unverified`; each one has to be re-verified against
  your entitlements and live tenant before you trust it.
- **Rebuilds are validated by replay.** Held-out historical cases are
  replayed against the replacement, with lineage rules so an acceptance case
  can't leak into development examples, and an explicit register separating
  intended improvements from unexplained divergence.

The repo also ships a synthetic worked example (so you can see every
artifact without anyone's tenant data), a cross-artifact validator that runs
in CI, and a reference rebuild — a restricted-party screening engine where
the legal-effect logic is deterministic, tested Python and the model is
optional and can't overrule an exact match.

What it deliberately doesn't do: touch a vendor's source code, bypass access
controls, or claim every SaaS can become a prompt. It reverse-engineers the
part a customer already owns — configuration, data, observed workflows,
integrations, historical behavior. Shared transactional state still belongs
in a database, not a skill; the protocol makes you pick a runtime per
capability instead of assuming the answer.

Honest limits: the recipe corpus is 29/100 and none of those recipes have
been verified against a live tenant yet (that's the contribution I'd most
like help with — the schema has `community-verified` and `tenant-verified`
statuses waiting to be earned). The bibliography is recipe-level, not
claim-addressable. And a replay suite is only as good as its case coverage,
which the contracts make you state rather than solve.

Repo: https://github.com/chrbailey/saas-rebuild

I'd especially like to hear from people who've done a SaaS exit or ERP
de-implementation: what evidence did you wish you'd had, and what did you
fail to export before the contract ended?

---

## Reviewer notes (delete before posting)

- Every number above is pinned to the repo at v0.7: 29/100 recipes, all
  `doc-derived-unverified`. If recipes were added or promoted since, update
  both counts and the "none verified" sentence.
- The screening engine's "302 tests" claim was deliberately left out of the
  post — test counts invite "tests prove nothing" derails. The assurance
  case link covers it if asked.
- Prepare for the two predictable HN objections before posting:
  1. "This is just usage analytics / SAM tooling" → the difference is the
     preservation manifest + replay acceptance, not the usage report.
  2. "LLM in the loop = untrustworthy evidence" → verdicts are
     schema-gated to citations; the reference rebuild shows the model as
     optional adjudicator that cannot clear an exact match.
