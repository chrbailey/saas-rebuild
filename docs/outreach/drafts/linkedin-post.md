# DRAFT — FOR HUMAN REVIEW — LinkedIn post

> Format notes (from venue research): text-only post, ~1,200–1,500 chars,
> hook must land in the first 210 characters (the "…see more" fold). **No
> external link in the body** — 2026 algorithm cuts link-post reach ~60%
> and now also penalizes link-in-first-comment; add the repo link as a
> comment only after engagement starts, or let people search the repo name.
> 3–5 hashtags at the end, hygiene only. Post Tue–Thu morning.
> Optional upgrade: turn the KEEP/SIMPLIFY/DROP table from the synthetic
> example into a 4–6 page PDF document post — document posts get ~5x the
> reach of link posts.

## Post text

Most ERP and SaaS renewal decisions are made with zero evidence about what
the company actually uses.

I've watched this for years as a consultant: the vendor shows up with an
adoption deck, someone internally guesses "we probably need most of it,"
and the renewal signs. Then a migration comes, and the data export starts
*after* the contract decision — which is exactly backwards.

So I built an open-source protocol for doing it with evidence, and I'm
giving it away (MIT, nothing for sale):

→ Every feature gets a KEEP / SIMPLIFY / DROP / DEFER verdict, and the
schemas literally reject a verdict that has no cited evidence behind it.
Configuration alone doesn't prove use. A 30-day log doesn't prove non-use.

→ Preservation is separated from verdicts: everything reachable gets
exported and checksummed — records, files, audit history, config — even
for the features you drop. You keep the data either way.

→ It ships with documented extraction routes for 29 common B2B apps
(NetSuite, Salesforce, QuickBooks, Dynamics…) — export rights, API routes,
rate limits, retention windows, each with a dated vendor-doc bibliography
and marked unverified until someone proves them against a real tenant.

→ If you rebuild, the replacement is validated by replaying historical
behavior, not by a demo.

It runs in your browser with your own API key (nothing to install, no
connector into your tenant) or as a Claude Code plugin, on tenants you
administer. Repo is "saas-rebuild" on
GitHub (chrbailey) — links in comments.

What I'd ask this network: when you left an ERP or major SaaS, what did
you fail to export before the contract ended? That failure list is what
I'm trying to make impossible.

#ERP #SaaS #ITAssetManagement #OpenSource #SoftwareAudit

## First comment (post after engagement starts)

Try it without installing anything: https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app
(static app, your Anthropic API key stays in your browser and goes only to
Anthropic). Repo: https://github.com/chrbailey/saas-rebuild — the synthetic
worked example shows every artifact without anyone's tenant data. If you
administer a tenant and want a genuinely useful way to help: pick one of
the 29 extraction recipes and verify its routes against your live account.
CONTRIBUTING.md explains the whole loop.

## Reviewer notes (delete before posting)

- Character count of the main post is ~1,750 — trim to taste; the first
  two lines are the hook and must stay above the fold.
- "29" and "unverified" must stay in sync with the repo at posting time
  (pinned at v0.8, skill 0.8.0: 29/100, all `doc-derived-unverified`).
- Open the hosted workspace URL and confirm it loads before posting the
  comment.
- Timely alternates for later weeks: (a) Dynamics GP end-of-sales
  (Apr 2026) preservation angle; (b) riff on Zylo's 2026 index
  ($19.8M/yr avg. waste) or Flexera's 2026 ITAM report — both circulate
  heavily on LinkedIn and invite a "here's how to measure yours" reply.
