"""Command line interface.

    xscreen refresh                 download and parse the official lists
    xscreen screen parties.csv      screen a party file end to end
    xscreen diff old.csv new.csv    what changed between two runs (new hits)
    xscreen cases                   every still-open case across all runs
    xscreen explain "Acme Ltd"      show why a single name does or does not match
    xscreen audit verify|head       check or publish the audit chain
    xscreen policy show|verify      inspect or attest the country policy file
    xscreen selftest                run the built-in fixture suite

Exit codes are meaningful so this can sit in a shipping-release gate:
0 = clean, 1 = usage or infrastructure error, 2 = cases require human review,
3 = at least one BLOCKED disposition.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from . import __version__
from .audit import AuditLog
from .fetch import age_days, load_manifest, refresh, staleness_check
from .llm import BackendError, get_backend, is_offline
from .models import ScreeningResult
from .pipeline import build_index, parse_party_file, run, screen_subject
from .report import markdown_report, summary_csv
from .rules import load_policy
from .sources import ALL_SOURCES, DEFAULT_REFRESH

DEFAULT_HOME = Path.home() / "Dev" / "export-compliance"


def _paths(args) -> tuple[Path, Path, Path]:
    home = Path(args.home).expanduser()
    return home, home / "lists", home / "audit" / "screening-audit.jsonl"


# --------------------------------------------------------------------------

def cmd_refresh(args) -> int:
    _, data_dir, audit_path = _paths(args)
    codes = tuple(args.sources) if args.sources else DEFAULT_REFRESH
    print(f"Refreshing {len(codes)} source(s) into {data_dir}", file=sys.stderr)
    manifest = refresh(data_dir, codes, offline=args.offline)

    for f in manifest.files:
        status = "ERROR" if f.get("error") else f"{f.get('parties', 0)} parties"
        print(f"  {f['code']:<9} {status}", file=sys.stderr)
        if f.get("error"):
            print(f"             {f['error']}", file=sys.stderr)
        for w in f.get("warnings", []):
            print(f"             ! {w}", file=sys.stderr)
        if f.get("unmapped_columns"):
            print(f"             ! unmapped columns: {f['unmapped_columns']}", file=sys.stderr)

    print(f"\nTotal listed parties: {manifest.total_parties}", file=sys.stderr)
    print(f"Manifest digest: {manifest.digest}", file=sys.stderr)

    AuditLog(audit_path).append("lists.refresh", {
        "digest": manifest.digest,
        "total_parties": manifest.total_parties,
        "degraded": manifest.degraded,
        "degraded_reason": manifest.degraded_reason,
        "files": [{"code": f.get("code"), "sha256": f.get("sha256"),
                   "url": f.get("url"), "parties": f.get("parties"),
                   "error": f.get("error")} for f in manifest.files],
    })

    if manifest.degraded:
        print(f"\nDEGRADED: {manifest.degraded_reason}", file=sys.stderr)
        return 1
    return 0


def cmd_status(args) -> int:
    home, data_dir, audit_path = _paths(args)
    try:
        manifest = load_manifest(data_dir)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    ok, msg = staleness_check(manifest)
    policy = load_policy()
    log = AuditLog(audit_path)
    seq, head = log.head()
    intact, problems = log.verify() if seq else (True, [])

    print(f"xscreen {__version__}")
    print(f"home:           {home}")
    print(f"listed parties: {manifest.total_parties}")
    print(f"list age:       {age_days(manifest):.1f} days")
    print(f"freshness:      {'OK' if ok else 'STALE/DEGRADED'} — {msg}")
    print(f"manifest:       {manifest.digest}")
    print(f"policy as_of:   {policy.as_of} "
          f"({'verified' if policy.verified else 'NOT VERIFIED — run: xscreen policy verify'})")
    print(f"audit entries:  {seq} (head {head[:16]}…)")
    print(f"audit chain:    {'intact' if intact else 'BROKEN'}")
    for p in problems[:5]:
        print(f"                ! {p}")
    try:
        be = get_backend(args.backend)
        print(f"model backend:  {getattr(be, 'name', '?')}")
    except BackendError as e:
        print(f"model backend:  unavailable — {e}")
    return 0 if (ok and intact) else 1


def read_party_file(path: Path) -> tuple[str, list[str]]:
    """Read a party CSV, tolerating the encodings ERP exports actually use.

    Excel and most ERP "export to CSV" buttons produce CP-1252 or Latin-1 on a
    Windows desktop, and those are exactly the files carrying the accented
    names this tool exists to normalize. A UnicodeDecodeError traceback is the
    wrong answer for the most common real-world input.
    """
    raw = path.read_bytes()
    notes: list[str] = []
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc not in ("utf-8-sig", "utf-8"):
            notes.append(
                f"{path.name} is not UTF-8; decoded as {enc}. Check that accented "
                "names came through correctly, and prefer exporting as UTF-8."
            )
        return text, notes
    text = raw.decode("utf-8", errors="replace")
    notes.append(
        f"{path.name} could not be decoded cleanly in any known encoding. "
        "Undecodable bytes were replaced, which CAN CORRUPT NAMES AND COST YOU "
        "A MATCH. Re-export the file as UTF-8 before relying on this run."
    )
    return text, notes


def cmd_screen(args) -> int:
    home, data_dir, audit_path = _paths(args)
    party_path = Path(args.party_file).expanduser()
    if not party_path.exists():
        print(f"No party file at {party_path}", file=sys.stderr)
        print("Pass the path to a CSV of the counterparties to screen. See "
              "templates/party-file.schema.json for the columns.", file=sys.stderr)
        return 1
    if party_path.is_dir():
        print(f"{party_path} is a directory; pass a CSV file.", file=sys.stderr)
        return 1
    try:
        text, encoding_notes = read_party_file(party_path)
    except OSError as e:
        print(f"Could not read {party_path}: {e}", file=sys.stderr)
        return 1
    for n in encoding_notes:
        print(f"! {n}", file=sys.stderr)
    subjects, warnings = parse_party_file(text)
    for w in warnings:
        print(f"! {w}", file=sys.stderr)
    if not subjects:
        print(f"No screenable rows found in {party_path}.", file=sys.stderr)
        return 1

    backend = critic_backend = None
    use_llm = not args.no_llm
    if use_llm:
        try:
            backend = get_backend(args.backend)
        except BackendError as e:
            print(f"! No model backend ({e}). Falling back to deterministic-only; "
                  "every candidate will route to human review.", file=sys.stderr)
            use_llm = False
        else:
            # `get_backend` returns the offline sentinel rather than raising
            # when nothing is configured, so catching BackendError alone left
            # the model stages enabled on a default install. Every case then
            # burned four failing adjudications and four failing critic passes
            # before landing on ESCALATE -- instead of the documented, and much
            # clearer, deterministic human-review path.
            if is_offline(backend):
                print("! No model backend configured. Running deterministic-only; "
                      "every candidate routes to human review. Set "
                      "XSCREEN_LLM_BASE_URL/XSCREEN_LLM_MODEL or ANTHROPIC_API_KEY "
                      "to enable adjudication.", file=sys.stderr)
                use_llm = False
                backend = None
    use_critic = use_llm and not args.no_critic
    if use_critic:
        try:
            critic_backend = get_backend(args.critic_backend)
        except BackendError as e:
            print(f"! Critic backend unavailable ({e}); critic disabled.", file=sys.stderr)
            use_critic = False
        else:
            if is_offline(critic_backend):
                print("! No critic backend configured; critic disabled. "
                      "Adjudications will not be independently reviewed.", file=sys.stderr)
                use_critic = False
                critic_backend = None
    if use_critic and getattr(critic_backend, "name", "a") == getattr(backend, "name", "b"):
        print("! Adjudicator and critic are the same model. Cross-model review is "
              "stronger: set XSCREEN_CRITIC_BACKEND to a different family.", file=sys.stderr)

    def progress(i: int, n: int, name: str) -> None:
        print(f"  [{i}/{n}] {name[:60]}", file=sys.stderr)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    try:
        results, summary = run(
            subjects, data_dir, audit_path,
            use_llm=use_llm, use_critic=use_critic,
            backend=backend, critic_backend=critic_backend,
            as_of=as_of, allow_stale=args.allow_stale, progress=progress,
        )
    except (RuntimeError, FileNotFoundError) as e:
        print(str(e), file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else home / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r.to_dict(), ensure_ascii=False) for r in results), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "dispositions.csv").write_text(summary_csv(results), encoding="utf-8")
    (out_dir / "REPORT.md").write_text(markdown_report(results, summary), encoding="utf-8")

    print(f"\nWrote {out_dir}", file=sys.stderr)
    for d, n in sorted(summary["dispositions"].items()):
        print(f"  {d:<14} {n}", file=sys.stderr)

    if summary["dispositions"].get("BLOCKED"):
        return 3
    if summary.get("requires_human"):
        return 2
    return 0


def cmd_explain(args) -> int:
    _, data_dir, _ = _paths(args)
    from .models import SubjectParty
    index, manifest = build_index(data_dir)
    policy = load_policy()
    subject = SubjectParty(
        ref="explain", name=args.name, country=args.country or "",
        destination_country=args.country or "", eccn=args.eccn or "",
    )
    result = screen_subject(subject, index, manifest, policy, date.today())
    live = [c for c in result.candidates if c.get("band") != "NONE"]
    print(f"Query: {args.name}")
    print(f"Index: {index.size} indexed names over {manifest.total_parties} parties")
    print(f"Candidates: {len(live)}\n")
    for c in live[: args.limit]:
        print(f"  {c['band']:<7} {c['score']:<7} {c['listed_source']:<7} {c['listed_name']}")
        for k, v in sorted(c["signals"].items()):
            print(f"          {k}: {v}")
        print()
    if result.rule_flags:
        print("Rule flags:")
        for f in result.rule_flags:
            print(f"  [{f['severity']}] {f['rule_id']}: {f['title']}")
    print(f"\nProvisional disposition: {result.disposition} — {result.disposition_reason}")
    return 0


def cmd_diff(args) -> int:
    from .report import NEW_HIT, CHANGED, diff_dispositions, diff_report, load_dispositions

    paths = [Path(args.before).expanduser(), Path(args.after).expanduser()]
    for p in paths:
        if not p.exists():
            print(f"No such file: {p}", file=sys.stderr)
            return 1
    before = load_dispositions(paths[0].read_text(encoding="utf-8-sig"))
    after = load_dispositions(paths[1].read_text(encoding="utf-8-sig"))
    groups = diff_dispositions(before, after)
    md = diff_report(groups, str(paths[0]), str(paths[1]))

    # Record the comparison BEFORE writing output. A reader closing the pipe
    # must not be able to prevent the diff from reaching the audit log.
    _, _, audit_path = _paths(args)
    AuditLog(audit_path).append("run.diff", {
        "before": str(paths[0]), "after": str(paths[1]),
        "counts": {k: len(v) for k, v in groups.items()},
    })
    if groups[NEW_HIT]:
        print(f"{len(groups[NEW_HIT])} new hit(s) — investigate every one.", file=sys.stderr)

    if args.out:
        Path(args.out).expanduser().write_text(md, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(md)

    if groups[NEW_HIT]:
        return 3
    if groups[CHANGED]:
        return 2
    return 0


def cmd_cases(args) -> int:
    from .report import load_dispositions, open_cases_report

    home, _, _ = _paths(args)
    runs_dir = Path(args.runs) if args.runs else home / "runs"
    files = sorted(runs_dir.glob("*/dispositions.csv"))
    if not files:
        print(f"No screening runs found under {runs_dir}", file=sys.stderr)
        return 1
    runs = [(f.parent.name, load_dispositions(f.read_text(encoding="utf-8-sig")))
            for f in files]
    md = open_cases_report(runs)
    if args.out:
        Path(args.out).expanduser().write_text(md, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(md)
    return 0


def cmd_audit(args) -> int:
    _, _, audit_path = _paths(args)
    log = AuditLog(audit_path)
    if args.action == "head":
        seq, head = log.head()
        print(json.dumps({"seq": seq, "head_hash": head, "path": str(audit_path)}))
        return 0
    intact, problems = log.verify()
    seq, head = log.head()
    print(f"entries: {seq}\nhead:    {head}\nstatus:  {'INTACT' if intact else 'BROKEN'}")
    for p in problems:
        print(f"  ! {p}")
    print(f"\nRetention floor ({log.retention_floor()}): entries dated before this may "
          "be purged under EAR 762.6 / OFAC 501.601 five-year rules. Confirm no "
          "longer retention obligation applies before purging anything.")
    return 0 if intact else 1


def cmd_policy(args) -> int:
    from .rules import POLICY_PATH
    if args.action == "show":
        print(POLICY_PATH.read_text(encoding="utf-8"))
        return 0
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    raw["verified_by"] = args.by
    raw["verified_on"] = date.today().isoformat()
    if args.as_of:
        raw["as_of"] = args.as_of
    POLICY_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _, _, audit_path = _paths(args)
    AuditLog(audit_path).append("policy.verified", {
        "verified_by": args.by, "as_of": raw["as_of"],
    })
    print(f"Policy attested by {args.by} on {raw['verified_on']} (as_of {raw['as_of']}).")
    return 0


def cmd_sources(args) -> int:
    for s in ALL_SOURCES:
        print(f"{s.code:<9} {s.name}")
        print(f"          agency: {s.agency}   parser: {s.parser}   aggregate: {s.aggregate}")
        print(f"          effect: {s.legal_effect}")
        for c in s.caveats:
            print(f"          caveat: {c}")
        print()
    return 0


def cmd_selftest(args) -> int:
    import unittest
    from pathlib import Path as _P
    loader = unittest.TestLoader()
    suite = loader.discover(str(_P(__file__).parent / "tests"), top_level_dir=str(_P(__file__).parent.parent))
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    return 0 if runner.run(suite).wasSuccessful() else 1


# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xscreen", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home", default=str(DEFAULT_HOME),
                   help=f"working directory (default {DEFAULT_HOME})")
    p.add_argument("--version", action="version", version=f"xscreen {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("refresh", help="download and parse official lists")
    r.add_argument("--sources", nargs="*", help=f"default: {' '.join(DEFAULT_REFRESH)}")
    r.add_argument("--offline", action="store_true", help="parse cached files without downloading")
    r.set_defaults(func=cmd_refresh)

    st = sub.add_parser("status", help="show list freshness, policy state and audit health")
    st.add_argument("--backend")
    st.set_defaults(func=cmd_status)

    s = sub.add_parser("screen", help="screen a party CSV end to end")
    s.add_argument("party_file")
    s.add_argument("--out", help="output directory (default <home>/runs/<timestamp>)")
    s.add_argument("--no-llm", action="store_true", help="deterministic only; all candidates to human review")
    s.add_argument("--no-critic", action="store_true", help="skip the independent critic pass")
    s.add_argument("--backend", help="adjudicator backend, e.g. anthropic:claude-sonnet-5 or openai:<model>")
    s.add_argument("--critic-backend", help="critic backend; use a different model family")
    s.add_argument("--as-of", help="transaction date YYYY-MM-DD for order-validity rules")
    s.add_argument("--allow-stale", action="store_true", help="proceed on stale lists (recorded in the audit log)")
    s.set_defaults(func=cmd_screen)

    e = sub.add_parser("explain", help="show the matcher's reasoning for one name")
    e.add_argument("name")
    e.add_argument("--country")
    e.add_argument("--eccn")
    e.add_argument("--limit", type=int, default=10)
    e.set_defaults(func=cmd_explain)

    d = sub.add_parser(
        "diff", help="compare two screening runs; surfaces parties newly hitting")
    d.add_argument("before", help="earlier dispositions.csv")
    d.add_argument("after", help="later dispositions.csv")
    d.add_argument("--out", help="write the comparison to a file instead of stdout")
    d.set_defaults(func=cmd_diff)

    c = sub.add_parser(
        "cases", help="roll every still-open case across all runs into one worklist")
    c.add_argument("--runs", help="runs directory (default <home>/runs)")
    c.add_argument("--out", help="write the worklist to a file instead of stdout")
    c.set_defaults(func=cmd_cases)

    a = sub.add_parser("audit", help="verify or publish the audit chain")
    a.add_argument("action", choices=["verify", "head"])
    a.set_defaults(func=cmd_audit)

    po = sub.add_parser("policy", help="inspect or attest the country policy file")
    po.add_argument("action", choices=["show", "verify"])
    po.add_argument("--by", default="", help="name of the person attesting")
    po.add_argument("--as-of", help="date the policy was checked against the CFR")
    po.set_defaults(func=cmd_policy)

    so = sub.add_parser("sources", help="list registered sources and their legal effect")
    so.set_defaults(func=cmd_sources)

    t = sub.add_parser("selftest", help="run the built-in test suite")
    t.add_argument("--verbose", action="store_true")
    t.set_defaults(func=cmd_selftest)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "policy" and args.action == "verify" and not args.by:
        print("policy verify requires --by \"<name of person attesting>\"", file=sys.stderr)
        return 1
    try:
        return args.func(args)
    except BrokenPipeError:
        # `xscreen diff ... | head` is a normal thing to do, and it must not
        # change the answer. Returning 0 here turned "4000 new hits" (exit 3)
        # into a clean exit purely because the reader closed the pipe -- a
        # gating CLI must never fail open through an exception handler.
        # Exit 1 says "this run did not complete", which is true and is not
        # mistakable for a pass.
        try:
            sys.stdout.close()
        except Exception:  # noqa: BLE001
            pass
        print("Output pipe closed before the command finished; the exit code "
              "does not reflect the screening result. Re-run with --out to a "
              "file if you need the code.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Nothing further was written.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
