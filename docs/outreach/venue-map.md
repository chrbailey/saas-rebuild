# Venue map — where saas-rebuild's audience actually talks

Research date: 2026-08-09. Compiled from live web research for the
community-launch brief (`docs/community-launch-brief.md`).

**Hard rule restated:** nothing in this document is posted automatically.
The maintainer reviews, verifies, and posts personally, with affiliation
disclosed. Drafts live in `docs/outreach/drafts/`.

**Verification caveat, read first.** The research environment's egress proxy
blocks direct fetches to most community sites (news.ycombinator.com,
reddit.com, lobste.rs, indiehackers.com, community.spiceworks.com, vendor
community domains). Thread URLs below were corroborated through search-index
title matches — usually by two independent queries — but most pages could
not be loaded directly. **Re-verify every thread URL (existence, date, and
that it is still open for replies) from a normal browser before posting.**
Confidence tags: `[fetched]` page was loaded; `[search-verified]` URL +
title/summary from live search results; `[unverified]` inference or
background knowledge.

## Priority summary

| # | Venue | Verdict | Why |
|---|---|---|---|
| 1 | Hacker News (Show HN) | Primary launch | Repo qualifies cleanly under Show HN rules; SaaS-waste/ERP-regret discourse recurs monthly |
| 2 | GitHub ecosystem submissions | Primary, zero-drama | Official plugin directory + awesome-claude-code have formal, verified submission processes |
| 3 | LinkedIn | Primary broadcast | Maintainer's professional graph; practitioner text/document posts are what the 2026 algorithm rewards |
| 4 | Reddit (see section) | Split verdict | r/ClaudeCode launch-viable, r/Netsuite probably; the big generalist subs are comments-only or closed |
| 5 | NetSuite Professionals Slack | Secondary, join-first | Where NetSuite regret actually lives day-to-day; observe norms before sharing |
| 6 | IndieHackers | Tertiary | Real but thin activity; frame carefully (audience *sells* SaaS) |
| 7 | Spiceworks | Manual check needed | Alive post-Discourse-migration but unverifiable from this environment |
| 8 | lobste.rs | Deferred | Invite-only; new accounts barred from `show` tag; launch-as-first-act is their ban pattern |
| — | SAP Community | Skip | Rules of Engagement prohibit external-tool promotion outright |
| — | Oracle NetSuite Community | Caution | Oracle-run; "map what you use" framing only, never "exit NetSuite" |

---

## 1. Hacker News

**Rules.** Show HN rules [fetched norms via search]:
https://news.ycombinator.com/showhn.html — must be your own work, you must
be present in the thread, trivially try-able (a `/plugin install`-able repo
qualifies), early-stage fine. Never solicit upvotes — ring detection kills
posts. General guidelines: https://news.ycombinator.com/newsguidelines.html.
FAQ sanctions reposting a post that got no traction:
https://news.ycombinator.com/newsfaq.html.

**Format that works.** Concrete, falsifiable title; author's first comment
tells the motivation story. 2026 HN is fatigued by AI-tool launches — lead
with the domain problem (SaaS waste, ERP regret, export rights), not
"Claude plugin". The HN-legible hooks: evidence-cited verdicts, checksummed
preservation manifest, 29/100 doc-derived recipes, replay validation.

**Reply-target threads** (HN threads older than ~2 weeks are effectively
closed; re-verify openness before replying):

| URL | Title | Est. date | Why the repo answers it |
|---|---|---|---|
| https://news.ycombinator.com/item?id=49169640 [search-verified] | "Agent skills that bring team coding standards to Claude Code and Codex" | ~Aug 2–3, 2026 — likely open | Thread is about shipping process as versioned skills; the repo is that pattern applied to a business domain |
| https://news.ycombinator.com/item?id=49045271 [search-verified] | "Ask HN: How would you harden AI changes to a 1M-line legacy SaaS before review?" | late Jul/early Aug 2026 — borderline | Replay-historical-behavior validation is a direct answer |
| https://news.ycombinator.com/item?id=49148884 [search-verified] | "Ask HN: What are you working on? (August 2026)" | ~Aug 1, 2026 | Monthly thread; top-level self-promo is sanctioned here. (A similar id=49233423 appeared in one result — check which is canonical) |

**Pattern evidence (closed, do not reply — proves recurring demand):**
"Ask HN: What internal tools/SaaS replacements are you building?"
(item?id=48803546, ~Jul 6 2026); "Ask HN: Are SaaS businesses going to
zero?" (item?id=48130604, ~May 2026); "$300B Evaporated. The
SaaS-Pocalypse Has Begun" (item?id=46911267, ~Jan–Feb 2026); "Ask HN: What
is the future of SaaS when things are this easy to build?"
(item?id=46169788, ~Dec 2025); "Ask HN: How are you cleaning and
transforming data before imports/uploads?" (item?id=43986417, ~May 2025 —
Salesforce/Workday/NetSuite export pain). The internal-tools Ask HN recurs
every few months — worth watching for the next occurrence.

