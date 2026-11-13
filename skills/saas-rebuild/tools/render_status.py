#!/usr/bin/env python3
"""Render an autopilot run directory into one self-refreshing status.html.

Standard library only. Reads whichever of teardown.json, autopilot.json,
feature-inventory.json and preservation-manifest.json exist, so it is safe to
run after every step of a run that is still in progress.

    python render_status.py <run-dir>
"""

from __future__ import annotations

import html
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USED = {"daily", "weekly", "rare", "workaround-external", "workaround-internal"}
VERDICTS = ("KEEP", "SIMPLIFY", "DROP", "DEFER")
STEP_MARK = {"done": "✓", "running": "●", "pending": "○", "skipped": "–", "blocked": "!"}
REFRESH_SECONDS = 5


def load(path: Path, default: Any) -> Any:
    """Return parsed JSON, or default when the file is absent or mid-write."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def summarize(features: list[dict[str, Any]]) -> dict[str, Any]:
    used = sum(1 for f in features if f.get("usage") in USED)
    never = sum(1 for f in features if f.get("usage") == "never")
    return {
        "total": len(features),
        "used": used,
        "never": never,
        "unknown": len(features) - used - never,
        "verdicts": {v: sum(1 for f in features if f.get("verdict") == v) for v in VERDICTS},
    }


def usage_label(usage: Any) -> str:
    if usage in (None, "", "unknown"):
        return "not yet known"
    if usage == "rare":
        return "used"  # the rules default to "rare" when cadence is not measured
    return str(usage).replace("-", " ")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


CSS = """
:root{--bg:#f6f5f1;--card:#fff;--ink:#1c1b19;--mute:#6b6862;--line:#e3e0d8;
--keep:#1f7a4d;--simp:#b7791f;--drop:#b3372f;--defer:#5b6472;--accent:#2b5fd9}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--card:#201f1c;--ink:#f1efe9;
--mute:#a09c93;--line:#34322d;--keep:#5fc28f;--simp:#e0b05a;--drop:#ef7b72;
--defer:#9aa3b2;--accent:#8fb0ff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:20px;margin:0}
h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:0 0 10px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.chip{font-size:13px;font-weight:600;padding:4px 12px;border-radius:999px;
border:1px solid var(--line);background:var(--card)}
.chip.run{color:var(--accent)}.chip.done{color:var(--keep)}.chip.stop{color:var(--drop)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px;margin-top:16px}
.big{font-size:44px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
.big small{font-size:20px;font-weight:500;color:var(--mute)}
.sub{color:var(--mute);margin-top:6px}
.now{font-size:18px}
ul{list-style:none;margin:0;padding:0}
li{padding:6px 0;display:flex;gap:10px}
.mark{width:1.2em;text-align:center;flex:none}
.s-done .mark{color:var(--keep)}.s-running .mark{color:var(--accent)}
.s-blocked .mark{color:var(--drop)}.s-pending,.s-skipped{color:var(--mute)}
.detail{color:var(--mute)}
.bars{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.bar{border-top:4px solid;padding-top:8px}
.bar b{display:block;font-size:26px;font-variant-numeric:tabular-nums}
.bar.KEEP{border-color:var(--keep)}.bar.SIMPLIFY{border-color:var(--simp)}
.bar.DROP{border-color:var(--drop)}.bar.DEFER{border-color:var(--defer)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-top:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600;border-top:0}
.v{font-weight:700;white-space:nowrap}
.v.KEEP{color:var(--keep)}.v.SIMPLIFY{color:var(--simp)}.v.DROP{color:var(--drop)}.v.DEFER{color:var(--defer)}
.note{border-left:3px solid var(--simp);padding-left:12px;color:var(--mute);margin-top:12px}
footer{color:var(--mute);font-size:13px;margin-top:20px}
"""


def render(run_dir: Path) -> str:
    state = load(run_dir / "teardown.json", {})
    auto = load(run_dir / "autopilot.json", {})
    features = load(run_dir / "feature-inventory.json", [])
    if not isinstance(features, list):
        features = []
    features = [f for f in features if isinstance(f, dict)]
    manifest = load(run_dir / "preservation-manifest.json", {})

    app = (state.get("app") or {}).get("name") or run_dir.name
    status = state.get("status", "in-progress")
    # A first pass ends at phase 3, and the state schema reserves "complete"
    # for a finished teardown, so the report step marks the end of the pass.
    first_pass_done = any(
        isinstance(s, dict) and s.get("id") == "report" and s.get("status") == "done"
        for s in auto.get("steps", [])
    )
    live = status == "in-progress" and not first_pass_done
    needs = [n for n in auto.get("needs_you", []) if n]
    chip = {"complete": ("done", "Done"), "blocked": ("stop", "Stopped — needs you"),
            "abandoned": ("stop", "Abandoned")}.get(status, ("run", "Running"))
    if first_pass_done and status == "in-progress":
        chip = ("done", "First pass done")
    counts = summarize(features)
    out: list[str] = []
    add = out.append

    add("<!doctype html><html lang=en><head><meta charset=utf-8>")
    add('<meta name=viewport content="width=device-width,initial-scale=1">')
    if live:
        add(f'<meta http-equiv=refresh content="{REFRESH_SECONDS}">')
    add(f"<title>{esc(app)} — SaaS Rebuild</title><style>{CSS}</style></head><body><main>")
    add(f'<div class=top><h1>{esc(app)}</h1><span class="chip {chip[0]}">{chip[1]}</span></div>')

    add("<section class=card>")
    if counts["total"]:
        add(f'<div class=big>{counts["used"]} <small>of {counts["total"]} features '
            "show evidence of use</small></div>")
        add(f'<div class=sub>{counts["never"]} never used · {counts["unknown"]} not yet known'
            + (" · still counting" if live else "") + "</div>")
    else:
        add("<div class=big><small>Mapping the app…</small></div>")
        add("<div class=sub>The count appears here as soon as the first screens are read.</div>")
    if auto.get("access_level") in {"standard", "view-only"}:
        add("<div class=note>This account does not have admin access. These findings describe "
            "what this role can see and does, not the whole company account.</div>")
    add("</section>")

    if live and auto.get("now"):
        add(f'<section class=card><h2>Right now</h2><div class=now>{esc(auto["now"])}</div></section>')

    if needs:
        add("<section class=card><h2>Needs you (the run keeps going without these)</h2><ul>")
        for item in needs:
            add(f"<li><span class=mark>→</span><span>{esc(item)}</span></li>")
        add("</ul></section>")

    steps = [s for s in auto.get("steps", []) if isinstance(s, dict)]
    if steps:
        add("<section class=card><h2>Steps</h2><ul>")
        for step in steps:
            st = step.get("status", "pending")
            detail = f' <span class=detail>— {esc(step["detail"])}</span>' if step.get("detail") else ""
            add(f'<li class="s-{esc(st)}"><span class=mark>{STEP_MARK.get(st, "○")}</span>'
                f'<span>{esc(step.get("label"))}{detail}</span></li>')
        add("</ul></section>")

    role = auto.get("role") or {}
    if role.get("name"):
        add(f'<section class=card><h2>Your role</h2><div class=now>{esc(role["name"])}'
            f' <span class=detail>({esc(auto.get("access_level", "unknown"))} access)</span></div>')
        for label, key in (("Can", "can"), ("Cannot", "cannot")):
            if role.get(key):
                add(f'<div class=sub><b>{label}:</b> {esc(", ".join(map(str, role[key])))}</div>')
        add("</section>")

    if any(counts["verdicts"].values()):
        add("<section class=card><h2>What to do with each feature</h2><div class=bars>")
        for verdict in VERDICTS:
            add(f'<div class="bar {verdict}"><b>{counts["verdicts"][verdict]}</b>{verdict.title()}</div>')
        add("</div></section>")

    artifacts = [a for a in manifest.get("artifacts", []) if isinstance(a, dict)]
    if artifacts:
        saved = sum(1 for a in artifacts if a.get("status") == "exported")
        add("<section class=card><h2>Your data</h2>"
            f'<div class=now>{saved} of {len(artifacts)} data sets saved to this computer</div>')
        missing = [a.get("id") for a in artifacts if a.get("status") != "exported"]
        if missing:
            add(f'<div class=sub>Not saved yet: {esc(", ".join(map(str, missing)))}</div>')
        add("</section>")

    if features:
        order = {"KEEP": 0, "SIMPLIFY": 1, "DEFER": 2, "DROP": 3}
        rows = sorted(features, key=lambda f: (
            0 if f.get("usage") in USED else 1, order.get(f.get("verdict"), 4), str(f.get("name"))))
        add("<section class=card><h2>Every feature found</h2><div class=scroll><table>"
            "<tr><th>Feature</th><th>Where</th><th>Use</th><th>Verdict</th><th>Why</th></tr>")
        for f in rows:
            verdict = f.get("verdict") or ""
            add(f'<tr><td>{esc(f.get("name"))}</td><td>{esc(f.get("nav_path"))}</td>'
                f'<td>{esc(usage_label(f.get("usage")))}</td>'
                f'<td class="v {esc(verdict)}">{esc(verdict) or "—"}</td><td>{esc(f.get("why"))}</td></tr>')
        add("</table></div></section>")

    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    tail = f" · refreshes every {REFRESH_SECONDS} seconds" if live else ""
    add(f"<footer>Updated {stamp}{tail}. Counts come from cited evidence in "
        "feature-inventory.json; “not yet known” is never counted as unused.</footer>")
    add("</main></body></html>")
    return "".join(out)


def write_status(run_dir: Path) -> Path:
    """Write status.html atomically so a refreshing browser never reads half a page."""
    target = run_dir / "status.html"
    fd, tmp = tempfile.mkstemp(dir=run_dir, prefix=".status-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(render(run_dir))
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1]).expanduser()
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 2
    print(write_status(run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
