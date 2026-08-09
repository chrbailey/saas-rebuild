# Community launch brief — bring people to saas-rebuild

Execute this brief in a fresh Claude Code session on chrbailey/saas-rebuild.
Goal: get the repo in front of the people who feel SaaS-consolidation pain,
and make it trivially easy for them to contribute their own teardowns —
**through content the maintainer personally reviews and posts**, never
automated posting.

## Hard rules (these define the engagement, read first)

1. **No automated posting, ever.** This session researches and drafts;
   a human (the maintainer) posts, under their own account, with their
   affiliation as the repo author plainly stated. Never create accounts,
   never post via APIs or browser automation, never draft content
   designed to hide its origin.
2. **Relevance over reach.** Only draft replies for threads where the
   repo genuinely answers the question being asked. A dozen on-point
   comments beat a hundred drive-bys — and platform rules (and community
   patience) treat the latter as spam.
3. **Honest claims only.** The repo's own standard applies: mechanisms,
   not adjectives. 29/100 recipes is stated as 29/100. "Doc-derived,
   unverified" recipes are described exactly that way.

## Phase 1 — Map the watering holes

Research (WebSearch/WebFetch) where these conversations actually happen:
SaaS sprawl/spend complaints, "we only use 10% of X", ERP implementation
regret, data-export/exit-planning questions, build-vs-buy debates, and
Claude-skill/agent tooling interest. Candidate venues to evaluate (find
the real activity, don't assume): Hacker News, r/sysadmin, r/msp,
r/ExperiencedDevs, r/smallbusiness, r/Netsuite, r/salesforce, IndieHackers,
lobste.rs, LinkedIn, specialized forums (Spiceworks, ERP-focused
communities). For each: what content format works there, self-promotion
norms/rules, and 3–5 live threads (URLs) where the repo is a genuine
answer. Deliverable: `docs/outreach/venue-map.md`.

## Phase 2 — Draft the launch kit

All drafts go in `docs/outreach/drafts/`, clearly marked DRAFT — FOR
HUMAN REVIEW. Write in the maintainer's plain first-person voice, always
disclosing "I built this":

1. A Show HN post (title + body) leading with the mechanism story:
   evidence-cited verdicts, preservation export, extraction recipes,
   replay-validated rebuilds.
2. One tailored post per top venue (2–3 venues), matching each
   community's norms.
3. Reply drafts for the live threads found in Phase 1 — each answering
   the actual question first, mentioning the repo second.
4. A short "share your teardown" pitch that channels people to the
   Teardown Report issue template, emphasizing sanitization rules.

## Phase 3 — Lower the contribution bar in the repo

On branch `claude/community-launch`, PR the repo-side welcome mat:
- `CONTRIBUTING.md`: the three contribution lanes (teardown reports via
  the issue template; extraction-recipe PRs — point at
  `docs/corpus-batches/` and the recipe schema; recipe verification
  promotions with evidence).
- A "good first contribution" section: verify one doc-derived recipe
  against a tenant you administer and PR the promotion.
- Check the Teardown Report issue template still matches the current
  schema vocabulary; fix if drifted.

Open a draft PR, subscribe to it, drive it to green. The outreach drafts
ship in the same PR so the maintainer reviews everything in one place.

## Deliverable recap

venue-map.md, drafts/ (posts + replies, all marked for human review),
CONTRIBUTING.md, one green draft PR. End your final message with a
checklist of exactly what the maintainer should review and post, in
priority order.