**Risks.** Flagging of anything marketing-scented; AI-launch fatigue;
lottery-like traffic (mitigation: the FAQ-sanctioned repost).

## 2. GitHub ecosystem (verified submission channels)

- **anthropics/claude-plugins-official** [fetched] — official plugin
  directory (33k+ stars). Third-party plugins enter `/external_plugins` via
  the submission form at `clau.de/plugin-directory-submission`, with quality
  and security review. Highest-value single submission for the plugin.
- **hesreallyhim/awesome-claude-code** [fetched] — ~52k stars. Submissions
  **only via the issue form** (PRs rejected); resource must be ≥14 days old
  with ongoing development OR ≥100 stars; factual non-salesy description, no
  emojis; the maintainer explicitly warns against treating the list as a
  marketing channel. Submit once, matter-of-factly.
- Also: anthropics/skills repo, awesome-claude-skills (~13k stars),
  claudemarketplaces.com [search-verified].
- **Claude Discord** (~120k members, invite
  discord.com/invite/6PPFFzqPDZ) [search-verified] — channel norms
  unverified; look for a #showcase-style channel before posting.

## 3. LinkedIn (maintainer's broadcast channel)

**2026 algorithm reality** [search-verified across several sources]:
external links in the post body cost ~60% of reach, and the
link-in-first-comment workaround is now penalized too — post native text
first, add the repo link in a comment after engagement starts, or name the
repo in plain text. Best formats: first-person practitioner text posts
(~1,200–1,500 chars, hook in the first 210) and document/carousel PDF posts
(~5x image CTR). One substantial post per week beats daily. Hashtags are
hygiene only (3–5, end of post). Tue–Thu mornings, B2B.

**The conversation to join.** ERP-failure discourse anchors on voices like
Eric Kimberling (Third Stage Consulting) posting named failure post-mortems;
SaaS-waste discourse re-erupts around vendor research reports — Zylo's 2026
SaaS Management Index (avg. org wastes $19.8M/yr on unused licenses; ~50%
of licenses underutilized monthly) and Flexera's 2026 State of ITAM (61% of
IT leaders had unplanned SaaS costs derail projects) [search-verified].
Commenting substantively on those threads, and posting a sanitized
KEEP/SIMPLIFY/DROP mini-case-study as a document post, is the native move.
LinkedIn ITAM/SAM Groups are historically low-signal; feed posts win.

## 4. Reddit

**Access caveat (worse than the general one):** Reddit blocks Anthropic's
fetcher AND filters out of the web-search index available here, so **no
thread URLs could be verified and none are listed — none were invented.**
Rules below come from third-party rule databases (cited in the drafts
folder) plus model background knowledge, tagged with confidence. For each
sub: the maintainer runs the listed searches (sorted by new), picks live
threads, and adapts the reply templates in
`drafts/reddit-reply-templates.md`.

| Subreddit | Launch post viable? | Strategy | Rules confidence |
|---|---|---|---|
| r/ClaudeCode (~355k, most active) | **Yes — plugin writeups are a native genre** | Technical writeup post, repo link inline is normal | Medium |
| r/Netsuite (~30–40k) | **Probably — verify sidebar first** | Substantive tool post, NetSuite-recipe angle | Low |
| r/salesforce (~500k) | Marginal | Non-AI framing ("open-source audit protocol"), or comments; flair likely required | Low |
| r/sysadmin (~1M) | Marginal | Methodology war-story text post, link in comments; automod filters links from low-history accounts | Med-high |
| r/smallbusiness (~1.5–2M) | **No** — promo only in weekly promo thread | Helpful comments in cost/export threads only | High |
| r/msp (~160–200k) | **No standalone post** | Disclosed comments only, after building comment history; most vendor-hostile sub of the set | Medium |
| r/ExperiencedDevs (~1M) | **No — rules effectively prohibit tool posts** | Comments in build-vs-buy / rewrite-validation threads; link only if asked | Medium |

Per-sub notes:

- **r/sysadmin** — no advertising incl. own blog/product; account ≥24h,
  body text required, no URL shorteners; "low-quality or LLM-created
  content is disallowed" and enforced with enthusiasm — anything that
  smells AI-written gets flamed. Recurring archetypes: license true-up
  dread, "found N unused M365 licenses", renewal-season rants. Searches:
  `site:reddit.com/r/sysadmin "saas sprawl"`, `"license audit"`,
  `"what do we actually use"`.
- **r/msp** — vendor-skeptical to the point of maintaining suspect-account
  lists; affiliation disclosure mandatory and possibly still insufficient.
  Archetypes: "client SaaS spend out of control", "client wants to cancel
  X, how do we get their data out" (extraction recipes fit MSP offboarding
  exactly). Searches: `site:reddit.com/r/msp saas spend`,
  `"get their data out"`.
- **r/ExperiencedDevs** — discussion questions only; replay-validation is
  genuinely on-topic in "how do you validate a rewrite" threads. Searches:
  `site:reddit.com/r/ExperiencedDevs "build vs buy"`,
  `rewrite validate parity`.
