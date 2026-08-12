// Where the app loads protocol data (skill.md, references, recipes) from.
// Default: the co-hosted ./data/ directory (kept in sync by
// scripts/sync_web_data.py). A standalone deployment that doesn't ship the
// data files can point this at a raw.githubusercontent URL pinned to a commit
// SHA, e.g.:
//   window.SR_DATA_BASE = "https://raw.githubusercontent.com/chrbailey/saas-rebuild/<sha>/web/data/";
window.SR_DATA_BASE = "data/";
