# SaaS Rebuild — web workspace

A fully static, bring-your-own-key web app that runs the SaaS Rebuild teardown
protocol (and the export-compliance reference skill) in the browser, guided by
Claude. Nothing to install and no account: open the hosted copy, paste an
Anthropic API key, and start.

**Hosted:** [saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app](https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app)

## What you can do with it

- **Run a teardown as a chat.** Pick the protocol (teardown or the
  export-compliance reference), pick a model (Claude Opus 5 by default;
  Sonnet 5 or Haiku 4.5 for cheaper passes), describe the tenant you
  administer, and paste evidence: exports, audit-log samples, contract line
  items, interview notes. The assistant opens with the Phase 0 scoping
  questions and works through the protocol from there.
- **Download every artifact.** `teardown.json`, `feature-inventory.json`,
  `usage-analysis.md`, `preservation-manifest.json`, `REBUILD_PLAN.md`, and
  the rest arrive as fenced blocks with a download button. The web preamble
  instructs the assistant to re-emit the full artifact, not a diff, whenever
  state changes, so a download is complete.
- **Attach context.** Tick any of the three reference playbooks (extraction,
  process mining, dependency graph) to append it to the system prompt, and
  attach any of the 29 extraction recipes for the application you are
  auditing.
- **Browse the recipe corpus** at `#/corpus`, filterable by name, vendor, or
  category, with no API key required. Each recipe page shows the export-rights
  summary, routes, and bibliography, and offers the JSON for download.
- **Pause and resume.** Sessions autosave to the browser and can be exported
  and re-imported as JSON, the web analog of the protocol's resumable
  `teardown.json`. A transcript can be downloaded as Markdown.

What it cannot do: it has no connector into your tenant and no filesystem.
You run the exports and queries yourself and paste sanitized results; the
assistant is instructed never to ask for credentials. A full teardown is a
long, multi-phase conversation with a large protocol prompt, so expect real
API spend on a serious engagement; prompt caching is enabled on the system
block to reduce it.

## How it works

- **No backend.** Everything in this directory is static. The user's Anthropic
  API key is stored in browser localStorage and sent only to
  `api.anthropic.com`, using the documented
  `anthropic-dangerous-direct-browser-access: true` CORS opt-in header. The key
  never touches any server operated by this project. Everything you paste into
  the chat goes to Anthropic's API under your own key and account terms.
- **The protocol is the system prompt.** `data/skill.md` (a synced copy of
  `skills/saas-rebuild/SKILL.md`) is wrapped in a web-adaptation preamble: no
  filesystem, so artifacts (`teardown.json`, `usage-analysis.md`,
  `preservation-manifest.json`, …) are emitted as fenced code blocks that the
  app turns into downloadable files. Prompt caching is enabled on the system
  block, since the protocol prompt is large and stable.
- **Recipes are first-class.** The 29 schema-validated extraction recipes are
  browsable at `#/corpus` and attachable to a conversation as context. They
  are `doc-derived-unverified` route hypotheses; verify every route against
  your tenant and entitlements before relying on it.
- **Sessions are resumable.** Conversations autosave to localStorage and can be
  exported/imported as JSON — the web analog of the protocol's resumable
  `teardown.json` state file.

## Local development

No build step. Serve the directory with any static server:

```bash
cd web && python3 -m http.server 8080
```

(A plain `file://` open won't work because the app fetches `data/` files.)

## Keeping data in sync

`web/data/` is generated from the canonical skill sources. After editing
anything under `skills/`, re-run:

```bash
python3 scripts/sync_web_data.py
```

and commit the result. CI-friendly: the script is deterministic and idempotent.

## Deployment

The hosted copy is a Vercel project linked to this GitHub repository:

- Root directory: `web`
- Framework preset: **Other**
- Build command: *(none)*
- Output directory: `.`

Every push to `main` auto-deploys to
[saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app](https://saas-rebuild-workspace-christopher-baileys-projects-7c988399.vercel.app).
Any other static host works the same way, since the app is plain HTML, CSS,
and JavaScript with the protocol data alongside it; `config.js` shows how to
point a standalone deployment at data files served from elsewhere.
