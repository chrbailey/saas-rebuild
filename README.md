# saas-rebuild

A Claude Code skill that helps you **tear down a SaaS application you
administer and plan its replacement as a Claude skill**.

Most teams use a fraction of the software they pay for. This skill runs a
systematic five-phase pipeline to find out which fraction, and what a leaner
replacement looks like:

1. **Scope** — which app, which modules, who uses it.
2. **Feature inventory** — a breadth-first browser walk of every screen,
   form, report, and setting (via browser automation on *your* authenticated
   session; the skill never handles credentials).
3. **Usage evidence** — record counts, empty modules, stale data, exports,
   and structured user interviews. Used-vs-unused verdicts cite evidence,
   not vibes.
4. **Extraction map** — the best route to get each kept entity's data out
   (API/connector → built-in export → report CSV → scrape as last resort).
5. **Rebuild plan** — a milestone-based plan to rebuild the kept workflows
   as a Claude skill: schemas, data corpus, CSV bridges, audit trail,
   parallel-run, cutover.

Outputs land in `~/Dev/teardowns/<app-slug>/` with a resumable state file, so
a teardown can span multiple sessions (and wait for interview answers).

## Install

**As a plugin (recommended):**

```
/plugin marketplace add chrbailey/saas-rebuild
/plugin install saas-rebuild
```

**Manual:** copy `skills/saas-rebuild/` into `~/.claude/skills/`.

**Project-level:** copy `skills/saas-rebuild/` into your repo's
`.claude/skills/` — everyone who clones the repo gets it.

## Use

Say things like:

- "Tear down our CRM"
- "What do we actually use in [app]?"
- "Replace [app] with a skill"

You'll need a browser-automation MCP connected (e.g. Claude in Chrome) for
the inventory phase, and admin access to the app you're analyzing.

## Share your teardown — let's replace SaaS collectively

Every teardown produces the same artifact: a feature map with evidence-backed
KEEP / SIMPLIFY / DROP / DEFER verdicts. Those maps are far more valuable
shared than siloed:

- **The used-fraction repeats.** If your team uses 20% of your CRM, odds are
  the next team uses a similar 20%. One shared teardown is a head start for
  everyone on the same app or category.
- **Others uncover what you missed.** A second teardown of the same app finds
  the modules, workflows, and workarounds your walk skipped — and gaps in
  this pipeline itself (a phase that needs a step, a signal the schema
  doesn't capture).
- **Convergent verdicts become community skills.** When several teardowns of
  an app category agree on the KEEP set, that's a spec: the community can
  build and maintain one replacement skill instead of each team rebuilding
  alone.

**How to post results:** open a
[Teardown Report issue](../../issues/new?template=teardown-report.yml) with
the app (or just its category, if you'd rather not name it), feature counts
by verdict, your top "why unused" reasons, and anything the pipeline missed.
PRs improving the phases, templates, or schema are very welcome.

**Sanitize before you share.** Your teardown output contains your business
data — the report you post must not. No record contents, no exports, no
customer or employee names, no screenshots with real data, no internal URLs.
Share the *structure* (feature names, verdicts, why-categories, rough record
counts as ranges). If in doubt, leave it out — a verdict table with no
numbers is still useful.

## Responsible use

This skill is for analyzing **your own tenant** of software you legitimately
administer, for migration planning. It will not probe other tenants or other
users' private data, and it prefers official exports/APIs over scraping.
Check your vendor agreement before bulk-extracting data.

## License

MIT
