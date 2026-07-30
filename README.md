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

## Responsible use

This skill is for analyzing **your own tenant** of software you legitimately
administer, for migration planning. It will not probe other tenants or other
users' private data, and it prefers official exports/APIs over scraping.
Check your vendor agreement before bulk-extracting data.

## License

MIT
