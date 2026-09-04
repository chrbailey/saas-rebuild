# DRAFT — FOR HUMAN REVIEW — Reddit reply templates by thread archetype

> Reddit could not be reached from the research environment, so these are
> templates keyed to the recurring thread archetypes each sub is known
> for — NOT replies to specific threads. Workflow: run the per-sub
> searches in `../venue-map.md`, pick a live thread (days old, not
> months), adapt the matching template to what the person actually asked,
> and cut anything that doesn't answer their question. Always: answer
> first, repo second, "I built this" disclosure whenever the repo is
> named. In r/sysadmin and r/msp, put links in a comment only, expect
> automod filtering, and never post anything that reads AI-written.

---

## Archetype A — "License true-up / renewal is coming, how do I know what we actually use?" (r/sysadmin, r/salesforce)

Answer the question first with the method, not the tool:

Start from evidence classes, not from the vendor's adoption dashboard:
(1) structural — what's configured, which roles exist, which integrations
have credentials; (2) runtime — login/audit logs, transaction counts,
scheduled-job history over as long a window as retention allows; (3) human
— a short interview pass, because the workaround spreadsheet nobody
mentions is where the real process lives. Then classify each feature
KEEP / SIMPLIFY / DROP / DEFER and write down the evidence for each call,
because the renewal negotiation is exactly the place someone will
challenge it. Two traps: configured ≠ used, and a 30-day quiet log ≠
unused (year-end processes exist).

Optional second paragraph (only if the thread is tool-friendly):

I got tired of doing this ad hoc, so I open-sourced the protocol I use —
schemas that reject verdicts without evidence attached, plus documented
export routes for 29 common B2B apps (disclosure: I built it; MIT;
saas-rebuild on GitHub). It runs in the browser with your own Anthropic
API key, nothing to install, if you want to look before committing to it:
https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app

## Archetype B — "We're leaving [vendor], how do we get our data out?" (r/Netsuite, r/salesforce, r/smallbusiness, r/msp)

Answer first:

Before anything else: inventory every data class you can reach — records,
attachments/files, audit history, configuration, saved reports,
integration configs — and rehearse the export while the contract is
healthy, not during the notice period. Check the terms for a
post-termination retrieval window (some vendors document one; many don't),
and checksum what you export so you can prove completeness later. The
things people consistently lose: attachments, audit trails, and the
configuration that explains why the data looks the way it does.

Optional second paragraph:

I maintain an open corpus of exactly this — documented export rights and
extraction routes per vendor, cited to their own docs with retrieval
dates (disclosure: mine, MIT — saas-rebuild on GitHub, recipes under
skills/saas-rebuild/corpus/). The [vendor] recipe lists the routes in
preference order with rate limits and gotchas. It's doc-derived and
marked unverified — if you actually run this export, filing what matched
reality (or didn't) makes the recipe trustworthy for the next person. The
recipes are readable without cloning anything at
https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app/#/corpus

## Archetype C — "Client SaaS spend is out of control" (r/msp — comments only, disclosed, after building history)

For MSPs the leverage is making the audit a productized, evidence-based
engagement instead of a spreadsheet argument: per client tenant, join
what's configured against what runtime logs show actually ran, classify
with reasons, and hand the client a defensible KEEP/DROP list plus a
rehearsed export of everything before any cancellation. The export
rehearsal is the differentiator — clients remember the MSP that had their
data safe before the vendor conversation started. (Disclosure if linking:
I built an open MIT protocol + per-vendor export-route corpus for this —
saas-rebuild on GitHub.)

## Archetype D — "Build vs buy / replacing a SaaS with internal tooling" (r/ExperiencedDevs — prose only, link only if asked)

The build-vs-buy debate usually skips the measurement step: the honest
comparison isn't "the product" vs "what we'd build," it's "the subset of
the product this org demonstrably uses" vs what you'd build — and that
subset is an empirical question you can answer from config, logs, and
interviews before writing a line. Two design rules if you do replace:
preserve everything exportable first (verdicts about what to rebuild
should never decide what to keep), and accept the replacement by replaying
historical inputs against it rather than by demo — held-out cases,
divergences triaged into intended vs unexplained. The rebuild is usually
hybrid: the deterministic core wants to be boring tested code; shared
state wants a real database; only the reasoning/orchestration layer is a
candidate for an agent.

## Archetype E — "Drowning in subscriptions" (r/smallbusiness — helpful comment, link only if asked)

A one-afternoon version of the audit: for each subscription, write down
(1) the workflows someone actually ran last quarter — not features, actual
"Maria does X every Friday" workflows; (2) what happens if it disappeared
tomorrow; (3) whether you can export your data today and when you last
tried. Cancel-by-default anything with an empty first line, and rehearse
the export on anything you keep — export access has a way of mattering
exactly when the relationship sours. The pattern I see doing this
professionally: the keep-list is short but real, and the export rehearsal
finds a surprise about half the time.
