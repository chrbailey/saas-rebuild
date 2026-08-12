# SaaS Rebuild — web workspace

A fully static, bring-your-own-key web app that runs the SaaS Rebuild teardown
protocol (and the export-compliance reference skill) in the browser, guided by
Claude.

## How it works

- **No backend.** Everything in this directory is static. The user's Anthropic
  API key is stored in browser localStorage and sent only to
  `api.anthropic.com`, using the documented
  `anthropic-dangerous-direct-browser-access: true` CORS opt-in header. The key
  never touches any server operated by this project.
- **The protocol is the system prompt.** `data/skill.md` (a synced copy of
  `skills/saas-rebuild/SKILL.md`) is wrapped in a web-adaptation preamble: no
  filesystem, so artifacts (`teardown.json`, `usage-analysis.md`,
  `preservation-manifest.json`, …) are emitted as fenced code blocks that the
  app turns into downloadable files. Prompt caching is enabled on the system
  block, since the protocol prompt is large and stable.
- **Recipes are first-class.** The 29 schema-validated extraction recipes are
  browsable at `#/corpus` and attachable to a conversation as context.
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

## Deploying

Deploy the `web/` directory as a static site on Vercel (or any static host):

- Framework preset: **Other**
- Root directory: `web`
- Build command: *(none)*
- Output directory: `.`
