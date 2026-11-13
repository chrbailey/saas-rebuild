#!/usr/bin/env python3
"""Assemble one portable rebuild spec from a run directory.

Standard library only, and no judgment: every line of the spec is copied or
counted from files the run already wrote. A feature goes under "build" only
when it is marked used and carries a citation that supports that usage (a
runtime measure on a live run, a dated document on a document-based one),
under "do_not_build" only with a DROP verdict or a "never" usage, and
everything else stays "undecided".
Recorded history (replay pairs) becomes the acceptance tests.

    python build_spec.py <run-dir>

Writes rebuild-spec.json and rebuild-spec.html next to the inputs.
"""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.12.0"
USED = {"daily", "weekly", "rare", "workaround-external", "workaround-internal"}
INSTRUCTIONS = [
    "Build every item under build, and nothing else.",
    "Do not build anything under do_not_build or undecided. Undecided means the evidence is "
    "missing, not that the feature is unused; ask the owner before adding or dropping it.",
    "Every case under acceptance_tests is real recorded history. Given its input, the rebuild "
    "must produce its expected output. A rebuild that fails a case is not finished.",
    "Load the files under data before testing. A data set whose status is not exported has "
    "not been saved yet and must be saved before the old app is cancelled.",
    "Read limits before trusting this spec. They say what the evidence does not cover.",
]


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_pairs(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def proof(feature: dict[str, Any], usage_only: bool) -> list[dict[str, Any]]:
    rows = []
    for item in feature.get("evidence", []):
        if usage_only and "usage" not in item.get("supports", []):
            continue
        row = {"evidence_id": item.get("evidence_id", ""), "claim": item.get("claim", ""),
               "source": item.get("source", "")}
        if isinstance(item.get("measure"), dict):
            row["measure"] = item["measure"]
        rows.append(row)
    return rows


def classify(feature: dict[str, Any]) -> str:
    usage, verdict = feature.get("usage"), feature.get("verdict")
    if verdict == "DROP" or usage == "never":
        return "do_not_build"
    if usage in USED and proof(feature, usage_only=True):
        return "build"
    return "undecided"


def build(run_dir: Path) -> dict[str, Any]:
    state = load(run_dir / "teardown.json", {})
    auto = load(run_dir / "autopilot.json", {})
    features = [f for f in load(run_dir / "feature-inventory.json", []) if isinstance(f, dict)]
    manifest = load(run_dir / "preservation-manifest.json", {})
    pairs = load_pairs(run_dir / "pairs.jsonl")
    app = state.get("app") or {}
    access = auto.get("access_level") or "unknown"

    spec: dict[str, Any] = {
        "schema_version": VERSION,
        "spec_id": f'{app.get("slug") or run_dir.name}-rebuild-spec',
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app": {"name": app.get("name") or run_dir.name, "slug": app.get("slug") or run_dir.name},
        "source": {
            "teardown_id": state.get("teardown_id", ""),
            "access_level": access,
            "role": (auto.get("role") or {}).get("name"),
            "scope": {"admin": "What an administrator of this account could see.",
                      "unknown": "What the available evidence shows."}.get(
                          access, "What one signed-in account could see."),
        },
        "instructions": INSTRUCTIONS,
        "build": [], "do_not_build": [], "undecided": [], "data": [], "acceptance_tests": [],
        "limits": [],
    }
    for f in features:
        bucket = classify(f)
        base = {"id": f.get("id", ""), "name": f.get("name", "")}
        if bucket == "build":
            spec["build"].append({**base, "kind": f.get("kind", ""), "where": f.get("nav_path", ""),
                                  "usage": f["usage"],
                                  "decision": f.get("verdict") if f.get("verdict") in ("KEEP", "SIMPLIFY")
                                  else "needs-owner",
                                  "proof": proof(f, usage_only=True)})
        elif bucket == "do_not_build":
            spec["do_not_build"].append({**base, "reason": f.get("why", ""),
                                         "proof": proof(f, usage_only=False)})
        else:
            empty = (f.get("observed_signals") or {}).get("empty_state") is True
            spec["undecided"].append({**base, "state": "empty-so-far" if empty else "not-checked",
                                      "reason": f.get("why", "")})
    for a in manifest.get("artifacts", []):
        if isinstance(a, dict):
            spec["data"].append({"id": str(a.get("id", "")), "status": str(a.get("status", "")),
                                 "path": a.get("path"), "sha256": a.get("sha256")})
    for p in pairs:
        if p.get("pair_type") == "replay" and p.get("label_authority") == "system-of-record":
            spec["acceptance_tests"].append({"id": p.get("pair_id", ""), "given": p.get("input"),
                                             "expect": p.get("output"), "authority": "system-of-record"})

    limits = spec["limits"]
    documents_only = bool(spec["build"]) and not any(
        "measure" in row for item in spec["build"] for row in item["proof"])
    if documents_only:
        limits.append("Built from documents, not from the running system. Usage is what the papers "
                      "show, not a count taken inside the app.")
    if access not in ("admin", "unknown"):
        limits.append("Built from one non-admin login. It covers that role, not the whole company account.")
    if not spec["acceptance_tests"]:
        limits.append("No recorded history cases yet, so a rebuild cannot be tested against real results.")
    if not spec["data"]:
        limits.append("No saved data is listed yet. Save the exports before relying on this spec.")
    elif any(d["status"] != "exported" for d in spec["data"]):
        limits.append("Some data sets are not saved yet.")
    if any(b["decision"] == "needs-owner" for b in spec["build"]):
        limits.append("Items marked needs-owner are in use, but nobody has yet said which of them "
                      "the work depends on. They are listed to be built in full until an owner says otherwise.")
    if spec["undecided"]:
        limits.append(f'{len(spec["undecided"])} features are undecided. They are left out of the build, '
                      "not declared unused.")
    return spec


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


CSS = """:root{--bg:#f6f5f1;--card:#fff;--ink:#1c1b19;--mute:#6b6862;--line:#e3e0d8;--go:#1f7a4d;--no:#b3372f;--wait:#b7791f}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--card:#201f1c;--ink:#f1efe9;--mute:#a09c93;--line:#34322d;--go:#5fc28f;--no:#ef7b72;--wait:#e0b05a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 64px}h1{font-size:28px;margin:0 0 4px}h2{font-size:20px;margin:0 0 10px}
.sub{color:var(--mute)}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin-top:16px}
.go{border-left:8px solid var(--go)}.no{border-left:8px solid var(--no)}.wait{border-left:8px solid var(--wait)}
ul,ol{margin:0;padding-left:22px}li{margin:6px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}
.n{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}.n b{display:block;font-size:34px}
@media(max-width:640px){.grid{grid-template-columns:repeat(2,1fr)}}small{color:var(--mute)}"""


def render_html(spec: dict[str, Any]) -> str:
    out: list[str] = []
    add = out.append
    add("<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f'<title>{esc(spec["app"]["name"])} — rebuild spec</title><style>{CSS}</style></head><body><main>')
    add(f'<h1>{esc(spec["app"]["name"])} — rebuild spec</h1>'
        f'<div class=sub>{esc(spec["source"]["scope"])} Generated {esc(spec["generated_at"][:10])}. '
        "The machine-readable copy is rebuild-spec.json in the same folder.</div>")
    add("<div class=grid>")
    for label, key in (("to build", "build"), ("not to build", "do_not_build"),
                       ("undecided", "undecided"), ("history tests", "acceptance_tests")):
        add(f'<div class=n><b>{len(spec[key])}</b>{label}</div>')
    add("</div>")
    if spec["limits"]:
        add("<section class='card wait'><h2>Read this first</h2><ul>")
        for item in spec["limits"]:
            add(f"<li>{esc(item)}</li>")
        add("</ul></section>")
    add("<section class='card go'><h2>Build these</h2>")
    if spec["build"]:
        add("<ul>")
        for b in spec["build"]:
            claims = " ".join(esc(p["claim"]) for p in b["proof"])
            tag = "" if b["decision"] != "needs-owner" else " <small>(in use; owner to confirm)</small>"
            add(f'<li><b>{esc(b["name"])}</b>{tag}<br><small>{claims}</small></li>')
        add("</ul>")
    else:
        add("<div class=sub>Nothing has evidence of use yet.</div>")
    add("</section><section class='card no'><h2>Do not build these</h2>")
    if spec["do_not_build"]:
        add("<ul>" + "".join(f'<li><b>{esc(d["name"])}</b><br><small>{esc(d["reason"])}</small></li>'
                             for d in spec["do_not_build"]) + "</ul>")
    else:
        add("<div class=sub>Nothing is proven unused yet. That needs evidence covering the account's whole life.</div>")
    add("</section><section class='card wait'><h2>Undecided — left out, not declared unused</h2>")
    for state, title in (("empty-so-far", "Opened and empty so far"), ("not-checked", "Not checked yet")):
        names = [u["name"] for u in spec["undecided"] if u["state"] == state]
        if names:
            add(f'<p><b>{title} ({len(names)}):</b> {esc(", ".join(names))}</p>')
    add("</section><section class=card><h2>Rules for whoever builds it</h2><ol>")
    for item in spec["instructions"]:
        add(f"<li>{esc(item)}</li>")
    add("</ol></section></main></body></html>")
    return "".join(out)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python build_spec.py <run-dir>", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1]).expanduser()
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 2
    spec = build(run_dir)
    (run_dir / "rebuild-spec.json").write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
    (run_dir / "rebuild-spec.html").write_text(render_html(spec), encoding="utf-8")
    print(run_dir / "rebuild-spec.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