- **r/smallbusiness** — high-frequency "drowning in subscriptions" and
  "QuickBooks/HubSpot price hike, how do I export and leave" threads; the
  QuickBooks/HubSpot recipes are direct comment material. Searches:
  `site:reddit.com/r/smallbusiness "too many subscriptions"`,
  `quickbooks leaving export`.
- **r/Netsuite** — best genuine-fit sub; practitioner-heavy, lives with
  implementation regret; free tools with substance historically well
  received; small sub so a flop is public. Searches:
  `site:reddit.com/r/netsuite leaving OR export OR cancel`,
  `"get our data out"`, `renewal price increase`.
- **r/salesforce** — ISV-spam fatigue plus 2026 Agentforce-AI fatigue:
  "AI agent tool" framing could backfire. Archetypes: unused-license audits
  before true-up, org cleanup, weekly-export pain. Searches:
  `site:reddit.com/r/salesforce unused licenses`,
  `full data export backup leaving`.
- **r/ClaudeCode / r/ClaudeAI** — lowest rule risk, highest noise floor
  (dozens of plugin announcements weekly); differentiation carries the
  post, and "real-world non-coding uses of Claude Code" is the strong hook.
  r/ClaudeAI is the secondary crosspost under a showcase flair.

## 5. NetSuite Professionals Slack

~10,000+ members; join via https://netsuiteprofessionals.com/slack/ (email
invite); public archive at /slack-archive/ [search-verified; domain
egress-blocked]. This is where day-to-day NetSuite implementation pain and
"what are we actually paying for" conversations happen. Self-promo norms
unverified — join, read #general/#announcements norms, participate for a
week or two, then share once with disclosure. The extraction-recipe corpus
(NetSuite recipe included) and the verify-a-recipe good-first-contribution
are the natural offers.

## 6. IndieHackers

Alive in 2026 but well below its 2019–21 peak; treat as mid-tier
[search-verified]. No strict sitewide self-promo rule; code of conduct at
https://www.indiehackers.com/code-of-conduct plus per-group posting
guidelines. Narrative + numbers posts work; pure launches don't. **Framing
risk:** IH members *sell* SaaS — frame as "know what your customers
actually use / make exits trustworthy", not "help people drop SaaS".

Candidate reply targets (IH threads stay open; dates unverified,
low-visibility):

- https://www.indiehackers.com/post/the-uncomfortable-truth-about-ai-tool-pricing-in-2026-92944b6a4d [search-verified]
- https://www.indiehackers.com/post/most-saas-subscriptions-aren-t-worth-it-dfff617e78 [search-verified]
- https://www.indiehackers.com/post/which-saas-do-you-pay-for-as-an-indie-hacker-131cca2b19 [search-verified]
- https://www.indiehackers.com/post/saas-companies-love-subscription-pricing-do-small-businesses-179d5af273 [search-verified]

Expect single-digit engagement; low-effort secondary venue.

## 7. Spiceworks Community

Migrated to Discourse in March 2024; operational per third-party status
monitors, but no 2025–26 press found and Discourse-era content is poorly
indexed — zero relevant threads findable from here, and the guidelines page
is egress-blocked. Historically: vendor-flagged accounts, disclosure
required, promotion confined to designated areas [unverified]. **Action:
browse manually before investing anything.** If alive, the ITAM/licensing
angle fits.

## 8. lobste.rs — deferred

Invite-only (https://lobste.rs/about); authored-by submissions require the
"authored by" checkbox and <~25% self-promo share; **new users cannot use
the `show` tag at all**, and a fresh account whose first act is a launch
post is their canonical ban pattern [search-verified via meta threads].
No genuine recent reply-target threads found. Realistic path, if ever:
get invited (the "author of a submitted story" route), participate for
weeks, then submit with the checkbox. Value is credibility, not reach.

## Skip list

- **SAP Community** — Rules of Engagement prohibit content driving traffic
  to non-SAP products; re-affirmed Feb 2026 [search-verified]. A
  methodology-only article might pass review; a repo link won't. Skip.
- **Oracle NetSuite Community** — active (SuiteWorld 2026 threads through
  June 2026) but Oracle-run; "exit" framing is a fast way to get moderated.
  At most, "map what you actually use" framing. Low priority.
- **ERPfocus** — publication, no forum; the move would be pitching a
  bylined article (customerteam@erpfocus.com), which is a separate decision.
- **Panorama Consulting / Third Stage blogs** — sources of failure case
  studies to cite, not venues to post in.
- **Acumatica Community** — moderator-gated, marketplace partner-gated; not
  worth it unless targeting Acumatica.

## Timely angle worth knowing

**Dynamics GP end-of-life:** new subscription sales ended April 1, 2026;
support ends 2029, product EOL April 2031; Microsoft is actively pushing
NAV/GP/SL customers to migrate (Microsoft blog, July 28, 2026)
[search-verified]. GP customers deciding what to preserve before a forced
migration are the preservation-manifest use case exactly. The repo has
Dynamics 365 recipes (Business Central, Sales) already; a GP-focused post
or recipe would meet a live, dated need.
